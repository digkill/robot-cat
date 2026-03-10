#!/bin/bash
set -euo pipefail

# Запуск робота в фоне на самой удаленной машине.
# После запуска можно закрыть SSH/терминал — процесс останется работать.

cd "$(dirname "$0")/.."

LOG_DIR="$PWD/logs"
PID_FILE="$LOG_DIR/robot_bg.pid"
LOG_FILE="$LOG_DIR/robot_bg.log"

mkdir -p "$LOG_DIR"

if [ -f "$PID_FILE" ]; then
    OLD_PID="$(tr -d '[:space:]' < "$PID_FILE" 2>/dev/null || true)"
    if [ -n "${OLD_PID:-}" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Робот уже запущен в фоне (PID $OLD_PID)."
        echo "Лог: $LOG_FILE"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "Проверка sudo..."
    sudo -v
    START_CMD="sudo ./run_robot.sh"
else
    START_CMD="./run_robot.sh"
fi

echo "Запуск робота в фоне..."
nohup bash -lc "cd \"$PWD\" && exec $START_CMD" >>"$LOG_FILE" 2>&1 < /dev/null &
PID=$!
echo "$PID" > "$PID_FILE"

sleep 1
if kill -0 "$PID" 2>/dev/null; then
    echo "Робот запущен в фоне."
    echo "PID: $PID"
    echo "Лог: $LOG_FILE"
else
    echo "Не удалось запустить робота. Смотрите лог: $LOG_FILE" >&2
    exit 1
fi
