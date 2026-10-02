from flask import Flask
import socket

app = Flask(__name__)


@app.route("/")
def home():
    return {
        "message": "Running inside Kubernetes",
        "hostname": socket.gethostname()
    }


@app.route("/health")
def health():
    return {
        "status": "healthy"
    }


app.run(
    host="0.0.0.0",
    port=5000
)
