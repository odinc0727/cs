# Reactor TCP Echo 示例

[C23 + Libevent](reactor.c) 和 [Java NIO](ReactorServer.java) 都用单线程事件循环，把收到的 TCP 字节原样回显。
两版都监听 `127.0.0.1:8080`，切换版本前先按 Ctrl+C 停掉当前服务器。

## 运行

在本目录执行。C 版需要支持 `-std=c23` 的编译器、Libevent 开发库和 `pkg-config`。

```sh
cc -std=c23 -Wall -Wextra -Wpedantic reactor.c -o /tmp/reactor-libevent $(pkg-config --cflags --libs libevent)
/tmp/reactor-libevent
```

Java 版使用 JDK 17 或更新版本，只用标准库。

```sh
java ReactorServer.java
```

另开一个终端运行 `nc 127.0.0.1 8080`。输入一行并回车，然后再输入一行，可以观察同一条连接上的多次回显。
也可以同时打开第二个客户端，观察服务器如何在一个线程上处理多个连接。

## 对照源码

| 阶段           | C23 + Libevent                                                      | Java NIO                                                                                                               |
| -------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| 等待与分发     | `event_base_dispatch()` 负责等待和分发回调                          | `selector.select()` 等待就绪，`runEventLoop()` 从 `selectedKeys()` 取出 `SelectionKey`，调用 `attachment()` 上的处理器 |
| 接受连接       | `evconnlistener` 接受连接，`on_accept()` 创建该连接的 `bufferevent` | 监听 Channel 注册 `OP_ACCEPT`，`accept()` 接受连接后，把非阻塞客户端 Channel 注册为 `OP_READ`                          |
| 读入数据       | Libevent 已把字节读进输入缓冲区，`on_read()` 把它们移到输出缓冲区   | `Handler.read()` 收到可读通知后调用 `SocketChannel.read()`，再用 `flip()` 让 `ByteBuffer` 可供写出                     |
| 回显并恢复读取 | Libevent 负责非阻塞写入，输出缓冲区清空时 `on_write()` 恢复读取     | `Handler.write()` 根据 `ByteBuffer` 的位置续写，写完后 `clear()`，并从 `OP_WRITE` 切回 `OP_READ`                       |

Java 版里，`interestOps()` 决定下一轮关注哪些操作，`isReadable()` 和 `isWritable()` 检查这一轮哪些操作就绪。
`write()` 可能只写出一部分，甚至返回 0。缓冲区有剩余字节时继续关注 `OP_WRITE`。缓冲区清空后切回 `OP_READ`，避免空闲连接反复收到可写通知。
两版都等当前这批回显交给内核后才继续从该连接读取，避免客户端接收太慢时，待发送数据一直积压在应用缓冲区。
[SelectionKey](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/nio/channels/SelectionKey.html) · [SocketChannel](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/nio/channels/SocketChannel.html)

C 版启动时会打印实际使用的事件后端。在 Linux 上，可以先按 Ctrl+C 退出，再用 `EVENT_NOEPOLL=1 /tmp/reactor-libevent` 启动，观察 Libevent 如何选择其他后端。
