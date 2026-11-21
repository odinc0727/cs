package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

type testBackends struct {
	value  string
	err    error
	reads  int
	events []lookupEvent
}

func (b *testBackends) Find(context.Context, string) (string, error) {
	b.reads++
	return "hello", b.err
}

func (b *testBackends) Get(context.Context, string) (string, bool, error) {
	return b.value, b.value != "", nil
}

func (b *testBackends) Set(_ context.Context, _, value string) error {
	b.value = value
	return nil
}

func (b *testBackends) Publish(_ context.Context, event lookupEvent) error {
	b.events = append(b.events, event)
	return nil
}

func TestLookup(t *testing.T) {
	var log bytes.Buffer
	backends := new(testBackends)
	handler := newHandler(slog.New(slog.NewJSONHandler(&log, nil)), backends, backends, backends)
	const incomingTrace = "4bf92f3577b34da6a3ce929d0e0e4736"

	request := func(token string, status int) string {
		t.Helper()
		log.Reset()
		req := httptest.NewRequest(http.MethodGet, "/items/"+demoUID, nil)
		req.Header.Set("Authorization", "Bearer "+token)
		req.Header.Set("traceparent", "00-"+incomingTrace+"-00f067aa0ba902b7-01")
		res := httptest.NewRecorder()
		handler.ServeHTTP(res, req)
		if res.Code != status || res.Header().Get("X-Trace-ID") != incomingTrace {
			t.Fatalf("response %d, headers %v, body %s", res.Code, res.Header(), res.Body)
		}
		id := res.Header().Get("X-Request-ID")
		if id == "" {
			t.Fatal("missing request ID")
		}
		for line := range strings.Lines(log.String()) {
			var entry struct {
				RequestID string `json:"request_id"`
				TraceID   string `json:"trace_id"`
			}
			if err := json.Unmarshal([]byte(line), &entry); err != nil || entry.RequestID != id || entry.TraceID != incomingTrace {
				t.Fatalf("log correlation failed: %s", line)
			}
		}
		return id
	}

	request("bad", http.StatusUnauthorized)
	request("demo-viewer", http.StatusForbidden)
	if backends.reads != 0 || len(backends.events) != 0 {
		t.Fatal("rejected requests reached the business layer")
	}

	firstID := request("demo-reader", http.StatusOK)
	if !strings.Contains(log.String(), "postgres.select") || !strings.Contains(log.String(), "redis.set") {
		t.Fatalf("cold lookup steps missing: %s", log.String())
	}
	secondID := request("demo-reader", http.StatusOK)
	if firstID == secondID || backends.reads != 1 || len(backends.events) != 2 ||
		backends.events[1].RequestID != secondID || backends.events[1].TraceID != incomingTrace ||
		strings.Contains(log.String(), "postgres.select") {
		t.Fatalf("unexpected cache-hit behavior: %+v, logs: %s", backends, log.String())
	}

	backends.value = ""
	backends.err = errors.New("test database unavailable")
	request("demo-reader", http.StatusInternalServerError)
	if !strings.Contains(log.String(), "\"level\":\"ERROR\"") ||
		!strings.Contains(log.String(), "test database unavailable") ||
		!strings.Contains(log.String(), "\"status\":500") || len(backends.events) != 2 {
		t.Fatalf("unexpected failure logs: %s", log.String())
	}
}

func TestRateLimit(t *testing.T) {
	var log bytes.Buffer
	backends := new(testBackends)
	handler := newHandler(slog.New(slog.NewJSONHandler(&log, nil)), backends, backends, backends)
	for i := range userLimit + 1 {
		req := httptest.NewRequest(http.MethodGet, "/items/"+demoUID, nil)
		req.Header.Set("Authorization", "Bearer demo-reader")
		res := httptest.NewRecorder()
		handler.ServeHTTP(res, req)
		want := http.StatusOK
		if i == userLimit {
			want = http.StatusTooManyRequests
		}
		if res.Code != want {
			t.Fatalf("request %d got %d, want %d", i+1, res.Code, want)
		}
	}
	if len(backends.events) != userLimit {
		t.Fatalf("published %d events", len(backends.events))
	}
}
