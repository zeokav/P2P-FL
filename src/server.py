import pickle
import os

import numpy as np
import cv2
from flask import Flask, request, jsonify

app = Flask(__name__)


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
    if not os.path.exists("model_weights"):
        return jsonify({
            "error": "Model not ready"
        }), 500

    img_np = np.frombuffer(request.files['req_image'].read(), np.uint8)
    img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

    model = load_data("model_weights")

    # We'll have to reshape the image here.
    prediction = model.predict(img)

    # This will try to return an ndarray, need to transform.
    return jsonify({
        "predicted_class": prediction,
        "confidence": 50
    }), 200


@app.route("/node_list", methods=["GET"])
def node_list():
    return jsonify({"branching": 4, "node_list" : [1, 2, 3, 4, 5]
                    # load_data("node_list")
                    }), 200

    if os.path.exists("node_list"):
        # Change this to return a jsonified obj as above.
        return jsonify({"branching": 4, "node_list" : [1, 2, 3, 4, 5]
            # load_data("node_list")
                        }), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
