# -*- coding: utf-8 -*-
"""Анимация лица-котика на дисплее GC9A01: глаза, брови, нос, улыбка, усы."""

import math
import time
import threading
import random
from gc9a01 import GC9A01, WIDTH, HEIGHT

CX, CY = 120, 115
FACE_X0, FACE_Y0 = 36, 44
FACE_W, FACE_H = 168, 136


def rgb(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


COLOR_BG = rgb(5, 5, 8)
COLOR_GLOW = rgb(100, 200, 255)
COLOR_IRIS = rgb(24, 70, 110)


def fill_circle(disp, cx, cy, radius, color):
    if radius <= 0:
        return
    for dy in range(-radius, radius + 1):
        y = cy + dy
        if y < 0 or y >= HEIGHT:
            continue
        t = dy / radius
        if t * t > 1:
            continue
        half = radius * math.sqrt(1 - t * t)
        x0 = max(0, int(cx - half))
        x1 = min(WIDTH - 1, int(cx + half))
        if x1 >= x0:
            disp.fill_rect(x0, y, x1 - x0 + 1, 1, color)


def fill_ellipse(disp, cx, cy, rx, ry, color):
    """Заполненный эллипс, чтобы глаза были более кошачьими, а не круглыми."""
    if rx <= 0 or ry <= 0:
        return
    for dy in range(-ry, ry + 1):
        y = cy + dy
        if y < 0 or y >= HEIGHT:
            continue
        t = dy / ry
        if t * t > 1:
            continue
        half = rx * math.sqrt(1 - t * t)
        x0 = max(0, int(cx - half))
        x1 = min(WIDTH - 1, int(cx + half))
        if x1 >= x0:
            disp.fill_rect(x0, y, x1 - x0 + 1, 1, color)


def ease_smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def draw_eye_ring(disp, cx, cy, radius, thickness, blink_ratio=1.0):
    """Глаз как раньше: светящееся кольцо, но с более мягким прищуром."""
    blink_ratio = max(0.0, min(1.0, blink_ratio))
    if blink_ratio < 0.22:
        slit_h = max(1, int(radius * 0.12 * (1.0 + blink_ratio * 2.0)))
        y0 = max(0, cy - slit_h)
        y1 = min(HEIGHT - 1, cy + slit_h)
        w = max(3, int(radius * 0.68))
        for y in range(y0, y1 + 1):
            edge_soft = 1.0 - abs(y - cy) / max(1, slit_h + 1)
            half = max(3, int(w * (0.82 + edge_soft * 0.18)))
            x0 = max(0, cx - half)
            x1 = min(WIDTH - 1, cx + half)
            if x1 >= x0:
                disp.fill_rect(x0, y, x1 - x0 + 1, 1, COLOR_GLOW)
        return
    r_outer = max(1, int(radius * (0.50 + 0.50 * blink_ratio)))
    r_inner = max(0, r_outer - max(1, int(thickness * (0.65 + 0.35 * blink_ratio))))
    fill_circle(disp, cx, cy, r_outer, COLOR_GLOW)
    if r_inner > 0:
        fill_circle(disp, cx, cy, r_inner, COLOR_BG)


def draw_eyebrow(disp, cx, cy, radius):
    """Небольшая светящаяся бровь-ушко над глазом."""
    fill_circle(disp, cx, cy, radius, COLOR_GLOW)


def draw_nose(disp, cx, cy, size):
    """Нос — перевёрнутый треугольник."""
    for i in range(size):
        w = size - i
        y = cy + i
        if 0 <= y < HEIGHT:
            x0 = max(0, cx - w)
            x1 = min(WIDTH - 1, cx + w)
            if x1 >= x0:
                disp.fill_rect(x0, y, x1 - x0 + 1, 1, COLOR_GLOW)


def draw_mouth_smile(disp, cx, cy, open_ratio):
    """Кошачья мордочка: центральная линия и две мягкие щечки-улыбки."""
    open_ratio = max(0.0, min(1.0, open_ratio))
    stem_h = 4 + int(5 * open_ratio)
    disp.fill_rect(cx, cy - 1, 1, stem_h, COLOR_GLOW)

    arc_rx = 7 + int(6 * open_ratio)
    arc_ry = 4 + int(4 * open_ratio)
    arc_cy = cy + stem_h + 1
    for side in (-1, 1):
        arc_cx = cx + side * 9
        for dy in range(-arc_ry, arc_ry + 1):
            y = arc_cy + dy
            if y < 0 or y >= HEIGHT:
                continue
            t = dy / max(1, arc_ry)
            half = int(arc_rx * math.sqrt(max(0.0, 1.0 - t * t)))
            if half <= 0:
                continue
            if side < 0:
                x0 = max(0, arc_cx - half)
                x1 = min(WIDTH - 1, arc_cx)
            else:
                x0 = max(0, arc_cx)
                x1 = min(WIDTH - 1, arc_cx + half)
            if x1 >= x0:
                disp.fill_rect(x0, y, x1 - x0 + 1, 1, COLOR_GLOW)

    if open_ratio > 0.18:
        fill_ellipse(disp, cx, cy + stem_h + arc_ry + 3, 5 + int(4 * open_ratio), 2 + int(3 * open_ratio), COLOR_IRIS)


def draw_whiskers(disp, cx, cy, spread=0.0):
    """Усы — немного шевелятся и расправляются, когда кот говорит."""
    spread = max(0.0, min(1.0, spread))
    for side in (-1, 1):
        length = 12 + int(5 * spread)
        for idx, base_dy in enumerate((-5, 0, 5)):
            y = cy + base_dy + int((idx - 1) * spread * 2)
            if 0 <= y < HEIGHT:
                x0 = cx + side * 20
                x1 = cx + side * (20 + length)
                x = max(0, min(x0, x1))
                x2 = min(WIDTH, max(x0, x1) + 1)
                w = x2 - x
                if w > 0:
                    disp.fill_rect(x, y, w, 1, COLOR_GLOW)


def draw_face(disp, blink_ratio=1.0, mouth_ratio=0.0, breath=0.0, whisker_spread=0.0, ear_perk=0.0):
    """Рисует лицо кота с живым idle-состоянием."""
    disp.fill_rect(FACE_X0, FACE_Y0, FACE_W, FACE_H, COLOR_BG)
    breath = max(0.0, min(1.0, breath))
    face_bob = int(round((breath - 0.5) * 3.0))
    eye_cx_l, eye_cx_r = CX - 38, CX + 38
    eye_cy = CY - 15 + face_bob
    eye_radius = 28
    ring_thickness = 6
    brow_y = eye_cy - 31 - int(ear_perk * 4)

    draw_eyebrow(disp, eye_cx_l - 8, brow_y, 5)
    draw_eyebrow(disp, eye_cx_r + 8, brow_y - int(ear_perk * 2), 5)
    draw_eye_ring(disp, eye_cx_l, eye_cy, eye_radius, ring_thickness, blink_ratio)
    draw_eye_ring(disp, eye_cx_r, eye_cy, eye_radius, ring_thickness, blink_ratio)
    draw_nose(disp, CX, CY + 24 + face_bob, 6)
    draw_mouth_smile(disp, CX, CY + 40 + face_bob, mouth_ratio)
    draw_whiskers(disp, CX, CY + 40 + face_bob, whisker_spread)


class FaceAnimator:
    """Управление анимацией лица: кошачье моргание, дыхание и живая мордочка."""

    def __init__(self, disp):
        self.disp = disp
        self._blink_ratio = 1.0
        self._mouth_ratio = 0.0
        self._breath = 0.5
        self._whisker_spread = 0.15
        self._ear_perk = 0.0
        self._last_frame_key = None
        self._speaking = False
        self._running = True
        self._thread = threading.Thread(target=self._animate, daemon=True)

    def set_speaking(self, on: bool):
        self._speaking = on

    def _draw(self, force=False):
        frame_key = (
            round(self._blink_ratio * 20),
            round(self._mouth_ratio * 14),
            round(self._breath * 10),
            round(self._whisker_spread * 10),
            round(self._ear_perk * 10),
        )
        if not force and frame_key == self._last_frame_key:
            return
        draw_face(
            self.disp,
            self._blink_ratio,
            self._mouth_ratio,
            self._breath,
            self._whisker_spread,
            self._ear_perk,
        )
        self._last_frame_key = frame_key

    def _run_blink(self):
        frames = 24
        for i in range(frames):
            if not self._running:
                break
            t = i / max(1, frames - 1)
            if t < 0.44:
                self._blink_ratio = 1.0 - ease_smoothstep(t / 0.44)
            elif t < 0.58:
                self._blink_ratio = 0.0
            else:
                self._blink_ratio = ease_smoothstep((t - 0.58) / 0.42)
            self._draw()
            time.sleep(0.010)
        self._blink_ratio = 1.0

    def _animate(self):
        # Кошка моргает мягко, иногда делает двойное моргание, и чуть шевелит мордочкой.
        next_blink = time.monotonic() + random.uniform(3.5, 7.5)
        next_ear_flick = time.monotonic() + random.uniform(5.0, 11.0)
        mouth_phase = 0
        breath_phase = random.uniform(0.0, math.tau)
        while self._running:
            now = time.monotonic()
            if now >= next_blink:
                self._run_blink()
                next_blink = time.monotonic() + random.uniform(4.5, 9.0)
                if random.random() < 0.18 and self._running:
                    time.sleep(0.08)
                    self._run_blink()
                continue

            if now >= next_ear_flick:
                self._ear_perk = 1.0
                next_ear_flick = now + random.uniform(6.0, 14.0)

            breath_phase += 0.09 if self._speaking else 0.045
            self._breath = 0.5 + 0.5 * math.sin(breath_phase)

            if self._speaking:
                mouth_phase += 0.2
                self._mouth_ratio = 0.20 + 0.45 * (0.5 + 0.5 * math.sin(mouth_phase * 1.7))
                self._mouth_ratio += 0.10 * (0.5 + 0.5 * math.sin(mouth_phase * 0.63))
                self._whisker_spread = 0.45 + 0.35 * (0.5 + 0.5 * math.sin(mouth_phase * 1.1))
            else:
                self._mouth_ratio *= 0.72
                if self._mouth_ratio < 0.02:
                    self._mouth_ratio = 0.0
                self._whisker_spread = 0.12 + 0.12 * (0.5 + 0.5 * math.sin(breath_phase * 1.7))

            self._ear_perk *= 0.82
            self._draw()
            time.sleep(0.07 if self._speaking else 0.11)

    def start(self):
        self._draw(force=True)
        try:
            from modules.watchlog import log
            log("face", "анимация лица: живая кошачья мордочка без ряби")
        except Exception:
            pass
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive() and threading.current_thread() is not self._thread:
            try:
                self._thread.join(timeout=1.5)
            except KeyboardInterrupt:
                try:
                    from modules.watchlog import log
                    log("face", "join прерван Ctrl+C во время stop")
                except Exception:
                    pass
