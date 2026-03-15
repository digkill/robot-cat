package httpserver

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"

	"github.com/digkill/gc9a01_rpi/backend/internal/config"
	"github.com/digkill/gc9a01_rpi/backend/internal/service"
	"github.com/digkill/gc9a01_rpi/backend/internal/ws"
)

type Server struct {
	httpServer *http.Server
}

func New(cfg config.Config, svc *service.RobotService, hub *ws.Hub) *Server {
	router := chi.NewRouter()
	router.Use(middleware.RequestID, middleware.RealIP, middleware.Recoverer, middleware.Timeout(30*time.Second))

	router.Get("/healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})

	router.Get("/ws/robot", hub.HandleRobotWS)

	router.Route("/api/v1", func(r chi.Router) {
		r.Get("/robots", func(w http.ResponseWriter, r *http.Request) {
			robots, err := svc.ListRobots(r.Context())
			if err != nil {
				writeError(w, http.StatusInternalServerError, err)
				return
			}
			writeJSON(w, http.StatusOK, robots)
		})

		r.Get("/robots/{robotID}", func(w http.ResponseWriter, r *http.Request) {
			robot, err := svc.GetRobot(r.Context(), chi.URLParam(r, "robotID"))
			if err != nil {
				writeError(w, http.StatusNotFound, err)
				return
			}
			writeJSON(w, http.StatusOK, robot)
		})

		r.Get("/robots/{robotID}/events", func(w http.ResponseWriter, r *http.Request) {
			limit := parseLimit(r.URL.Query().Get("limit"))
			events, err := svc.ListEvents(r.Context(), chi.URLParam(r, "robotID"), limit)
			if err != nil {
				writeError(w, http.StatusInternalServerError, err)
				return
			}
			writeJSON(w, http.StatusOK, events)
		})

		r.Get("/robots/{robotID}/commands", func(w http.ResponseWriter, r *http.Request) {
			limit := parseLimit(r.URL.Query().Get("limit"))
			commands, err := svc.ListCommands(r.Context(), chi.URLParam(r, "robotID"), limit)
			if err != nil {
				writeError(w, http.StatusInternalServerError, err)
				return
			}
			writeJSON(w, http.StatusOK, commands)
		})

		r.Post("/robots/{robotID}/commands", func(w http.ResponseWriter, r *http.Request) {
			var req struct {
				Action  string         `json:"action"`
				Payload map[string]any `json:"payload"`
			}
			if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
				writeError(w, http.StatusBadRequest, err)
				return
			}
			command, err := svc.CreateAndDispatchCommand(r.Context(), chi.URLParam(r, "robotID"), req.Action, req.Payload)
			if err != nil {
				writeError(w, http.StatusBadRequest, err)
				return
			}
			writeJSON(w, http.StatusCreated, command)
		})
	})

	return &Server{
		httpServer: &http.Server{
			Addr:         cfg.HTTPAddr,
			Handler:      router,
			ReadTimeout:  cfg.ReadTimeout,
			WriteTimeout: cfg.WriteTimeout,
			IdleTimeout:  cfg.IdleTimeout,
		},
	}
}

func (s *Server) ListenAndServe() error {
	return s.httpServer.ListenAndServe()
}

func (s *Server) Shutdown(ctx context.Context) error {
	return s.httpServer.Shutdown(ctx)
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeError(w http.ResponseWriter, status int, err error) {
	writeJSON(w, status, map[string]string{"error": err.Error()})
}

func parseLimit(value string) int {
	if value == "" {
		return 100
	}
	limit, err := strconv.Atoi(value)
	if err != nil {
		return 100
	}
	return limit
}
