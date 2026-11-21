package main

import (
	"context"
	"log/slog"
	"net"
	"net/http"
	"slices"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	ipLimit   = 20
	userLimit = 5
	window    = 10 * time.Second
)

type middleware func(http.Handler) http.Handler

func chain(next http.Handler, stack ...middleware) http.Handler {
	for _, s := range slices.Backward(stack) {
		next = s(next)
	}
	return next
}

type identityKey struct{}

type identity struct {
	uid     string
	canRead bool
}

func authenticate(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, end := recordStep(r.Context(), "auth.authenticate")
		scheme, token, _ := strings.Cut(r.Header.Get("Authorization"), " ")
		var actor identity
		if strings.EqualFold(scheme, "Bearer") {
			switch token {
			case "demo-reader":
				actor = identity{uid: "019b4d3b-77d0-7f43-9d7e-0c5272be81a7", canRead: true}
			case "demo-viewer":
				actor = identity{uid: "019b4d3b-77d0-7f43-9d7e-0c5272be81a8"}
			}
		}
		end()
		if actor.uid == "" {
			w.Header().Set("WWW-Authenticate", "Bearer")
			writeError(w, http.StatusUnauthorized)
			return
		}
		next.ServeHTTP(w, r.WithContext(context.WithValue(r.Context(), identityKey{}, actor)))
	})
}

func principal(r *http.Request) identity {
	return r.Context().Value(identityKey{}).(identity)
}

func authorize(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, end := recordStep(r.Context(), "auth.authorize")
		allowed := principal(r).canRead
		end()
		if !allowed {
			writeError(w, http.StatusForbidden)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func recoverPanics(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if recovered := recover(); recovered != nil {
				requestState(r.Context()).log.ErrorContext(r.Context(), "request panicked", "panic", recovered)
				if w.(*responseStatus).code == 0 {
					writeError(w, http.StatusInternalServerError)
				}
			}
		}()
		next.ServeHTTP(w, r)
	})
}

type limiter struct {
	limit int
	mu    sync.Mutex
	until time.Time
	count map[string]int
}

func (l *limiter) allow(key string) (bool, int) {
	l.mu.Lock()
	defer l.mu.Unlock()
	now := time.Now()
	if !now.Before(l.until) {
		l.until = now.Add(window)
		l.count = make(map[string]int)
	}
	if l.count[key] >= l.limit {
		wait := l.until.Sub(now)
		return false, int((wait + time.Second - 1) / time.Second)
	}
	l.count[key]++
	return true, 0
}

func rateLimit(name string, limit int, key func(*http.Request) string) middleware {
	l := limiter{limit: limit}
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			_, end := recordStep(r.Context(), name)
			ok, retryAfter := l.allow(key(r))
			end()
			if !ok {
				w.Header().Set("Retry-After", strconv.Itoa(retryAfter))
				writeError(w, http.StatusTooManyRequests)
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}

func clientIP(r *http.Request) string {
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return host
}

func newHandler(log *slog.Logger, db itemStore, cache itemCache, events eventPublisher) http.Handler {
	app := itemService{db: db, cache: cache, events: events}
	mux := http.NewServeMux()
	mux.Handle("GET /items/{uid}", chain(
		http.HandlerFunc(app.handle),
		authenticate,
		rateLimit("limit.user", userLimit, func(r *http.Request) string {
			return principal(r).uid
		}),
		authorize,
	))
	return chain(mux, observe(log), recoverPanics, rateLimit("limit.ip", ipLimit, clientIP))
}
