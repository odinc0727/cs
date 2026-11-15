#include <stdio.h>

void fooi(int x) {
        printf("%d\n", x);
}

void foof(float x) {
        printf("%f\n", x);
}

#define foo(x) _Generic(x, int: fooi(x), float: foof(x))

int main() {
        foo(69);
        foo(69.420f);

        return 0;
}
