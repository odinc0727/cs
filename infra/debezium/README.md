# PostgreSQL → Debezium → Kafka → Python → Redis

修改数据库，直接看到 Redis 跟着更新。首次启动同步已有商品，随后捕获提交后的 INSERT、UPDATE、DELETE。

```text
PostgreSQL products（uid UUIDv7）
        │ 初始快照 / WAL 逻辑复制，pgoutput
        ▼
Debezium PostgreSQL Connector（运行在 Kafka Connect 中）
        │ JSON，保留 op / before / after / source
        ▼
Kafka topic: cdc.public.products（1 个 partition）
        │ Python consumer group: cdc-redis-projector
        ▼
Redis string: cdc:product:<uid>（值是商品 JSON）
```

RabbitMQ 同时部署供其他消息队列练习，独立于这条 CDC 链路。Kafka 依赖 Java；RabbitMQ 依赖 Erlang。

## 当前环境

| 服务                     | 版本                               | 地址 / 数据                                                |
| ------------------------ | ---------------------------------- | ---------------------------------------------------------- |
| Kafka                    | 4.4.0，KRaft 单节点                | `127.0.0.1:9092`，控制器 `127.0.0.1:9093`                  |
| RabbitMQ                 | 4.4.0，Erlang 29.1.2               | AMQP `127.0.0.1:5672`                                      |
| RabbitMQ 管理页面        | management 插件                    | <http://127.0.0.1:15672>，`guest` / `guest`                |
| PostgreSQL               | 18.6                               | `127.0.0.1:55438`，数据库 `cdc_demo`                       |
| Kafka Connect / Debezium | Kafka 4.4.0 / Debezium 3.7.1.Final | <http://127.0.0.1:18083/connectors/cdc-products/status>    |
| Redis                    | 复用本机服务                       | `127.0.0.1:6379`，database 0，专用 key 前缀 `cdc:product:` |
| Python                   | 3.14                               | **统一使用 `cs/.venv`、`cs/pyproject.toml`、`cs/uv.lock`** |

Kafka、RabbitMQ 已通过 Homebrew 启动，登录后自动启动。其他 CDC 进程由本目录脚本管理，不设置开机自启。

## 启动与验证

全部 Python 命令从 `cs` 目录运行，编辑器直接打开 `cs` 即可识别共享环境：

```sh
cd /Users/gopher/Codespace/myrepo/cs
uv sync --locked
brew services start kafka
brew services start rabbitmq
uv run python debezium/manage.py up
uv run python debezium/manage.py status
```

`up` 会检查 Kafka/Redis，下载并校验 Debezium 插件，初始化独立 PostgreSQL，创建表和 publication，启动 Connect 和消费者。重复执行保留数据库、复制槽和消费进度，不重新格式化 Kafka。默认 Homebrew 路径 `/opt/homebrew`；其他路径可设置 `HOMEBREW_PREFIX`。

```sh
# 快照、增删改、重复业务值、事务回滚、消费者停机后追赶
uv run python debezium/smoke.py

# Kafka 协议收发；RabbitMQ 经 HTTP API 投递、出队和确认
uv run python debezium/smoke_brokers.py

# 事件解析及提交顺序的单元测试（从 debezium 子目录运行，也会找到 cs 的 uv 项目）
uv run --directory debezium python -m unittest discover -s tests -v
```

CDC smoke 只操作新建的 UUIDv7 测试商品，结束时删除该商品。broker smoke 使用 `cdc.broker-smoke` topic，RabbitMQ 临时测试队列在结束时清理。

## 亲手试一次

终端一观察消费者：

```sh
cd /Users/gopher/Codespace/myrepo/cs
tail -f debezium/.runtime/logs/consumer.log
```

终端二连接**示例实例 55438**，密码仅用于本机学习：

```sh
psql 'postgresql://cdc:cdc_local_only@127.0.0.1:55438/cdc_demo'
```

在同一个 psql 会话执行，`\gset` 把数据库生成的 UUIDv7 保存为变量：

```sql
INSERT INTO products (name, price_cents)
VALUES ('机械键盘', 19900)
RETURNING uid \gset

\echo 商品 uid = :uid

UPDATE products
SET price_cents = 15900, updated_at = now()
WHERE uid = :'uid';

SELECT * FROM products WHERE uid = :'uid';

DELETE FROM products WHERE uid = :'uid';
```

消费者日志依次出现 `SET`、`SET`、`DEL`。也可在删除前用 Redis 检查实际内容：

