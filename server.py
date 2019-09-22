from flask import Flask, request
from bdays import get_birthdays

app = Flask(__name__)


@app.route("/", methods=["POST"])
def hello():
    email = request.get_json()["email"]
    password = request.get_json()["pass"]
    return get_birthdays(email, password)
