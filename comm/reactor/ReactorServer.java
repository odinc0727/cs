// 用 NIO 的 Selector（IO multiplexing） + ServerSocketChannel + SocketChannel（非阻塞） + SelectionKey（事件） 实现 Reactor 模型（事件分发）
// 本质上是让线程不是阻塞在某一个连接的 Read() 上，而是阻塞在 selector.select() 上。

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.ByteBuffer;
import java.nio.channels.SelectionKey;
import java.nio.channels.Selector;
import java.nio.channels.ServerSocketChannel;
import java.nio.channels.SocketChannel;

public class ReactorServer {
    static void main(String[] args) throws IOException {
        new Reactor(8080).run();
    }

    static class Reactor implements Runnable {
        private final Selector selector;
        private final ServerSocketChannel server;

        Reactor(int port) throws IOException {
            selector = Selector.open();

            server = ServerSocketChannel.open();
            server.configureBlocking(false);
            server.bind(new InetSocketAddress(port));

            SelectionKey key = server.register(selector, SelectionKey.OP_ACCEPT);
            key.attach(new Acceptor(selector, server));
        }

        @Override
        public void run() {
            while (!Thread.currentThread().isInterrupted()) {
                try {
                    selector.select();

                    var iterator = selector.selectedKeys().iterator();
                    while (iterator.hasNext()) {
                        SelectionKey key = iterator.next();
                        iterator.remove();

                        if (!key.isValid()) {
                            continue;
                        }

                        Runnable handler = (Runnable) key.attachment();
                        if (handler != null) {
                            try {
                                handler.run();
                            } catch (RuntimeException e) {
                                e.printStackTrace();
                                key.cancel();

                                try {
                                    key.channel().close();
                                } catch (IOException ignored) {

                                }
                            }
                        }
                    }
                } catch (IOException e) {
                    e.printStackTrace();
                } finally {
                    try {
                        selector.close();
                        server.close();
                    } catch (IOException ignored) {

                    }
                }
            }
        }
    }

    static class Acceptor implements Runnable {
        private final Selector selector;
        private final ServerSocketChannel server;

        Acceptor(Selector selector, ServerSocketChannel server) {
            this.selector = selector;
            this.server = server;
        }

        @Override
        public void run() {
            try {
                while (true) {
                    SocketChannel client = server.accept();
                    if (client == null) {
                        break;
                    }

                    IO.println("connected: " + client.getRemoteAddress());

                    client.configureBlocking(false);

                    SelectionKey key = client.register(selector, SelectionKey.OP_READ);
                    key.attach(new Handler(client, key));
                }
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
    }

    static class Handler implements Runnable {
        private final SocketChannel channel;
        private final SelectionKey key;

        private final ByteBuffer readBuffer = ByteBuffer.allocate(1024);
        private ByteBuffer writeBuffer;

        Handler(SocketChannel channel, SelectionKey key) {
            this.channel = channel;
            this.key = key;
        }

        @Override
        public void run() {
            try {
                if (key.isReadable()) {
                    read();
                }
                if (key.isWritable()) {
                    write();
                }
            } catch (IOException e) {
                close();
            }
        }

        private void read() throws IOException {
            int n = channel.read(readBuffer);
            if (n == -1) {
                close();
                return;
            }
            if (n == 0) {
                return;
            }

            readBuffer.flip();

            writeBuffer = ByteBuffer.allocate(readBuffer.remaining());
            writeBuffer.put(readBuffer);
            writeBuffer.flip();

            readBuffer.clear();

            key.interestOps(SelectionKey.OP_WRITE);
        }

        private void write() throws IOException {
            channel.write(writeBuffer);
            if (!writeBuffer.hasRemaining()) {
                writeBuffer = null;
                key.interestOps(SelectionKey.OP_READ);
            }
        }

        private void close() {
            try {
                key.cancel();
                channel.close();
            } catch (IOException ignored) {

            }
        }
    }
}
