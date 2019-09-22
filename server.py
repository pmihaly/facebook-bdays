from flask import Flask, request, Response
from bdays import get_birthdays

app = Flask(__name__)


@app.route("/", methods=["POST"])
def main_route():
    email = request.get_json()["email"]
    password = request.get_json()["pass"]
    return Response(get_birthdays(email, password), mimetype="text/ics", headers={"Content-disposition":
                                                                                  "attachment; filename=birthdays.ics"})
