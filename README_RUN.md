# Запуск робота

## Запуск

Обычный запуск:

```bash
./run_robot.sh
```

Или вручную:
```bash
python3 robot_main.py
```

## Автозапуск после перезагрузки

На самой Raspberry Pi можно установить `systemd`-сервис:

```bash
./scripts/install_robot_service.sh
```

После этого робот будет подниматься автоматически при загрузке системы, даже если терминал закрыт.

Полезные команды:

```bash
sudo systemctl status robot-bot.service
journalctl -u robot-bot.service -f
```

Сервис запускается от обычного пользователя. Если на конкретной Raspberry Pi не хватает прав на GPIO/SPI, это лучше решать через группы/udev, а не запуском всего робота под `sudo`, чтобы не ломать звук.

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

- **Ошибка -5 (Permission denied)** — на этой системе не хватает прав к железу. Лучше выдать права пользователю, а не запускать весь процесс под `sudo`, иначе может пропасть звук.

## Локаль

```bash
sudo locale-gen en_US.UTF-8
sudo update-locale
```

## Venv

Скрипт ищет Python в:
- `./.venv/bin/python3`
- `~/Projects/Mini/.venv/bin/python3`
