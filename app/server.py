"""
Servidor HTTP local (solo 127.0.0.1) que recibe URLs desde la extensión
de navegador y las coloca en una cola que la app de escritorio consume.
No expone nada a la red externa.
"""
import queue
import threading

from flask import Flask, jsonify, request
from flask_cors import CORS

incoming_queue: "queue.Queue[str]" = queue.Queue()

app = Flask(__name__)
# Solo permitir orígenes de extensión (chrome-extension:// / moz-extension://)
CORS(app, resources={r"/*": {"origins": "*"}})


@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"app": "VidGrab", "status": "ok"})


@app.route("/add-url", methods=["POST"])
def add_url():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url.startswith("http"):
        return jsonify({"ok": False, "error": "URL inválida"}), 400
    incoming_queue.put(url)
    return jsonify({"ok": True})


def run_server(port: int = 8743):
    def _run():
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t
