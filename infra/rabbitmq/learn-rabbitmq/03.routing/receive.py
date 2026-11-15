import sys

import pika

conn = pika.BlockingConnection(pika.ConnectionParameters())

ch = conn.channel()

ch.exchange_declare(exchange="d-logs", exchange_type="direct")

res = ch.queue_declare(queue="", exclusive=True)
queue_name = res.method.queue

severities = sys.argv[1:]
if not severities:
    sys.stderr.write(f"Usage: {sys.argv[0]} [info] [warning] [error]\n")
    sys.exit(1)

for severity in severities:
    ch.queue_bind(exchange="d-logs", queue=queue_name, routing_key=severity)


def callback(ch, method, properties, body):
    print(f" [x] {method.routing_key}:{body.decode('utf-8')}")


ch.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

ch.start_consuming()
