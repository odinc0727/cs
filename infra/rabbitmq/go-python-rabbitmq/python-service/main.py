"""Send to Go every five seconds while consuming messages sent by Go."""
import json
import logging
import os
import sys

import pika

class ColorFormatter(logging.Formatter):
    def format(self, record):
        text = super().format(record)
        if not sys.stderr.isatty() or os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
            return text
        color = "31" if record.levelno >= logging.WARNING else getattr(record, "color", "33")
        return f"\033[{color}m{text}\033[0m"


handler = logging.StreamHandler()
handler.setFormatter(ColorFormatter(
    "%(asctime)s %(message)s", datefmt="%Y/%m/%d %H:%M:%S",
))
logging.basicConfig(level=logging.INFO, handlers=[handler])
# Keep the demo focused on application messages.
logging.getLogger("pika").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def main():
    url = os.environ.get("RABBITMQ_URL", "amqp://demo:demo@localhost:5672/")
    connection = pika.BlockingConnection(pika.URLParameters(url))

    try:
        channel = connection.channel()
        # Same queue names and declaration options as the Go service.
        for name in ("to.go", "to.python"):
            channel.queue_declare(queue=name, durable=True)

        def send():
            message = {"from": "Python", "text": "Hello world from Python"}
            channel.basic_publish(
                exchange="", routing_key="to.go",
                body=json.dumps(message).encode("utf-8"),
                properties=pika.BasicProperties(content_type="application/json"),
            )
            logger.info("[Python -> Go] sent: %s", message, extra={"color": "32"})
            # Timer callbacks run in Pika's event loop, on the same thread.
            connection.call_later(5, send)

        send()

        def receive(ch, method, properties, body):
            try:
                msg = json.loads(body)
                sender, text = msg["from"], msg["text"]
            except (ValueError, KeyError, TypeError):
                logger.warning("invalid message: %r", body)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            logger.info("[Python received from %s] %s", sender, text, extra={"color": "36"})
            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue="to.python", on_message_callback=receive)
        logger.info("[Python] listening on to.python")

        try:
            channel.start_consuming()
        except KeyboardInterrupt:
            channel.stop_consuming()

    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("[Python error] service failed")
        sys.exit(1)
