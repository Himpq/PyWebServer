
import pathos.multiprocessing as _pathosmp
import pathos
import multiprocessing as _mp
import multiprocess as _mp_
import threading as tr
import time
from server_config import config
from Logger import Logger
Logger = Logger()

Thread = tr.Thread
Process = _mp.Process
Manager = _mp_.Manager

USE_MP = config['use-multiprocessing']

def Worker(IDENT, threads, isStarted, isStop):
    Logger.info("[MPThread] [INFO] 开启 Worker-%s 进程"%IDENT)
    isStarted[IDENT] = True
    while not isStop.value:

        if not len(threads) == 0:
            try:
                t = threads.pop()
                Logger.warn("[MPThread]", IDENT, "开启进程:", t)
                t.start()
            except:
                 continue

            
        time.sleep(0.001) #防止持续检测导致cpu占用
    return 'Process %s had been stop.' % IDENT



isStarted = None
Threadings = None

def startWorker(worker_number):
    global Threadings
    if USE_MP:
        pool = _pathosmp.ProcessingPool()

        x = list(range(worker_number))
        
        MNG = Manager()
        threads = MNG.list([])
        Status = MNG.Value("isStop", False)
        Started = MNG.list([])

        globals()['Threadings'] = threads
        globals()['pool'] = pool
        globals()['stat'] = Status
        globals()['MNG'] = MNG
        globals()['isStarted'] = Started

        #print(globals()['Threadings'])

        res = []
        for num in x:
            Started.append(False)
            res.append(pool.apipe(Worker, num, threads, Started, Status))

        pool.close()
        pool.join()
    else:
        class x:
            pass
        Threadings = x()
        Threadings.append = lambda thing:thing.start()


fib=lambda n:1 if n<=2 else fib(n-1)+fib(n-2)
def testStart():
    #使用斐波那契数列测试线程与进程的效率
    global Threadings
    start()
    o = Thread(target=lambda:print("PROCESS1",fib(36)))
    Threadings.append(o)
    o2= Thread(target=lambda:print("PROCESS2",fib(36)))
    Threadings.append(o2)
    p = Thread(target=lambda:print("THREAD", fib(36)))
    p.start()
    p2 = Thread(target=lambda:print("THREAD2", fib(36)))
    p2.start()


def start():
    o = Thread(target=startWorker, args=(4,))
    o.start()
    if USE_MP:
        while not isStarted or not all(isStarted):
            time.sleep(0.01)

        Logger.warn("[MPThread] [INFO] All processes are running.")
    else:
        Logger.warn("[MPThread] [INFO] Running as thread mode.")

def quit():
    global stat
    stat.value = True

if __name__ == '__main__':
    pass
