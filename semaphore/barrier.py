import threading

barrier = threading.Barrier(3)


def worker(n):
        for phase in range(10):
                print(f'线程 {n} 完成阶段 {phase}')
                barrier.wait()


threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]

for thread in threads:
        thread.start()

for thread in threads:
        thread.join()
