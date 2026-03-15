package config

import (
	"bufio"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type Config struct {
	AppEnv          string
	HTTPAddr        string
	MySQLDSN        string
	ReadTimeout     time.Duration
	WriteTimeout    time.Duration
	IdleTimeout     time.Duration
	ShutdownTimeout time.Duration
}

func Load() (Config, error) {
	loadDotEnv(".env")

	cfg := Config{
		AppEnv:          getenv("APP_ENV", "development"),
		HTTPAddr:        getenv("HTTP_ADDR", ":8080"),
		MySQLDSN:        os.Getenv("MYSQL_DSN"),
		ReadTimeout:     mustDuration(getenv("READ_TIMEOUT", "10s")),
		WriteTimeout:    mustDuration(getenv("WRITE_TIMEOUT", "20s")),
		IdleTimeout:     mustDuration(getenv("IDLE_TIMEOUT", "60s")),
		ShutdownTimeout: mustDuration(getenv("SHUTDOWN_TIMEOUT", "10s")),
	}

	if cfg.MySQLDSN == "" {
		return Config{}, errors.New("MYSQL_DSN is required")
	}

	return cfg, nil
}

func loadDotEnv(path string) {
	file, err := os.Open(filepath.Clean(path))
	if err != nil {
		return
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, value, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		key = strings.TrimSpace(key)
		value = strings.Trim(strings.TrimSpace(value), `"'`)
		if key == "" {
			continue
		}
		if _, exists := os.LookupEnv(key); !exists {
			_ = os.Setenv(key, value)
		}
	}
}

func getenv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func mustDuration(value string) time.Duration {
	d, err := time.ParseDuration(value)
	if err != nil {
		panic(err)
	}
	return d
}
