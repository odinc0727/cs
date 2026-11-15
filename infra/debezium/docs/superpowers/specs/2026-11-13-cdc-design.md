# 本地 CDC 示例

用户已选择 Python 数据同步版，并授权开始及本地部署 Kafka、RabbitMQ。

目标：PostgreSQL products 表首次快照及后续增删改经 Debezium、Kafka 后自动写入 Redis；可运行演示并验证停止后追赶。

方案：Homebrew 安装 Kafka/Java、RabbitMQ/Erlang，作为本地服务。CDC 在目录内使用独立 PostgreSQL 18 实例（55438），不改现有 5432 的配置。Kafka 使用 9092，Kafka Connect standalone 使用 18083，Redis 使用现有 6379。RabbitMQ 独立运行，供其他消息队列练习，不接入此 CDC 链路。

考虑过缓存失效版（只 DEL，需要应用查询回填）、数据同步版（能直接看到增删改），用户选择后者。与容器部署相比，本机部署复用现有环境，但需要 Java 和本机进程管理。

约束：数据库主键 uid uuid，默认 uuidv7()；所有示例资源使用 cdc 前缀，Redis 使用 cdc:product:<uid>。商品价格用整数分 price_cents，避免 decimal 二进制编码影响教学。单 topic、单 partition、单消费者，按顺序 SET/DEL，写 Redis 成功后显式同步提交 Kafka offset。异常停止不跳过坏消息，允许重试造成的重复事件。演示是最终一致的数据投影，无 TTL；不支持用清空 Redis 后沿旧 offset 直接恢复全部数据。TRUNCATE 必须明确拒绝，不默默提交。

交付：SQL、Kafka Connect 配置、消费者、管理脚本、端到端 smoke、中文 README 与验证结果。用户指定依赖统一加入 cs/pyproject.toml、cs/uv.lock，并使用 cs/.venv，debezium 不单独建 uv 项目。运行数据留在 debezium/.runtime，不提交。保留现有文件，不自动提交 Git。
