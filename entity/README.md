# Go HTTP 请求链路示例

一个 `GET /items/{uid}` 接口，串起限流、身份认证、权限校验、Redis、PostgreSQL 和 RabbitMQ。Go 代码只导入标准库，复用仓库根目录的 Go 模块。

## 运行

准备本机的 PostgreSQL、Redis 和启用 management 插件的 RabbitMQ，并让 `psql`、`redis-cli` 在 `PATH` 上可用。下面的命令从 `cs` 根目录运行：

```sh
PGHOST=127.0.0.1 PGDATABASE=postgres go run ./entity
```

PostgreSQL 使用 libpq 的连接设置，例如 `PGPORT`、`PGUSER` 和 `.pgpass`。查询用一条 SQL `VALUES` 提供固定记录，直接在 PostgreSQL 执行，无需建表。

| 设置                                  | 默认值                                             |
| ------------------------------------- | -------------------------------------------------- |
| `ENTITY_ADDR`                         | `127.0.0.1:8080`                                   |
| `REDIS_HOST` / `REDIS_PORT`           | `127.0.0.1` / `6379`                               |
| `ENTITY_CACHE_PREFIX`                 | `cs:entity:`                                       |
| `RABBITMQ_HTTP_URL`                   | `http://127.0.0.1:15672`                           |
| `RABBITMQ_USER` / `RABBITMQ_PASSWORD` | `guest` / `guest`，本机演示凭据                    |
| `ENTITY_QUEUE`                        | `cs.entity.lookups`，启动时声明，默认 vhost 为 `/` |

Redis 如需密码，可由环境传入 `REDISCLI_AUTH`。缓存 TTL 为 60 秒。RabbitMQ 队列最多保留 1000 条消息，消息 TTL 为 10 分钟。发布使用管理 HTTP API，便于在标准库示例中观察消息路由。PostgreSQL 和 Redis 的计时包含客户端进程启动与建立连接的时间。

## 观察请求

```sh
url='http://127.0.0.1:8080/items/019b4d3b-77d0-7f43-9d7e-0c5272be81a6'
curl -i -H 'Authorization: Bearer demo-reader' "$url"
curl -i -H 'Authorization: Bearer demo-reader' "$url"
curl -i "$url"
curl -i -H 'Authorization: Bearer demo-viewer' "$url"
```

- 冷缓存返回 `source: postgres`，之后在 TTL 内返回 `source: redis`。每次成功查找都尝试发布一条 `item.lookup` 事件，可以在 RabbitMQ 管理页面查看。
- 后两次请求分别得到 `401` 和 `403`。同一 IP 每 10 秒最多 20 次，认证通过的同一用户每 10 秒最多 5 次，超过后返回 `429` 和 `Retry-After`。
- 未知的有效 UUID 返回 `404`。使用 `PGPORT=1 ENTITY_CACHE_PREFIX=cs:entity:dbfail:` 重新启动，再查固定记录，可以复现数据库连接失败。访问日志和业务错误日志使用相同的 `request_id`、`trace_id`，客户端收到通用 `500`。
- Redis 操作或 RabbitMQ 发布失败时记一条警告，已经查到的数据仍可返回。RabbitMQ 队列在启动阶段声明，方便区分启动配置失败和请求期间的发布失败。

每个响应带 `X-Request-ID` 和 `X-Trace-ID`。传入有效的 W3C `traceparent` 版本 `00` 可延续其中的 Trace ID。访问日志包含 `duration_ms` 和 `steps`，其中 `parent` 指向上层阶段。Service 的耗时会包含其内部的 Redis、PostgreSQL 和 RabbitMQ 调用，总耗时在请求入口单独测量。

## 文件

| 文件                                       | 职责                                           |
| ------------------------------------------ | ---------------------------------------------- |
| `main.go`                                  | 配置、声明演示队列、启动服务                   |
| `middleware.go`                            | 路由、限流、认证、权限校验和 panic 恢复        |
| `timing.go`                                | Request ID、Trace ID、逐阶段计时和访问日志     |
| `item.go`                                  | 读取路径、缓存回填、发布事件和 HTTP 错误映射   |
| `postgres.go` / `redis.go` / `rabbitmq.go` | 三个依赖的接入                                 |
| `entity_test.go`                           | 用 `httptest` 检查缓存命中、错误日志关联和限流 |

`go test -race ./entity` 可以验证 HTTP 链路，测试用替身提供下游响应，无需启动三个服务。
