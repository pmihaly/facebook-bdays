#!/usr/bin/env python3

""" 
    fb2cal - Facebook Birthday Events to ICS file converter
    Created by: mobeigi

    This program is free software: you can redistribute it and/or modify it under
    the terms of the GNU General Public License as published by the Free Software
    Foundation, either version 3 of the License, or (at your option) any later
    version.

    This program is distributed in the hope that it will be useful, but WITHOUT
    ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
    FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
    You should have received a copy of the GNU General Public License along with
    this program. If not, see <http://www.gnu.org/licenses/>.
"""


import os
import sys
import platform
import re
import mechanicalsoup
import requests
import urllib.parse
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from babel import Locale
from babel.core import UnknownLocaleError
from babel.dates import format_date
import html
import locale
import pytz
import json
import ics
from ics import Calendar, Event
import configparser
import logging
from distutils import util

# Classes


class Birthday:
    def __init__(self, uid, name, day, month):
        # Unique identififer for person (required for ics events)
        self.uid = uid
        self.name = name
        self.day = day
        self.month = month

    def __str__(self):
        return f'{self.name} ({self.day}/{self.month})'

    def __unicode__(self):
        return u'{self.name} ({self.day}/{self.month})'

# Entry point


def get_birthdays(email, password):

    browser = mechanicalsoup.StatefulBrowser()
    init_browser(browser)

    # Attempt login
    facebook_authenticate(browser, email, password)

    # Get birthday objects for all friends via async endpoint
    birthdays = get_async_birthdays(browser)

    if len(birthdays) == 0:
        raise SystemError

    c = populate_birthdays_calendar(birthdays)

    # Remove blank lines
    return ''.join([line.rstrip('\n') for line in c])


