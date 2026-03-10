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
    AUDIO_CARD_INDEX,
    PERSON_INTERVAL,
    MOTION_COOLDOWN,
    DETECTION_EVENT_COOLDOWN,
    LISTEN_DURATION,
    LISTEN_MIN_TEXT,
    DISPLAY_BACKLIGHT_PIN,
    WAKE_WORD_ENABLED,
    WAKE_WORD_PHRASE,
)

from modules.detection import PersonMotionDetector, EventType
from modules.button import DoorbellButton
from modules.recorder import save_detection_snapshot
from modules.llm import (
    chat_with_emotion,
    get_character_settings,
    get_greeting_with_emotion,
    get_how_are_you_response_with_emotion,
    get_joke_with_emotion,
)
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
        self.button = None
        self._last_detection_event_ts = 0.0

    def _detection_event_allowed(self) -> bool:
        return (time.monotonic() - self._last_detection_event_ts) >= DETECTION_EVENT_COOLDOWN

    def _mark_detection_event(self):
        self._last_detection_event_ts = time.monotonic()

    def _speak_startup_greeting(self):
        """Озвучить короткое приветствие при запуске робота."""
        phrase = get_character_settings().get("startup", "Привет! Я робот и уже готов к работе.")
        log("startup_greeting", phrase)
        self._speak_with_emotion(phrase, "радостный")

    def _speak_with_emotion(self, text: str, emotion: str = "радостный"):
        if not text:
            return
        wakeword_was_paused = bool(self.wake_listener and getattr(self.wake_listener, "_paused", False))
        if self.wake_listener and not wakeword_was_paused:
            self._pause_wakeword()
        self.face.set_emotion(emotion)
        log("face", f"эмоция: {emotion}")
        self.face.set_speaking(True)
        log("face", "режим говорения")
        try:
            speak(text, blocking=True)
        finally:
            self.face.set_speaking(False)
            self.face.set_emotion("радостный")
            if self.wake_listener and not wakeword_was_paused and self._running:
                self._resume_wakeword()
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
                    ["amixer", "-c", str(AUDIO_CARD_INDEX), "-q", "set", control, value],
                    capture_output=True,
                    text=True,
                    timeout=4,
                )
                if result.returncode == 0:
                    log("audio", f"{control} -> {value}")
            except Exception as e:
                log("audio", f"{control}: ошибка восстановления ({e})")

    def _on_person(self, event):
        if not self._running:
            return False
        if not self._action_queue.empty():
            return False
        if get_state() != "idle":
            return False
        if not self._detection_event_allowed():
            return False
        self._mark_detection_event()
        self.events.append({"type": "person", "ts": event.timestamp})
        log("person_detected", f"человек в кадре (conf={event.confidence:.2f})")
        log("action_queue", "добавлено: person")
        self._action_queue.put(("person", event))
        return True

    def _on_motion(self, event):
        if not self._running:
            return False
        if not self._action_queue.empty():
            return False
        if get_state() != "idle":
            return False
        if not self._detection_event_allowed():
            return False
        self._mark_detection_event()
        self.events.append({"type": "motion", "ts": event.timestamp})
        log("motion_detected", "движение в кадре")
        log("action_queue", "добавлено: motion")
        self._action_queue.put(("motion", event))
        return True

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

    def _on_button_press(self):
        if not self._running:
            return
        if not self._action_queue.empty():
            return
        if get_state() != "idle":
            return
        log("button", "звонок")
        log("action_queue", "добавлено: button")
        self._action_queue.put(("button", {"ts": time.time()}))

    def _pause_wakeword(self):
        if self.wake_listener:
            self.wake_listener.pause()

    def _resume_wakeword(self):
        if self.wake_listener and self._running:
            self.wake_listener.resume()

    def _process_person(self):
        set_state("greeting")
        log("greeting_start", "приветствие человека — запуск LLM и TTS")
        greeting, greeting_emotion = get_greeting_with_emotion()
        greeting = greeting or "Привет! Рад тебя видеть!"
        log("llm", f"приветствие: {greeting[:60]}...")
        log("tts", f"озвучивание: {greeting[:60]}...")
        self._speak_with_emotion(greeting, greeting_emotion)
        log("tts", "приветствие озвучено")
        time.sleep(0.5)
        how, how_emotion = get_how_are_you_response_with_emotion()
        how = how or "Как дела?"
        log("llm", f"вопрос: {how[:60]}...")
        log("tts", f"озвучивание: {how[:60]}...")
        self._speak_with_emotion(how, how_emotion)
        log("tts", "вопрос озвучен")
        time.sleep(0.3)
        joke, joke_emotion = get_joke_with_emotion()
        joke = joke or "Почему роботы не боятся призраков? Потому что у них железные нервы!"
        log("llm", f"шутка: {joke[:60]}...")
        log("tts", f"озвучивание шутки: {joke[:60]}...")
        self._speak_with_emotion(joke, joke_emotion)
        log("tts", "шутка озвучена")
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
                reply, reply_emotion = chat_with_emotion(text)
                if reply:
                    log("llm", f"ответ: {reply[:60]}...")
                    self._speak_with_emotion(reply, reply_emotion)
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

    def _process_button(self):
        set_state("button")
        log("button", "кнопка нажата — переход в диалог")
        self._speak_with_emotion("Ку-ку! Кто там?", "кукушка")
        self._listen_and_respond()

    def _process_motion(self, event):
        set_state("snapshot")
        log("recording_start", "снимок при движении: 1 кадр")
        path = save_detection_snapshot(
            event.frame if event else None,
            is_rgb=getattr(self.detector, "_use_picam", False),
            prefix="motion",
        )
        if path:
            self.events.append({"type": "motion_captured", "file": str(path)})
            log("recording_saved", path.name)
        else:
            log("recording_failed", "не удалось сохранить снимок")
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
                    log("worker", "обработка motion — снимок")
                    self._process_motion(event)
                elif action == "wake":
                    log("worker", "обработка wake — диалог")
                    self._process_wake()
                elif action == "button":
                    log("worker", "обработка button — диалог")
                    self._process_button()
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

        worker = threading.Thread(target=self._worker, daemon=True)
        worker.start()

        self.detector = PersonMotionDetector(
            person_callback=self._on_person,
            motion_callback=self._on_motion,
            person_interval=PERSON_INTERVAL,
            motion_cooldown=MOTION_COOLDOWN,
        )
        self.detector.start()
        log("detector", "детекция камеры запущена")

        self.button = DoorbellButton(callback=self._on_button_press)
        self.button.start()
        log("button", "кнопка звонка активна")

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
            if self.button:
                self._safe_cleanup_step("остановка кнопки", self.button.stop)
            if self.wake_listener:
                self._safe_cleanup_step("остановка wake word", self.wake_listener.stop)
            self._safe_cleanup_step("выключение дисплея", self._shutdown_display)

    def get_events(self):
        return self.events.copy()


if __name__ == "__main__":
    robot = Robot()
    robot.run()
