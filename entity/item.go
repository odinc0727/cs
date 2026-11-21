package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"strings"
)

const demoUID = "019b4d3b-77d0-7f43-9d7e-0c5272be81a6"

var (
	errNotFound = errors.New("item not found")
	uidPattern  = regexp.MustCompile("(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
)

type itemStore interface {
	Find(ctx context.Context, uid string) (string, error)
}

type itemCache interface {
	Get(ctx context.Context, uid string) (string, bool, error)
	Set(ctx context.Context, uid, value string) error
}

type eventPublisher interface {
	Publish(ctx context.Context, event lookupEvent) error
}

type lookupEvent struct {
	Type      string `json:"type"`
	UID       string `json:"uid"`
	Source    string `json:"source"`
	RequestID string `json:"request_id"`
	TraceID   string `json:"trace_id"`
}

type item struct {
	UID    string `json:"uid"`
	Value  string `json:"value"`
	Source string `json:"source"`
}

type itemService struct {
	db     itemStore
	cache  itemCache
	events eventPublisher
}

func (s itemService) handle(w http.ResponseWriter, r *http.Request) {
	ctx, end := startStep(r.Context(), "http.get_item")
	defer end()
	uid := strings.ToLower(r.PathValue("uid"))
	if !uidPattern.MatchString(uid) {
		writeError(w, http.StatusBadRequest)
		return
	}

	result, err := s.lookup(ctx, uid)
	switch {
	case errors.Is(err, errNotFound):
		writeError(w, http.StatusNotFound)
	case err != nil:
		requestState(ctx).log.ErrorContext(ctx, "item lookup failed", "uid", uid, "err", err)
		writeError(w, http.StatusInternalServerError)
	default:
		writeJSON(w, http.StatusOK, result)
	}
}

func (s itemService) lookup(ctx context.Context, uid string) (item, error) {
	ctx, end := startStep(ctx, "service.lookup")
	defer end()

	o := requestState(ctx)

	_, cacheEnd := recordStep(ctx, "redis.get")
	value, hit, cacheErr := s.cache.Get(ctx, uid)
	cacheEnd()
	if cacheErr != nil {
		o.log.WarnContext(ctx, "cache read failed", "uid", uid, "err", cacheErr)
	}

	source := "redis"
	if !hit {
		source = "postgres"
		_, dbEnd := recordStep(ctx, "postgres.select")
		var err error
		value, err = s.db.Find(ctx, uid)
		dbEnd()
		if err != nil {
			return item{}, fmt.Errorf("find item: %w", err)
		}

		if cacheErr == nil {
			_, setEnd := recordStep(ctx, "redis.set")
			err := s.cache.Set(ctx, uid, value)
			setEnd()
			if err != nil {
				o.log.WarnContext(ctx, "cache write failed", "uid", uid, "err", err)
			}
		}
	}

	_, eventEnd := recordStep(ctx, "rabbitmq.publish")
	err := s.events.Publish(ctx, lookupEvent{
		Type:      "item.lookup",
		UID:       uid,
		Source:    source,
		RequestID: o.requestID,
		TraceID:   o.traceID,
	})
	eventEnd()
	if err != nil {
		o.log.WarnContext(ctx, "lookup event publish failed", "uid", uid, "err", err)
	}

	return item{
		UID:    uid,
		Value:  value,
		Source: source,
	}, nil
}

func writeError(w http.ResponseWriter, code int) {
	writeJSON(w, code, map[string]string{
		"message": http.StatusText(code),
	})
}

func writeJSON(w http.ResponseWriter, code int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(value)
}
