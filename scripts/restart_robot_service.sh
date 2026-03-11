#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/_robot_service_common.sh"

$SUDO systemctl restart "$SERVICE_NAME"
echo "Сервис перезапущен: $SERVICE_NAME"
