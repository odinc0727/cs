"""Kafka protocol round trip and RabbitMQ HTTP publish/get round trip."""

import base64
import json
import logging
import time
from contextlib import closing
from urllib.request import Request, urlopen
from uuid import uuid7

from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer
from kafka.admin import NewTopic
from kafka.errors import TopicAlreadyExistsError
from kafka.structs import TopicPartition


def rabbit(method, path, body=None):
        request = Request(
                'http://127.0.0.1:15672/api' + path,
                data=None if body is None else json.dumps(body).encode(),
                method=method,
                headers={
                        'Authorization': 'Basic ' + base64.b64encode(b'guest:guest').decode(),
                        'Content-Type': 'application/json',
                },
        )
        with urlopen(request, timeout=10) as response:
                data = response.read()
                return json.loads(data) if data else None


def main():
        logging.basicConfig(level=logging.ERROR)
        token = f'local-broker-check-{uuid7()}'
        topic = 'cdc.broker-smoke'
        with closing(KafkaAdminClient(bootstrap_servers='127.0.0.1:9092')) as admin:
                try:
                        admin.create_topics([NewTopic(topic, 1, 1)])
                except TopicAlreadyExistsError:
                        pass
        consumer = KafkaConsumer(bootstrap_servers='127.0.0.1:9092', group_id=None, enable_auto_commit=False)
        producer = KafkaProducer(bootstrap_servers='127.0.0.1:9092', acks='all')
        try:
                consumer.assign([TopicPartition(topic, 0)])
                consumer.seek_to_end()
                consumer.position(TopicPartition(topic, 0))  # Resolve the lazy seek before producing.
                producer.send(topic, key=token.encode(), value=token.encode()).get(timeout=10)
                deadline = time.monotonic() + 10
                found = False
                while time.monotonic() < deadline and not found:
                        found = any(
                                record.value == token.encode()
                                for records in consumer.poll(timeout_ms=500).values()
                                for record in records
                        )
                assert found, 'Kafka round trip timed out'
                print('PASS Kafka: produce -> broker -> consume')
        finally:
                producer.close()
                consumer.close(autocommit=False)

        queue_path = '/queues/%2F/' + token
        rabbit('PUT', queue_path, {'durable': True, 'auto_delete': False, 'arguments': {'x-queue-type': 'classic'}})
        try:
                result = rabbit(
                        'POST',
                        '/exchanges/%2F/amq.default/publish',
                        {
                                'properties': {'delivery_mode': 2},
                                'routing_key': token,
                                'payload': token,
                                'payload_encoding': 'string',
                        },
                )
                assert isinstance(result, dict), f'Expected a publish response object, got {result!r}'
                assert result['routed'] is True, result
                messages = rabbit(
                        'POST', queue_path + '/get', {'count': 1, 'ackmode': 'ack_requeue_false', 'encoding': 'auto'}
                )
                assert isinstance(messages, list), f'Expected a message list, got {messages!r}'
                assert len(messages) == 1 and messages[0]['payload'] == token, messages
                print('PASS RabbitMQ: HTTP publish -> queue -> HTTP get/ack')
        finally:
                rabbit('DELETE', queue_path)
        print('Local broker checks passed')


if __name__ == '__main__':
        main()
