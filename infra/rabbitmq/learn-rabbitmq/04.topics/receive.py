import sys

import pika

conn = pika.BlockingConnection(pika.ConnectionParameters())

ch = conn.channel()

ch.exchange_declare(exchange="topic_logs", exchange_type="topic")

res = ch.queue_declare("", exclusive=True)
queue_name = res.method.queue

binding_keys = sys.argv[1:]
if not binding_keys:
    sys.stderr.write(f"Usage: {sys.argv[0]} [binding_key]...\n")
    sys.exit(1)

for binding_key in binding_keys:
    ch.queue_bind(exchange="topic_logs", queue=queue_name, routing_key=binding_key)


def callback(ch, method, properties, body):
    print(f"[x] {method.routing_key}:{body.decode()}")


ch.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

ch.start_consuming()
