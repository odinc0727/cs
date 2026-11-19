/*
 * event_base 管理事件注册和回调分发。
 * epoll、poll 等后端报告哪些 fd 已就绪，Libevent 据此执行非阻塞 I/O，再调用本文件注册的回调。
 * 所有回调共用运行事件循环的线程。某个回调阻塞时，其他连接也得等。
 */
#include <arpa/inet.h>
#include <event2/bufferevent.h>
#include <event2/event.h>
#include <event2/listener.h>
#include <event2/util.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

// 执行到这里时，Libevent 已从 socket 读取字节，并把它们放进了输入缓冲区
static void on_read(struct bufferevent* connection, void* context) {
        (void)context;

        // 暂停这条连接的读取，避免客户端发送得比接收快时，回显数据不断积压
        // bufferevent_write_buffer() 将现有字节从输入移到输出，Libevent 在 socket 可写时发送
        if (bufferevent_disable(connection, EV_READ) < 0 ||
            bufferevent_write_buffer(connection, bufferevent_get_input(connection)) < 0) {
                bufferevent_free(connection);
        }
}

static void on_write(struct bufferevent* connection, void* context) {
        (void)context;

        // 写低水位默认为 0
        // 输出缓冲区清空时，这一批字节已交给内核，可以恢复读取
        if (bufferevent_enable(connection, EV_READ) < 0) {
                bufferevent_free(connection);
        }
}

static void on_connection_event(struct bufferevent* connection, short events, void* context) {
        (void)context;

        // 对端结束发送时会读到 EOF
        // 正常回显中，恢复读取前已把上一批数据交给内核
        // BEV_OPT_CLOSE_ON_FREE 让释放 bufferevent 时一并关闭这条连接的 fd
        if (events & (BEV_EVENT_EOF | BEV_EVENT_ERROR)) {
                bufferevent_free(connection);
        }
}

// 监听 socket 就绪后，evconnlistener 负责 accept，并将非阻塞的客户端 fd 交给这个回调
static void on_accept(struct evconnlistener* listener, evutil_socket_t fd, struct sockaddr* peer, int peer_length,
                      void* context) {
        (void)peer;
        (void)peer_length;
        (void)context;

        // 每条连接都有自己的 bufferevent、读写缓冲区和回调，统一挂在同一个事件循环上
        struct event_base*  base       = evconnlistener_get_base(listener);
        struct bufferevent* connection = bufferevent_socket_new(base, fd, BEV_OPT_CLOSE_ON_FREE);
        if (connection == nullptr) {
                // 创建失败时，fd 仍由当前回调负责关闭
                evutil_closesocket(fd);
                return;
        }

        // 读高水位设为 64 KiB
        // 输入缓冲区达到高水位时，Libevent 会暂停从 socket 取数据
        constexpr size_t read_buffer_limit = 64 * 1024;
        bufferevent_setwatermark(connection, EV_READ, 0, read_buffer_limit);
        bufferevent_setcb(connection, on_read, on_write, on_connection_event, nullptr);
        if (bufferevent_enable(connection, EV_READ | EV_WRITE) < 0) {
                bufferevent_free(connection);
        }
}

// 监听器遇到不可重试的错误时，记录失败并退出事件循环
static void on_listener_error(struct evconnlistener* listener, void* context) {
        bool* failed = context;
        *failed      = true;
        perror("listener");
        event_base_loopbreak(evconnlistener_get_base(listener));
}

int main(void) {
        // 对端可能在回显期间断开
        // 忽略 SIGPIPE，让写失败按连接错误处理
        if (signal(SIGPIPE, SIG_IGN) == SIG_ERR) {
                perror("signal");
                return EXIT_FAILURE;
        }

        // 创建 Reactor 的事件循环
        // Libevent 在这里选择可用的 I/O 后端
        struct event_base* base = event_base_new();
        if (base == nullptr) {
                fputs("event_base_new failed\n", stderr);
                return EXIT_FAILURE;
        }

        constexpr uint16_t port    = 8080;
        struct sockaddr_in address = {
                .sin_family = AF_INET,
                .sin_port   = htons(port),
                .sin_addr   = {.s_addr = htonl(INADDR_LOOPBACK)},
        };
        // 创建并注册监听 socket
        // 后续接受的新连接交给 on_accept()
        bool                   listener_failed = false;
        struct evconnlistener* listener =
                evconnlistener_new_bind(base, on_accept, &listener_failed, LEV_OPT_CLOSE_ON_FREE | LEV_OPT_REUSEABLE,
                                        -1, (struct sockaddr*)&address, sizeof(address));
        if (listener == nullptr) {
                perror("listener setup");
                event_base_free(base);
                return EXIT_FAILURE;
        }
        evconnlistener_set_error_cb(listener, on_listener_error);

        printf("Listening on 127.0.0.1:%u (%s)\n", (unsigned int)port, event_base_get_method(base));
        fflush(stdout);

        // 反复等待就绪事件并分发回调
        // 收到退出请求、没有待处理事件或发生错误时返回
        int result = event_base_dispatch(base);
        evconnlistener_free(listener);
        event_base_free(base);
        return result == 0 && !listener_failed ? EXIT_SUCCESS : EXIT_FAILURE;
}
