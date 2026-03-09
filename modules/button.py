# -*- coding: utf-8 -*-
"""Сенсорная кнопка — звонок в дверь."""

import threading
import time

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False

from config import PIN_BUTTON, BUTTON_ACTIVE_LOW


class DoorbellButton:
    def __init__(self, callback=None):
        self.callback = callback
        self._running = False
        self._thread = None
        self._last_trigger = 0
        self._debounce_sec = 0.5
        if HAS_GPIO:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                pull = GPIO.PUD_UP if BUTTON_ACTIVE_LOW else GPIO.PUD_DOWN
                GPIO.setup(PIN_BUTTON, GPIO.IN, pull_up_down=pull)
            except Exception as e:
                try:
                    from modules.watchlog import log
                    log("button", f"ошибка инициализации: {e}")
                except Exception:
                    pass

    def _on_press(self, channel=None):
        now = time.monotonic()
        if now - self._last_trigger < self._debounce_sec:
            return
        self._last_trigger = now
        if self.callback:
            try:
                from modules.watchlog import log
                log("button", "нажатие")
            except Exception:
                pass
            self.callback()

    def _poll(self):
        """Резервный опрос, если add_event_detect не сработал."""
        last = GPIO.input(PIN_BUTTON) if HAS_GPIO else 1
        pressed = GPIO.LOW if BUTTON_ACTIVE_LOW else GPIO.HIGH
        while self._running and HAS_GPIO:
            try:
                state = GPIO.input(PIN_BUTTON)
                if state != last and state == pressed:
                    self._on_press()
                last = state
            except Exception:
                pass
            time.sleep(0.05)

    def start(self):
        self._running = True
        if HAS_GPIO:
            self._thread = threading.Thread(target=self._poll, daemon=True)
            self._thread.start()
            try:
                from modules.watchlog import log
                log("button", "опрос кнопки запущен")
            except Exception:
                pass
        else:
            try:
                from modules.watchlog import log
                log("button", "GPIO недоступен")
            except Exception:
                pass

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        try:
            from modules.watchlog import log
            log("button", "кнопка остановлена")
        except Exception:
            pass
