// 用 NIO 的 Selector（IO multiplexing） + ServerSocketChannel + SocketChannel（非阻塞） + SelectionKey（事件） 实现 Reactor 模型（事件分发）
// 本质上是让线程不是阻塞在某一个连接的 Read() 上，而是阻塞在 selector.select() 上。
//
// Selector 报告 Channel 的就绪状态，实际读写由处理器发起。

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.ByteBuffer;
import java.nio.channels.SelectionKey;
import java.nio.channels.Selector;
import java.nio.channels.ServerSocketChannel;
import java.nio.channels.SocketChannel;

public class ReactorServer {

        public static void main(String[] args) throws IOException {
                var address = new InetSocketAddress("127.0.0.1", 8080);
                try (
                        Selector selector = Selector.open();
                        ServerSocketChannel listener =
                                ServerSocketChannel.open()
                ) {
                        listener.configureBlocking(false);
                        listener.bind(address);
                        // 监听 Channel 关心接受连接的事件，并把 accept 处理器挂到注册键上。
                        listener.register(
                                selector,
                                SelectionKey.OP_ACCEPT,
                                (EventHandler) ReactorServer::accept
                        );
                        System.out.println(
                                "Listening on " +
                                        address.getHostString() +
                                        ":" +
                                        address.getPort()
                        );

                        try {
                                runEventLoop(selector);
                        } finally {
                                // 关闭 Selector 会注销注册键。仍打开的客户端 Channel 需要显式关闭。
                                for (SelectionKey key : selector.keys()) {
                                        if (
                                                key.channel() instanceof
                                                        SocketChannel client
                                        ) {
                                                closeClient(client);
                                        }
                                }
                        }
                }
        }

        private interface EventHandler {
                void handle(SelectionKey key) throws IOException;
        }

        private static void runEventLoop(Selector selector) throws IOException {
                while (!Thread.currentThread().isInterrupted()) {
                        // 等待的是所有已注册 Channel 的就绪事件。处理器在当前线程依次执行。
                        selector.select();
                        var readyKeys = selector.selectedKeys().iterator();
                        while (readyKeys.hasNext()) {
                                SelectionKey key = readyKeys.next();
                                // 从本轮就绪集合移除。Channel 仍然注册在 Selector 上。
                                readyKeys.remove();
                                if (!key.isValid()) {
                                        continue;
                                }

                                EventHandler handler =
                                        (EventHandler) key.attachment();
                                try {
                                        handler.handle(key);
                                } catch (IOException e) {
                                        if (
                                                key.channel() instanceof
                                                        SocketChannel client
                                        ) {
                                                System.err.println(
                                                        "Client I/O: " +
                                                                e.getMessage()
                                                );
                                                closeClient(client);
                                        } else {
                                                throw e;
                                        }
                                }
                        }
                }
        }

        private static void accept(SelectionKey key) throws IOException {
                var listener = (ServerSocketChannel) key.channel();
                SocketChannel client = listener.accept();
                if (client == null) {
                        return;
                }

                try {
                        // 新连接先关注可读。每条连接有一个独立的 Handler 保存自己的缓冲状态。
                        client.configureBlocking(false);
                        client.register(
                                key.selector(),
                                SelectionKey.OP_READ,
                                new Handler()
                        );
                } catch (IOException e) {
                        System.err.println(
                                "Client registration: " + e.getMessage()
                        );
                        closeClient(client);
                }
        }

        private static void closeClient(SocketChannel client) {
                try {
                        // Channel 关闭时，它的 SelectionKey 会自动被取消。
                        client.close();
                } catch (IOException e) {
                        System.err.println("Client close: " + e.getMessage());
                }
        }

        private static final class Handler implements EventHandler {

                private final ByteBuffer buffer = ByteBuffer.allocate(1024);

                @Override
                public void handle(SelectionKey key) throws IOException {
                        var client = (SocketChannel) key.channel();
                        if (key.isReadable()) {
                                read(client, key);
                        } else if (key.isWritable()) {
                                write(client, key);
                        }
                }

                private void read(
                        SocketChannel client,
                        SelectionKey key
                ) throws IOException {
                        int count = client.read(buffer);
                        if (count == -1) {
                                closeClient(client);
                        } else if (count > 0) {
                                // flip() 让 Channel.write() 从刚读到的第一字节开始发送。
                                buffer.flip();
                                // 暂停读入下一批，等这一批回显数据全部写出。
                                key.interestOps(SelectionKey.OP_WRITE);
                        }
                }

                private void write(
                        SocketChannel client,
                        SelectionKey key
                ) throws IOException {
                        // 非阻塞 write() 可能只发送一部分，甚至发送 0 字节。
                        // ByteBuffer 的 position 记录已写进内核的进度，下次可写时接着写。
                        client.write(buffer);
                        if (!buffer.hasRemaining()) {
                                buffer.clear();
                                // 没有待发数据时取消 OP_WRITE，避免反复收到可写通知。
                                key.interestOps(SelectionKey.OP_READ);
                        }
                }
        }
}