def init_browser(browser):
    """ Initialize browser as needed """
    browser.set_user_agent(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36')


def facebook_authenticate(browser, email, password):
    """ Authenticate with Facebook setting up session for further requests """

    FACEBOOK_LOGIN_URL = 'http://www.facebook.com/login.php'
    FACEBOOK_DATR_TOKEN_REGEXP = r'\"_js_datr\",\"(.*?)\"'
    regexp = re.compile(FACEBOOK_DATR_TOKEN_REGEXP, re.MULTILINE)

    # Add 'datr' cookie to session for countries adhering to GDPR compliance
    login_page = browser.get(FACEBOOK_LOGIN_URL)

    if login_page.status_code != 200:
        raise SystemError

    matches = regexp.search(login_page.text)

    if not matches or len(matches.groups()) != 1:
        raise SystemError

    _js_datr = matches[1]

    datr_cookie = requests.cookies.create_cookie(
        domain='.facebook.com', name='datr', value=_js_datr)
    _js_datr_cookie = requests.cookies.create_cookie(
        domain='.facebook.com', name='_js_datr', value=_js_datr)
    browser.get_cookiejar().set_cookie(datr_cookie)
    browser.get_cookiejar().set_cookie(_js_datr_cookie)

    # Perform main login now
    login_page = browser.get(FACEBOOK_LOGIN_URL)

    if login_page.status_code != 200:
        raise SystemError

    login_form = login_page.soup.find('form', {'id': 'login_form'})
    login_form.find('input', {'id': 'email'})['value'] = email
    login_form.find('input', {'id': 'pass'})['value'] = password
    login_response = browser.submit(login_form, login_page.url)

    if login_response.status_code != 200:
        raise SystemError

    # Check to see if login failed
    if login_response.soup.find('link', {'rel': 'canonical', 'href': 'https://www.facebook.com/login/'}):
        raise SystemError

    # Check to see if we hit Facebook security checkpoint
    if login_response.soup.find('button', {'id': 'checkpointSubmitButton'}):
        raise SystemError


__cached_async_token = None


def get_async_token(browser):
    """ Get async authorization token (CSRF protection token) that must be included in all async requests """

    global __cached_async_token

    if __cached_async_token:
        return __cached_async_token

    # async token is present on this page
    FACEBOOK_BIRTHDAY_EVENT_PAGE_URL = 'https://www.facebook.com/events/birthdays/'
    FACEBOOK_ASYNC_TOKEN_REGEXP_STRING = r'{\"token\":\".*?\",\"async_get_token\":\"(.*?)\"}'
    regexp = re.compile(FACEBOOK_ASYNC_TOKEN_REGEXP_STRING, re.MULTILINE)

    birthday_event_page = browser.get(FACEBOOK_BIRTHDAY_EVENT_PAGE_URL)

    if birthday_event_page.status_code != 200:
        raise SystemError

    matches = regexp.search(birthday_event_page.text)

    if not matches or len(matches.groups()) != 1:
        raise SystemError

    __cached_async_token = matches[1]

    return matches[1]


__locale = None


def get_facebook_locale(browser):
    """ Returns users Facebook locale """

    global __locale

    if __locale:
        return __locale

    FACEBOOK_LOCALE_ENDPOINT = 'https://www.facebook.com/ajax/settings/language/account.php?'
    FACEBOOK_LOCALE_REGEXP_STRING = r'[a-z]{2}_[A-Z]{2}'
    regexp = re.compile(FACEBOOK_LOCALE_REGEXP_STRING, re.MULTILINE)

    # Not all fields are required for response to be given, required fields are fb_dtsg_ag and __a
    query_params = {'fb_dtsg_ag': get_async_token(browser),
                    '__a': '1'}

    response = browser.get(FACEBOOK_LOCALE_ENDPOINT +
                           urllib.parse.urlencode(query_params))

    if response.status_code != 200:
        raise SystemError

    # Parse json response
    try:
        json_response = json.loads(strip_ajax_response_prefix(response.text))
        current_locale = json_response['jsmods']['require'][0][3][1]['currentLocale']
    except json.decoder.JSONDecodeError as e:
        raise SystemError
    except KeyError as e:
        raise SystemError

    # Validate locale
    if not regexp.match(current_locale):
        raise SystemError

    __locale = current_locale

    return __locale


def get_async_birthdays(browser):
    """ Returns list of birthday objects by querying the Facebook birthday async page """

    FACEBOOK_BIRTHDAY_ASYNC_ENDPOINT = 'https://www.facebook.com/async/birthdays/?'

    birthdays = []

    next_12_months_epoch_timestamps = get_next_12_month_epoch_timestamps()

    for epoch_timestamp in next_12_months_epoch_timestamps:

        # Not all fields are required for response to be given, required fields are date, fb_dtsg_ag and __a
        query_params = {'date': epoch_timestamp,
                        'fb_dtsg_ag': get_async_token(browser),
                        '__a': '1'}

        response = browser.get(
            FACEBOOK_BIRTHDAY_ASYNC_ENDPOINT + urllib.parse.urlencode(query_params))

        if response.status_code != 200:
            raise SystemError

        birthdays_for_month = parse_birthday_async_output(
            browser, response.text)
        birthdays.extend(birthdays_for_month)

    return birthdays


def get_next_12_month_epoch_timestamps():
    """ Returns array of epoch timestamps corresponding to the 1st day of the next 12 months starting from the current month.
        For example, if the current date is 2000-05-20, will return epoch for 2000-05-01, 2000-06-01, 2000-07-01 etc for 12 months """

    epoch_timestamps = []

    # Facebook timezone seems to use Pacific Standard Time locally for these epochs
    # So we have to convert our 00:00:01 datetime on 1st of month from Pacific to UTC before getting our epoch timestamps
    pdt = pytz.timezone('America/Los_Angeles')
    cur_date = datetime.now()

    # Loop for next 12 months
    for _ in range(12):
        # Reset day to 1 and time to 00:00:01
        cur_date = cur_date.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)

        # Convert from Pacific to UTC and store timestamp
        utc_date = pdt.localize(cur_date).astimezone(pytz.utc)
        epoch_timestamps.append(int(utc_date.timestamp()))

        # Move cur_date to 1st of next month
        cur_date = cur_date + relativedelta(months=1)

    return epoch_timestamps


