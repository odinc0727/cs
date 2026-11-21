package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"log/slog"
	"net/http"
	"strings"
	"sync"
	"time"
)

type (
	observationKey struct{}
	parentKey      struct{}
)

type step struct {
	Number     int     `json:"step"`
	Parent     int     `json:"parent,omitempty"`
	Name       string  `json:"name"`
	StartMS    float64 `json:"start_ms"`
	DurationMS float64 `json:"duration_ms"`
}

type observation struct {
	started   time.Time
	requestID string
	traceID   string
	log       *slog.Logger
	mu        sync.Mutex
	steps     []step
}

func requestState(ctx context.Context) *observation {
	return ctx.Value(observationKey{}).(*observation)
}

// The returned context links work done by a child operation to this step.
func startStep(ctx context.Context, name string) (context.Context, func()) {
	stepID, end := recordStep(ctx, name)
	return context.WithValue(ctx, parentKey{}, stepID), end
}

func recordStep(ctx context.Context, name string) (int, func()) {
	started := time.Now()
	o := requestState(ctx)
	parent, _ := ctx.Value(parentKey{}).(int)
	o.mu.Lock()
	index := len(o.steps)
	o.steps = append(o.steps, step{
		Number:  index + 1,
		Parent:  parent,
		Name:    name,
		StartMS: milliseconds(started.Sub(o.started)),
	})
	o.mu.Unlock()

	return index + 1, func() {
		elapsed := time.Since(started)
		o.mu.Lock()
		o.steps[index].DurationMS = milliseconds(elapsed)
		o.mu.Unlock()
	}
}

func (o *observation) snapshot() []step {
	o.mu.Lock()
	defer o.mu.Unlock()
	return append([]step{}, o.steps...)
}

func milliseconds(d time.Duration) float64 {
	return float64(d) / float64(time.Millisecond)
}

func getTraceID(header string) string {
	parts := strings.Split(header, "-")
	if len(parts) == 4 && parts[0] == "00" && lowerHex(parts[1], 32) &&
		lowerHex(parts[2], 16) && lowerHex(parts[3], 2) &&
		strings.Trim(parts[1], "0") != "" && strings.Trim(parts[2], "0") != "" {
		return parts[1]
	}
	var id [16]byte
	for id == ([16]byte{}) {
		rand.Read(id[:])
	}
	return hex.EncodeToString(id[:])
}

func lowerHex(value string, length int) bool {
	return len(value) == length && strings.Trim(value, "0123456789abcdef") == ""
}

type responseStatus struct {
	http.ResponseWriter
	code int
}

func (w *responseStatus) Unwrap() http.ResponseWriter {
	return w.ResponseWriter
}

func (w *responseStatus) WriteHeader(code int) {
	if w.code == 0 && code >= 200 {
		w.code = code
	}
	w.ResponseWriter.WriteHeader(code)
}

func (w *responseStatus) Write(p []byte) (int, error) {
	if w.code == 0 {
		w.WriteHeader(http.StatusOK)
	}
	return w.ResponseWriter.Write(p)
}

func observe(log *slog.Logger) middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			o := &observation{
				started: time.Now(),
			}

			ctx := context.WithValue(r.Context(), observationKey{}, o)
			_, end := recordStep(ctx, "request.ids")
			o.requestID = rand.Text()
			o.traceID = getTraceID(r.Header.Get("traceparent"))
			o.log = log.With("request_id", o.requestID, "trace_id", o.traceID)
			end()
			w.Header().Set("X-Request-ID", o.requestID)
			w.Header().Set("X-Trace-ID", o.traceID)
			status := &responseStatus{
				ResponseWriter: w,
			}
			r = r.WithContext(ctx)

			defer func() {
				duration := milliseconds(time.Since(o.started))
				code := status.code
				if code == 0 {
					code = http.StatusOK
				}
				o.log.InfoContext(ctx, "request completed",
					"method", r.Method,
					"route", r.Pattern,
					"status", code,
					"duration_ms", duration,
					"steps", o.snapshot(),
				)
			}()

			next.ServeHTTP(status, r)
		})
	}
}
