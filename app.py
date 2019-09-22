from flask import Flask, request, Response
from bdays import get_birthdays

app = Flask(__name__)


@app.route("/", methods=["POST"])
def main_route():

    return Response(
        get_birthdays(request.get_json()["email"], request.get_json()["pass"]),
        mimetype="text/ics",
        headers={"Content-disposition": "attachment; filename=birthdays.ics"})
