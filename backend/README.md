# Robot Backend

Production-grade Go backend for robot control:

- Go `1.26.1` toolchain
- MySQL
- goose SQL migrations
- WebSocket control plane for robots
- HTTP API for operators/backoffice

## Quick start

1. Copy env:

```bash
cp .env.example .env
```

2. Configure MySQL DSN in `.env`

3. Run migrations:

```bash
make migrate-up
```

4. Start server:

```bash
make run
```

## Main endpoints

- `GET /healthz`
- `GET /api/v1/robots`
- `GET /api/v1/robots/{robotID}`
- `GET /api/v1/robots/{robotID}/events`
- `GET /api/v1/robots/{robotID}/commands`
- `POST /api/v1/robots/{robotID}/commands`
- `GET /ws/robot`

## WebSocket auth

Robot should connect with:

- `Authorization: Bearer <token>`
- `X-Robot-Id: <robot_id>`

The first successful `hello` frame persists robot metadata and marks robot online.
