import queue
import threading


from server_config import config
"""调度模块"""
ThreadPool = queue.PriorityQueue(config['threadpool-maxsize'])
STOP = False
ThreadLock = threading.Lock()

class Task(object):
    def __init__(self, priority, obj, useLock):
        self.priority = priority
        self.obj      = obj
        self.useLock  = useLock
    def __str__(self):
        return f"Task(object={self.obj} priority={self.priority})"
    def __lt__(self, other):
        return self.priority < (other.priority if 'priority' in other.__dir__() else 3)

def lock():
    ThreadLock.acquire()
def release():
    ThreadLock.release()

def addThread(obj, priority=1, useLock=True):
    ThreadPool.put(Task(priority, obj, useLock))

def work():
    global ThreadPool, STOP
    while not STOP:
        thread = ThreadPool.get()
        print(thread, thread.useLock)
        lock() if thread.useLock else 0
        thread.obj.start()
        release() if thread.useLock else 0

worker = threading.Thread(target=work)
worker.start()