def parse_birthday_async_output(browser, text):
    """ Parsed Birthday Async output text and returns list of Birthday objects """
    BIRTHDAY_STRING_REGEXP_STRING = r'class=\"_43q7\".*?href=\"https://www\.facebook\.com/(.*?)\".*?data-tooltip-content=\"(.*?)\">.*?alt=\"(.*?)\".*?/>'
    regexp = re.compile(BIRTHDAY_STRING_REGEXP_STRING, re.MULTILINE)

    birthdays = []

    # Fetch birthday card html payload from json response
    try:
        json_response = json.loads(strip_ajax_response_prefix(text))
        birthday_card_html = json_response['domops'][0][3]['__html']
    except json.decoder.JSONDecodeError as e:
        raise SystemError
    except KeyError as e:
        raise SystemError

    user_locale = get_facebook_locale(browser)

    for vanity_name, tooltip_content, name in regexp.findall(birthday_card_html):
        # Check to see if user has no custom vanity name in which case we'll just take the id directly
        if vanity_name.startswith('profile.php?id='):
            uid = vanity_name[15:]
        else:
            uid = get_entity_id_from_vanity_name(browser, vanity_name)

        # Parse tooltip content into day/month
        day, month = parse_birthday_day_month(
            tooltip_content, name, user_locale)

        birthdays.append(Birthday(uid, html.unescape(name), day, month))

    return birthdays


def parse_birthday_day_month(tooltip_content, name, user_locale):
    """ Convert the Facebook birthday tooltip content to a day and month number. Facebook will use a tooltip format based on the users Facebook language (locale).
        The date will be in some date format which reveals the birthday day and birthday month.
        This is done for all birthdays expect those in the following week relative to the current date.
        Those will instead show day names such as 'Monday', 'Tuesday' etc for the next 7 days. """

    birthday_date_str = tooltip_content

    # List of strings that will be stripped away from tooltip_content
    # The goal here is to remove all other characters except the birthday day, birthday month and day/month seperator symbol
    strip_list = [
        name,  # Full name of user which will appear somewhere in the string
        '(',  # Regular left bracket
        ')',  # Regular right bracket
        '&#x200f;',  # Remove right-to-left mark (RLM)
        '&#x200e;',  # Remove left-to-right mark (LRM)
        '&#x55d;'  # Backtick character name postfix in Armenian
    ]

    for string in strip_list:
        birthday_date_str = birthday_date_str.replace(string, '')

    birthday_date_str = birthday_date_str.strip()

    # Dict with mapping of locale identifier to month/day datetime format
    locale_date_format_mapping = {
        'af_ZA': '%d-%m',
        'am_ET': '%m/%d',
        # 'ar_AR': '', # TODO: parse Arabic numeric characters
        # 'as_IN': '', # TODO: parse Assamese numeric characters
        'az_AZ': '%d.%m',
        'be_BY': '%d.%m',
        'bg_BG': '%d.%m',
        'bn_IN': '%d/%m',
        'br_FR': '%d/%m',
        'bs_BA': '%d.%m.',
        'ca_ES': '%d/%m',
        # 'cb_IQ': '', # TODO: parse Arabic numeric characters
        'co_FR': '%m-%d',
        'cs_CZ': '%d. %m.',
        'cx_PH': '%m-%d',
        'cy_GB': '%d/%m',
        'da_DK': '%d.%m',
        'de_DE': '%d.%m.',
        'el_GR': '%d/%m',
        'en_GB': '%d/%m',
        'en_UD': '%m/%d',
        'en_US': '%m/%d',
        'eo_EO': '%m-%d',
        'es_ES': '%d/%m',
        'es_LA': '%d/%m',
        'et_EE': '%d.%m',
        'eu_ES': '%m/%d',
        # 'fa_IR': '', # TODO: parse Persian numeric characters
        'ff_NG': '%d/%m',
        'fi_FI': '%d.%m.',
        'fo_FO': '%d.%m',
        'fr_CA': '%m-%d',
        'fr_FR': '%d/%m',
        'fy_NL': '%d-%m',
        'ga_IE': '%d/%m',
        'gl_ES': '%d/%m',
        'gn_PY': '%m-%d',
        'gu_IN': '%d/%m',
        'ha_NG': '%m/%d',
        'he_IL': '%d.%m',
        'hi_IN': '%d/%m',
        'hr_HR': '%d. %m.',
        'ht_HT': '%m-%d',
        'hu_HU': '%m. %d.',
        'hy_AM': '%d.%m',
        'id_ID': '%d/%m',
        'is_IS': '%d.%m.',
        'it_IT': '%d/%m',
        'ja_JP': '%m/%d',
        'ja_KS': '%m/%d',
        'jv_ID': '%d/%m',
        'ka_GE': '%d.%m',
        'kk_KZ': '%d.%m',
        'km_KH': '%d/%m',
        'kn_IN': '%d/%m',
        'ko_KR': '%m. %d.',
        'ku_TR': '%m-%d',
        'ky_KG': '%d-%m',
        'lo_LA': '%d/%m',
        'lt_LT': '%m-%d',
        'lv_LV': '%d.%m.',
        'mg_MG': '%d/%m',
        'mk_MK': '%d.%m',
        'ml_IN': '%d/%m',
        'mn_MN': '%m-&#x440; &#x441;&#x430;&#x440;/%d',
        # 'mr_IN': '', # TODO: parse Marathi numeric characters
        'ms_MY': '%d-%m',
        'mt_MT': '%m-%d',
        # 'my_MM': '', # TODO: parse Myanmar numeric characters
        'nb_NO': '%d.%m.',
        # 'ne_NP': '', # TODO: parse Nepali numeric characters
        'nl_BE': '%d/%m',
        'nl_NL': '%d-%m',
        'nn_NO': '%d.%m.',
        'or_IN': '%m/%d',
        'pa_IN': '%d/%m',
        'pl_PL': '%d.%m',
        # 'ps_AF': '', # TODO: parse Afghani numeric characters
        'pt_BR': '%d/%m',
        'pt_PT': '%d/%m',
        'ro_RO': '%d.%m',
        'ru_RU': '%d.%m',
        'rw_RW': '%m-%d',
        'sc_IT': '%m-%d',
        'si_LK': '%m-%d',
        'sk_SK': '%d. %m.',
        'sl_SI': '%d. %m.',
        'sn_ZW': '%m-%d',
        'so_SO': '%m/%d',
        'sq_AL': '%d.%m',
        'sr_RS': '%d.%m.',
        'sv_SE': '%d/%m',
        'sw_KE': '%d/%m',
        'sy_SY': '%m-%d',
        'sz_PL': '%m-%d',
        'ta_IN': '%d/%m',
        'te_IN': '%d/%m',
        'tg_TJ': '%m-%d',
        'th_TH': '%d/%m',
        'tl_PH': '%m/%d',
        'tr_TR': '%d/%m',
        'tt_RU': '%d.%m',
        'tz_MA': '%m/%d',
        'uk_UA': '%d.%m',
        'ur_PK': '%d/%m',
        'uz_UZ': '%d/%m',
        'vi_VN': '%d/%m',
        'zh_CN': '%m/%d',
        'zh_HK': '%d/%m',
        'zh_TW': '%m/%d',
        'zz_TR': '%m-%d'
    }

    # Ensure a supported locale is being used
    if user_locale not in locale_date_format_mapping:
        raise SystemError

    try:
        # Try to parse the date using appropriate format based on locale
        parsed_date = datetime.strptime(
            birthday_date_str, locale_date_format_mapping[user_locale])
        return (parsed_date.day, parsed_date.month)
    except ValueError:
        # Otherwise, have to convert day names to a day and month
        offset_dict = get_day_name_offset_dict(user_locale)
        cur_date = datetime.now()

        # Use beautiful soup to parse special html codes properly before matching with our dict
        day_name = BeautifulSoup(birthday_date_str, 'lxml').get_text().lower()

        if day_name in offset_dict:
            cur_date = cur_date + relativedelta(days=offset_dict[day_name])
            return (cur_date.day, cur_date.month)

    raise SystemError


