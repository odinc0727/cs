package main

import (
	"context"
	"encoding/json"
	"log"
	"os"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
)

type Message struct {
	From string `json:"from"`
	Text string `json:"text"`
}

func colorLog(color, format string, args ...any) {
	info, err := os.Stderr.Stat()
	if err == nil && info.Mode()&os.ModeCharDevice != 0 && os.Getenv("NO_COLOR") == "" && os.Getenv("TERM") != "dumb" {
		format = "\x1b[" + color + "m" + format + "\x1b[0m"
	}
	log.Printf(format, args...)
}

func main() {
	if err := run(); err != nil {
		colorLog("31", "[Go error] %v", err)
		os.Exit(1)
	}
}

func run() error {
	url := os.Getenv("RABBITMQ_URL")
	if url == "" {
		url = "amqp://demo:demo@localhost:5672/"
	}

	conn, err := amqp.Dial(url)
	if err != nil {
		return err
	}
	defer conn.Close()

	ch, err := conn.Channel()
	if err != nil {
		return err
	}
	defer ch.Close()

	// Both services declare both queues: either service may start first.
	for _, name := range []string{"to.go", "to.python"} {
		if _, err = ch.QueueDeclare(name, true, false, false, false, nil); err != nil {
			return err
		}
	}

	body, err := json.Marshal(Message{From: "Go", Text: "Hello world from Go"})
	if err != nil {
		return err
	}

	send := func() error {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		// Default exchange routes to the queue matching the routing key.
		if err := ch.PublishWithContext(ctx, "", "to.python", false, false, amqp.Publishing{
			ContentType: "application/json", Body: body,
		}); err != nil {
			return err
		}
		colorLog("32", "[Go -> Python] sent: %s", body)

		return nil
	}
	if err := send(); err != nil {
		return err
	}

	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	messages, err := ch.Consume("to.go", "", false, false, false, false, nil)
	if err != nil {
		return err
	}
	colorLog("33", "[Go] listening on to.go")

	for {
		select {
		case <-ticker.C:
			if err := send(); err != nil {
				return err
			}

		case delivery, ok := <-messages:
			if !ok {
				return amqp.ErrClosed
			}

			var msg Message
			if err := json.Unmarshal(delivery.Body, &msg); err != nil {
				colorLog("31", "invalid JSON: %v", err)
				if err := delivery.Nack(false, false); err != nil {
					return err
				}
				continue
			}
			colorLog("36", "[Go received from %s] %s", msg.From, msg.Text)

			if err := delivery.Ack(false); err != nil {
				return err
			}
		}
	}
}
