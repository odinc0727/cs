"""Manage only this demo's PostgreSQL, Connect and Python processes.

Kafka/RabbitMQ are managed separately with brew services. No data is deleted.
"""

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import tarfile
import time
from contextlib import closing
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / '.runtime'
BREW = Path(os.getenv('HOMEBREW_PREFIX', '/opt/homebrew'))
PG = BREW / 'opt/postgresql@18/bin'
KAFKA = BREW / 'opt/kafka/bin'
VERSION = '3.7.1.Final'
DATABASE_URL = 'postgresql://cdc:cdc_local_only@127.0.0.1:55438/cdc_demo'


def run(args, **kwargs):
        return subprocess.run([str(arg) for arg in args], check=True, cwd=ROOT, **kwargs)


def java_env():
        return {
                **os.environ,
                'JAVA_HOME': str(BREW / 'opt/openjdk/libexec/openjdk.jdk/Contents/Home'),
                'KAFKA_HEAP_OPTS': '-Xms128m -Xmx512m',
                'LOG_DIR': str(RUNTIME / 'logs'),
        }


def wait_for(check, description, timeout=90):
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
                try:
                        if check():
                                return
                except (OSError, URLError, ValueError) as exc:
                        last = exc
                time.sleep(0.5)
        raise TimeoutError(f'Timed out waiting for {description}: {last}; see .runtime/logs/')


def alive(name):
        pidfile = RUNTIME / f'{name}.pid'
        if not pidfile.exists():
                return False
        pid = int(pidfile.read_text())
        result = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], check=False, capture_output=True, text=True)
        # Validate process identity before trusting a PID that macOS might have reused.
        return (
                result.returncode == 0
                and str(ROOT) in result.stdout
                and ('consumer.py' if name == 'consumer' else 'ConnectStandalone') in result.stdout
        )


def start(name, args):
        if alive(name):
                print(f'{name}: already running')
                return
        with (RUNTIME / 'logs' / f'{name}.log').open('ab') as log:
                proc = subprocess.Popen(
                        [str(arg) for arg in args],
                        cwd=ROOT,
                        env=java_env(),
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                )
        (RUNTIME / f'{name}.pid').write_text(str(proc.pid))
        time.sleep(1)
        if proc.poll() is not None:
                raise RuntimeError(f'{name} exited; see .runtime/logs/{name}.log')
        print(f'{name}: started (pid={proc.pid})')


def stop(name):
        if alive(name):
                pid = int((RUNTIME / f'{name}.pid').read_text())
                os.kill(pid, signal.SIGTERM)
                wait_for(lambda: not alive(name), f'{name} shutdown', timeout=45)
                print(f'{name}: stopped')


def install_plugin():
        plugin = RUNTIME / 'plugins' / 'debezium-connector-postgres'
        if (plugin / f'debezium-connector-postgres-{VERSION}.jar').exists():
                return
        base = f'https://repo.maven.apache.org/maven2/io/debezium/debezium-connector-postgres/{VERSION}'
        filename = f'debezium-connector-postgres-{VERSION}-plugin.tar.gz'
        archive = RUNTIME / filename
        print(f'Downloading Debezium {VERSION}', flush=True)
        run(
                [
                        'curl',
                        '--fail',
                        '--location',
                        '--retry',
                        '3',
                        '--connect-timeout',
                        '15',
                        '--max-time',
                        '300',
                        '--output',
                        archive,
                        f'{base}/{filename}',
                ]
        )
        with urlopen(f'{base}/{filename}.sha512', timeout=30) as response:
                expected = response.read().decode().split()[0].lower()
        if hashlib.sha512(archive.read_bytes()).hexdigest() != expected:
                raise ValueError('Debezium archive checksum mismatch')
        (RUNTIME / 'plugins').mkdir(exist_ok=True)
        with tarfile.open(archive) as package:
                package.extractall(RUNTIME / 'plugins', filter='data')


