package mysql

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/digkill/gc9a01_rpi/backend/internal/domain"
)

type RobotRepository struct {
	db *sql.DB
}

func NewRobotRepository(db *sql.DB) *RobotRepository {
	return &RobotRepository{db: db}
}

func (r *RobotRepository) UpsertHeartbeat(ctx context.Context, robotID, status, videoMode string) error {
	const query = `
INSERT INTO robots (robot_id, name, status, video_mode, last_seen_at)
VALUES (?, ?, ?, ?, UTC_TIMESTAMP())
ON DUPLICATE KEY UPDATE
	status = VALUES(status),
	video_mode = VALUES(video_mode),
	last_seen_at = UTC_TIMESTAMP(),
	updated_at = UTC_TIMESTAMP()`
	_, err := r.db.ExecContext(ctx, query, robotID, robotID, status, videoMode)
	return err
}

func (r *RobotRepository) SetStatus(ctx context.Context, robotID, status string) error {
	_, err := r.db.ExecContext(ctx, `
UPDATE robots
SET status = ?, updated_at = UTC_TIMESTAMP()
WHERE robot_id = ?`, status, robotID)
	return err
}

func (r *RobotRepository) List(ctx context.Context) ([]domain.Robot, error) {
	rows, err := r.db.QueryContext(ctx, `
SELECT id, robot_id, name, token_hash, status, video_mode, last_seen_at, created_at, updated_at
FROM robots
ORDER BY updated_at DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var robots []domain.Robot
	for rows.Next() {
		var robot domain.Robot
		if err := rows.Scan(
			&robot.ID,
			&robot.RobotID,
			&robot.Name,
			&robot.TokenHash,
			&robot.Status,
			&robot.VideoMode,
			&robot.LastSeenAt,
			&robot.CreatedAt,
			&robot.UpdatedAt,
		); err != nil {
			return nil, err
		}
		robots = append(robots, robot)
	}
	return robots, rows.Err()
}

func (r *RobotRepository) GetByRobotID(ctx context.Context, robotID string) (domain.Robot, error) {
	var robot domain.Robot
	err := r.db.QueryRowContext(ctx, `
SELECT id, robot_id, name, token_hash, status, video_mode, last_seen_at, created_at, updated_at
FROM robots WHERE robot_id = ?`, robotID).Scan(
		&robot.ID,
		&robot.RobotID,
		&robot.Name,
		&robot.TokenHash,
		&robot.Status,
		&robot.VideoMode,
		&robot.LastSeenAt,
		&robot.CreatedAt,
		&robot.UpdatedAt,
	)
	return robot, err
}

func (r *RobotRepository) CreateSession(ctx context.Context, robotID, remoteAddr, protocolVersion string, clientInfo any) (int64, error) {
	payload, err := json.Marshal(clientInfo)
	if err != nil {
		return 0, err
	}
	res, err := r.db.ExecContext(ctx, `
INSERT INTO robot_sessions (robot_id, connected_at, remote_addr, protocol_version, client_info_json)
VALUES (?, UTC_TIMESTAMP(), ?, ?, ?)`, robotID, remoteAddr, protocolVersion, string(payload))
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

func (r *RobotRepository) CloseSession(ctx context.Context, sessionID int64) error {
	_, err := r.db.ExecContext(ctx, `
UPDATE robot_sessions
SET disconnected_at = UTC_TIMESTAMP()
WHERE id = ? AND disconnected_at IS NULL`, sessionID)
	return err
}

func (r *RobotRepository) AddEvent(ctx context.Context, robotID, eventType string, payload any) error {
	raw, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	_, err = r.db.ExecContext(ctx, `
INSERT INTO robot_events (robot_id, event_type, payload_json, created_at)
VALUES (?, ?, ?, UTC_TIMESTAMP())`, robotID, eventType, string(raw))
	return err
}

func (r *RobotRepository) ListEvents(ctx context.Context, robotID string, limit int) ([]domain.RobotEvent, error) {
	if limit <= 0 || limit > 500 {
		limit = 100
	}
	query := fmt.Sprintf(`
SELECT id, robot_id, event_type, payload_json, created_at
FROM robot_events
WHERE robot_id = ?
ORDER BY created_at DESC
LIMIT %d`, limit)
	rows, err := r.db.QueryContext(ctx, query, robotID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var events []domain.RobotEvent
	for rows.Next() {
		var event domain.RobotEvent
		if err := rows.Scan(&event.ID, &event.RobotID, &event.EventType, &event.PayloadJSON, &event.CreatedAt); err != nil {
			return nil, err
		}
		events = append(events, event)
	}
	return events, rows.Err()
}

func (r *RobotRepository) CreateCommand(ctx context.Context, robotID, requestID, action string, payload any) (domain.RobotCommand, error) {
	raw, err := json.Marshal(payload)
	if err != nil {
		return domain.RobotCommand{}, err
	}

	now := time.Now().UTC()
	res, err := r.db.ExecContext(ctx, `
INSERT INTO robot_commands (robot_id, request_id, action, payload_json, status, created_at)
VALUES (?, ?, ?, ?, 'queued', UTC_TIMESTAMP())`, robotID, requestID, action, string(raw))
	if err != nil {
		return domain.RobotCommand{}, err
	}
	id, _ := res.LastInsertId()
	return domain.RobotCommand{
		ID:          id,
		RobotID:     robotID,
		RequestID:   requestID,
		Action:      action,
		PayloadJSON: string(raw),
		Status:      "queued",
		CreatedAt:   now,
	}, nil
}

func (r *RobotRepository) MarkCommandSent(ctx context.Context, requestID string) error {
	_, err := r.db.ExecContext(ctx, `
UPDATE robot_commands
SET status = 'sent'
WHERE request_id = ?`, requestID)
	return err
}

func (r *RobotRepository) CompleteCommand(ctx context.Context, requestID string, ok bool, payload any, errorText string) error {
	status := "completed"
	if !ok {
		status = "failed"
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	_, err = r.db.ExecContext(ctx, `
UPDATE robot_commands
SET status = ?, error_text = ?, payload_json = ?, completed_at = UTC_TIMESTAMP()
WHERE request_id = ?`, status, errorText, string(raw), requestID)
	return err
}

func (r *RobotRepository) ListCommands(ctx context.Context, robotID string, limit int) ([]domain.RobotCommand, error) {
	if limit <= 0 || limit > 500 {
		limit = 100
	}
	query := fmt.Sprintf(`
SELECT id, robot_id, request_id, action, payload_json, status, error_text, created_at, completed_at
FROM robot_commands
WHERE robot_id = ?
ORDER BY created_at DESC
LIMIT %d`, limit)
	rows, err := r.db.QueryContext(ctx, query, robotID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var commands []domain.RobotCommand
	for rows.Next() {
		var command domain.RobotCommand
		if err := rows.Scan(
			&command.ID,
			&command.RobotID,
			&command.RequestID,
			&command.Action,
			&command.PayloadJSON,
			&command.Status,
			&command.ErrorText,
			&command.CreatedAt,
			&command.CompletedAt,
		); err != nil {
			return nil, err
		}
		commands = append(commands, command)
	}
	return commands, rows.Err()
}

func (r *RobotRepository) AddRecording(ctx context.Context, robotID, recordingName, storageKey, localPath string, withAudio bool) error {
	_, err := r.db.ExecContext(ctx, `
INSERT INTO robot_recordings (robot_id, recording_name, storage_key, local_path, with_audio, created_at)
VALUES (?, ?, ?, ?, ?, UTC_TIMESTAMP())`, robotID, recordingName, storageKey, localPath, withAudio)
	return err
}
