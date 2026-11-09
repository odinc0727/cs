import threading
import time

semaphore = threading.BoundedSemaphore(3)


def worker(n):
        with semaphore:
                print(f'{n} start...')
                time.sleep(1)
                print(f'{n} end...')


threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]

for thread in threads:
        thread.start()

for thread in threads:
        thread.join()
