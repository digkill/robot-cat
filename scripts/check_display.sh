#!/bin/bash
# Диагностика дисплея GC9A01 — проверка SPI, GPIO, прав доступа.

cd "$(dirname "$0")/.."

for v in "$PWD/.venv/bin/python3" python3; do
    [ -x "$v" ] && PYTHON="$v" && break
done
PYTHON="${PYTHON:-python3}"

echo "=== Проверка дисплея GC9A01 ==="
echo

# 1. SPI
echo "1. SPI интерфейс:"
if [ -e /dev/spidev0.0 ]; then
    echo "   /dev/spidev0.0 — OK"
    ls -la /dev/spidev0.0
else
    echo "   /dev/spidev0.0 — НЕ НАЙДЕН"
    echo "   Включите SPI: sudo raspi-config → Interface Options → SPI → Enable"
    echo "   Или добавьте в /boot/firmware/config.txt: dtparam=spi=on"
fi
echo

# 2. Права на SPI
echo "2. Права доступа к SPI:"
if [ -e /dev/spidev0.0 ]; then
    if [ -r /dev/spidev0.0 ] && [ -w /dev/spidev0.0 ]; then
        echo "   Чтение/запись — OK"
    else
        echo "   Permission denied — добавьте пользователя в группу spi:"
        echo "   sudo usermod -aG spi \$USER"
        echo "   (перелогиньтесь или reboot)"
    fi
fi
echo

# 3. Python-модули
echo "3. Python-модули:"
PYTHON="${PYTHON:-python3}"
for mod in spidev RPi.GPIO; do
    if "$PYTHON" -c "import $mod" 2>/dev/null; then
        echo "   $mod — OK"
    else
        echo "   $mod — НЕ УСТАНОВЛЕН"
        echo "   pip install spidev RPi.GPIO"
    fi
done
echo

# 4. Тест дисплея
echo "4. Тест инициализации дисплея:"
if "$PYTHON" -c "
from gc9a01 import GC9A01
d = GC9A01(dc=24, rst=25, cs=8, backlight=26)
d.fill(0xFFFF)
d.close()
print('   Дисплей инициализирован — OK')
" 2>&1; then
    :
else
    echo "   Ошибка при инициализации (см. выше)"
fi
echo

echo "=== Подключение (GPIO_WIRING.md) ==="
echo "SCL→23, SDA→19, CS→24, DC→18, RST→22, BL→37 (GPIO26)"
echo "Питание: 3.3V (pin 1), GND (pin 6)"
