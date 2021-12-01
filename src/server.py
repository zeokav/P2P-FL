# NOTE!!
# For handling files: https://flask.palletsprojects.com/en/2.0.x/quickstart/#file-uploads
# General flask handlers overview: https://flask.palletsprojects.com/en/2.0.x/quickstart/

# From the host, you can reach this server on localhost:8080. I've mapped the ports.
# Try chrome -> localhost:8080/hitme

from flask import Flask
import os

app = Flask(__name__)

def loadData(fname):
    datafile = open(fname, 'rb')
    db = pickle.load(datafile)
    datafile.close()
    return db

@app.route("/inference", methods = ["POST"])
def inference():

    data = request.data
    if os.path.exists("model_weights"):
        model = load_data("model_weights")
        prediction = model.predict(data)
        return prediction

@app.route("/node_list", methods = ["GET"])
def node_list():

    if os.path.exists("node_list"):
        return 4, load_data("node_list")


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
