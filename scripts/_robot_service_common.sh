#!/bin/bash
set -euo pipefail

SERVICE_NAME="${ROBOT_SERVICE_NAME:-robot-bot.service}"

if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
fi
