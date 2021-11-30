# NOTE!!
# For handling files: https://flask.palletsprojects.com/en/2.0.x/quickstart/#file-uploads
# General flask handlers overview: https://flask.palletsprojects.com/en/2.0.x/quickstart/

# From the host, you can reach this server on localhost:8080. I've mapped the ports.
# Try chrome -> localhost:8080/hitme

from flask import Flask

app = Flask(__name__)


@app.route("/hitme")
def hello_world():
    return "<p>Reachable outside :)</p>"


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
