import sys

import pika

conn = pika.BlockingConnection(pika.ConnectionParameters())

ch = conn.channel()

ch.exchange_declare(exchange="d-logs", exchange_type="direct")

severity = sys.argv[1] if len(sys.argv) > 1 else 'info'
msg = ' '.join(sys.argv[2:]) or 'Hello World!'

ch.basic_publish(exchange="d-logs", routing_key=severity, body=msg)

print(f" [x] Sent {severity}:{msg}")

conn.close()