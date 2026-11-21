package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"time"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	if err := run(logger); err != nil {
		logger.Error("server stopped", "err", err)
		os.Exit(1)
	}
}

func run(logger *slog.Logger) error {
	rabbit := rabbitPublisher{
		baseURL:  env("RABBITMQ_HTTP_URL", "http://127.0.0.1:15672"),
		username: env("RABBITMQ_USER", "guest"),
		password: env("RABBITMQ_PASSWORD", "guest"),
		queue:    env("ENTITY_QUEUE", "cs.entity.lookups"),
		client:   &http.Client{Timeout: 2 * time.Second},
	}
	if err := rabbit.declareQueue(context.Background()); err != nil {
		return fmt.Errorf("declare demo queue: %w", err)
	}

	cache := redisCache{
		host:   env("REDIS_HOST", "127.0.0.1"),
		port:   env("REDIS_PORT", "6379"),
		prefix: env("ENTITY_CACHE_PREFIX", "cs:entity:"),
	}

	server := &http.Server{
		Addr:              env("ENTITY_ADDR", "127.0.0.1:8080"),
		Handler:           newHandler(logger, postgresStore{}, cache, rabbit),
		ReadHeaderTimeout: 5 * time.Second,
	}

	logger.Info("server listening", "addr", server.Addr, "queue", rabbit.queue)

	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
