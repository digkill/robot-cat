# Робот — инструкция

## Возможности

- **Камера**: детекция человека (приветствие, «как дела», шутка) и движения (запись 30 сек → S3)
- **Дисплей**: анимация глаз и рта при говорении
- **RGB LED**: цвет по эмоциям (нейтрально, приветствие, шутка, движение, кнопка)
- **Кнопка**: сенсорная, как звонок в дверь
- **Веб**: события, записи, снимки, голосовой ассистент, запись с микрофона

## Установка

```bash
pip install -r requirements.txt
# Для CSI: sudo apt install rpicam-apps
# Для TTS: sudo apt install espeak-ng
```

## Конфигурация (.env)

- **S3** — уже заданы для Beget
- **LLM_CONSOLE_URL** — URL API mediarise-robot-console (ESP32), например `http://192.168.1.100:8080/api/chat`
- **LLM_API_KEY** — ключ OpenAI, если не используете консоль

## Запуск

```bash
# Только робот
sudo python3 robot_main.py

# Робот + веб (http://IP:5000)
sudo python3 run_all.py

# Только веб (без дисплея/камеры)
python3 web_app.py
```

## Подключение GPIO

См. **GPIO_WIRING.md** для полной распиновки.

| LED (S V G) | Кнопка |
|-------------|--------|
| S → GPIO 21 (pin 40) | Сигнал → GPIO 23 (pin 16) |
| V → 5V (pin 2) | GND → pin 14 |
| G → GND (pin 39) | |

**LED:** адресная WS2812B. Установка: `pip install rpi_ws281x`

## mediarise-robot-console

Укажите в `.env`:
```
LLM_CONSOLE_URL=http://IP_ESP32:PORT/api/chat
```

Ожидаемый формат API: `POST` с `{"text": "..."}` или `{"messages": [...]}`, ответ `{"reply": "..."}`.
