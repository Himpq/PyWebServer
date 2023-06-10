import queue
import threading


from server_config import config
"""调度模块"""
ThreadPool = queue.PriorityQueue(config['threadpool-maxsize'])
STOP = False
ThreadLock = threading.Lock()

class Task(object):
    def __init__(self, priority, obj):
        self.priority = priority
        self.obj      = obj
    def __str__(self):
        return f"Task(priority={self.priority}, object={self.obj})"
    def __lt__(self, other):
        return self.priority < (other.priority if 'priority' in other.__dir__() else 3)

    

def addThread(obj, priority=1):
    ThreadPool.put(Task(priority, obj))

def work():
    global ThreadPool, STOP
    while not STOP:
        thread = ThreadPool.get()
        
        ThreadLock.acquire()
        thread.obj.start()
        ThreadLock.release()

worker = threading.Thread(target=work)
worker.start()
