package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strings"
)

type rabbitPublisher struct {
	baseURL  string
	username string
	password string
	queue    string
	client   *http.Client
}

func (p rabbitPublisher) declareQueue(ctx context.Context) error {
	return p.request(ctx, http.MethodPut, "/api/queues/%2F/"+url.PathEscape(p.queue), map[string]any{
		"durable": true,
		"arguments": map[string]int{
			"x-message-ttl": 600000,
			"x-max-length":  1000,
		},
	}, nil)
}

func (p rabbitPublisher) Publish(ctx context.Context, event lookupEvent) error {
	payload, err := json.Marshal(event)
	if err != nil {
		return err
	}
	var result struct {
		Routed bool `json:"routed"`
	}
	err = p.request(ctx, http.MethodPost, "/api/exchanges/%2F/amq.default/publish", map[string]any{
		"properties": map[string]string{
			"content_type": "application/json",
		},
		"routing_key":      p.queue,
		"payload":          string(payload),
		"payload_encoding": "string",
	}, &result)
	if err != nil {
		return err
	}
	if !result.Routed {
		return errors.New("rabbitmq did not route the lookup event")
	}
	return nil
}

func (p rabbitPublisher) request(ctx context.Context, method, path string, payload any, result any) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	req, err := http.NewRequestWithContext(ctx, method, strings.TrimRight(p.baseURL, "/")+path, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.SetBasicAuth(p.username, p.password)
	req.Header.Set("Content-Type", "application/json")

	res, err := p.client.Do(req)
	if err != nil {
		return err
	}
	defer res.Body.Close()

	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return fmt.Errorf("rabbitmq %s %s: %s", method, path, res.Status)
	}
	if result != nil {
		return json.NewDecoder(res.Body).Decode(result)
	}
	return nil
}
