import pika

conn = pika.BlockingConnection(pika.ConnectionParameters())

ch = conn.channel()

ch.exchange_declare(exchange="logs", exchange_type="fanout")

res = ch.queue_declare(queue="", exclusive=True)

queue_name = res.method.queue

ch.queue_bind(queue=queue_name, exchange="logs")


def callback(ch, method, properties, body):
    print(f" [x] {body.decode("utf-8")}")


ch.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

ch.start_consuming()
