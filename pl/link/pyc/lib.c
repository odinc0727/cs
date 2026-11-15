#include <stdint.h>

int32_t add(int32_t a, int32_t b) {
        return a + b;
}

double multiply(double a, double b) {
        return a * b;
}

typedef struct {
        int x;
        int y;
} Point;

void move_point(Point* p, int dx, int dy) {
        p->x += dx;
        p->y += dy;
}

// 编译成动态库
// Arch:  cc -shared -fPIC lib.c -o libmath.so
// Maxos: cc -dynamiclib lib.c -o libmath.dylib
