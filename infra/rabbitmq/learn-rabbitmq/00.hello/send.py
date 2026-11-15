import pika

conn = pika.BlockingConnection(pika.ConnectionParameters())

ch = conn.channel()

ch.queue_declare(queue="hello", durable=True, arguments={'x-queue-type': "quorum"})

msg = "Hello World from emit.py!"

# 队列创建时会自动绑定到默认交换机，生产者可以用队列名作为 routing key 发布消息。
ch.basic_publish(exchange="", routing_key="hello", body=msg)

print(f" [x] Sent {msg}")

conn.close()