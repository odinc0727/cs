import sys
import uuid
from typing import Final

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic

WORKQUEUE: Final = "retry.work"
DEADEXCHANGE: Final = "retry.dlx"
DEADQUEUE: Final = "retry.dead"
DEADROUTINGKEY: Final = "dead"
RETRYQUEUES: Final = [
        ("retry.retry.2s", 2_000),
        ("retry.retry.3s", 3_000),
        ("retry.retry.4s", 4_000),
]


def connect():
        return pika.BlockingConnection(pika.ConnectionParameters())


def declare(ch: BlockingChannel) -> None:
        # 延迟队列
        for name, delay_ms in RETRYQUEUES:
                ch.queue_declare(
                        queue=name,
                        durable=True,
                        arguments={
                                "x-queue-type": "quorum",
                                "x-message-ttl": delay_ms,
                                "x-dead-letter-exchange": "",
                                "x-dead-letter-routing-key": WORKQUEUE,
                        },
                )

        # 工作队列
        ch.queue_declare(
                queue=WORKQUEUE,
                durable=True,
                arguments={
                        "x-queue-type": "quorum",
                        "x-dead-letter-exchange": DEADEXCHANGE,
                        "x-dead-letter-routing-key": DEADROUTINGKEY,
                },
        )

        # 死信交换机和死信队列
        ch.exchange_declare(exchange=DEADEXCHANGE, exchange_type="direct", durable=True)
        ch.queue_declare(queue=DEADQUEUE, durable=True, arguments={"x-queue-type": "quorum"})
        ch.queue_bind(queue=DEADQUEUE, exchange=DEADEXCHANGE, routing_key=DEADROUTINGKEY)


def republished_properties(old_properties: pika.BasicProperties, headers):
        return pika.BasicProperties(
                content_type=old_properties.content_type,
                content_encoding=old_properties.content_encoding,
                headers=headers,
                delivery_mode=pika.DeliveryMode.Persistent,
                priority=old_properties.priority,
                correlation_id=old_properties.correlation_id,
                reply_to=old_properties.reply_to,
                message_id=old_properties.message_id,
                timestamp=old_properties.timestamp,
                type=old_properties.type,
                app_id=old_properties.app_id,
        )


def handle_message(body):
        print(f"处理消息：{body.decode()}")

        # 模拟处理失败
        if body == b"fail":
                raise RuntimeError("处理失败")


def on_message(ch: BlockingChannel, method: Basic.Deliver, properties: pika.BasicProperties, body: bytes):
        headers = dict(properties.headers or {})
        retry_count = headers.get("x-retry-count", 0)
        if not isinstance(retry_count, int):
                raise TypeError

        try:
                handle_message(body)
        except Exception as exc:  # noqa: BLE001
                print(f"处理失败：{exc}")

                if retry_count < len(RETRYQUEUES):
                        retry_queue, delay_ms = RETRYQUEUES[retry_count]
                        headers["x-retry-count"] = retry_count + 1

                        # 先确认重发成功再 ACK
                        ch.basic_publish(
                                exchange="",
                                routing_key=retry_queue,
                                body=body,
                                properties=republished_properties(properties, headers),
                                mandatory=True,
                        )
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        print(f"安排第 {retry_count + 1} 次重试，延迟约 {delay_ms} ms")
                else:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                        print("重试次数用完，消息进入死信队列")
        else:
                ch.basic_ack(delivery_tag=method.delivery_tag)
                print("处理成功")


def consume():
        conn = connect()
        ch = conn.channel()
        declare(ch)

        ch.confirm_delivery()
        ch.basic_qos(prefetch_count=1)
        ch.basic_consume(queue=WORKQUEUE, on_message_callback=on_message, auto_ack=False)

        print(f"等待消费 {WORKQUEUE}；Ctrl+C 退出")
        ch.start_consuming()


def send(body):
        conn = connect()
        ch = conn.channel()
        declare(ch)

        ch.confirm_delivery()
        ch.basic_publish(
                exchange="",
                routing_key=WORKQUEUE,
                body=body.encode(),
                properties=pika.BasicProperties(
                        delivery_mode=pika.DeliveryMode.Persistent,
                        message_id=str(uuid.uuid4()),
                        headers={"x-retry-count": 0},
                ),
                mandatory=True,
        )

        print(f"已发送：{body}")
        conn.close()


if __name__ == "__main__":
        if len(sys.argv) < 2:
                print(f"用法：{sys.argv[0]} consume | send <消息>")
                raise SystemExit(1)

        match (command := sys.argv[1]):
                case "consume":
                        consume()
                case "send":
                        send(" ".join(sys.argv[2:]) or "fail")
                case _:
                        raise SystemExit(f"未知命令：{command}")
