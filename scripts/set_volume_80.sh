#!/bin/bash
# Установить громкость 100% для wm8960.
# Вариант 1: Запустить вручную
#   ./set_volume_80.sh
# Вариант 2: Сохранить и восстанавливать при загрузке
#   ./set_volume_80.sh && sudo alsactl store

set +e

amixer -c 0 -q set Headphone 100% 2>/dev/null || true
amixer -c 0 -q set Speaker 100% 2>/dev/null || true
amixer -c 0 -q set Playback 100% 2>/dev/null || true
alsactl store 0 2>/dev/null || true

exit 0