def get_day_name_offset_dict(user_locale):
    """ The day name to offset dict maps a day name to a numerical day offset which can be used to add days to the current date.
        Day names will match the provided user locale and will be in lowercase.
    """

    offset_dict = {}

    # Todays birthdays will be shown normally (as a date) so start from tomorrow
    start_date = datetime.now() + relativedelta(days=1)

    # Method 1: Babel
    try:
        babel_locale = Locale.parse(user_locale, sep='_')
        cur_date = start_date

        # Iterate through the following 7 days
        for i in range(1, 8):
            offset_dict[format_date(
                cur_date, 'EEEE', locale=babel_locale).lower()] = i
            cur_date = cur_date + relativedelta(days=1)

        return offset_dict
    except UnknownLocaleError as e:
        raise SystemError

        # Method 2: System locale
    cur_date = start_date
    locale_check_list = [user_locale, user_locale +
                         'UTF-8', user_locale + 'utf-8']
    system_locale = None

    # Windows
    if any(platform.win32_ver()):
        for locale_to_check in locale_check_list:
            if locale_to_check in locale.windows_locale.values():
                system_locale = locale_to_check
                break
    # POSIX
    else:
        for locale_to_check in locale_check_list:
            if locale_to_check in locale.locale_alias.values():
                system_locale = locale_to_check
                break

    # Check if system locale was found
    if system_locale:
        locale.setlocale(locale.LC_ALL, system_locale)

        # Iterate through the following 7 days
        for i in range(1, 8):
            offset_dict[cur_date.strftime('%A').lower()] = i
            cur_date = cur_date + relativedelta(days=1)

        return offset_dict
    else:

        # Failure
        raise SystemError


