# 本机验证记录：2026-11-13

环境：macOS Apple Silicon；Python 3.14.7（cs/.venv）、PostgreSQL 18.6、Kafka 4.4.0、OpenJDK 27.0.1、Debezium 3.7.1.Final、Redis、RabbitMQ 4.4.0、Erlang 29.1.2。

已实际执行并通过：

- `uv run --directory debezium python -m unittest discover -s tests -v`：5 项测试，包括 r/c/u/d/tombstone、schema envelope、非法事件及 Redis 写失败不提交 offset。
- `uv run python debezium/smoke.py`：运行中 connector 不过滤任何操作、Kafka 中初始 op=r 与 Redis 快照一致、UUIDv7/中文/零价格、新增、更新、重复业务值更新、事务回滚、真实停止消费者后数据库写入再恢复追赶、删除。
- `uv run python debezium/smoke_brokers.py`：Kafka 原生客户端发送并读回；RabbitMQ HTTP API 投递、出队并确认；测试队列已清理。
- `manage.py down` 后 `up`，及重复 `up`：保留数据库、复制槽、Connect offset 和 consumer group，现有进程不重复启动。
- Ruff lint、format check 和 `git diff --check`：通过。首次格式检查受沙箱缓存写入限制，之后禁用缓存重新检查通过。
- 最终 `manage.py status`：PostgreSQL 55438、Kafka 9092、Redis 6379、Connect 18083、Python consumer 全部 OK。
- `brew services list`：Kafka、RabbitMQ、原有 PostgreSQL、Redis 均 started；RabbitMQ diagnostics ping 成功，最终 AMQP/HTTP/distribution listener 均为 127.0.0.1。

审查及修正：独立只读代码审查发现 Debezium 默认 skipped.operations=t 会绕过消费者的 TRUNCATE 拒绝逻辑。先新增运行时配置断言并观察失败，再加入 skipped.operations=none、重启 Connect，完整回归通过。未实际 TRUNCATE 示例表；拒绝逻辑由单元测试覆盖，上游传递设置由运行中的 connector 配置核对。

环境调整：用户要求统一 uv 环境后，依赖迁入 cs/pyproject.toml、cs/uv.lock、cs/.venv，删除本次创建的 debezium 独立 uv 文件及虚拟环境。保留用户原有 redis/README.md 和 UNIX环境编程 的改动，未提交 Git。

安装附带处理：Homebrew 自动更新在 gromgit/fuse tap 留下 rebase 冲突，自动审批首次拒绝 abort。取得用户明确许可后中止本次 rebase，确认回到 main 且工作区干净；未尝试合并或改写该 tap 的用户提交。

限制：这是本机单节点演示，验证不等于生产故障完备性。Redis 持久化故障、数据全量重建、Kafka/WAL 保留过期等边界见 README。
