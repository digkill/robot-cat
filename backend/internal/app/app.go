package app

import (
	"context"
	"database/sql"
	"errors"
	"log"
	"net/http"

	"github.com/digkill/gc9a01_rpi/backend/internal/config"
	"github.com/digkill/gc9a01_rpi/backend/internal/db"
	"github.com/digkill/gc9a01_rpi/backend/internal/httpserver"
	repo "github.com/digkill/gc9a01_rpi/backend/internal/repository/mysql"
	"github.com/digkill/gc9a01_rpi/backend/internal/service"
	"github.com/digkill/gc9a01_rpi/backend/internal/ws"
)

type App struct {
	cfg    config.Config
	db     *sql.DB
	server *httpserver.Server
}

func New(cfg config.Config) (*App, error) {
	mysqlDB, err := db.OpenMySQL(cfg.MySQLDSN)
	if err != nil {
		return nil, err
	}

	robotRepo := repo.NewRobotRepository(mysqlDB)
	robotService := service.NewRobotService(robotRepo, nil)
	hub := ws.NewHub(robotService)
	robotService.SetDispatcher(hub)
	server := httpserver.New(cfg, robotService, hub)

	return &App{
		cfg:    cfg,
		db:     mysqlDB,
		server: server,
	}, nil
}

func (a *App) Run(ctx context.Context) error {
	errCh := make(chan error, 1)
	go func() {
		log.Printf("http server listening on %s", a.cfg.HTTPAddr)
		if err := a.server.ListenAndServe(); err != nil {
			errCh <- err
		}
	}()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), a.cfg.ShutdownTimeout)
		defer cancel()
		return a.server.Shutdown(shutdownCtx)
	case err := <-errCh:
		if errors.Is(err, context.Canceled) || errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	}
}

func (a *App) Close() {
	if a.db != nil {
		_ = a.db.Close()
	}
}
