# C23 Arena 分配器

[main.c](main.c) 用一块固定容量的内存处理两轮模拟请求。每轮先分配一个字符串，再分配一个引用该字符串的结构体。两者一起用完，适合一起回收。

## 运行

在本目录用支持 C23 的编译器构建，仅依赖 C 标准库。

```sh
cc -std=c23 -Wall -Wextra -Wpedantic main.c -o /tmp/c23-arena-demo
/tmp/c23-arena-demo
```

在本机，`struct Request` 大小为 16 字节，对齐要求为 8 字节。运行结果如下。

```text
request 1 (echo): label +0, struct +8 (alignment 8), used 24/128
reset: used 0/128
request 2 (echo): label +0, struct +8 (alignment 8), used 24/128
reset: used 0/128
```

## 分配、对齐和重置

1. **分配。** `malloc()` 申请整块内存，`used` 记录从起点到下一块可用空间的偏移。`arena_alloc()` 返回块内的指针，并把 `used` 推进到这次分配的末尾。容量不足或参数无效时返回 `nullptr`，游标保持原值。
2. **对齐。** 调用者传入 `alignof(T)`。字符串 `"echo"` 连同结尾的 `\0` 占 5 字节。若结构体要求 8 字节对齐，就从偏移 8 开始放，中间的 3 字节是填充。本例支持不超过 `alignof(max_align_t)` 的基本对齐。 [WG14 C23 草案，§6.2.8 与 §7.24.3](https://www9.open-std.org/JTC1/SC22/WG14/www/docs/n3096.pdf)
3. **重置。** 确认本轮数据已全部用完后，`arena_reset()` 把 `used` 归零。底层内存和原有字节仍在，下一轮分配可以覆盖它们，因此重置后应停止使用本轮取得的指针。整个 Arena 用完后，由 `free(arena.base)` 一次释放底层内存。

放进 Reactor 时，重置的时机由数据的最后一个使用者决定。如果发送队列仍引用 Arena 内的响应数据，要等队列用完该数据再重置。
