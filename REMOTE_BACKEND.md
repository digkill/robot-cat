# Remote Backend Protocol

Python process on the robot acts as a hardware agent and keeps an outbound WebSocket connection to your Go backend.

## Persistence

Use MySQL as the primary database for the Go backend.

## Transport

- Control plane: WebSocket
- Recommended video plane: WebRTC
- Fallback video plane during migration: local MJPEG/recording endpoints already present in Flask

## Why this split

- WebSocket is good for commands, status, events, auth, reconnects
- WebRTC is the correct browser-facing live video transport for production
- RTSP is fine for backend ingest, but not as the main browser transport
- MySQL is good for persistent robot registry, command history, sessions, recordings metadata and audit events

## Recommended MySQL tables

1. `robots`
Fields:
`id`, `robot_id`, `name`, `token_hash`, `status`, `last_seen_at`, `video_mode`, `created_at`, `updated_at`

2. `robot_sessions`
Fields:
`id`, `robot_id`, `connected_at`, `disconnected_at`, `remote_addr`, `protocol_version`, `client_info_json`

3. `robot_events`
Fields:
`id`, `robot_id`, `event_type`, `payload_json`, `created_at`

4. `robot_commands`
Fields:
`id`, `robot_id`, `request_id`, `action`, `payload_json`, `status`, `error_text`, `created_at`, `completed_at`

5. `robot_recordings`
Fields:
`id`, `robot_id`, `recording_name`, `storage_key`, `local_path`, `with_audio`, `created_at`

6. `robot_snapshots`
Fields:
`id`, `robot_id`, `snapshot_name`, `storage_key`, `local_path`, `created_at`

7. `robot_media_assets`
Fields:
`id`, `robot_id`, `media_name`, `media_type`, `storage_key`, `created_at`

## Indexes

- `robots.robot_id` unique
- `robot_commands.request_id` unique
- `robot_events (robot_id, created_at)`
- `robot_commands (robot_id, created_at)`
- `robot_recordings (robot_id, created_at)`

## Config

Use `.env`:

```env
REMOTE_BRIDGE_ENABLED=true
REMOTE_BRIDGE_URL=wss://your-go-backend/ws/robot
REMOTE_BRIDGE_TOKEN=secret
REMOTE_ROBOT_ID=robot-cat-01
REMOTE_PING_INTERVAL=15
REMOTE_STATUS_INTERVAL=5
REMOTE_VIDEO_MODE=webrtc
```

MySQL on the Go backend side should be configured separately there, for example:

```env
MYSQL_DSN=user:password@tcp(127.0.0.1:3306)/robot_prod?parseTime=true&charset=utf8mb4
```

## Agent messages

### hello

Sent right after connect.

```json
{
  "type": "hello",
  "robot_id": "robot-cat-01",
  "payload": {
    "protocol": "robot-bridge.v1",
    "video_mode": "webrtc",
    "capabilities": ["speak", "face_control", "audio_control", "camera_recording", "snapshots", "web_local"]
  }
}
```

### status

Periodic runtime snapshot.

### event

Async event from robot side.

### command

Backend -> robot:

```json
{
  "type": "command",
  "request_id": "uuid",
  "action": "set_face",
  "payload": {
    "emotion": "радостный",
    "theme": "ocean",
    "animation_mode": "idle"
  }
}
```

### command_result

Robot -> backend:

```json
{
  "type": "command_result",
  "request_id": "uuid",
  "ok": true,
  "payload": {}
}
```

## Implemented actions

- `get_status`
- `set_face`
- `set_volume`
- `set_mute`
- `speak`
- `camera_record_start`
- `camera_record_stop`

## Production note

For live video наружу делайте signaling/media на Go backend и держите Python только как hardware agent.
The current Python side is prepared for this control model, but Go-side signaling for WebRTC still needs implementation.
MySQL should be the source of truth for robots, commands, sessions and media metadata.
