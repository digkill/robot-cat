# Дисплей GC9A01 на Raspberry Pi Zero 2 W

Драйвер и тест для круглого TFT-дисплея **GC9A01** (240×240) по SPI на Raspberry Pi Zero 2 W (и других моделях с 40-pin GPIO).

## Подключение (распиновка)

| Дисплей GC9A01 | Raspberry Pi Zero 2 W |
|----------------|------------------------|
| VCC            | 3.3V (pin 1)           |
| GND            | GND (pin 6, 9 или 14)  |
| SCL            | GPIO 11 (SCLK) — pin 23 |
| SDA            | GPIO 10 (MOSI) — pin 19 |
| CS             | GPIO 8 (CE0) — pin 24   |
| DC             | GPIO 24 — pin 18        |
| RST            | GPIO 25 — pin 22        |
| BL (подсветка) | GPIO 18 — pin 12 (опционально) |

**Важно:** питание только **3.3 V**. MISO не используется (данные только от Pi к дисплею).

## Включение SPI

1. Включите интерфейс SPI:
   ```bash
   sudo raspi-config
   ```
   **Interface Options → SPI → Enable.**

2. Или вручную добавьте в `/boot/firmware/config.txt` (или `/boot/config.txt` на старых образах):
   ```ini
   dtparam=spi=on
   ```
   Затем перезагрузка: `sudo reboot`.

3. Проверка: должны появиться устройства:
   ```bash
   ls /dev/spi*
   # /dev/spidev0.0  /dev/spidev0.1
   ```

## Установка зависимостей

```bash
cd /home/mini/gc9a01_rpi
pip3 install -r requirements.txt
```

Или по отдельности:
```bash
pip3 install spidev RPi.GPIO Pillow
```

## Запуск теста

Скрипт нужно запускать с правами root (доступ к SPI и GPIO):

```bash
sudo python3 test_display.py
```

Тест по очереди выводит:
- синюю заливку;
- цветные прямоугольники;
- круги в центре экрана;
- текст «GC9A01 Test», «Raspberry Pi» и др. (если установлен Pillow);
- белый и чёрный экран.

Выход: **Ctrl+C**.

## Изменение пинов

В `test_display.py` и в своём коде можно задать другие пины:

```python
from gc9a01 import GC9A01

# dc, rst, cs — обязательные; backlight — по желанию
disp = GC9A01(dc=24, rst=25, cs=8, backlight=18)
disp.fill(disp.color_rgb(255, 0, 0))  # красный экран
disp.close()
```

## Пример использования в своих скриптах

```python
from gc9a01 import GC9A01, WIDTH, HEIGHT

disp = GC9A01(dc=24, rst=25, cs=8)
disp.fill(GC9A01.color_rgb(0, 0, 0))
disp.fill_rect(80, 100, 80, 40, GC9A01.color_rgb(0, 255, 0))
disp.pixel(120, 120, GC9A01.color_rgb(255, 255, 255))
disp.close()
```

## Файлы

- `gc9a01.py` — драйвер дисплея (SPI + GPIO).
- `test_display.py` — тестовый скрипт с тестовыми данными.
- `requirements.txt` — зависимости Python.
