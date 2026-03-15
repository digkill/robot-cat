package main

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"path/filepath"

	_ "github.com/go-sql-driver/mysql"
	"github.com/pressly/goose/v3"

	"github.com/digkill/gc9a01_rpi/backend/internal/config"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("load config: %v", err)
	}

	command := "status"
	if len(os.Args) > 1 {
		command = os.Args[1]
	}

	db, err := sql.Open("mysql", cfg.MySQLDSN)
	if err != nil {
		log.Fatalf("open db: %v", err)
	}
	defer db.Close()

	dir := filepath.Join(".", "migrations")
	if err := goose.SetDialect("mysql"); err != nil {
		log.Fatalf("set dialect: %v", err)
	}

	switch command {
	case "up":
		err = goose.Up(db, dir)
	case "down":
		err = goose.Down(db, dir)
	case "status":
		err = goose.Status(db, dir)
	default:
		err = fmt.Errorf("unsupported command %q", command)
	}

	if err != nil {
		log.Fatalf("goose %s: %v", command, err)
	}
}
