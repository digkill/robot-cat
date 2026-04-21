#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Веб-интерфейс робота: события, записи, голосовой ассистент.
Запуск: python3 web_app.py
"""

import json
import os
import socket
import threading
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename

from flask import Flask, render_template, jsonify, request, send_from_directory, Response

from config import MEDIA_DIR, RECORDINGS_DIR, SNAPSHOTS_DIR, WEB_HOST, WEB_PORT
from modules.camera_service import get_camera_service
from modules.audio_control import get_audio_status, set_audio_mute, set_audio_volume

app = Flask(__name__, static_folder="web/static", template_folder="web/templates")

# Глобальное состояние (связь с robot_main при совместном запуске)
_robot_instance = None
_events_store = []
_camera_service = get_camera_service()


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


@app.route("/camera/stream")
def camera_stream():
    if not _camera_service.start():
        return jsonify({"error": "Камера недоступна"}), 503

    def generate():
        for jpeg in _camera_service.iter_jpeg():
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            )

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/camera/status")
def api_camera_status():
    status = _camera_service.recording_status()
    status["stream_url"] = "/camera/stream"
    return jsonify(status)


@app.route("/api/audio/status")
def api_audio_status():
    return jsonify(get_audio_status())


@app.route("/api/audio/volume", methods=["POST"])
def api_audio_volume():
    data = request.get_json() or {}
    volume = data.get("volume")
    if volume is None:
        return jsonify({"error": "Не передана громкость"}), 400
    try:
        return jsonify(set_audio_volume(int(volume)))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/audio/mute", methods=["POST"])
def api_audio_mute():
    data = request.get_json() or {}
    muted = bool(data.get("muted"))
    try:
        return jsonify(set_audio_mute(muted))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/face")
def api_face():
    if not _robot_instance or not hasattr(_robot_instance, "face"):
        return jsonify({"error": "Робот недоступен"}), 503
    return jsonify({"state": _robot_instance.face.get_state(), "options": _robot_instance.face.get_options()})


@app.route("/api/face/settings", methods=["POST"])
def api_face_settings():
    if not _robot_instance or not hasattr(_robot_instance, "face"):
        return jsonify({"error": "Робот недоступен"}), 503
    data = request.get_json() or {}
    face = _robot_instance.face
    try:
        if "emotion" in data:
            face.set_emotion(str(data.get("emotion") or "").strip())
        if "theme" in data:
            face.set_theme(str(data.get("theme") or "").strip())
        if "animation_mode" in data:
            face.set_animation_mode(str(data.get("animation_mode") or "").strip())
        if "background_name" in data:
            face.set_background((data.get("background_name") or "").strip() or None)
        return jsonify(face.get_state())
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/media")
def api_media():
    files = []
    for f in sorted(MEDIA_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file():
            files.append(
                {
                    "name": f.name,
                    "path": f"/media/{f.name}",
                    "size": f.stat().st_size,
                    "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                }
            )
    return jsonify(files[:50])


@app.route("/api/media/upload", methods=["POST"])
def api_media_upload():
    if "media" not in request.files:
        return jsonify({"error": "Нет файла"}), 400
    f = request.files["media"]
    if f.filename == "":
        return jsonify({"error": "Пустой файл"}), 400
    name = secure_filename(f.filename)
    if not name:
        return jsonify({"error": "Некорректное имя файла"}), 400
    path = MEDIA_DIR / name
    f.save(str(path))
    return jsonify({"name": name, "path": f"/media/{name}"})


@app.route("/media/<path:filename>")
def serve_media(filename):
    return send_from_directory(MEDIA_DIR, filename)


@app.route("/api/camera/record/start", methods=["POST"])
def api_camera_record_start():
    try:
        status = _camera_service.start_recording()
        add_event({"type": "camera_record_start", "ts": datetime.now().timestamp()})
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/camera/record/stop", methods=["POST"])
def api_camera_record_stop():
    try:
        result = _camera_service.stop_recording()
        add_event(
            {
                "type": "camera_record_stop",
                "ts": datetime.now().timestamp(),
                "file": result.local_path,
                "s3_key": result.s3_key,
            }
        )
        return jsonify(
            {
                "name": result.name,
                "path": f"/recordings/{result.name}",
                "s3_key": result.s3_key,
                "with_audio": result.with_audio,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400


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


def default_route_ipv4() -> str | None:
    """IP интерфейса по умолчанию (для подсказки URL, если bind 0.0.0.0)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.3)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return None


def web_client_base_url(host: str, port: int) -> str:
    """URL для браузера: при bind на все адреса подставляем LAN-IP вместо 0.0.0.0."""
    h = (host or "").strip()
    if h not in ("0.0.0.0", "", "::", "0"):
        return f"http://{h}:{port}"
    ip = default_route_ipv4()
    if ip:
        return f"http://{ip}:{port}"
    return f"http://<ip-этой-машины>:{port}"


def run_web(host=WEB_HOST, port=WEB_PORT):
    Path("web/templates").mkdir(parents=True, exist_ok=True)
    Path("web/static").mkdir(parents=True, exist_ok=True)
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    print(f"Веб-интерфейс: {web_client_base_url(WEB_HOST, WEB_PORT)}  (слушаем {WEB_HOST}:{WEB_PORT})")
    run_web()
