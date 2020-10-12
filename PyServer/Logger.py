import time
import datetime
import sys
import ctypes

STD_INPUT_HANDLE = -10  
STD_OUTPUT_HANDLE= -11  
STD_ERROR_HANDLE = -12  
  
FOREGROUND_DARKBLUE = 0x01 # 暗蓝色
FOREGROUND_DARKGREEN = 0x02 # 暗绿色
FOREGROUND_DARKSKYBLUE = 0x03 # 暗天蓝色
FOREGROUND_DARKRED = 0x04 # 暗红色
FOREGROUND_DARKPINK = 0x05 # 暗粉红色
FOREGROUND_DARKYELLOW = 0x06 # 暗黄色
FOREGROUND_DARKWHITE = 0x07 # 暗白色
FOREGROUND_DARKGRAY = 0x08 # 暗灰色
FOREGROUND_BLUE = 0x09 # 蓝色
FOREGROUND_GREEN = 0x0a # 绿色
FOREGROUND_SKYBLUE = 0x0b # 天蓝色
FOREGROUND_RED = 0x0c # 红色
FOREGROUND_PINK = 0x0d # 粉红色
FOREGROUND_YELLOW = 0x0e # 黄色
FOREGROUND_WHITE = 0x0f # 白色
 
sohandle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

def warn(*arg, **args):
    times = datetime.datetime.now()
    times = times.strftime("%X")
    print("[Server] [%s] [Warnning]>>" % times,*arg, **args, file=sys.stderr)

class Logger:
    def set_color(self, color, handle=sohandle):
        self.bool = ctypes.windll.kernel32.SetConsoleTextAttribute(handle, color)

    def cprint(self, mess, color, **arg):
        self.set_color(color)
        print(mess, **arg)
        self.reset()
        
    def reset(self):
        self.set_color(FOREGROUND_DARKWHITE)

    def cpri(self,*arg, sep=' ', end='', type, color):
        timenow = datetime.datetime.now().strftime("%X")
        x = ''
        for i in arg:
            x += str(i)+sep
        x = x[0:len(x)-len(sep)]+end
        self.cprint("[Server] [%s] [%s] >> %s"%(timenow, type, x), color, end='')

    def warn(self, *arg, sep=' ', end='\n'):
        self.cpri(*arg, sep=sep, end=end, type="Warnning", color=FOREGROUND_YELLOW)
    def error(self, *arg, sep=' ', end='\n'):
        self.cpri(*arg, sep=sep, end=end, type="Error", color=FOREGROUND_RED)
    def info(self, *arg, sep=' ',  end='\n'):
        self.cpri(*arg, sep=sep, end=end, type="Info", color=FOREGROUND_SKYBLUE)
    def comp(self, *arg, sep=' ', end='\n'):
        self.cpri(*arg, sep=sep, end=end, type="Complete", color=FOREGROUND_GREEN)

def test():  
    a=Logger()
    a.warn('lbwnb')
    a.error('lbwnb')
    a.info('lbwnb')
    a.comp('lbwnb')

