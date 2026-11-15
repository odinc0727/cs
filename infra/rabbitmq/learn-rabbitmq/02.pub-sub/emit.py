import sys

import pika

conn = pika.BlockingConnection(pika.ConnectionParameters())

ch = conn.channel()

ch.exchange_declare(exchange="logs", exchange_type="fanout")

msg = ' '.join(sys.argv[1:]) or "info: Hello World!"

ch.basic_publish(exchange="logs", routing_key="", body=msg)

print(f" [x] Sent {msg}")

conn.close()