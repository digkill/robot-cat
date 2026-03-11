#!/bin/bash
set -euo pipefail

# Установка systemd-сервиса для автозапуска робота после перезагрузки.
# Запуск:
#   ./scripts/install_robot_service.sh

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_NAME="${ROBOT_SERVICE_NAME:-robot-bot.service}"

if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
fi

if [ -n "${ROBOT_AUDIO_USER:-}" ]; then
    AUDIO_USER="$ROBOT_AUDIO_USER"
else
    AUDIO_USER="$(stat -c '%U' "$PROJECT_DIR" 2>/dev/null || whoami)"
fi

AUDIO_UID="$(id -u "$AUDIO_USER")"
AUDIO_GROUP="$(id -gn "$AUDIO_USER")"
AUDIO_HOME="$(getent passwd "$AUDIO_USER" | cut -d: -f6)"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"

echo "Установка сервиса: $SERVICE_NAME"
echo "Проект: $PROJECT_DIR"
echo "Аудио-пользователь: $AUDIO_USER"

$SUDO tee "$SERVICE_PATH" >/dev/null <<EOF
[Unit]
Description=Robot Cat
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=simple
User=$AUDIO_USER
Group=$AUDIO_GROUP
WorkingDirectory=$PROJECT_DIR
Environment=ROBOT_AUDIO_USER=$AUDIO_USER
Environment=ROBOT_AUDIO_UID=$AUDIO_UID
Environment=ROBOT_AUDIO_HOME=$AUDIO_HOME
ExecStart=$PROJECT_DIR/run_robot.sh
Restart=always
RestartSec=5
StandardOutput=append:$PROJECT_DIR/logs/robot_systemd.log
StandardError=append:$PROJECT_DIR/logs/robot_systemd.log

[Install]
WantedBy=multi-user.target
EOF

$SUDO systemctl daemon-reload
$SUDO systemctl enable --now "$SERVICE_NAME"

echo
echo "Сервис установлен и запущен."
echo "Проверка статуса:"
echo "  sudo systemctl status $SERVICE_NAME"
echo "Лог:"
echo "  journalctl -u $SERVICE_NAME -f"
