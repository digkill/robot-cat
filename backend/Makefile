APP_NAME=robot-backend

.PHONY: run build migrate-up migrate-down migrate-status fmt

run:
	go run ./cmd/server

build:
	go build -o bin/$(APP_NAME) ./cmd/server

migrate-up:
	go run ./cmd/migrate up

migrate-down:
	go run ./cmd/migrate down

migrate-status:
	go run ./cmd/migrate status

fmt:
	gofmt -w ./cmd ./internal
