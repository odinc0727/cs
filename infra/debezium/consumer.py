"""Debezium events -> a Redis projection; commit only after the write succeeds."""

import json
import logging
import os
import signal
from uuid import UUID

LOG = logging.getLogger('cdc')


def decode_change(key: bytes | None, value: bytes | None) -> tuple[str, dict | None] | None:
        if value is None:
                return None  # Kafka compaction tombstone, following the actual delete event.

        def unwrap(raw):
                obj = json.loads(raw) if raw is not None else None
                if isinstance(obj, dict) and 'schema' in obj and 'payload' in obj:
                        obj = obj['payload']
                if not isinstance(obj, dict):
                        raise TypeError('Expected a JSON object')
                return obj

        event = unwrap(value)
        op = event.get('op')
        if op not in ('r', 'c', 'u', 'd'):
                raise ValueError(f'Unsupported CDC operation: {op!r}; TRUNCATE is not supported')
        uid = str(unwrap(key).get('uid', ''))
        try:
                if str(UUID(uid)) != uid:
                        raise ValueError('uid must be a canonical UUID')
        except (ValueError, AttributeError) as exc:
                raise ValueError(f'Invalid uid: {uid!r}') from exc
        if op == 'd':
                return f'cdc:product:{uid}', None
        row = event.get('after')
        if not isinstance(row, dict) or row.get('uid') != uid:
                raise ValueError('Missing after row or after.uid differs from message key')
        return f'cdc:product:{uid}', row


def process_record(record, cache, consumer):
        from kafka.structs import OffsetAndMetadata, TopicPartition

        change = decode_change(record.key, record.value)
        if change is not None:
                key, row = change
                if row is None:
                        cache.delete(key)
                        LOG.info('DEL %s (offset=%s)', key, record.offset)
                else:
                        cache.set(key, json.dumps(row, ensure_ascii=False, separators=(',', ':')))
                        LOG.info('SET %s = %s (offset=%s)', key, row, record.offset)
        # An explicit per-record offset avoids committing past an unprocessed message.
        consumer.commit({TopicPartition(record.topic, record.partition): OffsetAndMetadata(record.offset + 1, '', -1)})


def main():
        from kafka import KafkaConsumer
        from redis import Redis

        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
        logging.getLogger('kafka').setLevel(logging.WARNING)
        running = True

        def stop(signum, frame):
                nonlocal running
                running = False

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        cache = Redis.from_url(
                os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0'), socket_connect_timeout=5, socket_timeout=5
        )
        cache.ping()
        consumer = KafkaConsumer(
                os.getenv('KAFKA_TOPIC', 'cdc.public.products'),
                bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS', '127.0.0.1:9092'),
                group_id=os.getenv('KAFKA_GROUP_ID', 'cdc-redis-projector'),
                auto_offset_reset='earliest',
                enable_auto_commit=False,
                max_poll_records=1,
                client_id='cdc-redis-projector',
        )
        try:
                LOG.info('Consumer ready; group=%s', consumer.config['group_id'])
                while running:
                        for records in consumer.poll(timeout_ms=1000, max_records=1).values():
                                for record in records:
                                        process_record(record, cache, consumer)
        finally:
                consumer.close(autocommit=False)
                cache.close()


if __name__ == '__main__':
        main()
