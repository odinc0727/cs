# Go ↔ Python，通过 RabbitMQ 双向发送 Hello

两个独立服务使用 AMQP 0-9-1 和 JSON 通信，没有互相调用 HTTP。

```text
Go 发布 Hello world from Go      → RabbitMQ 队列 to.python → Python 消费并打印
Python 发布 Hello world from Python → RabbitMQ 队列 to.go  → Go 消费并打印
```

这是异步单向消息的双向演示，不是等待返回值的 RPC：发送方提交消息，接收方执行打印。两个方向相互独立。每个服务启动时发送一次，随后每 5 秒发送一次，同时持续消费。发送由定时器触发，不会收到一条再回复一条造成无限循环。

启动 Go 服务：

```sh
cd /Users/gopher/Documents/Codex/2026-09-16/n-ne/outputs/go-python-rabbitmq/go-service
go mod tidy
RABBITMQ_URL='amqp://guest:guest@localhost:5672/' go run .
```

启动 Python 服务：

```sh
cd /Users/gopher/Documents/Codex/2026-09-16/n-ne/outputs/go-python-rabbitmq/python-service
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
RABBITMQ_URL='amqp://guest:guest@localhost:5672/' .venv/bin/python main.py
```

消息格式：

```json
{"from":"Go","text":"Hello world from Go"}
```

## 如果需要 Python 返回结果给 Go

可在这个例子上增加 RabbitMQ RPC：请求设置 `reply_to`（回复队列）和 `correlation_id`（请求 ID）；接收方执行后把结果发到回复队列，并原样带回请求 ID。调用方关联结果并设置超时。反方向同理。本例刻意只展示最基本的双向消息收发。

## 示例边界与验证

队列为持久化队列，但消息未设置持久化、没有发布确认或断线重连；服务启动时以及之后每 5 秒发送一条消息。ACK 不代表严格只执行一次，断线重投可能重复。生产环境应按需求补充持久化、发布确认、幂等、重连和失败处理。demo 凭据仅用于本地演示，端口只绑定本机。

参考官方教程：
- https://www.rabbitmq.com/tutorials/tutorial-one-go
- https://www.rabbitmq.com/tutorials/tutorial-one-python
- https://www.rabbitmq.com/tutorials/tutorial-six-python

两端声明均设置 durable=true，避免默认禁用的 transient_nonexcl_queues。队列持久化与消息持久化是两回事。若之前已存在同名非持久化队列，会报 PRECONDITION_FAILED；请先检查旧队列中是否有需要保留的消息，再决定迁移或使用新队列名，不要直接删除业务队列。

定时发送实现：Go 使用 `time.NewTicker` 和 `select` 同时处理定时发送及接收；Python 使用 `connection.call_later` 在 Pika 事件循环中调度发送，不使用阻塞 sleep。停止进程即可停止定时发送。

两个服务均保留时间戳：发送绿色、接收青色、启动提示黄色、错误红色。日志写入 stderr；重定向到文件时自动关闭颜色，也可以设置 `NO_COLOR=1` 关闭。修改后重启两个服务即可。
