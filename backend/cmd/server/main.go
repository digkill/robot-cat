package main

import (
	"context"
	"log"
	"os/signal"
	"syscall"

	"github.com/digkill/gc9a01_rpi/backend/internal/app"
	"github.com/digkill/gc9a01_rpi/backend/internal/config"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("load config: %v", err)
	}

	application, err := app.New(cfg)
	if err != nil {
		log.Fatalf("init app: %v", err)
	}
	defer application.Close()

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	if err := application.Run(ctx); err != nil {
		log.Fatalf("run app: %v", err)
	}
}