```sh
redis-cli --scan --pattern 'cdc:product:*'
redis-cli GET 'cdc:product:<替换为刚才的 uid>'
```

观察 Kafka 原始事件：

```sh
kafka-console-consumer --bootstrap-server 127.0.0.1:9092 \
  --topic cdc.public.products --from-beginning --property print.key=true
```

| `op`            | 来源                     | Python 行为                                   |
| --------------- | ------------------------ | --------------------------------------------- |
| `r`             | 首次快照                 | 把 `after` 写入 Redis                         |
| `c`             | INSERT                   | 把 `after` 写入 Redis                         |
| `u`             | UPDATE                   | 用 `after` 覆盖 Redis                         |
| `d`             | DELETE                   | 根据 Kafka 消息 key 中的 `uid` 删除 Redis key |
| 消息值为 `null` | 删除后的 Kafka tombstone | 跳过写入，正常提交 offset                     |

价格使用整数分 `price_cents`，避免教学时混入 decimal 的编码处理。

## 停止、恢复与日志

```sh
cd /Users/gopher/Codespace/myrepo/cs

# 暂停消费者，期间改数据库，然后恢复：会从上次提交的 offset 继续
uv run python debezium/manage.py stop-consumer
uv run python debezium/manage.py start-consumer

# 停止本示例的 consumer、Connect、独立 PostgreSQL；保留数据
uv run python debezium/manage.py down
uv run python debezium/manage.py up

# Kafka / RabbitMQ 单独管理
brew services list
brew services stop kafka
brew services stop rabbitmq
```

- 示例日志：`debezium/.runtime/logs/consumer.log`、`connect.log`、`postgres.log`。
- 示例 PG 数据：`debezium/.runtime/postgres`；复制槽 `cdc_products_slot`。
- Connect 的 WAL 进度：`debezium/.runtime/connect.offsets`；Python 的消费进度存在 Kafka consumer group 中。这是两个不同的 offset。
- Kafka 配置：`/opt/homebrew/etc/kafka/server.properties`；数据：`/opt/homebrew/var/lib/kraft-combined-logs`。
- RabbitMQ 配置：`/opt/homebrew/etc/rabbitmq/rabbitmq.conf`，日志：`/opt/homebrew/var/log/rabbitmq`。
- 本次已将 Kafka、RabbitMQ 的消息与管理端口限制为本机监听；停用了 Homebrew 默认启用的 STOMP、MQTT、Stream 插件。RabbitMQ 节点为 `rabbit@localhost`。

## 这个示例保证到哪里

这是**最终一致的数据投影**，数据库提交后 Redis 可能短暂滞后。Redis 写成功才同步提交当前 Kafka 消息的 offset；写失败或坏消息会让消费者退出，不吞掉消息继续提交。故障恢复可能重复投递，顺序执行 `SET` / `DEL` 可重复应用。它不是跨 PostgreSQL、Kafka、Redis 的原子事务。

限定单表、单 partition、单个消费者顺序处理，Redis key 不设 TTL。不要让其他程序往同一前缀写旧值。本例用于普通小商品行；未扩展复杂 schema 演进、TOAST 大字段、主从切换或多实例并发投影。

不要对这张演示表执行 `TRUNCATE`：当前消费者会明确拒绝该事件，避免悄悄留下整表的旧 Redis key。使用 `DELETE` 逐行演示。

清空/淘汰 Redis 数据后，已有 consumer group 不会自动重放历史数据；需要设计全量重建，确保 Kafka 保有完整历史，或重新做数据库快照。Kafka 默认保留 7 天，示例复制槽的 WAL 保留上限为 1GB，超限后也可能需要重新快照。不要随手删除复制槽或 `.runtime/connect.offsets` 来“重置”。

首次快照的 smoke 检查依赖初始 `r` 事件仍保留在 Kafka，长时间后过期会明确报错。数据库账号为独立实例的本地演示超级用户，未做生产权限划分。

## 文件与参考

- `consumer.py`：解析 Debezium 事件，写 Redis，再提交 Kafka offset。
- `manage.py`：本地进程管理、独立 PG 初始化、插件下载校验。
- `config/`：Kafka Connect worker 与 PostgreSQL connector 配置。
- `sql/init.sql`：表、初始数据、publication。
- `tests/`、`smoke.py`、`smoke_brokers.py`：单元和实际链路验证。

参考：[Debezium PostgreSQL connector](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)、[Kafka Connect](https://kafka.apache.org/41/kafka-connect/user-guide/)、[RabbitMQ Homebrew 安装说明](https://www.rabbitmq.com/docs/install-homebrew)。
