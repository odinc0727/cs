Links:

- https://github.com/skywind3000/kcp
- https://docs.rs/kcp-ovo/latest/src/kcp_ovo/lib.rs.html#1-39

**KCP 的核心目标：在不可靠的数据报传输之上，提供可靠、有序、可控制延迟的数据传输。**

KCP 是一个 ARQ（Automatic Repeat reQuest，自动重传请求）可靠传输算法，并不直接负责 UDP Socket、连接建立或操作系统计时，本身不包含握手、连接认证、加密。

所以，实现可以分为两层：

- KCP Core：纯协议状态机，处理分片、序列号、ACK、滑动窗口、RTO、重传和拥塞控制。
- Transport：负责 UDP 收发、定时器、异步运行时和会话管理。

阶段性：

- [ ] 报文编解码
- [ ] 传输
- [ ] 分片重组
- [ ] 重传
- [ ] 流量与拥塞控制
- [ ] 网络集成
