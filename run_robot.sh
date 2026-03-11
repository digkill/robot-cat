#!/bin/bash
# Запуск робота без принудительного sudo.

export LC_ALL=C.UTF-8 2>/dev/null || export LC_ALL=C
cd "$(dirname "$0")"
for v in "$PWD/.venv/bin/python3" "$HOME/Projects/Mini/.venv/bin/python3" "/home/mini/Projects/Mini/.venv/bin/python3"; do
    [ -x "$v" ] && PYTHON="$v" && break
done
PYTHON="${PYTHON:-python3}"

echo "Освобождение камеры..."
if [ -e /dev/video0 ]; then
    fuser -k /dev/video0 2>/dev/null || true
    sleep 2
fi

cleanup() {
    echo "Выход."
}
trap cleanup EXIT

echo "Запуск робота..."
if [ -n "${ROBOT_AUDIO_USER:-}" ]; then
    AUDIO_USER="$ROBOT_AUDIO_USER"
    AUDIO_UID="${ROBOT_AUDIO_UID:-$(id -u "$AUDIO_USER")}"
    AUDIO_HOME="${ROBOT_AUDIO_HOME:-$(getent passwd "$AUDIO_USER" | cut -d: -f6)}"
else
    AUDIO_USER="$USER"
    AUDIO_UID="$(id -u)"
    AUDIO_HOME="$HOME"
fi

exec env \
    ROBOT_AUDIO_USER="$AUDIO_USER" \
    ROBOT_AUDIO_UID="$AUDIO_UID" \
    ROBOT_AUDIO_HOME="$AUDIO_HOME" \
    "$PYTHON" robot_main.py
