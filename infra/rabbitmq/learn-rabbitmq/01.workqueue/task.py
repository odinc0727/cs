import sys

import pika

conn = pika.BlockingConnection(pika.ConnectionParameters())

ch = conn.channel()

ch.queue_declare(queue="workqueue", durable=True, arguments={"x-queue-type": "quorum"})

msg = "".join(sys.argv[1:]) or "Hello World!"

ch.basic_publish(
    exchange="",
    routing_key="workqueue",
    body=msg,
    properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent),
)

print(f" [x] Sent {msg}")

conn.close()
