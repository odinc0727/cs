#include <stdint.h>
#include <stdio.h>

int main() {
        uint32_t val = 0x01020304;
        FILE* p      = fopen("test", "wb");
        fwrite(&val, sizeof(val), 1, p);
        fclose(p);

        return 0;
}
