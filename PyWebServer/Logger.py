

from ServerConfig import logger
from threading import Thread
import DispatchThread as DT
import platform
import datetime
import ctypes
import time
import os

Logs     = {}
STOP_LOG = False
STD_INPUT_HANDLE  = -10  
STD_OUTPUT_HANDLE = -11  
STD_ERROR_HANDLE  = -12  

if not os.path.isdir("logs"):
    os.mkdir("logs")
    open("./logs/log.txt", 'w').close()

def stopLog():
    globals()['STOP_LOG'] = True

def setLog(content, file='./logs/view.log', showTime=True):
    x = "["+time.ctime()+"] "
    if not showTime:
        x = ''
    ctx = (x+content+"\n")
    if not file in Logs.keys():
        Logs[file] = []
    Logs[file].append(ctx)

def setLogThread():
    import DispatchThread as DT
    while not STOP_LOG:
        DT.lock()
        try:
            for i in Logs:
                if not os.path.isfile(i):
                    with open(i, 'w') as f:
                        pass
                    
                with open(i, 'a', encoding='utf-8') as f:
                    for count in range(len(Logs[i])):
                        ctx = Logs[i].pop(0)
                        f.write(ctx)
        except RuntimeError as e:
            if 'dictionary changed' in str(e):
                pass
            else:
                from Logger import Logger
                Logger().error(e)
                
        DT.release()
        time.sleep(0.1)

def initLogThread():
    Logger("Logger").info("Starting Logger Thread...")
    print("Start Logger")
    import threading
    if any([t.name == 'logger' for t in threading.enumerate()]):
        print("already init")
        return
    setLogt = Thread(target=setLogThread, name='logger')
    setLogt.start()
    if os.path.isfile("./logs/h2.log"):
        os.remove("./logs/h2.log")


IGNORE_LIST = logger['ignore_list']
  
FOREGROUND_DARKBLU        = 0x01 # 暗蓝色
FOREGROUND_DARKGREEN      = 0x02 # 暗绿色
FOREGROUND_DARKSKYBLUE    = 0x03 # 暗天蓝色
FOREGROUND_DARKRED        = 0x04 # 暗红色
FOREGROUND_DARKPINK       = 0x05 # 暗粉红色
FOREGROUND_DARKYELLOW     = 0x06 # 暗黄色
FOREGROUND_DARKWHITE      = 0x07 # 暗白色
FOREGROUND_DARKGRAY       = 0x08 # 暗灰色
FOREGROUND_BLUE           = 0x09 # 蓝色
FOREGROUND_GREEN          = 0x0a # 绿色
FOREGROUND_SKYBLUE        = 0x0b # 天蓝色
FOREGROUND_RED            = 0x0c # 红色
FOREGROUND_PINK           = 0x0d # 粉红色
FOREGROUND_YELLOW         = 0x0e # 黄色
FOREGROUND_WHITE          = 0x0f # 白色
showColor   = 1

lock = DT.newLock("Logger")

if platform.system() == "Windows":
    sohandle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    
class Logger:
    def __init__(self, s="Server"):
        self.s = s
        
    def set_color(self, color, handle=sohandle):
        self.bool = ctypes.windll.kernel32.SetConsoleTextAttribute(handle, color)

    def cprint(self, mess, color, **arg):
        if showColor:
            self.set_color(color)
            print(mess, **arg)
            self.reset()
        else:
            print(mess, **arg)
        
    def reset(self):
        self.set_color(FOREGROUND_DARKWHITE)

    def cpri(self,*arg, sep=' ', end='', type, color):
        if type.strip().lower() in IGNORE_LIST:
            return
        
        lock.acquire()

        timenow = datetime.datetime.now().strftime("%X")
        ctx     = ''
        for i in arg:
            ctx += str(i)+sep
        ctx   = ctx[0:len(ctx)-len(sep)]+end
        msg = "[%s] [%s] [%s] >> %s"%(self.s, timenow, type, ctx)
        if platform.system() == "Windows":
            self.cprint(msg, color, end='')
        else:
            print(msg)

        setLog(msg, "./logs/logger.log", 0)

        lock.release()

    def warn(self, *arg, sep=' ', end='\n'):
        self.cpri(*arg, sep=sep, end=end, type="Warning ", color=FOREGROUND_YELLOW)
    def error(self, *arg, sep=' ', end='\n'):
        self.cpri(*arg, sep=sep, end=end, type="Error   ", color=FOREGROUND_RED)
    def info(self, *arg, sep=' ',  end='\n'):
        self.cpri(*arg, sep=sep, end=end, type="Info    ", color=FOREGROUND_SKYBLUE)
    def comp(self, *arg, sep=' ', end='\n'):
        self.cpri(*arg, sep=sep, end=end, type="Complete", color=FOREGROUND_GREEN)
