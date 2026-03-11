# -*- coding: utf-8 -*-
"""Локальное wake word распознавание через Vosk."""

import json
import os
import pwd
import signal
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from array import array
from pathlib import Path

from config import (
    AUDIO_DEVICE,
    WAKE_WORD_CHUNK_SEC,
    WAKE_WORD_COOLDOWN,
    WAKE_WORD_MODEL_DIR,
    WAKE_WORD_PHRASE,
)

try:
    from vosk import KaldiRecognizer, Model, SetLogLevel
    HAS_VOSK = True
    SetLogLevel(-1)
except ImportError:
    HAS_VOSK = False


def _log(msg: str):
    try:
        from modules.watchlog import log
        log("wakeword", msg)
    except Exception:
        print(f"[WakeWord] {msg}")


def _get_audio_user_env():
    """Окружение пользовательской аудио-сессии для записи через PipeWire."""
    user = os.environ.get("ROBOT_AUDIO_USER") or os.environ.get("SUDO_USER") or "mini"
    try:
        pw = pwd.getpwnam(user)
        uid = int(os.environ.get("ROBOT_AUDIO_UID") or pw.pw_uid)
        home = os.environ.get("ROBOT_AUDIO_HOME") or pw.pw_dir
    except KeyError:
        uid = int(os.environ.get("ROBOT_AUDIO_UID") or os.environ.get("SUDO_UID") or 1000)
        home = os.environ.get("ROBOT_AUDIO_HOME") or f"/home/{user}"
    runtime_dir = f"/run/user/{uid}"
    env = os.environ.copy()
    env.update({
        "HOME": home,
        "USER": user,
        "LOGNAME": user,
        "XDG_RUNTIME_DIR": runtime_dir,
    })
    bus_path = os.path.join(runtime_dir, "bus")
    if os.path.exists(bus_path):
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus_path}"
    return user, env


def _run_audio_capture(cmd, timeout):
    if os.geteuid() != 0:
        return subprocess.run(cmd, capture_output=True, timeout=timeout)
    user, env = _get_audio_user_env()
    return subprocess.run(
        [
            "sudo",
            "--preserve-env=HOME,USER,LOGNAME,XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS",
            "-u",
            user,
        ] + cmd,
        env=env,
        capture_output=True,
        timeout=timeout,
    )


def _spawn_audio_capture(cmd):
    if os.geteuid() != 0:
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    user, env = _get_audio_user_env()
    return subprocess.Popen(
        [
            "sudo",
            "--preserve-env=HOME,USER,LOGNAME,XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS",
            "-u",
            user,
        ] + cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )


def _run_pw_record_for_duration(path: Path, duration_sec: float):
    cmd = [
        "pw-record",
        "--rate", "16000",
        "--channels", "1",
        "--format", "s16",
        str(path),
    ]
    proc = _spawn_audio_capture(cmd)
    deadline = time.monotonic() + max(0.2, float(duration_sec))
    try:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(0.05)
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGINT)
        stdout, stderr = proc.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, stderr = proc.communicate()
    except ProcessLookupError:
        stdout, stderr = proc.communicate()
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout=stdout, stderr=stderr)


def _pipewire_is_unavailable(stderr_text: str) -> bool:
    stderr_text = (stderr_text or "").lower()
    return "pw_context_connect() failed" in stderr_text or "host is down" in stderr_text


