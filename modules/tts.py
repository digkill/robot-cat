# -*- coding: utf-8 -*-
"""Текст в речь (TTS). Предпочтительно через OpenAI, с локальным fallback."""

import os
import pwd
import shutil
import subprocess
import tempfile
import threading

try:
    from config import (
        AUDIO_DEVICE,
        AUDIO_CARD_INDEX,
        AUDIO_OUTPUT_VOLUME,
        TTS_PROVIDER,
        TTS_VOICE,
        TTS_SPEED,
        TTS_VOLUME,
        TTS_GAIN,
        TTS_OPENAI_MODEL,
        TTS_OPENAI_VOICE,
        LLM_API_KEY,
        PROXY_URL,
        HTTP_TIMEOUT,
    )
except ImportError:
    AUDIO_DEVICE = ""
    AUDIO_CARD_INDEX = 0
    AUDIO_OUTPUT_VOLUME = 100
    TTS_PROVIDER = "openai"
    TTS_VOICE = "ru"
    TTS_SPEED = 120
    TTS_VOLUME = 200
    TTS_GAIN = 2.5
    TTS_OPENAI_MODEL = "gpt-4o-mini-tts"
    TTS_OPENAI_VOICE = "alloy"
    LLM_API_KEY = ""
    PROXY_URL = ""
    HTTP_TIMEOUT = 30

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# root + espeak/aplay ломает PipeWire — запускаем от пользователя
_speak_lock = threading.Lock()


def _run_audio(cmd, timeout=60):
    """Аудио от пользователя при sudo, чтобы не ломать PipeWire."""
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


def _get_audio_user_env():
    """Окружение пользовательской аудио-сессии для PipeWire/PulseAudio."""
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


def _get_audio_device():
    """default = через PipeWire/систему."""
    return AUDIO_DEVICE or "default"


def _play_wav(path: str, timeout=30, gain: float = 1.0):
    """Воспроизвести WAV через PipeWire, с fallback на aplay."""
    _ensure_max_playback_volume()
    play_path = path
    boosted_path = None
    try:
        effective_gain = max(0.05, gain * (max(0, min(100, AUDIO_OUTPUT_VOLUME)) / 100.0))
        if abs(effective_gain - 1.0) > 0.01 and shutil.which("ffmpeg"):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                boosted_path = f.name
            conv = subprocess.run(
                ["ffmpeg", "-y", "-i", path, "-af", f"volume={effective_gain}", boosted_path],
                capture_output=True,
                timeout=min(timeout, 20),
            )
            if conv.returncode == 0 and os.path.exists(boosted_path):
                play_path = boosted_path
            elif conv.stderr:
                _log(f"ffmpeg gain: {conv.stderr.decode(errors='ignore').strip()[:160]}")
        # aplay более предсказуем для явного ALSA-устройства и внешних звуковых карт,
        # но если устройство не настроено, откатываемся на pw-play.
        if shutil.which("aplay"):
            result = _run_audio(["aplay", "-q", "-D", _get_audio_device(), play_path], timeout=timeout)
            if result.returncode == 0:
                return result
            stderr = result.stderr.decode(errors="ignore").strip()
            if stderr:
                _log(f"aplay: {stderr[:160]}")
        if shutil.which("pw-play"):
            return _run_audio(["pw-play", play_path], timeout=timeout)
        return subprocess.CompletedProcess(["playback"], 1, stdout=b"", stderr="aplay and pw-play not found".encode())
    finally:
        if boosted_path and os.path.exists(boosted_path):
            try:
                os.unlink(boosted_path)
            except Exception:
                pass


def _ensure_max_playback_volume():
    """Перед воспроизведением поднимаем аппаратную громкость карты на максимум."""
    if not shutil.which("amixer"):
        return
    for control in ("Headphone", "Speaker", "Playback"):
        try:
            subprocess.run(
                ["amixer", "-c", str(AUDIO_CARD_INDEX), "-q", "set", control, "100%"],
                capture_output=True,
                timeout=3,
            )
        except Exception:
            pass


def get_voice_settings():
    """Текущие настройки TTS из config/.env."""
    return {
        "provider": TTS_PROVIDER,
        "voice": TTS_VOICE,
        "speed": max(80, min(260, int(TTS_SPEED))),
        "volume": max(0, min(200, int(TTS_VOLUME))),
        "gain": max(0.5, min(5.0, float(TTS_GAIN))),
        "openai_model": TTS_OPENAI_MODEL,
        "openai_voice": TTS_OPENAI_VOICE,
    }


def _gtts_lang_from_voice(voice: str) -> str:
    """Грубое сопоставление espeak-голоса с языком gTTS."""
    voice = (voice or "ru").lower()
    mapping = [
        ("ru", "ru"),
        ("en", "en"),
        ("de", "de"),
        ("fr", "fr"),
        ("es", "es"),
        ("pl", "pl"),
        ("pt", "pt"),
    ]
    for prefix, lang in mapping:
        if voice.startswith(prefix):
            return lang
    return "ru"


