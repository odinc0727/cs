# uv run --no-project --python 3.14t python -X gil=0 main.py
# uv run --no-project --python 3.14t python -X gil=1 main.py

import sys
import threading
import time

N = 3_000_000


def work():
    x = 1
    for _ in range(N):
        x = (x * 1664525 + 1013904223) & 0xFFFFFFFF
    return x


def benchmark(n):
    results = [None] * n

    def worker(i):
        results[i] = work()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]

    start = time.perf_counter()

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    elapsed = time.perf_counter() - start
    print(f"{n} threads: {elapsed:.3f}s")


print("GIL enabled:", sys._is_gil_enabled())

for n in (1, 2, 4):
    benchmark(n)
