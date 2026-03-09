#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Веб-интерфейс робота: события, записи, голосовой ассистент.
Запуск: python3 web_app.py
"""

import json
import os
import threading
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, jsonify, request, send_from_directory, Response

from config import RECORDINGS_DIR, SNAPSHOTS_DIR

app = Flask(__name__, static_folder="web/static", template_folder="web/templates")

# Глобальное состояние (связь с robot_main при совместном запуске)
_robot_instance = None
_events_store = []


def set_robot(robot):
    global _robot_instance
    _robot_instance = robot


def add_event(evt):
    _events_store.append(evt)
    if len(_events_store) > 200:
        _events_store.pop(0)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/events")
def api_events():
    events = _robot_instance.get_events() if _robot_instance else _events_store
    try:
        from modules.watchlog import get_state
        return jsonify({"events": events, "state": get_state()})
    except Exception:
        return jsonify({"events": events, "state": "unknown"})


@app.route("/api/log")
def api_log():
    """Последние строки лога (watchlog)."""
    try:
        from modules.watchlog import read_tail
        lines = int(request.args.get("lines", 100))
        return jsonify({"log": read_tail(lines)})
    except Exception as e:
        return jsonify({"log": str(e)})


@app.route("/api/recordings")
def api_recordings():
    files = []
    for pattern in ["*.mp4", "*.webm", "*.wav"]:
        for f in sorted(RECORDINGS_DIR.glob(pattern), reverse=True)[:50]:
            files.append({
                "name": f.name,
                "path": f"/recordings/{f.name}",
                "size": f.stat().st_size,
                "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return jsonify(files[:50])


@app.route("/recordings/<path:filename>")
def serve_recording(filename):
    return send_from_directory(RECORDINGS_DIR, filename)


@app.route("/api/snapshots")
def api_snapshots():
    files = []
    for f in sorted(SNAPSHOTS_DIR.glob("*.jpg"), reverse=True)[:30]:
        files.append({
            "name": f.name,
            "path": f"/snapshots/{f.name}",
            "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    return jsonify(files)


@app.route("/snapshots/<path:filename>")
def serve_snapshot(filename):
    return send_from_directory(SNAPSHOTS_DIR, filename)


@app.route("/api/audio/upload", methods=["POST"])
def api_audio_upload():
    """Приём записи с микрофона из браузера. Опционально загрузка в S3."""
    if "audio" not in request.files:
        return jsonify({"error": "Нет файла"}), 400
    f = request.files["audio"]
    if f.filename == "":
        return jsonify({"error": "Пустой файл"}), 400
    name = f"web_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"
    path = RECORDINGS_DIR / name
    f.save(str(path))
    s3_key = None
    try:
        from modules.s3_upload import upload_file
        s3_key = upload_file(path)
    except Exception:
        pass
    return jsonify({"path": f"/recordings/{name}", "name": name, "s3_key": s3_key})


@app.route("/api/assistant", methods=["POST"])
def api_assistant():
    """Голосовой ассистент: текст → OpenAI → ответ + TTS."""
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Пустое сообщение"}), 400
    try:
        from modules.llm import chat
        reply = chat(text) or "Не удалось получить ответ."
        if _robot_instance and hasattr(_robot_instance, "face"):
            _robot_instance.face.set_speaking(True)
            from modules.tts import speak
            speak(reply, blocking=True)
            _robot_instance.face.set_speaking(False)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def run_web(host="0.0.0.0", port=5000):
    Path("web/templates").mkdir(parents=True, exist_ok=True)
    Path("web/static").mkdir(parents=True, exist_ok=True)
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    run_web()
