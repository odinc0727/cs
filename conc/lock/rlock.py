import threading

lock = threading.RLock()

with lock:
        print('first: lock')

        acquired = lock.acquire(timeout=1)

        if not acquired:
                print('1 秒内无法获取锁，可能发生死锁')
        else:
                print('second: lock')
                lock.release()
