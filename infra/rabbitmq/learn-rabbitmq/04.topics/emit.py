import sys

import pika

conn = pika.BlockingConnection(pika.ConnectionParameters())

ch = conn.channel()

ch.exchange_declare(exchange="topic_logs", exchange_type="topic")

routing_key = sys.argv[1] if len(sys.argv) > 2 else "anonymous.info"
msg = "".join(sys.argv[2:]) or "Hello world from Python!"

ch.basic_publish(exchange="topic_logs", routing_key=routing_key, body=msg)

print(f"[x] Sent {routing_key}:{msg}")

conn.close()
