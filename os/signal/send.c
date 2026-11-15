#include <signal.h>
#include <stdio.h>
#include <sys/types.h>
#include <unistd.h>

int main() {
        pid_t pid;

        printf("输入目标进程 ID：");
        scanf("%d", &pid);

        if (kill(pid, SIGUSR1) == 0) {
                printf("成功向进程 %d 发送 SIGUSR1 信号\n", pid);
        } else {
                perror("kill");
                return 1;
        }

        return 0;
}
