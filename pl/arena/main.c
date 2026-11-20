#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Arena {
        unsigned char* base;
        size_t         capacity;
        size_t         used;  // 从 base 起已经占用的字节数，包含对齐填充
};

struct Request {
        size_t      id;
        const char* label;
};

static void* arena_alloc(struct Arena* arena, size_t size, size_t alignment) {
        // 调用者用 alignof(T) 指定类型 T 的对齐
        // 这里支持不超过 alignof(max_align_t) 的 2 的幂
        if (size == 0 || alignment == 0 || alignment > alignof(max_align_t) || (alignment & (alignment - 1)) != 0) {
                return nullptr;
        }

        // malloc 得到的起点已经满足基本对齐，把 used 向上补到 alignment 的倍数即可
        // 例如 used = 5、alignment = 8 时，跳过 3 字节，从偏移 8 开始分配
        size_t padding   = (alignment - arena->used % alignment) % alignment;
        size_t remaining = arena->capacity - arena->used;
        // 先检查填充是否放得下，再检查剩余空间
        // 用减法避免 size 很大时加法溢出
        if (padding > remaining || size > remaining - padding) {
                return nullptr;
        }

        size_t offset = arena->used + padding;
        arena->used   = offset + size;
        return arena->base + offset;
}

static void arena_reset(struct Arena* arena) {
        // 等这一批数据的最后一个使用者结束后才重置
        // 这里只把游标移回开头，保留原来的内存块
        // 旧指针对应的区域随时可能被下一次分配覆盖
        arena->used = 0;
}

int main(void) {
        constexpr size_t capacity = 128;
        static_assert(capacity >= sizeof(max_align_t));

        // 程序只向 malloc 申请一次，随后每次 arena_alloc 都在同一块内存里切出一段
        struct Arena arena = {
                .base     = malloc(capacity),
                .capacity = capacity,
        };
        if (arena.base == nullptr) {
                fputs("Could not allocate Arena storage\n", stderr);
                return EXIT_FAILURE;
        }

        for (size_t id = 1; id <= 2; ++id) {
                // 先分配 5 字节的字符串，再分配一个通常需要更严格对齐的结构体
                char*           label   = arena_alloc(&arena, sizeof("echo"), alignof(char));
                struct Request* request = arena_alloc(&arena, sizeof(*request), alignof(struct Request));
                if (label == nullptr || request == nullptr) {
                        fputs("Arena allocation failed\n", stderr);
                        free(arena.base);
                        return EXIT_FAILURE;
                }

                memcpy(label, "echo", sizeof("echo"));
                *request = (struct Request){.id = id, .label = label};
                printf("request %zu (%s): label +%td, struct +%td (alignment %zu), used %zu/%zu\n", request->id,
                       request->label, (unsigned char*)label - arena.base, (unsigned char*)request - arena.base,
                       alignof(struct Request), arena.used, arena.capacity);

                // 打印是最后一次使用请求数据
                // 重置后，下一轮会从相同的偏移重新开始分配
                arena_reset(&arena);
                printf("reset: used %zu/%zu\n", arena.used, arena.capacity);
        }

        free(arena.base);
        return EXIT_SUCCESS;
}
