package main

import (
	"fmt"
	"net/http"
	"time"
)

// 使用共享 channel，适合演示单个消费者的情况。
// 多个客户端同时等待时，一条消息只会被其中一个客户端取走。
// 如果需要广播给所有客户端，就要使用订阅者列表或发布订阅机制。

func main() {
	events := make(chan string, 10)

	http.HandleFunc("/poll", func(w http.ResponseWriter, r *http.Request) {
		timer := time.NewTimer(30 * time.Second)
		defer timer.Stop()

		select {
		case msg := <-events:
			fmt.Fprintln(w, msg)

		case <-timer.C:
			w.WriteHeader(http.StatusNoContent)

		case <-r.Context().Done():
			return
		}
	})

	http.HandleFunc("/pub", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}

		select {
		case events <- "Hello from Long Polling":
			w.WriteHeader(http.StatusAccepted)

		default:
			http.Error(w, "queue full", http.StatusServiceUnavailable)
		}
	})

	http.ListenAndServe(":8080", nil)
}
