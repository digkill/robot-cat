package service

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"strings"

	"github.com/digkill/gc9a01_rpi/backend/internal/domain"
)

type RobotRepository interface {
	UpsertHeartbeat(ctx context.Context, robotID, status, videoMode string) error
	SetStatus(ctx context.Context, robotID, status string) error
	List(ctx context.Context) ([]domain.Robot, error)
	GetByRobotID(ctx context.Context, robotID string) (domain.Robot, error)
	CreateSession(ctx context.Context, robotID, remoteAddr, protocolVersion string, clientInfo any) (int64, error)
	CloseSession(ctx context.Context, sessionID int64) error
	AddEvent(ctx context.Context, robotID, eventType string, payload any) error
	ListEvents(ctx context.Context, robotID string, limit int) ([]domain.RobotEvent, error)
	CreateCommand(ctx context.Context, robotID, requestID, action string, payload any) (domain.RobotCommand, error)
	MarkCommandSent(ctx context.Context, requestID string) error
	CompleteCommand(ctx context.Context, requestID string, ok bool, payload any, errorText string) error
	ListCommands(ctx context.Context, robotID string, limit int) ([]domain.RobotCommand, error)
	AddRecording(ctx context.Context, robotID, recordingName, storageKey, localPath string, withAudio bool) error
}

type CommandDispatcher interface {
	Send(robotID string, command Envelope) error
}

type Envelope struct {
	Type      string         `json:"type"`
	RequestID string         `json:"request_id,omitempty"`
	Action    string         `json:"action,omitempty"`
	Payload   map[string]any `json:"payload,omitempty"`
}

type RobotService struct {
	repo       RobotRepository
	dispatcher CommandDispatcher
}

func NewRobotService(repo RobotRepository, dispatcher CommandDispatcher) *RobotService {
	return &RobotService{repo: repo, dispatcher: dispatcher}
}

func (s *RobotService) SetDispatcher(dispatcher CommandDispatcher) {
	s.dispatcher = dispatcher
}

func (s *RobotService) RegisterHello(ctx context.Context, robotID, remoteAddr string, payload map[string]any) (int64, error) {
	videoMode, _ := payload["video_mode"].(string)
	if err := s.repo.UpsertHeartbeat(ctx, robotID, "online", videoMode); err != nil {
		return 0, err
	}
	protocol, _ := payload["protocol"].(string)
	return s.repo.CreateSession(ctx, robotID, remoteAddr, protocol, payload)
}

func (s *RobotService) HandleStatus(ctx context.Context, robotID string, payload map[string]any) error {
	videoMode, _ := payload["video_mode"].(string)
	return s.repo.UpsertHeartbeat(ctx, robotID, "online", videoMode)
}

func (s *RobotService) HandleEvent(ctx context.Context, robotID, eventType string, payload map[string]any) error {
	if eventType == "camera_record_stop" {
		name, _ := payload["name"].(string)
		s3Key, _ := payload["s3_key"].(string)
		localPath, _ := payload["local_path"].(string)
		withAudio, _ := payload["with_audio"].(bool)
		if name != "" {
			if err := s.repo.AddRecording(ctx, robotID, name, s3Key, localPath, withAudio); err != nil {
				return err
			}
		}
	}
	return s.repo.AddEvent(ctx, robotID, eventType, payload)
}

func (s *RobotService) HandleCommandResult(ctx context.Context, requestID string, ok bool, payload map[string]any, errorText string) error {
	if strings.TrimSpace(requestID) == "" {
		return nil
	}
	return s.repo.CompleteCommand(ctx, requestID, ok, payload, errorText)
}

func (s *RobotService) CloseSession(ctx context.Context, sessionID int64, robotID string) error {
	if sessionID > 0 {
		if err := s.repo.CloseSession(ctx, sessionID); err != nil {
			return err
		}
	}
	if strings.TrimSpace(robotID) != "" {
		return s.repo.SetStatus(ctx, robotID, "offline")
	}
	return nil
}

func (s *RobotService) ListRobots(ctx context.Context) ([]domain.Robot, error) {
	return s.repo.List(ctx)
}

func (s *RobotService) GetRobot(ctx context.Context, robotID string) (domain.Robot, error) {
	return s.repo.GetByRobotID(ctx, robotID)
}

func (s *RobotService) ListEvents(ctx context.Context, robotID string, limit int) ([]domain.RobotEvent, error) {
	return s.repo.ListEvents(ctx, robotID, limit)
}

func (s *RobotService) ListCommands(ctx context.Context, robotID string, limit int) ([]domain.RobotCommand, error) {
	return s.repo.ListCommands(ctx, robotID, limit)
}

func (s *RobotService) CreateAndDispatchCommand(ctx context.Context, robotID, action string, payload map[string]any) (domain.RobotCommand, error) {
	if strings.TrimSpace(action) == "" {
		return domain.RobotCommand{}, errors.New("action is required")
	}
	if s.dispatcher == nil {
		return domain.RobotCommand{}, errors.New("command dispatcher is not configured")
	}
	requestID, err := generateRequestID()
	if err != nil {
		return domain.RobotCommand{}, err
	}
	command, err := s.repo.CreateCommand(ctx, robotID, requestID, action, payload)
	if err != nil {
		return domain.RobotCommand{}, err
	}
	if err := s.dispatcher.Send(robotID, Envelope{
		Type:      "command",
		RequestID: requestID,
		Action:    action,
		Payload:   payload,
	}); err != nil {
		return command, err
	}
	if err := s.repo.MarkCommandSent(ctx, requestID); err != nil {
		return command, err
	}
	command.Status = "sent"
	return command, nil
}

func generateRequestID() (string, error) {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return hex.EncodeToString(b[:]), nil
}

func MustPayload(raw string) map[string]any {
	if strings.TrimSpace(raw) == "" {
		return map[string]any{}
	}
	var out map[string]any
	if err := json.Unmarshal([]byte(raw), &out); err != nil {
		return map[string]any{"raw": raw}
	}
	return out
}
