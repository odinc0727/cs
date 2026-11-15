import os
import sys

import pika


def main():
    conn = pika.BlockingConnection(pika.ConnectionParameters())

    ch = conn.channel()

    ch.queue_declare(queue="hello", durable=True, arguments={"x-queue-type": "quorum"})

    def callback(ch, method, properties, body):
        print(f" [x] Received {body}")

    ch.basic_consume(queue="hello", on_message_callback=callback, auto_ack=True)

    print(' [*] Waiting for messages. To exit press CTRL+C')

    ch.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)