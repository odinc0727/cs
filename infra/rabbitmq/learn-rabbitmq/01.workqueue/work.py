import os
import sys
import time

import pika


def main():
    conn = pika.BlockingConnection(pika.ConnectionParameters())

    ch = conn.channel()

    ch.queue_declare(
        queue="workqueue", durable=True, arguments={"x-queue-type": "quorum"}
    )

    def callback(ch, method, properties, body):
        print(f" [x] Received {body.decode()}")
        time.sleep(body.count(b"."))
        print(" [x] Done")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(queue="workqueue", on_message_callback=callback)

    ch.start_consuming()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
