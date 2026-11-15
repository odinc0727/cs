import json
import unittest
from types import SimpleNamespace

from consumer import decode_change, process_record

UID = '019a71c6-7e71-7000-8000-000000000001'
KEY = json.dumps({'uid': UID}).encode()
ROW = {'uid': UID, 'name': 'Keyboard', 'price_cents': 19900}


class DecodeTests(unittest.TestCase):
        def test_snapshot_create_update_and_schema_envelope(self):
                for op in ('r', 'c', 'u'):
                        for wrapped in (False, True):
                                with self.subTest(op=op, wrapped=wrapped):
                                        value = {'op': op, 'after': ROW}
                                        key = {'uid': UID}
                                        if wrapped:
                                                value = {'schema': {}, 'payload': value}
                                                key = {'schema': {}, 'payload': key}
                                        result = decode_change(json.dumps(key).encode(), json.dumps(value).encode())
                                        self.assertEqual(result, (f'cdc:product:{UID}', ROW))

        def test_delete_uses_key_even_without_before(self):
                self.assertEqual(
                        decode_change(KEY, b'{"op":"d","before":null,"after":null}'),
                        (f'cdc:product:{UID}', None),
                )

        def test_tombstone_is_noop(self):
                self.assertIsNone(decode_change(KEY, None))

        def test_bad_messages_fail_closed(self):
                for key, value in (
                        (None, b'{"op":"t"}'),
                        (KEY, b'not-json'),
                        (KEY, b'{"op":"x"}'),
                        (KEY, b'{"op":"u","after":null}'),
                        (b'{"uid":"not-a-uuid"}', b'{"op":"d"}'),
                        (KEY, b'{"op":"c","after":{"uid":"019a71c6-7e71-7000-8000-000000000002"}}'),
                ):
                        with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                                decode_change(key, value)

        def test_commit_after_redis_and_never_on_write_failure(self):
                # Track the real boundary contract: Redis side effect must precede commit.
                effects = []

                class Cache:
                        def set(self, key, value):
                                effects.append(('set', key, json.loads(value)))

                class Consumer:
                        def commit(self, offsets):
                                effects.append(('commit', next(iter(offsets.values())).offset))

                record = SimpleNamespace(
                        topic='cdc.public.products',
                        partition=0,
                        offset=7,
                        key=KEY,
                        value=json.dumps({'op': 'c', 'after': ROW}).encode(),
                )
                process_record(record, Cache(), Consumer())
                self.assertEqual(effects, [('set', f'cdc:product:{UID}', ROW), ('commit', 8)])

                class BrokenCache:
                        def set(self, key, value):
                                raise ConnectionError('Redis unavailable')

                effects.clear()
                with self.assertRaises(ConnectionError):
                        process_record(record, BrokenCache(), Consumer())
                self.assertEqual(effects, [])


if __name__ == '__main__':
        unittest.main()
