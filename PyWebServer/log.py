import time
import os


Logs={}


def setLog(content, file='./logs/view.log', showTime=True):
    x = "["+time.ctime()+"] "
    if not showTime:
        x = ''
    ctx = (x+content+"\n")
    if not file in Logs.keys():
        Logs[file] = []
    Logs[file].append(ctx)
    

def setLogThread():
    while 1:
        for i in Logs:
            if not os.path.isfile(i):
                with open(i, 'w') as f:
                    pass
                
            with open(i, 'a', encoding='utf-8') as f:
                for count in range(len(Logs[i])):
                    ctx = Logs[i].pop(0)
                    f.write(ctx)
        time.sleep(0.1)


def initLogThread():
    from threading import Thread
    setLogt = Thread(target=setLogThread)
    setLogt.start()
    if os.path.isfile("./logs/h2.log"):
        os.remove("./logs/h2.log")