def postgres_up():
        pgdata = RUNTIME / 'postgres'
        if not (pgdata / 'PG_VERSION').exists():
                password_file = RUNTIME / 'pg-password'
                password_file.write_text('cdc_local_only\n')
                password_file.chmod(0o600)
                run(
                        [
                                PG / 'initdb',
                                '-D',
                                pgdata,
                                '-U',
                                'cdc',
                                '--encoding=UTF8',
                                '--locale=C',
                                '--auth-local=trust',
                                '--auth-host=scram-sha-256',
                                '--pwfile',
                                password_file,
                        ],
                        stdout=subprocess.DEVNULL,
                )
                with (pgdata / 'postgresql.conf').open('a') as config:
                        config.write(
                                f"\nport=55438\nlisten_addresses='127.0.0.1'\nwal_level=logical\n"
                                f"max_replication_slots=4\nmax_wal_senders=4\nmax_slot_wal_keep_size='1GB'\n"
                                f"unix_socket_directories='{RUNTIME}'\n"
                        )
                password_file.unlink()
        status = subprocess.run([str(PG / 'pg_ctl'), '-D', str(pgdata), 'status'], check=False, capture_output=True)
        if status.returncode:
                run([PG / 'pg_ctl', '-D', pgdata, '-l', RUNTIME / 'logs/postgres.log', '-w', 'start'])
        env = {**os.environ, 'PGPASSWORD': 'cdc_local_only'}
        result = run(
                [
                        PG / 'psql',
                        '-X',
                        '-h',
                        '127.0.0.1',
                        '-p',
                        '55438',
                        '-U',
                        'cdc',
                        '-d',
                        'postgres',
                        '-Atc',
                        "SELECT 1 FROM pg_database WHERE datname='cdc_demo'",
                ],
                env=env,
                capture_output=True,
                text=True,
        )
        if result.stdout.strip() != '1':
                run([PG / 'createdb', '-h', '127.0.0.1', '-p', '55438', '-U', 'cdc', 'cdc_demo'], env=env)
        run(
                [PG / 'psql', '-X', DATABASE_URL, '-v', 'ON_ERROR_STOP=1', '-f', ROOT / 'sql/init.sql'],
                stdout=subprocess.DEVNULL,
        )


def connector_status():
        with urlopen('http://127.0.0.1:18083/connectors/cdc-products/status', timeout=3) as response:
                status = json.load(response)
        tasks = status.get('tasks', [])
        return (
                status['connector']['state'] == 'RUNNING'
                and bool(tasks)
                and all(task['state'] == 'RUNNING' for task in tasks)
        )


def up():
        from kafka import KafkaAdminClient
        from kafka.admin import NewTopic
        from kafka.errors import TopicAlreadyExistsError
        from redis import Redis

        RUNTIME.mkdir(exist_ok=True)
        (RUNTIME / 'logs').mkdir(exist_ok=True)
        cache = Redis.from_url('redis://127.0.0.1:6379/0', socket_connect_timeout=5)
        cache.ping()
        cache.close()
        with closing(KafkaAdminClient(bootstrap_servers='127.0.0.1:9092', client_id='cdc-setup')) as admin:
                try:
                        admin.create_topics([NewTopic('cdc.public.products', num_partitions=1, replication_factor=1)])
                except TopicAlreadyExistsError:
                        pass
                topic = admin.describe_topics(['cdc.public.products'])[0]
                if len(topic['partitions']) != 1:
                        raise ValueError('Demo requires a one-partition cdc.public.products topic')
        install_plugin()
        postgres_up()
        config = (ROOT / 'config/connect-standalone.properties').read_text().replace('@ROOT@', str(ROOT))
        (RUNTIME / 'connect.properties').write_text(config)
        start(
                'connect',
                [KAFKA / 'connect-standalone', RUNTIME / 'connect.properties', ROOT / 'config/postgres.properties'],
        )
        wait_for(connector_status, 'Debezium connector and task RUNNING')
        start('consumer', [sys.executable, '-u', ROOT / 'consumer.py'])
        status()


def down():
        stop('consumer')
        stop('connect')
        if (RUNTIME / 'postgres/PG_VERSION').exists():
                result = subprocess.run(
                        [str(PG / 'pg_ctl'), '-D', str(RUNTIME / 'postgres'), 'status'],
                        check=False,
                        capture_output=True,
                )
                if result.returncode == 0:
                        run([PG / 'pg_ctl', '-D', RUNTIME / 'postgres', '-m', 'fast', '-w', 'stop'])
        print('Kafka/RabbitMQ/Redis and existing PostgreSQL are left running; demo data is preserved.')


def status():
        import psycopg
        from kafka import KafkaAdminClient
        from redis import Redis

        checks = {
                'PostgreSQL 55438': lambda: psycopg.connect(DATABASE_URL, connect_timeout=3),
                'Kafka 9092': lambda: KafkaAdminClient(bootstrap_servers='127.0.0.1:9092'),
                'Redis 6379': lambda: Redis(host='127.0.0.1', socket_connect_timeout=3).ping(),
                'Debezium Connect 18083': connector_status,
                'Python consumer': lambda: alive('consumer'),
        }
        good = True
        for name, check in checks.items():
                try:
                        result = check()
                        healthy = bool(result)
                        if hasattr(result, 'close'):
                                result.close()
                        print(f'{name}: {"OK" if healthy else "NOT RUNNING"}')
                        good = good and healthy
                except Exception as exc:  # noqa: BLE001 -- report all independent service checks
                        good = False
                        print(f'{name}: ERROR {exc}')
        return good


if __name__ == '__main__':
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('command', choices=['up', 'down', 'status', 'start-consumer', 'stop-consumer'])
        command = parser.parse_args().command
        if command == 'up':
                up()
        elif command == 'down':
                down()
        elif command == 'status':
                sys.exit(0 if status() else 1)
        elif command == 'start-consumer':
                start('consumer', [sys.executable, '-u', ROOT / 'consumer.py'])
        else:
                stop('consumer')