class WakeWordListener:
    """Фоновый офлайн-слушатель wake word."""

    def __init__(
        self,
        callback=None,
        phrase: str = WAKE_WORD_PHRASE,
        model_dir: str | Path = WAKE_WORD_MODEL_DIR,
        chunk_sec: float = WAKE_WORD_CHUNK_SEC,
        cooldown_sec: float = WAKE_WORD_COOLDOWN,
    ):
        self.callback = callback
        self.phrase = (phrase or "Hello Kitty").strip()
        self.model_dir = Path(model_dir)
        self.chunk_sec = max(1.0, float(chunk_sec))
        self.cooldown_sec = max(2.0, float(cooldown_sec))
        self._running = False
        self._paused = False
        self._thread = None
        self._last_trigger = 0.0
        self._model = None
        self._chunk_index = 0
        self._backend = "pw-record" if shutil.which("pw-record") else "arecord"

    def _ensure_model(self):
        if not HAS_VOSK:
            raise RuntimeError("vosk не установлен")
        if not self.model_dir.exists():
            raise RuntimeError(f"модель wake word не найдена: {self.model_dir}")
        if self._model is None:
            self._model = Model(str(self.model_dir))
            _log(f"модель загружена: {self.model_dir}")

    def _normalize(self, text: str) -> str:
        text = (text or "").lower().strip()
        filtered = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
        return " ".join(filtered.split())

    def _matches(self, text: str) -> bool:
        heard = self._normalize(text)
        phrase = self._normalize(self.phrase)
        if not heard or not phrase:
            return False
        if phrase in heard:
            return True
        return phrase.replace(" ", "") in heard.replace(" ", "")

    def _record_chunk(self) -> Path | None:
        use_pw_record = shutil.which("pw-record") is not None
        if not use_pw_record and not shutil.which("arecord"):
            _log("микрофон недоступен: ни pw-record, ни arecord не найдены")
            return None
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)
        device = AUDIO_DEVICE or "default"
        timeout = int(self.chunk_sec) + 5
        try:
            if use_pw_record:
                result = _run_pw_record_for_duration(path, self.chunk_sec)
                stderr = result.stderr.decode(errors="ignore").strip()
                if (result.returncode != 0 or not path.exists() or path.stat().st_size <= 1000) and _pipewire_is_unavailable(stderr) and shutil.which("arecord"):
                    _log("pw-record недоступен, fallback на arecord")
                    result = _run_audio_capture(
                        [
                            "arecord",
                            "-D", device,
                            "-d", str(int(self.chunk_sec)),
                            "-r", "16000",
                            "-c", "1",
                            "-f", "S16_LE",
                            "-q",
                            str(path),
                        ],
                        timeout=timeout,
                    )
            else:
                result = _run_audio_capture(
                    [
                        "arecord",
                        "-D", device,
                        "-d", str(int(self.chunk_sec)),
                        "-r", "16000",
                        "-c", "1",
                        "-f", "S16_LE",
                        "-q",
                        str(path),
                    ],
                    timeout=timeout,
                )
            if result.returncode == 0 and path.exists() and path.stat().st_size > 1000:
                return path
            stderr = result.stderr.decode(errors="ignore").strip()
            if stderr:
                _log(f"ошибка записи чанка: {stderr[:160]}")
        except Exception as e:
            _log(f"ошибка записи wake word: {e}")
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass
        return None

    def _measure_levels(self, audio_path: Path) -> tuple[int, int, float]:
        """Вернуть уровень сигнала: rms, peak, длительность."""
        try:
            with wave.open(str(audio_path), "rb") as wf:
                frames = wf.getnframes()
                rate = max(1, wf.getframerate())
                raw = wf.readframes(frames)
            samples = array("h")
            samples.frombytes(raw)
            if not samples:
                return 0, 0, 0.0
            peak = max(abs(s) for s in samples)
            square_mean = sum(s * s for s in samples) / len(samples)
            rms = int(square_mean ** 0.5)
            duration = frames / rate
            return rms, peak, duration
        except Exception:
            return 0, 0, 0.0

    def _describe_level(self, rms: int, peak: int) -> str:
        if peak < 300 or rms < 80:
            return "очень тихо"
        if peak < 1200 or rms < 250:
            return "тихо"
        if peak < 5000 or rms < 1200:
            return "нормально"
        return "громко"

    def _transcribe_chunk(self, audio_path: Path) -> str:
        self._ensure_model()
        try:
            with wave.open(str(audio_path), "rb") as wf:
                if wf.getnchannels() != 1:
                    return ""
                recognizer = KaldiRecognizer(
                    self._model,
                    wf.getframerate(),
                    json.dumps([self._normalize(self.phrase), "[unk]"]),
                )
                while True:
                    data = wf.readframes(4000)
                    if not data:
                        break
                    recognizer.AcceptWaveform(data)
                result = json.loads(recognizer.FinalResult() or "{}")
                return (result.get("text") or "").strip()
        except Exception as e:
            _log(f"ошибка Vosk: {e}")
            return ""

    def _run_loop(self):
        _log(
            f"фоновое слово включено: phrase='{self.phrase}', "
            f"backend={self._backend}, chunk={self.chunk_sec:.1f}s"
        )
        while self._running:
            if self._paused:
                time.sleep(0.2)
                continue
            if time.monotonic() - self._last_trigger < self.cooldown_sec:
                time.sleep(0.2)
                continue
            audio_path = self._record_chunk()
            if not audio_path:
                time.sleep(0.5)
                continue
            try:
                self._chunk_index += 1
                rms, peak, duration = self._measure_levels(audio_path)
                level = self._describe_level(rms, peak)
                _log(
                    f"микрофон chunk={self._chunk_index} duration={duration:.1f}s "
                    f"rms={rms} peak={peak} level={level}"
                )
                text = self._transcribe_chunk(audio_path)
                if text:
                    _log(f"распознано chunk={self._chunk_index}: {text}")
                else:
                    _log(f"распознано chunk={self._chunk_index}: пусто")
                if self._matches(text):
                    self._last_trigger = time.monotonic()
                    _log(f"wake word найден chunk={self._chunk_index}: {text}")
                    if self.callback:
                        self.callback(self.phrase, text)
                else:
                    _log(f"wake word не найден chunk={self._chunk_index}")
            finally:
                try:
                    audio_path.unlink()
                except Exception:
                    pass

    def start(self):
        self._ensure_model()
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive() and threading.current_thread() is not self._thread:
            try:
                self._thread.join(timeout=max(2.0, self.chunk_sec + 1.5))
            except KeyboardInterrupt:
                pass
