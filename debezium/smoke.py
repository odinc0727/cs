"""Real end-to-end CDC checks. Creates and cleans up only its own test product."""

import json
import logging
import time
from urllib.request import urlopen
from uuid import uuid7

import manage
import psycopg
from kafka import KafkaConsumer
from kafka.structs import TopicPartition

from redis import Redis


def wait_row(cache, uid, name, price):
        key = f'cdc:product:{uid}'

        def matched():
                value = cache.get(key)
                if name is None:
                        return value is None
                if value is None:
                        return False
                row = json.loads(value)
                return row['uid'] == str(uid) and row['name'] == name and row['price_cents'] == price

        manage.wait_for(matched, f'Redis {key}: {name!r} / {price}', timeout=30)


def check_snapshot(cache):
        observer = KafkaConsumer(bootstrap_servers='127.0.0.1:9092', group_id=None, enable_auto_commit=False)
        try:
                observer.assign([TopicPartition('cdc.public.products', 0)])
                observer.seek_to_beginning()
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                        for records in observer.poll(timeout_ms=500).values():
                                for record in records:
                                        if record.value is None:
                                                continue
                                        event = json.loads(record.value)
                                        if event['op'] == 'r':
                                                row = event['after']
                                                # The seed row remains untouched by these tests.
                                                if row['name'] == '初始快照商品':
                                                        wait_row(cache, row['uid'], row['name'], row['price_cents'])
                                                        print('PASS initial snapshot: op=r exists in Kafka and Redis')
                                                        return
                raise AssertionError('No seed snapshot event found (Kafka retention may have expired)')
        finally:
                observer.close(autocommit=False)


def main():
        logging.basicConfig(level=logging.ERROR)
        if not manage.status():
                raise RuntimeError('Run: uv run python debezium/manage.py up')
        with urlopen('http://127.0.0.1:18083/connectors/cdc-products/config', timeout=5) as response:
                config = json.load(response)
        assert config.get('skipped.operations') == 'none', 'TRUNCATE must reach the consumer and fail explicitly'
        print('PASS connector guard: no operation is silently filtered before the consumer')
        cache = Redis(host='127.0.0.1', decode_responses=True, socket_timeout=5)
        uid = None
        rollback_uid = uuid7()
        with psycopg.connect(manage.DATABASE_URL, autocommit=True) as db:
                try:
                        check_snapshot(cache)
                        created = db.execute(
                                'INSERT INTO products(name, price_cents) VALUES (%s, %s) RETURNING uid',
                                ('CDC 新商品', 0),
                        ).fetchone()
                        assert created is not None, 'INSERT RETURNING did not return a product'
                        uid = created[0]
                        assert uid.version == 7, f'Expected UUIDv7, got {uid}'
                        wait_row(cache, uid, 'CDC 新商品', 0)
                        print(f'PASS INSERT: {uid}, zero price and Unicode preserved')

                        db.execute(
                                'UPDATE products SET name=%s, price_cents=%s, updated_at=now() WHERE uid=%s',
                                ('CDC 更新商品', 1299, uid),
                        )
                        wait_row(cache, uid, 'CDC 更新商品', 1299)
                        print('PASS UPDATE: Redis reflects the committed row')

                        cached = cache.get(f'cdc:product:{uid}')
                        assert cached is not None, 'Product disappeared from Redis before the update check'
                        row = json.loads(cached)
                        db.execute('UPDATE products SET updated_at=now() WHERE uid=%s', (uid,))
                        manage.wait_for(
                                lambda: (
                                        (value := cache.get(f'cdc:product:{uid}')) is not None
                                        and json.loads(value)['updated_at'] != row['updated_at']
                                ),
                                'repeated values update delivered',
                                timeout=30,
                        )
                        wait_row(cache, uid, 'CDC 更新商品', 1299)
                        print('PASS repeated values: another event preserves the same business values')

                        db.execute('BEGIN')
                        db.execute(
                                'INSERT INTO products(uid, name, price_cents) VALUES (%s, %s, %s)',
                                (rollback_uid, '已回滚商品', 100),
                        )
                        db.execute('ROLLBACK')
                        # A later committed event is a barrier: do not rely on a fixed sleep.
                        db.execute(
                                'UPDATE products SET name=%s, updated_at=now() WHERE uid=%s', ('回滚之后的提交', uid)
                        )
                        wait_row(cache, uid, '回滚之后的提交', 1299)
                        assert cache.get(f'cdc:product:{rollback_uid}') is None
                        print('PASS ROLLBACK: uncommitted row never reaches Redis')

                        manage.stop('consumer')
                        try:
                                db.execute(
                                        'UPDATE products SET name=%s, price_cents=%s, updated_at=now() WHERE uid=%s',
                                        ('停机期间的更新', 2599, uid),
                                )
                                wait_row(cache, uid, '回滚之后的提交', 1299)
                        finally:
                                manage.start('consumer', [manage.sys.executable, '-u', manage.ROOT / 'consumer.py'])
                        wait_row(cache, uid, '停机期间的更新', 2599)
                        print('PASS consumer restart: catches up with changes written while stopped')

                        db.execute('DELETE FROM products WHERE uid=%s', (uid,))
                        wait_row(cache, uid, None, None)
                        print('PASS DELETE: key removed from Redis')
                finally:
                        if uid is not None:
                                db.execute('DELETE FROM products WHERE uid=%s', (uid,))
                        cache.close()
        print('CDC smoke: all checks passed')


if __name__ == '__main__':
        main()
