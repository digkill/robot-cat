#!/bin/bash
# Запуск робота (sudo для SPI/GPIO)

export LC_ALL=C.UTF-8 2>/dev/null || export LC_ALL=C
cd "$(dirname "$0")"
for v in "$PWD/.venv/bin/python3" "$HOME/Projects/Mini/.venv/bin/python3" "/home/mini/Projects/Mini/.venv/bin/python3"; do
    [ -x "$v" ] && PYTHON="$v" && break
done
PYTHON="${PYTHON:-python3}"

echo "Освобождение камеры..."
if [ -e /dev/video0 ]; then
    sudo fuser -k /dev/video0 2>/dev/null || true
    sleep 2
fi

cleanup() {
    echo "Выход."
}
trap cleanup EXIT

echo "Запуск робота..."
if [ "$(id -u)" -ne 0 ]; then
    exec sudo \
        ROBOT_AUDIO_USER="$USER" \
        ROBOT_AUDIO_UID="$(id -u)" \
        ROBOT_AUDIO_HOME="$HOME" \
        "$PYTHON" robot_main.py
else
    if [ -n "${SUDO_USER:-}" ]; then
        AUDIO_USER="$SUDO_USER"
        AUDIO_UID="${SUDO_UID:-$(id -u "$AUDIO_USER")}"
        AUDIO_HOME="$(getent passwd "$AUDIO_USER" | cut -d: -f6)"
    else
        AUDIO_USER="mini"
        AUDIO_UID="$(id -u "$AUDIO_USER")"
        AUDIO_HOME="$(getent passwd "$AUDIO_USER" | cut -d: -f6)"
    fi
    exec env \
        ROBOT_AUDIO_USER="$AUDIO_USER" \
        ROBOT_AUDIO_UID="$AUDIO_UID" \
        ROBOT_AUDIO_HOME="$AUDIO_HOME" \
        "$PYTHON" robot_main.py
fi