def _openai_client():
    """Клиент OpenAI для TTS с поддержкой прокси."""
    if not HAS_OPENAI or not LLM_API_KEY:
        return None
    kwargs = {"api_key": LLM_API_KEY}
    if PROXY_URL:
        try:
            import httpx
            kwargs["http_client"] = httpx.Client(proxy=PROXY_URL, timeout=float(HTTP_TIMEOUT))
        except Exception:
            os.environ["HTTP_PROXY"] = PROXY_URL
            os.environ["HTTPS_PROXY"] = PROXY_URL
    return OpenAI(**kwargs)


def _speak_openai(text: str, settings: dict) -> bool:
    """OpenAI TTS -> файл -> pw-play/aplay."""
    client = _openai_client()
    if not client:
        return False
    wav_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        with client.audio.speech.with_streaming_response.create(
            model=settings["openai_model"],
            voice=settings["openai_voice"],
            input=text,
            response_format="wav",
        ) as response:
            response.stream_to_file(wav_path)
        result = _play_wav(wav_path, timeout=45, gain=settings["gain"])
        if result.returncode == 0:
            return True
        stderr = result.stderr.decode(errors="ignore").strip()
        if stderr:
            _log(f"openai playback: {stderr[:160]}")
    except Exception as e:
        _log(f"OpenAI TTS ошибка: {e}")
    finally:
        if wav_path and os.path.exists(wav_path):
            try:
                os.unlink(wav_path)
            except Exception:
                pass
    return False


def _log(msg: str):
    try:
        from modules.watchlog import log
        log("tts", msg)
    except Exception:
        print(f"[TTS] {msg}")


def speak(text: str, blocking: bool = False):
    """Озвучить текст. OpenAI TTS, затем локальный fallback."""
    if not text or not text.strip():
        return

    def _do():
        wav_path = None
        played = False
        settings = get_voice_settings()
        with _speak_lock:
            if settings["provider"] in ("openai", "auto"):
                played = _speak_openai(text, settings)

            # 1) espeak / espeak-ng -> WAV -> pw-play/aplay
            for cmd in ["espeak", "espeak-ng"]:
                if played or settings["provider"] not in ("espeak", "auto", "openai"):
                    break
                if shutil.which(cmd):
                    try:
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                            wav_path = f.name
                        with open(wav_path, "wb") as out:
                            synth = subprocess.run(
                                [
                                    cmd,
                                    "-v", settings["voice"],
                                    "-s", str(settings["speed"]),
                                    "-a", str(settings["volume"]),
                                    "--stdout",
                                    text,
                                ],
                                stdout=out,
                                stderr=subprocess.PIPE,
                                timeout=60,
                            )
                        if synth.returncode != 0:
                            stderr = synth.stderr.decode(errors="ignore").strip()
                            if stderr:
                                _log(f"{cmd}: {stderr[:160]}")
                            if os.path.exists(wav_path):
                                os.unlink(wav_path)
                            wav_path = None
                            continue
                        result = _play_wav(wav_path, timeout=30, gain=settings["gain"])
                        if result.returncode == 0:
                            played = True
                            break
                        stderr = result.stderr.decode(errors="ignore").strip()
                        if stderr:
                            _log(f"playback: {stderr[:160]}")
                    except Exception as e:
                        _log(f"{cmd} ошибка: {e}")
                    finally:
                        if wav_path and os.path.exists(wav_path):
                            os.unlink(wav_path)
                        wav_path = None
                if played:
                    break

            # 2) gTTS -> WAV -> pw-play/aplay
            if not played and settings["provider"] in ("gtts", "auto", "openai"):
                try:
                    from gtts import gTTS
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                        mp3_path = f.name
                    tts = gTTS(text=text, lang=_gtts_lang_from_voice(settings["voice"]))
                    tts.save(mp3_path)
                    if shutil.which("ffmpeg"):
                        wav_path = mp3_path.replace(".mp3", ".wav")
                        conv = subprocess.run(
                            ["ffmpeg", "-y", "-i", mp3_path, "-acodec", "pcm_s16le", "-af", "volume=2.0", wav_path],
                            capture_output=True,
                            timeout=15,
                        )
                        if conv.returncode == 0:
                            result = _play_wav(wav_path, timeout=30, gain=settings["gain"])
                            played = result.returncode == 0
                            if not played and result.stderr:
                                _log(f"playback: {result.stderr.decode(errors='ignore').strip()[:160]}")
                        elif conv.stderr:
                            _log(f"ffmpeg: {conv.stderr.decode(errors='ignore').strip()[:160]}")
                    elif shutil.which("mpg123"):
                        result = _run_audio(["mpg123", "-q", mp3_path], 30)
                        played = result.returncode == 0
                        if not played and result.stderr:
                            _log(f"mpg123: {result.stderr.decode(errors='ignore').strip()[:160]}")
                    if os.path.exists(mp3_path):
                        os.unlink(mp3_path)
                    if wav_path and os.path.exists(wav_path):
                        os.unlink(wav_path)
                    wav_path = None
                except ImportError:
                    pass
                except Exception as e:
                    _log(f"gTTS ошибка: {e}")
                    if wav_path and os.path.exists(wav_path):
                        try:
                            os.unlink(wav_path)
                        except Exception:
                            pass

            if not played:
                _log("TTS не сработал! Проверьте OpenAI TTS или установите espeak")

    if blocking:
        _do()
    else:
        threading.Thread(target=_do, daemon=True).start()
