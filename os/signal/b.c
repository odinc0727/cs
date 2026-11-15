#include <signal.h>
#include <stdio.h>
#include <stdlib.h>

// Yet, you could use `kill -[?] [PID]`.
int main(int argc, char* argv[]) {
        pid_t pid = atoi(argv[1]);

        kill(pid, SIGUSR1);

        printf("Sent signal to process %d\n", pid);

        return 0;
}
