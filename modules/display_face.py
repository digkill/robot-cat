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
COLOR_PINK = rgb(255, 120, 180)
COLOR_RED = rgb(255, 90, 90)
COLOR_GOLD = rgb(255, 210, 90)
COLOR_LAVENDER = rgb(210, 160, 255)
COLOR_SOFT_BLUE = rgb(140, 190, 255)

EMOTION_PRESETS = {
    "веселый": {
        "accent": rgb(110, 220, 255),
        "iris": rgb(40, 110, 150),
        "eye_scale": 0.82,
        "mouth": "grin",
        "brow_lift": -4,
        "left_tilt": -1,
        "right_tilt": 1,
        "whisker_bias": 0.18,
    },
    "радостный": {
        "accent": COLOR_GLOW,
        "iris": COLOR_IRIS,
        "eye_scale": 0.94,
        "mouth": "smile",
        # Дефолтное лицо должно быть добрым: брови выше и почти горизонтальные.
        "brow_lift": -5,
        "left_tilt": 0,
        "right_tilt": 0,
        "whisker_bias": 0.12,
    },
    "грустный": {
        "accent": COLOR_SOFT_BLUE,
        "iris": rgb(50, 90, 140),
        "eye_scale": 0.68,
        "mouth": "frown",
        "brow_lift": 4,
        "left_tilt": 3,
        "right_tilt": -3,
        "whisker_bias": -0.08,
    },
    "злой": {
        "accent": COLOR_RED,
        "iris": rgb(120, 30, 30),
        "eye_scale": 0.58,
        "mouth": "flat",
        "brow_lift": -1,
        "left_tilt": 6,
        "right_tilt": -6,
        "whisker_bias": -0.12,
    },
    "задумчивый": {
        "accent": COLOR_LAVENDER,
        "iris": rgb(70, 80, 140),
        "eye_scale": 0.76,
        "mouth": "ponder",
        "brow_lift": -1,
        "left_tilt": 0,
        "right_tilt": 2,
        "whisker_bias": 0.0,
    },
    "стесняется": {
        "accent": rgb(255, 180, 215),
        "iris": rgb(150, 90, 120),
        "eye_scale": 0.63,
        "mouth": "shy",
        "brow_lift": 0,
        "left_tilt": 0,
        "right_tilt": 0,
        "blush": True,
        "whisker_bias": -0.02,
    },
    "влюбленный": {
        "accent": COLOR_PINK,
        "iris": COLOR_PINK,
        "eye_scale": 0.86,
        "mouth": "smile",
        "brow_lift": -1,
        "left_tilt": -1,
        "right_tilt": 1,
        "blush": True,
        "heart_eyes": True,
        "whisker_bias": 0.18,
    },
    "кукушка": {
        "accent": rgb(170, 255, 140),
        "iris": rgb(90, 150, 70),
        "eye_scale": 1.0,
        "mouth": "grin",
        "brow_lift": -6,
        "left_tilt": -1,
        "right_tilt": 1,
        "sparkles": True,
        "whisker_bias": 0.24,
    },
    "праздничный": {
        "accent": COLOR_GOLD,
        "iris": rgb(255, 150, 60),
        "eye_scale": 0.88,
        "mouth": "grin",
        "brow_lift": -4,
        "left_tilt": -2,
        "right_tilt": 2,
        "sparkles": True,
        "whisker_bias": 0.22,
    },
}


class FaceCanvas:
    """Локальный RGB565-буфер мордочки, чтобы отправлять кадр на дисплей одним blit."""

    def __init__(self, x0, y0, width, height, bg_color):
        self.x0 = x0
        self.y0 = y0
        self.width = width
        self.height = height
        hi = (bg_color >> 8) & 0xFF
        lo = bg_color & 0xFF
        self.buffer = bytearray([hi, lo] * (width * height))

    def fill_rect(self, x, y, w, h, color):
        if w <= 0 or h <= 0:
            return
        local_x0 = max(0, x - self.x0)
        local_y0 = max(0, y - self.y0)
        local_x1 = min(self.width, x - self.x0 + w)
        local_y1 = min(self.height, y - self.y0 + h)
        if local_x0 >= local_x1 or local_y0 >= local_y1:
            return
        hi = (color >> 8) & 0xFF
        lo = color & 0xFF
        row_width = self.width * 2
        span = (local_x1 - local_x0) * 2
        row = bytes([hi, lo] * (local_x1 - local_x0))
        for yy in range(local_y0, local_y1):
            offset = yy * row_width + local_x0 * 2
            self.buffer[offset:offset + span] = row

    def to_bytes(self):
        return self.buffer


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


