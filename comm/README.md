1. 阻塞 IO
- accept 等连接
- read   等数据
- write  等缓冲

2. fork
- 线程代价？（栈开销、调度开销、锁竞争） -- C10K

3. 五种 IO 模型
- 阻塞
- 非阻塞
- 多路复用 select - poll - epoll
- 信号驱动
- 异步

4. epoll
**epoll**
- epoll_create
- epoll_ctl 把 fd 放到内核红黑树，不必每次拷贝
- epoll_wait 拿到已经就绪的 fd

**触发模式**
- LT
- ET：必须配合非阻塞 IO

**惊群**
多个 worker 监听一个 listen_fd，一个连接来，所有 worker 被唤醒，但只有一个 accept 成功。
> EPOLLEXCLUSIVE 排他唤醒

5. Reactor 模型

6. 其他情况
- fd 数量少，活跃数多
> 可能 select 会更快

所有 IO 多路复用都依赖于 socket 的等待队列。

Linux 5.1 之后向 io_uring 倾斜，但目前 epoll 在生产环境还是优秀。

单机连接数真正的限制往往是 fd 上限、内核内存、TCP 缓冲区、端口范围等。
