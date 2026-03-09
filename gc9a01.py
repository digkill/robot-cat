# -*- coding: utf-8 -*-
"""
Драйвер дисплея GC9A01 (240x240) для Raspberry Pi через SPI.
Для Raspberry Pi Zero 2 W и других моделей с 40-pin GPIO.
"""

import time
import spidev
import RPi.GPIO as GPIO

# Размер дисплея
WIDTH = 240
HEIGHT = 240

# Команды GC9A01
CMD_SWRESET = 0x01
CMD_SLPOUT = 0x11
CMD_DISPON = 0x29
CMD_CASET = 0x2A   # Column address set
CMD_RASET = 0x2B   # Row address set
CMD_RAMWR = 0x2C   # Memory write
CMD_MADCTL = 0x36  # Memory access control
CMD_COLMOD = 0x3A  # Pixel format


class GC9A01:
    """Драйвер круглого TFT дисплея GC9A01 240x240 по SPI."""

    # Последовательность инициализации (из Adafruit CircuitPython GC9A01A)
    _INIT_SEQ = (
        (0xFE, [0x00]),           # Inter Register Enable1
        (0xEF, [0x00]),           # Inter Register Enable2
        (0xB6, [0x02, 0x00, 0x00]),  # Display Function Control
        (0x36, [0x48]),           # Memory Access Control
        (0x3A, [0x05]),           # 16-bit pixel format
        (0xC3, [0x13]),           # Power Control 2
        (0xC4, [0x13]),           # Power Control 3
        (0xC9, [0x22]),           # Power Control 4
        (0xF0, [0x45, 0x09, 0x08, 0x08, 0x26, 0x2A]),
        (0xF1, [0x43, 0x70, 0x72, 0x36, 0x37, 0x6F]),
        (0xF2, [0x45, 0x09, 0x08, 0x08, 0x26, 0x2A]),
        (0xF3, [0x43, 0x70, 0x72, 0x36, 0x37, 0x6F]),
        (0x66, [0x3C, 0x00, 0xCD, 0x67, 0x45, 0x45, 0x10, 0x00, 0x00, 0x00]),
        (0x67, [0x00, 0x3C, 0x00, 0x00, 0x00, 0x01, 0x54, 0x10, 0x32, 0x98]),
        (0x74, [0x10, 0x85, 0x80, 0x00, 0x00, 0x4E, 0x00]),
        (0x98, [0x3E, 0x07]),
        (0x35, [0x00]),           # Tearing Effect Line ON
        (0x21, []),               # Display Inversion ON
        (0x11, []),               # Sleep Out
        (0x29, []),               # Display ON
    )

    def __init__(self, spi_bus=0, spi_device=0, dc=24, rst=25, cs=8, backlight=None):
        """
        Инициализация дисплея.

        По умолчанию для Raspberry Pi Zero 2 W:
        - SPI: /dev/spidev0.0 (bus=0, device=0), CS = GPIO 8 (CE0)
        - DC (Data/Command) = GPIO 24
        - RST (Reset) = GPIO 25
        - Backlight опционально (например GPIO 18)
        """
        self._dc = dc
        self._rst = rst
        self._cs = cs
        self._bl = backlight
        # CE0=GPIO8 (device 0), CE1=GPIO7 (device 1) — заняты ядром, не трогаем
        self._cs_kernel = (spi_device == 0 and cs == 8) or (spi_device == 1 and cs == 7)
        self._spi = spidev.SpiDev()
        self._spi.open(spi_bus, spi_device)
        # Чуть ниже пикового значения: на Pi это обычно стабильнее и заметно меньше рябит.
        self._spi.max_speed_hz = 24_000_000
        self._spi.mode = 0

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._dc, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self._rst, GPIO.OUT, initial=GPIO.HIGH)
        if not self._cs_kernel:
            GPIO.setup(self._cs, GPIO.OUT, initial=GPIO.HIGH)
        if self._bl is not None:
            GPIO.setup(self._bl, GPIO.OUT, initial=GPIO.HIGH)

        self._reset()
        self._init_display()

    def _reset(self):
        """Сброс дисплея по RST."""
        GPIO.output(self._rst, GPIO.HIGH)
        time.sleep(0.1)
        GPIO.output(self._rst, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(self._rst, GPIO.HIGH)
        time.sleep(0.12)

    def _dc_cmd(self):
        GPIO.output(self._dc, GPIO.LOW)

    def _dc_data(self):
        GPIO.output(self._dc, GPIO.HIGH)

    def _write_cmd(self, cmd, data=None):
        """Отправить команду и опционально данные."""
        if not self._cs_kernel:
            GPIO.output(self._cs, GPIO.LOW)
        self._dc_cmd()
        self._spi.writebytes([cmd])
        if data:
            self._dc_data()
            self._spi.writebytes(data)
        if not self._cs_kernel:
            GPIO.output(self._cs, GPIO.HIGH)

    def _init_display(self):
        """Выполнить последовательность инициализации."""
        for cmd, data in self._INIT_SEQ:
            self._write_cmd(cmd, data if data else None)
            if cmd == 0x11:
                time.sleep(0.12)
            elif cmd == 0x29:
                time.sleep(0.02)

    def set_window(self, x0, y0, x1, y1):
        """Установить окно для записи пикселей (Column/Row Address)."""
        self._write_cmd(CMD_CASET, [
            (x0 >> 8) & 0xFF, x0 & 0xFF,
            (x1 >> 8) & 0xFF, x1 & 0xFF
        ])
        self._write_cmd(CMD_RASET, [
            (y0 >> 8) & 0xFF, y0 & 0xFF,
            (y1 >> 8) & 0xFF, y1 & 0xFF
        ])

    def _start_ram_write(self):
        """Начать запись в RAM (после set_window). Дальше вызывать _write_pixels()."""
        if not self._cs_kernel:
            GPIO.output(self._cs, GPIO.LOW)
        self._dc_cmd()
        self._spi.writebytes([CMD_RAMWR])
        self._dc_data()

    def _write_pixels(self, data):
        """Отправить байты пикселей (CS уже LOW, DC=DATA после _start_ram_write)."""
        if hasattr(self._spi, "writebytes2"):
            self._spi.writebytes2(data)
        else:
            self._spi.writebytes(list(data))

    def _end_ram_write(self):
        if not self._cs_kernel:
            GPIO.output(self._cs, GPIO.HIGH)

    def fill(self, color):
        """
        Залить весь экран цветом.
        color: 16-bit RGB565 (например 0xFFFF — белый, 0x0000 — чёрный).
        """
        buf = [(color >> 8) & 0xFF, color & 0xFF] * (WIDTH * HEIGHT)
        self.set_window(0, 0, WIDTH - 1, HEIGHT - 1)
        self._start_ram_write()
        chunk = 4096
        for i in range(0, len(buf), chunk):
            self._write_pixels(buf[i:i + chunk])
        self._end_ram_write()

    def fill_rect(self, x, y, w, h, color):
        """Залить прямоугольник цветом RGB565."""
        if x < 0 or y < 0 or x + w > WIDTH or y + h > HEIGHT:
            return
        buf = [(color >> 8) & 0xFF, color & 0xFF] * (w * h)
        self.set_window(x, y, x + w - 1, y + h - 1)
        self._start_ram_write()
        chunk = 4096
        for i in range(0, len(buf), chunk):
            self._write_pixels(buf[i:i + chunk])
        self._end_ram_write()

    def blit_buffer(self, x, y, w, h, data):
        """Вывести готовый RGB565-буфер в прямоугольник."""
        if w <= 0 or h <= 0:
            return
        if x < 0 or y < 0 or x + w > WIDTH or y + h > HEIGHT:
            return
        expected_size = w * h * 2
        if len(data) != expected_size:
            raise ValueError(f"invalid RGB565 buffer size: expected {expected_size}, got {len(data)}")
        self.set_window(x, y, x + w - 1, y + h - 1)
        self._start_ram_write()
        chunk = 8192
        for i in range(0, len(data), chunk):
            self._write_pixels(data[i:i + chunk])
        self._end_ram_write()

    def pixel(self, x, y, color):
        """Нарисовать один пиксель."""
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            self.set_window(x, y, x, y)
            self._start_ram_write()
            self._write_pixels([(color >> 8) & 0xFF, color & 0xFF])
            self._end_ram_write()

    @staticmethod
    def color_rgb(r, g, b):
        """Преобразовать R,G,B (0–255) в RGB565."""
        return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

    def backlight(self, on=True):
        """Включить/выключить подсветку (если пин задан)."""
        if self._bl is not None:
            GPIO.output(self._bl, GPIO.HIGH if on else GPIO.LOW)

    def close(self):
        """Закрыть SPI и освободить GPIO."""
        self._spi.close()
        pins = [self._dc, self._rst] + ([self._cs] if not self._cs_kernel else []) + ([self._bl] if self._bl else [])
        GPIO.cleanup(pins)


if __name__ == "__main__":
    d = GC9A01(dc=24, rst=25, cs=8)
    d.fill(GC9A01.color_rgb(0, 0, 255))
    time.sleep(2)
    d.close()
