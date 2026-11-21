package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"
	"time"
)

type redisCache struct {
	host   string
	port   string
	prefix string
}

func (c redisCache) Get(ctx context.Context, uid string) (string, bool, error) {
	out, err := c.command(ctx, "GET", c.prefix+uid)
	if err != nil {
		return "", false, err
	}
	var value *string
	if err := json.Unmarshal(out, &value); err != nil {
		return "", false, fmt.Errorf("decode redis reply: %w", err)
	}
	if value == nil {
		return "", false, nil
	}
	return *value, true, nil
}

func (c redisCache) Set(ctx context.Context, uid, value string) error {
	_, err := c.command(ctx, "SET", c.prefix+uid, value, "EX", "60")
	return err
}

func (c redisCache) command(ctx context.Context, args ...string) ([]byte, error) {
	ctx, cancel := context.WithTimeout(ctx, 500*time.Millisecond)
	defer cancel()

	options := []string{
		"-h", c.host,
		"-p", c.port,
		"-e",
		"--json",
	}
	out, err := exec.CommandContext(ctx, "redis-cli", append(options, args...)...).CombinedOutput()
	if err != nil {
		return nil, fmt.Errorf("redis %s: %w (%s)", args[0], err, strings.TrimSpace(string(out)))
	}
	return out, nil
}
