package domain

import "time"

type Robot struct {
	ID         int64     `json:"id"`
	RobotID    string    `json:"robot_id"`
	Name       string    `json:"name"`
	TokenHash  string    `json:"-"`
	Status     string    `json:"status"`
	VideoMode  string    `json:"video_mode"`
	LastSeenAt time.Time `json:"last_seen_at"`
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

type RobotSession struct {
	ID              int64      `json:"id"`
	RobotID         string     `json:"robot_id"`
	ConnectedAt     time.Time  `json:"connected_at"`
	DisconnectedAt  *time.Time `json:"disconnected_at,omitempty"`
	RemoteAddr      string     `json:"remote_addr"`
	ProtocolVersion string     `json:"protocol_version"`
	ClientInfoJSON  string     `json:"client_info_json"`
}

type RobotEvent struct {
	ID          int64     `json:"id"`
	RobotID     string    `json:"robot_id"`
	EventType   string    `json:"event_type"`
	PayloadJSON string    `json:"payload_json"`
	CreatedAt   time.Time `json:"created_at"`
}

type RobotCommand struct {
	ID          int64      `json:"id"`
	RobotID     string     `json:"robot_id"`
	RequestID   string     `json:"request_id"`
	Action      string     `json:"action"`
	PayloadJSON string     `json:"payload_json"`
	Status      string     `json:"status"`
	ErrorText   string     `json:"error_text"`
	CreatedAt   time.Time  `json:"created_at"`
	CompletedAt *time.Time `json:"completed_at,omitempty"`
}

type RobotRecording struct {
	ID            int64     `json:"id"`
	RobotID       string    `json:"robot_id"`
	RecordingName string    `json:"recording_name"`
	StorageKey    string    `json:"storage_key"`
	LocalPath     string    `json:"local_path"`
	WithAudio     bool      `json:"with_audio"`
	CreatedAt     time.Time `json:"created_at"`
}