def get_entity_id_from_vanity_name(browser, vanity_name):
    """ Given a vanity name (user/page custom name), try to get the unique identifier entity_id """

    # Method 1: Composer Query async
    # Loop through entries to see if a valid match is found where alias matches provided vanity name
    composer_query_entries = get_composer_query_entries(browser, vanity_name)
    for entry in composer_query_entries:
        # Skip other render types like commerce pages etc
        if entry['vertical_type'] != 'USER' and entry['render_type'] not in ['friend', 'non_friend']:
            continue

        if 'alias' in entry and entry['alias'] == vanity_name:
            # Match found!
            return entry['uid']

    # Method 2: Scrape users profile page for entity id (significantly slower)
    entity_id = get_entity_id_from_profile_page(browser, vanity_name)
    if entity_id:
        return entity_id

    # Failure
    raise SystemError


def get_composer_query_entries(browser, value):
    """ Get list of entries from the composer query endpoint """

    COMPOSER_QUERY_ASYNC_ENDPOINT = "https://www.facebook.com/ajax/mercury/composer_query.php?"

    # Not all fields are required for response to be given, required fields are value, fb_dtsg_ag and __a
    query_params = {'value': value,
                    'fb_dtsg_ag': get_async_token(browser),
                    '__a': '1'}

    response = browser.get(COMPOSER_QUERY_ASYNC_ENDPOINT +
                           urllib.parse.urlencode(query_params))

    if response.status_code != 200:
        return []

    # Parse json response
    try:
        json_response = json.loads(strip_ajax_response_prefix(response.text))
        return json_response['payload']['entries']
    except json.decoder.JSONDecodeError as e:
        return []
    except KeyError as e:
        return []


def get_entity_id_from_profile_page(browser, vanity_name):
    """ Get entity id from a users profile page """

    FACEBOOK_PROFILE_PAGE_ENTITY_ID_REGEXP_STRING = r'entity_id:(\d+),ef_page:'
    regexp = re.compile(
        FACEBOOK_PROFILE_PAGE_ENTITY_ID_REGEXP_STRING, re.MULTILINE)

    response = browser.get(f'https://m.facebook.com/{vanity_name}')
    if response.status_code != 200:
        return None

    matches = regexp.search(response.text)

    if not matches or len(matches.groups()) != 1:
        return None

    return matches[1]


def strip_ajax_response_prefix(payload):
    """ Strip the prefix that Facebook puts in front of AJAX responses """

    if payload.startswith('for (;;);'):
        return payload[9:]
    return payload


def populate_birthdays_calendar(birthdays):
    """ Populate a birthdays calendar using birthday objects """

    c = Calendar()
    c.scale = 'GREGORIAN'
    c.method = 'PUBLISH'
    c.creator = f'fb2cal'
    c._unused.append(ics.parse.ContentLine(name='X-WR-CALNAME',
                                           params={}, value='Facebook Birthdays (fb2cal)'))
    c._unused.append(ics.parse.ContentLine(
        name='X-PUBLISHED-TTL', params={}, value='PT12H'))
    c._unused.append(ics.parse.ContentLine(
        name='X-ORIGINAL-URL', params={}, value='/events/birthdays/'))

    cur_date = datetime.now()

    for birthday in birthdays:
        e = Event()
        e.uid = birthday.uid
        e.name = f"{birthday.name}'s Birthday"

        # Calculate the year as this year or next year based on if its past current month or not
        # Also pad day, month with leading zeros to 2dp
        year = cur_date.year if birthday.month >= cur_date.month else (
            cur_date + relativedelta(years=1)).year
        month = '{:02d}'.format(birthday.month)
        day = '{:02d}'.format(birthday.day)
        e.begin = f'{year}-{month}-{day} 00:00:00'
        e.make_all_day()
        e.duration = timedelta(days=1)
        e._unused.append(ics.parse.ContentLine(
            name='RRULE', params={}, value='FREQ=YEARLY'))

        c.events.add(e)

    return c
