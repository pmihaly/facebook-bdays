from flask import Flask, request, Response, render_template
from bdays import get_birthdays

app = Flask(__name__, static_folder="./dist/", template_folder="./dist")


@app.route("/", methods=["POST"])
def bdays():

    return Response(
        get_birthdays(request.get_json()["email"], request.get_json()["pass"]),
        mimetype="text/ics",
        headers={"Content-disposition": "attachment; filename=birthdays.ics"})


@app.route("/", methods=["GET"])
def serve_frontend():
    return render_template("index.html")


if __name__ == "__main__":
    app.run()
