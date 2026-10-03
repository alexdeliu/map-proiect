"""Starter skeleton for the MAP project.

Implements only the common contract: /health, /version, / and /reset.
Add the routes required by your assigned theme in this file or in separate modules.
"""

import os
import time

from flask import Flask, jsonify

APP_NAME = "map-project"
APP_VERSION = "0.1.0"

STARTED_AT = time.monotonic()

app = Flask(__name__)


class Store:
    """Holds the application data in memory.

    Everything is lost when the container restarts.
    Add your theme's structures here.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.next_id = 1
        # example: self.contacts = {}


store = Store()


@app.get("/health")
def health():
    return jsonify(
        status="ok",
        uptime_seconds=int(time.monotonic() - STARTED_AT),
    )


@app.get("/version")
def version():
    return jsonify(
        app=APP_NAME,
        version=APP_VERSION,
        commit=os.getenv("APP_COMMIT", "dev"),
        built_at=os.getenv("APP_BUILT_AT", "unknown"),
    )


@app.post("/reset")
def reset():
    store.reset()
    return "", 204


@app.get("/")
def home():
    commit = os.getenv("APP_COMMIT", "dev")
    return f"""<!DOCTYPE html>
<html lang="ro"><head><meta charset="utf-8"><title>{APP_NAME}</title></head>
<body>
<h1>{APP_NAME}</h1>
<p>Autor: NUME PRENUME, grupa GRUPA</p>
<p>Tema: NUMARUL TEMEI</p>
<p>Versiune: {APP_VERSION}, commit {commit}</p>
</body></html>"""


@app.errorhandler(404)
def not_found(_):
    return jsonify(error="not_found", message="route does not exist"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
