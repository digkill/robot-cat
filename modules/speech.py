# -*- coding: utf-8 -*-
"""Распознавание речи через OpenAI Whisper. Запись через arecord."""

import os
import pwd
import signal
import shutil
import subprocess
import time
from pathlib import Path

from config import RECORDINGS_DIR, LLM_API_KEY, PROXY_URL, HTTP_TIMEOUT, AUDIO_DEVICE

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def _log(msg: str):
    try:
        from modules.watchlog import log
        log("speech", msg)
    except Exception:
        print(f"[Speech] {msg}")


def _run_as_user(cmd, timeout=30):
    """Запуск от пользователя при sudo (для arecord + PipeWire)."""
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


def _spawn_as_user(cmd):
    """Запустить процесс записи так, чтобы его можно было остановить по таймеру."""
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
    proc = _spawn_as_user(cmd)
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


def record_audio(duration_sec: float = 6, device: str = None) -> Path | None:
    """Записать звук с микрофона. Предпочтительно через PipeWire."""
    use_pw_record = shutil.which("pw-record") is not None
    if not use_pw_record and not shutil.which("arecord"):
        _log("ни pw-record, ни arecord не найдены")
        return None
    device = device or AUDIO_DEVICE or "default"
    RECORDINGS_DIR.mkdir(exist_ok=True)
    path = RECORDINGS_DIR / f"listen_{os.getpid()}.wav"
    try:
        _log(f"старт записи: {'pw-record' if use_pw_record else 'arecord'}, duration={int(duration_sec)}с")
        if use_pw_record:
            r = _run_pw_record_for_duration(path, duration_sec)
        else:
            r = _run_as_user(
                ["arecord", "-D", device, "-d", str(int(duration_sec)), "-f", "cd", "-q", str(path)],
                timeout=int(duration_sec) + 5,
            )
        if r.returncode == 0 and path.exists() and path.stat().st_size > 1000:
            _log(f"аудио записано: {path.name} ({path.stat().st_size} байт)")
            return path
        stderr = r.stderr.decode(errors="ignore").strip()
        if stderr:
            _log(f"{'pw-record' if use_pw_record else 'arecord'}: {stderr[:160]}")
    except Exception as e:
        _log(f"ошибка записи: {e}")
    if path.exists():
        try:
            path.unlink()
        except Exception:
            pass
    return None


def transcribe(audio_path: Path) -> str:
    """Whisper API: аудио -> текст."""
    if not LLM_API_KEY:
        return ""
    if not audio_path or not audio_path.exists():
        return ""
    try:
        if HAS_OPENAI:
            kwargs = {"api_key": LLM_API_KEY}
            if PROXY_URL:
                try:
                    import httpx
                    kwargs["http_client"] = httpx.Client(proxy=PROXY_URL, timeout=float(HTTP_TIMEOUT))
                except Exception:
                    os.environ["HTTP_PROXY"] = PROXY_URL
                    os.environ["HTTPS_PROXY"] = PROXY_URL
            client = OpenAI(**kwargs)
            with open(audio_path, "rb") as f:
                r = client.audio.transcriptions.create(model="whisper-1", file=f, language="ru")
            return (r.text or "").strip()
        if HAS_REQUESTS:
            url = "https://api.openai.com/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {LLM_API_KEY}"}
            with open(audio_path, "rb") as f:
                files = {"file": (audio_path.name, f, "audio/wav")}
                data = {"model": "whisper-1", "language": "ru"}
                session = requests.Session()
                if PROXY_URL:
                    session.proxies = {"http": PROXY_URL, "https": PROXY_URL}
                r = session.post(url, headers=headers, files=files, data=data, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            out = r.json()
            return (out.get("text", "") or "").strip()
    except Exception as e:
        _log(f"Whisper ошибка: {e}")
    return ""


def listen(duration_sec: float = 6) -> str:
    """Записать и распознать. Пустая строка = тишина или ошибка."""
    path = record_audio(duration_sec)
    if not path:
        _log("звук не записан")
        return ""
    try:
        _log(f"отправка в Whisper: {path.name}")
        text = transcribe(path)
        if text:
            _log(f"распознано: {text[:120]}")
        else:
            _log("распознавание вернуло пустой текст")
        return text
    finally:
        try:
            path.unlink()
        except Exception:
            pass
