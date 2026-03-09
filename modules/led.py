# -*- coding: utf-8 -*-
"""RGB LED — WS2812B (S V G) или 3-pin (R G B). Цвет по эмоциям."""

from enum import Enum

try:
    from rpi_ws281x import PixelStrip, Color
    HAS_WS281X = True
except ImportError:
    HAS_WS281X = False

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False

from config import LED_TYPE, PIN_LED_DATA, PIN_RGB_R, PIN_RGB_G, PIN_RGB_B


class Emotion(Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    GREETING = "greeting"
    SPEAKING = "speaking"
    ALERT = "alert"
    OFF = "off"


COLORS = {
    Emotion.NEUTRAL: (50, 150, 255),
    Emotion.HAPPY: (0, 255, 100),
    Emotion.GREETING: (255, 200, 0),
    Emotion.SPEAKING: (255, 255, 255),
    Emotion.ALERT: (255, 50, 50),
    Emotion.OFF: (0, 0, 0),
}


class RGBLed:
    """LED: ws2812 (S V G) или rgb (3 пина R G B)."""

    def __init__(self, num_pixels=1):
        self._strip = None
        self._pwms = []
        self._mode = "none"

        if LED_TYPE == "ws2812" and HAS_WS281X:
            try:
                self._strip = PixelStrip(
                    num=num_pixels,
                    pin=PIN_LED_DATA,
                    freq_hz=800000,
                    dma=10,
                    invert=False,
                    brightness=100,
                    channel=0 if PIN_LED_DATA in (12, 18) else 1,
                )
                self._strip.begin()
                self._mode = "ws2812"
            except Exception as e:
                print("[LED] WS2812 ошибка:", e)

        if self._mode == "none" and (LED_TYPE == "rgb" or not self._strip) and HAS_GPIO:
            try:
                GPIO.setmode(GPIO.BCM)
                for p in (PIN_RGB_R, PIN_RGB_G, PIN_RGB_B):
                    GPIO.setup(p, GPIO.OUT)
                    pw = GPIO.PWM(p, 1000)
                    pw.start(0)
                    self._pwms.append(pw)
                self._mode = "rgb"
            except Exception as e:
                print("[LED] RGB PWM ошибка:", e)

        if self._mode == "none":
            print("[LED] LED отключена. LED_TYPE=ws2812|rgb в .env")

    def set_emotion(self, emotion: Emotion):
        r, g, b = COLORS.get(emotion, (0, 0, 0))
        self.set_color(r, g, b)

    def set_color(self, r: int, g: int, b: int):
        if self._mode == "ws2812" and self._strip:
            c = Color(r, g, b)
            for i in range(self._strip.numPixels()):
                self._strip.setPixelColor(i, c)
            self._strip.show()
        elif self._mode == "rgb" and self._pwms:
            for i, val in enumerate([r, g, b]):
                self._pwms[i].ChangeDutyCycle(min(100, max(0, val / 2.55)))

    def off(self):
        self.set_emotion(Emotion.OFF)

