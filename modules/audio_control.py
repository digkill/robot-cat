# -*- coding: utf-8 -*-
"""Управление системной громкостью и mute через ALSA/amixer."""

import re
import shutil
import subprocess

from config import AUDIO_CARD_INDEX

CONTROL_CANDIDATES = ("Headphone", "Speaker", "Playback")


def _log(message: str):
    try:
        from modules.watchlog import log
        log("audio_control", message)
    except Exception:
        pass


def _amixer(args: list[str], timeout: int = 4) -> subprocess.CompletedProcess | None:
    if not shutil.which("amixer"):
        return None
    try:
        return subprocess.run(
            ["amixer", "-c", str(AUDIO_CARD_INDEX), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as e:
        _log(f"amixer error: {e}")
        return None


def _available_controls() -> list[str]:
    found = []
    for control in CONTROL_CANDIDATES:
        result = _amixer(["sget", control])
        if result and result.returncode == 0:
            found.append(control)
    return found


def _parse_amixer_state(output: str) -> dict:
    volume_match = re.search(r"\[(\d{1,3})%\]", output or "")
    switch_matches = re.findall(r"\[(on|off)\]", output or "", flags=re.IGNORECASE)
    muted = False
    if switch_matches:
        muted = all(item.lower() == "off" for item in switch_matches)
    return {
        "volume": int(volume_match.group(1)) if volume_match else 0,
        "muted": muted,
    }


def get_audio_status() -> dict:
    controls = _available_controls()
    if not controls:
        return {"available": False, "volume": 0, "muted": False, "controls": []}
    result = _amixer(["sget", controls[0]])
    if not result or result.returncode != 0:
        return {"available": False, "volume": 0, "muted": False, "controls": controls}
    parsed = _parse_amixer_state(result.stdout)
    return {
        "available": True,
        "volume": parsed["volume"],
        "muted": parsed["muted"],
        "controls": controls,
    }


def set_audio_volume(volume: int) -> dict:
    controls = _available_controls()
    if not controls:
        raise RuntimeError("amixer/ALSA controls not available")
    value = max(0, min(100, int(volume)))
    for control in controls:
        _amixer(["-q", "set", control, f"{value}%", "unmute"])
    _amixer(["-q", "sset", "Master", f"{value}%"])
    _log(f"volume -> {value}%")
    return get_audio_status()


def set_audio_mute(muted: bool) -> dict:
    controls = _available_controls()
    if not controls:
        raise RuntimeError("amixer/ALSA controls not available")
    action = "mute" if muted else "unmute"
    for control in controls:
        _amixer(["-q", "set", control, action])
    _amixer(["-q", "sset", "Master", action])
    _log(f"mute -> {muted}")
    return get_audio_status()
