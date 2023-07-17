
import queue
import threading
from ServerConfig import config

ThreadPool = queue.PriorityQueue(config['threadpool-maxsize'])
STOP       = False
ThreadLock = threading.Lock()

class Task(object):
    def __init__(self, priority, obj, useLock):
        self.priority = priority
        self.obj      = obj
        self.useLock  = useLock
    def __str__(self):
        return f"{{self.__class__.__name__}}(object={self.obj} priority={self.priority})"
    def __repr__(self):
        return self.__str__()
    def __lt__(self, other):
        return self.priority > (other.priority if 'priority' in other.__dir__() else 3)

locks = {}

def newLock(id) -> threading.Lock:
    if not id in locks.keys():
        locks[id] = threading.Lock()
    return locks[id]

def lock():
    ThreadLock.acquire()
def release():
    ThreadLock.release()

def addThread(obj, priority=1, useLock=False):
    ThreadPool.put(Task(priority, obj, useLock))

def useThread(priority=1, useLock=False):
    def useThread_(func):
        def run(*arg, **args):
            t = threading.Thread(target=func, args=arg, kwargs=args)
            addThread(t, priority, useLock)
        return run
    return useThread_

def work():
    global ThreadPool, STOP
    while not STOP:
        thread = ThreadPool.get()
        lock() if thread.useLock else 0
        thread.obj.start()
        release() if thread.useLock else 0

def init():
    worker = threading.Thread(target=work)
    worker.start()
