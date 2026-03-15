# -*- coding: utf-8 -*-
"""Outbound WebSocket bridge to a remote backend."""

from __future__ import annotations

import json
import platform
import threading
import time
from pathlib import Path

try:
    import websocket
    HAS_WS = True
except ImportError:
    HAS_WS = False

from config import (
    BASE_DIR,
    REMOTE_BRIDGE_ENABLED,
    REMOTE_BRIDGE_TOKEN,
    REMOTE_BRIDGE_URL,
    REMOTE_PING_INTERVAL,
    REMOTE_ROBOT_ID,
    REMOTE_STATUS_INTERVAL,
    REMOTE_VIDEO_MODE,
)


def _log(action: str, detail: str = ""):
    try:
        from modules.watchlog import log
        log(action, detail)
    except Exception:
        pass


class RemoteBridge:
    def __init__(self):
        self.enabled = bool(REMOTE_BRIDGE_ENABLED and REMOTE_BRIDGE_URL)
        self.url = REMOTE_BRIDGE_URL
        self.token = REMOTE_BRIDGE_TOKEN
        self.robot_id = REMOTE_ROBOT_ID
        self.ping_interval = max(5.0, float(REMOTE_PING_INTERVAL))
        self.status_interval = max(2.0, float(REMOTE_STATUS_INTERVAL))
        self.video_mode = REMOTE_VIDEO_MODE
        self._robot = None
        self._ws = None
        self._thread = None
        self._running = False
        self._lock = threading.Lock()
        self._last_status_sent = 0.0

    def set_robot(self, robot):
        self._robot = robot

    def start(self):
        if not self.enabled:
            return
        if not HAS_WS:
            _log("remote_bridge", "websocket-client не установлен")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="remote-bridge")
        self._thread.start()
        _log("remote_bridge", f"enabled -> {self.url}")

    def stop(self):
        self._running = False
        with self._lock:
            ws = self._ws
            self._ws = None
        if ws:
            try:
                ws.close()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def publish_event(self, event_type: str, payload: dict | None = None):
        if not self.enabled:
            return
        self._send(
            {
                "type": "event",
                "robot_id": self.robot_id,
                "event": event_type,
                "payload": payload or {},
                "ts": time.time(),
            }
        )

    def _headers(self):
        headers = [f"X-Robot-Id: {self.robot_id}"]
        if self.token:
            headers.append(f"Authorization: Bearer {self.token}")
        return headers

    def _connect(self):
        return websocket.create_connection(
            self.url,
            timeout=10,
            header=self._headers(),
            enable_multithread=True,
        )

    def _run_loop(self):
        while self._running:
            try:
                ws = self._connect()
                with self._lock:
                    self._ws = ws
                self._on_connected()
                self._read_loop(ws)
            except Exception as e:
                _log("remote_bridge", f"reconnect after error: {e}")
                time.sleep(3)
            finally:
                with self._lock:
                    if self._ws:
                        try:
                            self._ws.close()
                        except Exception:
                            pass
                    self._ws = None

    def _on_connected(self):
        self._send(
            {
                "type": "hello",
                "robot_id": self.robot_id,
                "payload": {
                    "protocol": "robot-bridge.v1",
                    "video_mode": self.video_mode,
                    "platform": platform.platform(),
                    "python_agent": True,
                    "cwd": str(BASE_DIR),
                    "capabilities": [
                        "speak",
                        "face_control",
                        "audio_control",
                        "camera_recording",
                        "snapshots",
                        "web_local",
                    ],
                },
                "ts": time.time(),
            }
        )
        self._send_status(force=True)

    def _read_loop(self, ws):
        last_ping = 0.0
        while self._running:
            now = time.monotonic()
            if now - last_ping >= self.ping_interval:
                self._send({"type": "ping", "robot_id": self.robot_id, "ts": time.time()})
                last_ping = now
            if now - self._last_status_sent >= self.status_interval:
                self._send_status()
            ws.settimeout(1.0)
            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            if not raw:
                raise RuntimeError("websocket closed")
            self._handle_message(raw)

    def _send(self, payload: dict):
        if not self.enabled:
            return
        data = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            ws = self._ws
        if not ws:
            return
        ws.send(data)

    def _send_status(self, force: bool = False):
        if not self._robot:
            return
        if not force and (time.monotonic() - self._last_status_sent) < self.status_interval:
            return
        self._last_status_sent = time.monotonic()
        self._send(
            {
                "type": "status",
                "robot_id": self.robot_id,
                "payload": self._robot.get_runtime_status(),
                "ts": time.time(),
            }
        )

    def _reply(self, request_id, ok: bool, payload=None, error: str | None = None):
        self._send(
            {
                "type": "command_result",
                "robot_id": self.robot_id,
                "request_id": request_id,
                "ok": ok,
                "payload": payload or {},
                "error": error,
                "ts": time.time(),
            }
        )

    def _handle_message(self, raw: str):
        try:
            message = json.loads(raw)
        except Exception:
            _log("remote_bridge", f"invalid json: {raw[:120]}")
            return
        msg_type = message.get("type")
        if msg_type == "ping":
            self._send({"type": "pong", "robot_id": self.robot_id, "ts": time.time()})
            return
        if msg_type != "command":
            return
        request_id = message.get("request_id")
        action = (message.get("action") or "").strip()
        payload = message.get("payload") or {}
        try:
            result = self._execute_command(action, payload)
            self._reply(request_id, True, result or {})
        except Exception as e:
            self._reply(request_id, False, error=str(e))

    def _execute_command(self, action: str, payload: dict):
        if not self._robot:
            raise RuntimeError("robot not attached")
        if action == "get_status":
            return self._robot.get_runtime_status()
        if action == "set_face":
            return self._robot.apply_face_settings(payload)
        if action == "set_volume":
            return self._robot.set_volume(int(payload.get("volume", 0)))
        if action == "set_mute":
            return self._robot.set_mute(bool(payload.get("muted")))
        if action == "speak":
            return self._robot.remote_speak(str(payload.get("text") or ""), payload.get("emotion"))
        if action == "camera_record_start":
            return self._robot.camera_record_start()
        if action == "camera_record_stop":
            return self._robot.camera_record_stop()
        raise RuntimeError(f"unsupported action: {action}")


_bridge = RemoteBridge()


def get_remote_bridge() -> RemoteBridge:
    return _bridge
