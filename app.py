from flask import Flask, request, Response, render_template
from bdays import get_birthdays

app = Flask(__name__, static_folder="./dist/", template_folder="./dist")


@app.route("/", methods=["POST"])
def serve_bdays():
    return Response(
        get_birthdays(request.get_json()["email"], request.get_json()["pass"]))


@app.route("/", methods=["GET"])
def serve_frontend():
    return render_template("index.html")


@app.after_request
def after_request(response):
    header = response.headers
    header['Access-Control-Allow-Origin'] = '*'
    header['Access-Control-Allow-Methods'] = 'GET,POST'
    header['Access-Control-Allow-Headers'] = '*'
    return response


if __name__ == "__main__":
    app.run()
