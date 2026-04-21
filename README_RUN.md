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

Или через готовые скрипты:

```bash
./scripts/status_robot_service.sh
./scripts/restart_robot_service.sh
./scripts/stop_robot_service.sh
./scripts/logs_robot_service.sh
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

## Веб-интерфейс и камера с другой сети / из интернета

Страница и поток `/camera/stream` используют **относительные** пути — с браузера открывайте сам робот по его адресу.

1. В `.env`: **`WEB_HOST=0.0.0.0`** (уже по умолчанию), **`WEB_PORT=5000`** или другой свободный порт.
2. **Локальная сеть**: с телефона/ПК в том же Wi‑Fi откройте `http://<IP-Raspberry>:5000` (IP в логе при старте или `hostname -I`).
3. **Интернет**: на роутере сделайте **проброс порта** (NAT) с внешнего порта на `IP_малины:WEB_PORT`. Нужен «белый» IP или DDNS. Учтите, что HTTP без TLS — слабая защита; для постоянного доступа лучше VPN или туннель (Tailscale, WireGuard, Cloudflare Tunnel).
4. Если включён **ufw**: `sudo ufw allow 5000/tcp` (или ваш `WEB_PORT`) и `sudo ufw reload`.

При **`WEB_HOST=127.0.0.1`** сервер доступен только с самой Pi — удалённо к камере подключиться не получится.

## Venv

Скрипт ищет Python в:
- `./.venv/bin/python3`
- `~/Projects/Mini/.venv/bin/python3`
