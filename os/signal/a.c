#include <signal.h>
#include <stdio.h>
#include <unistd.h>

void handler_siguser1(int sig) {
        printf("\nReceived SIGUSER1 signal! Continuing...\n");
}

int main() {
        // 现在，当程序 B 发出 SIGUSER1 信号，程序 A 执行此处理函数而不会默认中断
        signal(SIGUSR1, handler_siguser1);

        printf("Process ID: %d\n", getpid());

        const char* message = "Subscribe";
        while (1) {
                printf("\r           ");
                printf("\r%s", message);
                fflush(stdout);
                sleep(1);
                for (int i = 0; i < 3; i++) {
                        printf(".");
                        fflush(stdout);
                        sleep(1);
                }
        }

        return 0;
}
