# -*- coding: utf-8 -*-
"""Конфигурация робота. Загружает переменные из .env"""

import os
from pathlib import Path

# Загрузка .env
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"\''))

# S3
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
AWS_DEFAULT_REGION = os.environ.get("AWS_DEFAULT_REGION", "ru1")
AWS_BUCKET = os.environ.get("AWS_BUCKET", "")
AWS_ENDPOINT = os.environ.get("AWS_ENDPOINT", "https://s3.ru1.storage.beget.cloud")
AWS_USE_PATH_STYLE = os.environ.get("AWS_USE_PATH_STYLE_ENDPOINT", "true").lower() == "true"

# LLM — либо консоль робота (mediarise-robot-console), либо OpenAI
LLM_CONSOLE_URL = os.environ.get("LLM_CONSOLE_URL", "")  # http://IP:port/api/chat
LLM_API_URL = os.environ.get("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

# Прокси для LLM (SOCKS5 с DNS: socks5h://user:pass@host:port)
PROXY_URL = os.environ.get("PROXY_URL", "")
HTTP_TIMEOUT = int(os.environ.get("HTTP_TIMEOUT", "30"))
HTTP_RETRIES = int(os.environ.get("HTTP_RETRIES", "2"))

# Пути
BASE_DIR = Path(__file__).parent
RECORDINGS_DIR = BASE_DIR / "recordings"
SNAPSHOTS_DIR = BASE_DIR / "snapshots"
RECORDINGS_DIR.mkdir(exist_ok=True)
SNAPSHOTS_DIR.mkdir(exist_ok=True)

# GPIO (BCM)
# LED: rgb (R G B G — 4 контакта) или ws2812 (S V G)
LED_TYPE = os.environ.get("LED_TYPE", "rgb")
PIN_LED_DATA = int(os.environ.get("PIN_LED_DATA", "12"))
PIN_RGB_R, PIN_RGB_G, PIN_RGB_B = 17, 27, 22
PIN_BUTTON = 23
# ВАЖНО: не используйте GPIO18 для подсветки, он нужен I2S/PCM для wm8960.
# Рекомендуемый безопасный пин подсветки: GPIO26.
_backlight_pin = os.environ.get("DISPLAY_BACKLIGHT_PIN", "").strip()
DISPLAY_BACKLIGHT_PIN = int(_backlight_pin) if _backlight_pin else None
# Кнопка: active_low (нажатие = GND) или active_high (нажатие = 3.3V)
BUTTON_ACTIVE_LOW = os.environ.get("BUTTON_ACTIVE_LOW", "true").lower() == "true"

# Камера для детекции: opencv (V4L2) или picamera2 (CSI)
CAMERA_DETECTION = os.environ.get("CAMERA_DETECTION", "opencv")
CAMERA_INDEX = int(os.environ.get("CAMERA_INDEX", "0"))

# Детекция: только локальный Python/OpenCV (Haar/HOG), без токенов
# Интервал проверки человека (сек), пауза после движения (сек)
PERSON_INTERVAL = float(os.environ.get("PERSON_INTERVAL", "8"))
MOTION_COOLDOWN = float(os.environ.get("MOTION_COOLDOWN", "5"))
DETECTION_EVENT_COOLDOWN = float(os.environ.get("DETECTION_EVENT_COOLDOWN", "30"))

# Звук: пусто = default (через PipeWire), иначе явно
AUDIO_DEVICE = os.environ.get("AUDIO_DEVICE", "").strip()
AUDIO_CARD_INDEX = int(os.environ.get("AUDIO_CARD_INDEX", "0"))
AUDIO_OUTPUT_VOLUME = max(0, min(100, int(os.environ.get("AUDIO_OUTPUT_VOLUME", "100"))))
TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "openai").strip().lower() or "openai"
TTS_VOICE = os.environ.get("TTS_VOICE", "ru").strip() or "ru"
TTS_SPEED = int(os.environ.get("TTS_SPEED", "120"))
TTS_VOLUME = int(os.environ.get("TTS_VOLUME", "200"))
TTS_GAIN = float(os.environ.get("TTS_GAIN", "2.5"))
TTS_OPENAI_MODEL = os.environ.get("TTS_OPENAI_MODEL", "gpt-4o-mini-tts").strip() or "gpt-4o-mini-tts"
TTS_OPENAI_VOICE = os.environ.get("TTS_OPENAI_VOICE", "alloy").strip() or "alloy"
ASSISTANT_CHARACTER = os.environ.get("ASSISTANT_CHARACTER", "robot_cat").strip() or "robot_cat"

# Wake word: локальное пробуждение без токенов
WAKE_WORD_ENABLED = os.environ.get("WAKE_WORD_ENABLED", "false").lower() == "true"
WAKE_WORD_PHRASE = os.environ.get("WAKE_WORD_PHRASE", "Hello Kitty").strip() or "Hello Kitty"
WAKE_WORD_CHUNK_SEC = float(os.environ.get("WAKE_WORD_CHUNK_SEC", "2.0"))
WAKE_WORD_COOLDOWN = float(os.environ.get("WAKE_WORD_COOLDOWN", "6.0"))
WAKE_WORD_MODEL_DIR = os.environ.get(
    "WAKE_WORD_MODEL_DIR",
    str(BASE_DIR / "data" / "vosk-model-small-en-us-0.15"),
).strip()

# Слушать ответы: сек записи, мин. длина текста чтобы ответить
LISTEN_DURATION = float(os.environ.get("LISTEN_DURATION", "6"))
LISTEN_MIN_TEXT = int(os.environ.get("LISTEN_MIN_TEXT", "2"))

# Снимки камеры: интервал (сек), 0 = отключено
SNAPSHOT_INTERVAL = float(os.environ.get("SNAPSHOT_INTERVAL", "5"))
