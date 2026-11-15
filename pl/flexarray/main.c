#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// 不要对柔性数组做值拷贝
// 不要创建含有柔性数组的结构体数组

struct String {
        size_t len;
        size_t capacity;
        char data[];
};

struct String* string_new(const char* s) {
        size_t len = strlen(s);

        struct String* str = malloc(sizeof(*str) + len + 1);
        if (str == NULL) {
                return NULL;
        }

        str->len      = len;
        str->capacity = len;

        memcpy(str->data, s, len + 1);

        return str;
};

int main(void) {
        struct String* str = string_new("Hello");

        printf("len: %zu\n", str->len);
        printf("string: %s\n", str->data);

        free(str);
}
