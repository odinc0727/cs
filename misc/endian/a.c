#include <stdio.h>

int isLittleEndian(void) {
        union {
                unsigned int i;
                unsigned char c[sizeof(unsigned int)];
        } test           = {.i = 1};
        return test.c[0] = 1;
}

int main() {
        if (isLittleEndian()) {
                printf("小端模式\n");
        } else {
                printf("大端模式\n");
        }
}
