# Запуск робота

## Запуск с sudo (рекомендуется)

Для LED (WS2812), дисплея, камеры и GPIO нужны права root:

```bash
sudo ./run_robot.sh
```

Или вручную:
```bash
sudo $(which python3) robot_main.py
```

## LED

- **S V G (WS2812)** — нужен `sudo`. Ошибка -11: GPIO 12/18 не подходит — попробуйте в `.env`:
  ```
  PIN_LED_DATA=18
  ```
  или
  ```
  LED_TYPE=rgb
  ```
  (RGB = 3 пина R,G,B на 17, 27, 22)

- **Ошибка -5 (Permission denied)** — запускайте с `sudo`.

## Локаль

```bash
sudo locale-gen en_US.UTF-8
sudo update-locale
```

## Venv

Скрипт ищет Python в:
- `./.venv/bin/python3`
- `~/Projects/Mini/.venv/bin/python3`
