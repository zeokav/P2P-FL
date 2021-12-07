import pickle
import os

import numpy as np
import cv2
from flask import Flask, request, jsonify
from tensorflow import keras


app = Flask(__name__)
class_list = ['airplane', 'automobile', 'bird', 'cat', 'deer', 'dog', 'frog', 'horse', 'ship', 'truck']

def load_data(fname):
    datafile = open(fname, 'rb')
    db = pickle.load(datafile)
    datafile.close()
    return db


@app.after_request
def after_request(response):
    header = response.headers
    header["Access-Control-Allow-Headers"] = "*"
    header["Access-Control-Allow-Origin"] = "*"
    header["Access-Control-Allow-Methods"] = "*"
    return response


@app.route("/inference", methods=["POST"])
def inference():
    if not os.path.exists("model"):
        return jsonify({
            "error": "Model not ready"
        }), 404

    img_np = np.frombuffer(request.files['req_image'].read(), np.uint8)
    img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

    model = keras.models.load_model("model")

    prediction = model.predict(np.expand_dims(img, 0))
    max_ind = np.argmax(prediction[0])

    return jsonify({
        "predicted_class": class_list[max_ind],
        "confidence": prediction[0].tolist()[max_ind]
    }), 200


@app.route("/node_list", methods=["GET"])
def node_list():
    if os.path.exists("node_list"):
        return jsonify({
            "branching": 4,
            "node_list": load_data("node_list")
        }), 200
    else:
        return "Not found", 404


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
