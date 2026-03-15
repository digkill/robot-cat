package ws

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"sync"

	"github.com/gorilla/websocket"

	"github.com/digkill/gc9a01_rpi/backend/internal/service"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

type Client struct {
	robotID   string
	conn      *websocket.Conn
	sessionID int64
	writeMu   sync.Mutex
}

type Hub struct {
	mu      sync.RWMutex
	clients map[string]*Client
	service *service.RobotService
}

func NewHub(svc *service.RobotService) *Hub {
	return &Hub{
		clients: make(map[string]*Client),
		service: svc,
	}
}

func (h *Hub) Send(robotID string, envelope service.Envelope) error {
	h.mu.RLock()
	client := h.clients[robotID]
	h.mu.RUnlock()
	if client == nil {
		return errors.New("robot is offline")
	}
	client.writeMu.Lock()
	defer client.writeMu.Unlock()
	return client.conn.WriteJSON(envelope)
}

func (h *Hub) HandleRobotWS(w http.ResponseWriter, r *http.Request) {
	robotID := r.Header.Get("X-Robot-Id")
	if robotID == "" {
		http.Error(w, "missing X-Robot-Id", http.StatusUnauthorized)
		return
	}

	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		http.Error(w, "upgrade failed", http.StatusBadRequest)
		return
	}

	client := &Client{robotID: robotID, conn: conn}
	h.mu.Lock()
	h.clients[robotID] = client
	h.mu.Unlock()

	defer func() {
		h.mu.Lock()
		delete(h.clients, robotID)
		h.mu.Unlock()
		_ = h.service.CloseSession(context.Background(), client.sessionID, robotID)
		_ = conn.Close()
	}()

	for {
		var payload map[string]any
		if err := conn.ReadJSON(&payload); err != nil {
			return
		}
		if err := h.handleIncoming(r.Context(), r.RemoteAddr, client, payload); err != nil {
			client.writeMu.Lock()
			_ = conn.WriteJSON(map[string]any{"type": "error", "error": err.Error()})
			client.writeMu.Unlock()
		}
	}
}

func (h *Hub) handleIncoming(ctx context.Context, remoteAddr string, client *Client, message map[string]any) error {
	msgType, _ := message["type"].(string)
	switch msgType {
	case "hello":
		payload := asMap(message["payload"])
		sessionID, err := h.service.RegisterHello(ctx, client.robotID, remoteAddr, payload)
		if err != nil {
			return err
		}
		client.sessionID = sessionID
		client.writeMu.Lock()
		defer client.writeMu.Unlock()
		return client.conn.WriteJSON(map[string]any{"type": "hello_ack"})
	case "status":
		return h.service.HandleStatus(ctx, client.robotID, asMap(message["payload"]))
	case "event":
		eventType, _ := message["event"].(string)
		return h.service.HandleEvent(ctx, client.robotID, eventType, asMap(message["payload"]))
	case "command_result":
		requestID, _ := message["request_id"].(string)
		ok, _ := message["ok"].(bool)
		errorText, _ := message["error"].(string)
		return h.service.HandleCommandResult(ctx, requestID, ok, asMap(message["payload"]), errorText)
	case "ping":
		client.writeMu.Lock()
		defer client.writeMu.Unlock()
		return client.conn.WriteJSON(map[string]any{"type": "pong"})
	default:
		raw, _ := json.Marshal(message)
		return h.service.HandleEvent(ctx, client.robotID, "unhandled_message", map[string]any{"raw": string(raw)})
	}
}

func asMap(value any) map[string]any {
	if value == nil {
		return map[string]any{}
	}
	if typed, ok := value.(map[string]any); ok {
		return typed
	}
	return map[string]any{}
}