def draw_stroke(disp, x0, y0, x1, y1, thickness, color):
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(steps + 1):
        t = i / steps
        x = int(round(x0 + (x1 - x0) * t))
        y = int(round(y0 + (y1 - y0) * t))
        fill_circle(disp, x, y, thickness, color)


def ease_smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def draw_heart(disp, cx, cy, size, color):
    fill_circle(disp, cx - size // 2, cy - size // 4, max(1, size // 2), color)
    fill_circle(disp, cx + size // 2, cy - size // 4, max(1, size // 2), color)
    for i in range(size + 1):
        half = max(1, size - i)
        y = cy + i
        if 0 <= y < HEIGHT:
            x0 = max(0, cx - half)
            x1 = min(WIDTH - 1, cx + half)
            if x1 >= x0:
                disp.fill_rect(x0, y, x1 - x0 + 1, 1, color)


def draw_sparkle(disp, cx, cy, size, color):
    disp.fill_rect(max(0, cx - size), cy, min(WIDTH - max(0, cx - size), size * 2 + 1), 1, color)
    disp.fill_rect(cx, max(0, cy - size), 1, min(HEIGHT - max(0, cy - size), size * 2 + 1), color)


def draw_eye_ring(disp, cx, cy, radius, thickness, blink_ratio=1.0, accent_color=COLOR_GLOW, eye_scale=1.0, heart_eyes=False):
    """Глаз как раньше: светящееся кольцо, но с более мягким прищуром."""
    blink_ratio = max(0.0, min(1.0, blink_ratio * eye_scale))
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
                disp.fill_rect(x0, y, x1 - x0 + 1, 1, accent_color)
        return
    if heart_eyes:
        outer = max(8, int(radius * 0.62))
        inner = max(4, outer - thickness)
        draw_heart(disp, cx, cy - 2, outer, accent_color)
        draw_heart(disp, cx, cy - 2, inner, COLOR_BG)
        return
    r_outer = max(1, int(radius * (0.50 + 0.50 * blink_ratio)))
    r_inner = max(0, r_outer - max(1, int(thickness * (0.65 + 0.35 * blink_ratio))))
    fill_ellipse(disp, cx, cy, r_outer, max(3, int(r_outer * (0.78 + blink_ratio * 0.18))), accent_color)
    if r_inner > 0:
        fill_ellipse(disp, cx, cy, r_inner, max(2, int(r_inner * (0.74 + blink_ratio * 0.16))), COLOR_BG)


def draw_eyebrow(disp, cx, cy, half_width, tilt, accent_color):
    """Бровь как светящийся штрих с наклоном."""
    draw_stroke(disp, cx - half_width, cy + tilt, cx + half_width, cy - tilt, 1, accent_color)


def draw_nose(disp, cx, cy, size, accent_color):
    """Нос — перевёрнутый треугольник."""
    for i in range(size):
        w = size - i
        y = cy + i
        if 0 <= y < HEIGHT:
            x0 = max(0, cx - w)
            x1 = min(WIDTH - 1, cx + w)
            if x1 >= x0:
                disp.fill_rect(x0, y, x1 - x0 + 1, 1, accent_color)


def draw_mouth(disp, cx, cy, open_ratio, accent_color, iris_color, style="smile"):
    """Кошачья мордочка: центральная линия и две мягкие щечки-улыбки."""
    open_ratio = max(0.0, min(1.0, open_ratio))
    if style == "flat":
        disp.fill_rect(cx - 10, cy + 6, 21, 2, accent_color)
        return
    if style == "ponder":
        disp.fill_rect(cx - 8, cy + 5, 16, 2, accent_color)
        disp.fill_rect(cx + 8, cy + 5, 4, 1, accent_color)
        return
    stem_h = 3 + int(5 * open_ratio)
    if style in ("smile", "grin", "shy"):
        disp.fill_rect(cx, cy - 1, 1, stem_h, accent_color)
    arc_rx = 7 + int(6 * open_ratio)
    arc_ry = 4 + int(4 * open_ratio)
    if style == "grin":
        arc_rx += 2
        arc_ry += 1
    if style == "shy":
        arc_rx = max(5, arc_rx - 2)
        arc_ry = max(3, arc_ry - 1)
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
            if style == "frown":
                y = cy + 7 - dy
            if side < 0:
                x0 = max(0, arc_cx - half)
                x1 = min(WIDTH - 1, arc_cx)
            else:
                x0 = max(0, arc_cx)
                x1 = min(WIDTH - 1, arc_cx + half)
            if x1 >= x0 and 0 <= y < HEIGHT:
                disp.fill_rect(x0, y, x1 - x0 + 1, 1, accent_color)
    if style in ("smile", "grin") and open_ratio > 0.18:
        fill_ellipse(disp, cx, cy + stem_h + arc_ry + 3, 5 + int(4 * open_ratio), 2 + int(3 * open_ratio), iris_color)


def draw_whiskers(disp, cx, cy, accent_color, spread=0.0, bias=0.0):
    """Усы — немного шевелятся и расправляются, когда кот говорит."""
    spread = max(0.0, min(1.0, spread))
    for side in (-1, 1):
        length = 12 + int(5 * spread)
        for idx, base_dy in enumerate((-5, 0, 5)):
            y = cy + base_dy + int((idx - 1) * spread * 2) + int(bias * 6)
            if 0 <= y < HEIGHT:
                x0 = cx + side * 20
                x1 = cx + side * (20 + length)
                x = max(0, min(x0, x1))
                x2 = min(WIDTH, max(x0, x1) + 1)
                w = x2 - x
                if w > 0:
                    disp.fill_rect(x, y, w, 1, accent_color)


def draw_blush(disp, cx, cy, color):
    fill_ellipse(disp, cx - 38, cy + 20, 8, 4, color)
    fill_ellipse(disp, cx + 38, cy + 20, 8, 4, color)


def draw_face(disp, blink_ratio=1.0, mouth_ratio=0.0, breath=0.0, whisker_spread=0.0, ear_perk=0.0, emotion="радостный"):
    """Рисует лицо кота с живым idle-состоянием."""
    profile = EMOTION_PRESETS.get(emotion, EMOTION_PRESETS["радостный"])
    accent_color = profile["accent"]
    iris_color = profile["iris"]
    canvas = FaceCanvas(FACE_X0, FACE_Y0, FACE_W, FACE_H, COLOR_BG)
    breath = max(0.0, min(1.0, breath))
    face_bob = int(round((breath - 0.5) * 3.0))
    eye_cx_l, eye_cx_r = CX - 38, CX + 38
    eye_cy = CY - 15 + face_bob
    eye_radius = 28
    ring_thickness = 6
    brow_y = eye_cy - 31 - int(ear_perk * 4) + profile.get("brow_lift", 0)

    draw_eyebrow(canvas, eye_cx_l - 8, brow_y, 10, profile.get("left_tilt", 0), accent_color)
    draw_eyebrow(canvas, eye_cx_r + 8, brow_y - int(ear_perk * 2), 10, profile.get("right_tilt", 0), accent_color)
    draw_eye_ring(
        canvas,
        eye_cx_l,
        eye_cy,
        eye_radius,
        ring_thickness,
        blink_ratio,
        accent_color,
        profile.get("eye_scale", 1.0),
        profile.get("heart_eyes", False),
    )
    draw_eye_ring(
        canvas,
        eye_cx_r,
        eye_cy,
        eye_radius,
        ring_thickness,
        blink_ratio,
        accent_color,
        profile.get("eye_scale", 1.0),
        profile.get("heart_eyes", False),
    )
    draw_nose(canvas, CX, CY + 24 + face_bob, 6, accent_color)
    draw_mouth(canvas, CX, CY + 40 + face_bob, mouth_ratio, accent_color, iris_color, profile.get("mouth", "smile"))
    draw_whiskers(canvas, CX, CY + 40 + face_bob, accent_color, whisker_spread, profile.get("whisker_bias", 0.0))
    if profile.get("blush"):
        draw_blush(canvas, CX, CY + face_bob, COLOR_PINK)
    if profile.get("sparkles"):
        draw_sparkle(canvas, CX - 58, CY - 38 + face_bob, 3, accent_color)
        draw_sparkle(canvas, CX + 58, CY - 44 + face_bob, 3, accent_color)
    disp.blit_buffer(FACE_X0, FACE_Y0, FACE_W, FACE_H, canvas.to_bytes())


class FaceAnimator:
    """Управление анимацией лица: кошачье моргание, дыхание и живая мордочка."""

    def __init__(self, disp):
        self.disp = disp
        self._blink_ratio = 1.0
        self._mouth_ratio = 0.0
        self._breath = 0.5
        self._whisker_spread = 0.15
        self._ear_perk = 0.0
        self._emotion = "радостный"
        self._last_frame_key = None
        self._speaking = False
        self._running = True
        self._thread = threading.Thread(target=self._animate, daemon=True)

    def set_speaking(self, on: bool):
        self._speaking = on

    def set_emotion(self, emotion: str):
        if emotion in EMOTION_PRESETS:
            self._emotion = emotion
        else:
            self._emotion = "радостный"

    def _draw(self, force=False):
        frame_key = (
            round(self._blink_ratio * 20),
            round(self._mouth_ratio * 14),
            round(self._breath * 10),
            round(self._whisker_spread * 10),
            round(self._ear_perk * 10),
            self._emotion,
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
            self._emotion,
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
