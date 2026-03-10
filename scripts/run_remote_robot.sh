#!/bin/bash
set -euo pipefail

# Запуск робота на удаленной машине через SSH.
# Примеры:
#   ./scripts/run_remote_robot.sh robotcat@192.168.1.50
#   ./scripts/run_remote_robot.sh robotcat@192.168.1.50 ~/Projects/robot-cat

REMOTE_HOST="${1:-${ROBOT_REMOTE_HOST:-}}"
REMOTE_DIR="${2:-${ROBOT_REMOTE_DIR:-~/Projects/robot-cat}}"

if [ -z "$REMOTE_HOST" ]; then
    echo "Usage: $0 <user@host> [remote_project_dir]" >&2
    echo "Or set ROBOT_REMOTE_HOST and optional ROBOT_REMOTE_DIR." >&2
    exit 1
fi

ssh -t "$REMOTE_HOST" "bash -lc '
set -e
cd \"$REMOTE_DIR\"

if [ -x ./run_robot.sh ]; then
    exec ./run_robot.sh
fi

if [ -x ./.venv/bin/python3 ]; then
    exec sudo \
        ROBOT_AUDIO_USER=\"\${USER}\" \
        ROBOT_AUDIO_UID=\"\$(id -u)\" \
        ROBOT_AUDIO_HOME=\"\${HOME}\" \
        ./.venv/bin/python3 robot_main.py
fi

exec sudo python3 robot_main.py
'"
