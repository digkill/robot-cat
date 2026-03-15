-- +goose Up
CREATE TABLE IF NOT EXISTS robots (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    robot_id VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    token_hash VARCHAR(255) NOT NULL DEFAULT '',
    status VARCHAR(64) NOT NULL DEFAULT 'offline',
    video_mode VARCHAR(64) NOT NULL DEFAULT 'webrtc',
    last_seen_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_robots_robot_id (robot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS robot_sessions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    robot_id VARCHAR(128) NOT NULL,
    connected_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    disconnected_at DATETIME(6) NULL,
    remote_addr VARCHAR(255) NOT NULL DEFAULT '',
    protocol_version VARCHAR(64) NOT NULL DEFAULT '',
    client_info_json JSON NOT NULL,
    KEY idx_robot_sessions_robot_id_connected_at (robot_id, connected_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS robot_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    robot_id VARCHAR(128) NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    payload_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_robot_events_robot_id_created_at (robot_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS robot_commands (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    robot_id VARCHAR(128) NOT NULL,
    request_id VARCHAR(64) NOT NULL,
    action VARCHAR(128) NOT NULL,
    payload_json JSON NOT NULL,
    status VARCHAR(64) NOT NULL DEFAULT 'queued',
    error_text TEXT NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    completed_at DATETIME(6) NULL,
    UNIQUE KEY uq_robot_commands_request_id (request_id),
    KEY idx_robot_commands_robot_id_created_at (robot_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS robot_recordings (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    robot_id VARCHAR(128) NOT NULL,
    recording_name VARCHAR(255) NOT NULL,
    storage_key VARCHAR(512) NOT NULL DEFAULT '',
    local_path VARCHAR(512) NOT NULL DEFAULT '',
    with_audio TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_robot_recordings_robot_id_created_at (robot_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS robot_snapshots (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    robot_id VARCHAR(128) NOT NULL,
    snapshot_name VARCHAR(255) NOT NULL,
    storage_key VARCHAR(512) NOT NULL DEFAULT '',
    local_path VARCHAR(512) NOT NULL DEFAULT '',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_robot_snapshots_robot_id_created_at (robot_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS robot_media_assets (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    robot_id VARCHAR(128) NOT NULL,
    media_name VARCHAR(255) NOT NULL,
    media_type VARCHAR(64) NOT NULL,
    storage_key VARCHAR(512) NOT NULL DEFAULT '',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_robot_media_assets_robot_id_created_at (robot_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- +goose Down
DROP TABLE IF EXISTS robot_media_assets;
DROP TABLE IF EXISTS robot_snapshots;
DROP TABLE IF EXISTS robot_recordings;
DROP TABLE IF EXISTS robot_commands;
DROP TABLE IF EXISTS robot_events;
DROP TABLE IF EXISTS robot_sessions;
DROP TABLE IF EXISTS robots;
