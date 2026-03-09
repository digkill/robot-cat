#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Робот: камера, детекция человека/движения, LLM, TTS, запись в S3.
Анимация глаз и рта, кнопка-звонок.
Запуск: sudo python3 robot_main.py
"""

import shutil
import subprocess
import threading
import time
import queue
from pathlib import Path

from gc9a01 import GC9A01, WIDTH, HEIGHT
from config import (
    RECORDINGS_DIR,
    MOTION_RECORD_SEC,
    PERSON_INTERVAL,
    MOTION_COOLDOWN,
    LISTEN_DURATION,
    LISTEN_MIN_TEXT,
    DISPLAY_BACKLIGHT_PIN,
    WAKE_WORD_ENABLED,
    WAKE_WORD_PHRASE,
)

from modules.detection import PersonMotionDetector, EventType
from modules.s3_upload import upload_file
from modules.recorder import record_video
from modules.llm import get_joke, get_greeting, get_how_are_you_response, chat, get_character_settings
from modules.tts import speak
from modules.speech import listen
from modules.display_face import FaceAnimator, draw_face
from modules.wakeword import WakeWordListener
from modules.watchlog import set_state, log, get_state
from modules.tts import get_voice_settings


class Robot:
    def __init__(self):
        self.disp = GC9A01(dc=24, rst=25, cs=8, backlight=DISPLAY_BACKLIGHT_PIN)
        if DISPLAY_BACKLIGHT_PIN is not None:
            self.disp.backlight(True)
        self.face = FaceAnimator(self.disp)
        self.events = []
        self._action_queue = queue.Queue()
        self._running = True
        self._cleanup_started = False
        self.wake_listener = None

    def _speak_startup_greeting(self):
        """Озвучить короткое приветствие при запуске робота."""
        phrase = get_character_settings().get("startup", "Привет! Я робот и уже готов к работе.")
        log("startup_greeting", phrase)
        self.face.set_speaking(True)
        log("face", "режим говорения")
        speak(phrase, blocking=True)
        self.face.set_speaking(False)
        log("face", "режим idle")

    def _restore_audio_levels(self):
        """Поднять уровни ALSA, если карта оказалась в тихом состоянии."""
        if not shutil.which("amixer"):
            log("audio", "amixer не найден — пропуск восстановления громкости")
            return
        controls = [
            ("Headphone", "100%"),
            ("Speaker", "100%"),
            ("Playback", "100%"),
        ]
        for control, value in controls:
            try:
                result = subprocess.run(
                    ["amixer", "-c", "0", "-q", "set", control, value],
                    capture_output=True,
                    text=True,
                    timeout=4,
                )
                if result.returncode == 0:
                    log("audio", f"{control} -> {value}")
            except Exception as e:
                log("audio", f"{control}: ошибка восстановления ({e})")

    def _on_person(self, event):
        self.events.append({"type": "person", "ts": event.timestamp})
        log("person_detected", f"человек в кадре (conf={event.confidence:.2f})")
        log("action_queue", "добавлено: person")
        self._action_queue.put(("person", event))

    def _on_motion(self, event):
        self.events.append({"type": "motion", "ts": event.timestamp})
        log("motion_detected", "движение в кадре")
        log("action_queue", "добавлено: motion")
        self._action_queue.put(("motion", event))

    def _on_wake_word(self, phrase, heard_text=""):
        if not self._running:
            return
        if not self._action_queue.empty():
            return
        if get_state() not in ("idle", "listening"):
            return
        self.events.append({"type": "wake_word", "ts": time.time(), "phrase": phrase})
        detail = heard_text or phrase
        log("wake_word", f"обнаружено: {detail}")
        log("action_queue", "добавлено: wake")
        self._action_queue.put(("wake", {"phrase": phrase, "heard": heard_text}))

    def _pause_wakeword(self):
        if self.wake_listener:
            self.wake_listener.pause()

    def _resume_wakeword(self):
        if self.wake_listener and self._running:
            self.wake_listener.resume()

    def _process_person(self):
        set_state("greeting")
        log("greeting_start", "приветствие человека — запуск LLM и TTS")
        self.face.set_speaking(True)
        log("face", "режим говорения")
        greeting = get_greeting() or "Привет! Рад тебя видеть!"
        log("llm", f"приветствие: {greeting[:60]}...")
        log("tts", f"озвучивание: {greeting[:60]}...")
        speak(greeting, blocking=True)
        log("tts", "приветствие озвучено")
        time.sleep(0.5)
        how = get_how_are_you_response() or "Как дела?"
        log("llm", f"вопрос: {how[:60]}...")
        log("tts", f"озвучивание: {how[:60]}...")
        speak(how, blocking=True)
        log("tts", "вопрос озвучен")
        time.sleep(0.3)
        joke = get_joke() or "Почему роботы не боятся призраков? Потому что у них железные нервы!"
        log("llm", f"шутка: {joke[:60]}...")
        log("tts", f"озвучивание шутки: {joke[:60]}...")
        speak(joke, blocking=True)
        log("tts", "шутка озвучена")
        self.face.set_speaking(False)
        log("face", "режим idle")
        log("greeting_done", "приветствие завершено")
        self._listen_and_respond()

    def _listen_and_respond(self):
        """Слушать ответ, если сказали — ответить через OpenAI. Долго тишина — молчать."""
        self._pause_wakeword()
        try:
            try:
                from config import LLM_API_KEY
                if not LLM_API_KEY:
                    log("listening", "LLM_API_KEY не задан — пропуск")
                    return
            except Exception:
                return
            if not shutil.which("arecord") and not shutil.which("pw-record"):
                log("listening", "ни arecord, ни pw-record не найдены — пропуск")
                return
            set_state("listening")
            log("listening", f"Слушаю до {int(LISTEN_DURATION)} сек...")
            text = listen(LISTEN_DURATION)
            if text and len(text.strip()) >= LISTEN_MIN_TEXT:
                log("speech", f"распознано: {text[:60]}...")
                set_state("responding")
                reply = chat(text)
                if reply:
                    log("llm", f"ответ: {reply[:60]}...")
                    self.face.set_speaking(True)
                    speak(reply, blocking=True)
                    self.face.set_speaking(False)
                    log("listening", "ответ озвучен")
            else:
                log("listening", "тишина — молчу")
            set_state("idle")
        finally:
            self._resume_wakeword()

    def _process_wake(self):
        set_state("wake_word")
        log("wake_word", "фраза пробуждения сработала — переход в диалог")
        self._listen_and_respond()

    def _process_motion(self):
        set_state("recording")
        log("recording_start", f"запись видео при движении ({MOTION_RECORD_SEC} сек)")
        log("camera", "пауза детектора для записи")
        self.detector.pause()
        time.sleep(1.5)
        log("recorder", "старт записи видео")
        path = record_video(MOTION_RECORD_SEC)
        log("recorder", f"запись завершена: {path or 'ошибка'}")
        log("camera", "возобновление детектора")
        self.detector.resume()
        if path:
            log("s3", f"загрузка: {path}")
            s3_key = upload_file(path)
            if s3_key:
                self.events.append({"type": "motion_recorded", "s3_key": s3_key})
                log("recording_uploaded", f"s3:{s3_key}")
            else:
                log("recording_saved", str(path))
        else:
            log("recording_failed", "ошибка записи")
        set_state("idle")

    def _worker(self):
        while self._running:
            try:
                action, event = self._action_queue.get(timeout=0.5)
                log("action_queue", f"обработка: {action}")
                if action == "person":
                    log("worker", "обработка person — приветствие")
                    self._process_person()
                elif action == "motion":
                    log("worker", "обработка motion — запись")
                    self._process_motion()
                elif action == "wake":
                    log("worker", "обработка wake — диалог")
                    self._process_wake()
            except queue.Empty:
                continue
            except Exception as e:
                log("error", str(e))

    def _safe_cleanup_step(self, title, func):
        log("cleanup", title)
        try:
            func()
        except KeyboardInterrupt:
            log("cleanup", f"{title} — Ctrl+C проигнорирован")
        except Exception as e:
            log("cleanup_error", f"{title}: {e}")

    def _shutdown_display(self):
        try:
            self.face.stop()
        except Exception:
            pass
        try:
            self.disp.fill(0)
            time.sleep(0.05)
        except Exception as e:
            log("cleanup_error", f"очистка дисплея: {e}")
        try:
            if DISPLAY_BACKLIGHT_PIN is not None:
                self.disp.backlight(False)
        except Exception:
            pass
        self.disp.close()

    def run(self):
        set_state("starting")
        log("robot_start", "запуск робота")
        # Проверка TTS при старте
        if not shutil.which("espeak") and not shutil.which("espeak-ng"):
            try:
                import gtts
            except ImportError:
                log("tts", "Локальный fallback TTS недоступен! Установите: sudo apt install espeak")
        # Проверка OpenAI и речи
        try:
            from config import LLM_API_KEY
            if LLM_API_KEY:
                log("llm", "OpenAI API подключен (чат + Whisper)")
            else:
                log("llm", "LLM_API_KEY не задан — запасные фразы, без слушания")
        except Exception:
            pass
        if not shutil.which("arecord") and not shutil.which("pw-record"):
            log("speech", "ни arecord, ни pw-record не найдены — слушание отключено")
        self._restore_audio_levels()
        if DISPLAY_BACKLIGHT_PIN is None:
            log("display", "управление подсветкой отключено, чтобы не занимать GPIO18 (I2S)")
        voice = get_voice_settings()
        character = get_character_settings()
        log("llm", f"персонаж={character['id']} ({character['name']})")
        log("tts", f"provider={voice['provider']}, openai_voice={voice['openai_voice']}, fallback_voice={voice['voice']}, speed={voice['speed']}, volume={voice['volume']}")
        log("display", "дисплей инициализирован")
        log("detection", "OpenCV Haar/HOG — без токенов")
        self.face.start()
        log("face", "анимация лица запущена")
        self._speak_startup_greeting()
        set_state("idle")

        self.detector = PersonMotionDetector(
            person_callback=self._on_person,
            motion_callback=self._on_motion,
            person_interval=PERSON_INTERVAL,
            motion_cooldown=MOTION_COOLDOWN,
        )
        self.detector.start()
        log("detector", "детекция камеры запущена")

        if WAKE_WORD_ENABLED:
            try:
                self.wake_listener = WakeWordListener(
                    callback=self._on_wake_word,
                    phrase=WAKE_WORD_PHRASE,
                )
                self.wake_listener.start()
                log("wake_word", f"локальное wake word включено: {WAKE_WORD_PHRASE}")
            except Exception as e:
                log("wake_word", f"не удалось запустить: {e}")

        worker = threading.Thread(target=self._worker, daemon=True)
        worker.start()

        try:
            log("robot_ready", "Робот запущен. Выход: Ctrl+C")
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            log("robot_interrupt", "Ctrl+C")
        finally:
            if self._cleanup_started:
                return
            self._cleanup_started = True
            self._running = False
            set_state("stopped")
            log("robot_stop", "остановка робота")
            if hasattr(self, "detector"):
                self._safe_cleanup_step("остановка детектора", self.detector.stop)
            if self.wake_listener:
                self._safe_cleanup_step("остановка wake word", self.wake_listener.stop)
            self._safe_cleanup_step("выключение дисплея", self._shutdown_display)

    def get_events(self):
        return self.events.copy()


if __name__ == "__main__":
    robot = Robot()
    robot.run()
