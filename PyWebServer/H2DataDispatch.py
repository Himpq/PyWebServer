
import queue
import threading
import time
from Logger import Logger
import DispatchThread as DT

Logger = Logger()

channels = {}

class DataDispatch:
    """This object should be created by a main stream(stream id=0), and stream use it to strive for priority to send data."""
    def __init__(self):
        self.queue = queue.PriorityQueue()
        self.STOP  = False
        self.tlock = threading.Lock()
        DT.lock()
        self.id    = len(channels)
        channels[self.id] = self
        DT.release()
        self.init()

    def get(self, id, priority = 1):
        task = Task(priority, id, self)
        self.queue.put(task)
        task.waitForLock()
        return task

    def init(self):
        self.thr = threading.Thread(target=self._handle)
        self.thr.start()

    def _handle(self):
        try:
            while not self.STOP:
                task = self.queue.get(timeout=15)
                task.getlock = True
                task.join()
        except queue.Empty:
            Logger.info(self, "Timeout")
            self.kill()
            return

    def _showlist(self):
        while not self.STOP:
            print(str(hash(self))[-5:], ":", self.queue.queue)
            time.sleep(5)

    def kill(self):
        self.STOP = True
        del channels[self.id]

class Task:
    """This object is used to control the 'Lock'."""
    def __init__(self, priority, id, channel:DataDispatch):
        self.id = id
        self.priority = priority
        self.getlock  = False
        self.channel  = channel
    def __lt__(self, other):
        return self.priority > other.priority #(other.priority if 'priority' in other.__dir__() else 3)
    def __str__(self):
        return f"<H2DataDispatch.Task priority={self.priority} id={self.id} getlock={self.getlock}>"
    def __repr__(self):
        return self.__str__()
    def isAcquire(self):
        return self.getlock
    def join(self):
        self.channel.tlock.acquire()
        self.channel.tlock.release()
    def waitForLock(self):
        self.channel.tlock.acquire()
        self.getlock = True
    def release(self):
        self.channel.tlock.release()
        self.getlock = False
        

