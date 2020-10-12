"""
    PyServer
    By Himpq|2020-10-12
"""
from threading import Thread
import socket
import time
import datetime
import json
import sys
import urllib
import os
import re
import CacheModule as TM
import urllib.parse as uparse
import wmi
import chardet
from Logger import Logger
from server_config import *
from ExpHttpData import *
import inspect
import ctypes
from memory_profiler import profile

Logger = Logger()
SERVER = "PyServer"
VERSION = "/2.1.31"

##导入PyFDB
if config['use_pyfdb']:
    sys.path.append("./PyFileDatabase")
    try:
        import pyfiledb
        pyfiledb.start()
    except:
        Logger.warn("Cannot found the PyfileDatabase. Please check your installed.")
    else:
        Logger.comp("Import PyFileDatabase successful.")
else:
    Logger.error("PyFileDatabase was disabled.")

#功能类
def _async_raise(tid, exctype):
    """Raises an exception in the threads with id tid"""
    if not inspect.isclass(exctype):
        raise TypeError("Only types can be raised (not instances)")
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(tid), ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


def stop_thread(thread):
    _async_raise(thread.ident, SystemExit)
def DeleteObjectAllProperties(objectInstance):
    if not objectInstance:
        return
    listPro =[key for key in objectInstance.__dict__.keys()]
    for key in listPro:
        objectInstance.__delattr__(key)
def get_memory():
    global server_memory
    pythoncom.CoInitialize()

    a = wmi.WMI()
    while 1:
        server_memory = [int(a.Win32_ComputerSystem()[0].TotalPhysicalMemory),
                        int(a.in32_OperatingSystem()[0].FreePhysicalMemory)]
        time.sleep(config['reload_information_time'])
def dict_inone(*arg):
    x = {}
    for i in arg:
        for f in i:
            x[f] = i[f]
    return x

#服务器


class Server:
    def __init__(self, ip='localhost', port=80, maxlisten=128):
        self.ip = ip
        self.port = port
        self.maxlisten = maxlisten
        self.is_start = False

        self.tpool = {}

    def __setattr(self, key, val):
        if self.is_start:
            raise KeyError("Cannot change any arguments when server is running.")
        self.__dict__[key] = val

    def _accept(self):
        ident = 0
        while 1:
            conn, addr = self.socket.accept()

            user = Thread(target=ServerResponse, args=(conn, addr, ident, self))
            user.start()
            self.tpool[ident] = user
            ident += 1

            time.sleep(0.01)

    def start(self):
        self.socket = socket.socket()
        self.socket.bind((self.ip, self.port))
        self.socket.listen(self.maxlisten)
        self.accept_thread = Thread(target=self._accept)
        self.accept_thread.start()
        Logger.comp("Server is running from now on.")
        self.is_start = True

class ServerResponse:
    def __init__(self, conn, ip, ident, server):
        self.server = server
        self.ident = ident
        self.conn = conn
        self.ip = ip
        self.cache2 = File_B()

        Logger.comp("Accept ip:", ip)

        self.response()
        stop_thread(server.tpool[self.ident])
        del server.tpool[self.ident]
        DeleteObjectAllProperties(self)

    def response(self):

        data = exp(exp2(self.conn))

        self.data = data
        Logger.info(data)

        time1 = time.time()

        if data.get("content_type", None) == 'multipart/form-data':
            self.updata(data)
            return

        try:
            if data['path'][-3:] == '.py':
                self.py(data)
            elif os.path.isdir(ServerPath+"/"+data['path']):
                for i in config['default-page']:
                    if os.path.isfile(ServerPath+"/"+data['path']+'/'+i):
                        data['path'] = data['path']+'/'+i
                        self.data = data
                        break
                if i[-3:] == '.py':
                    self.py(data)
                else:
                    self.fl(data)
            else:
                self.fl(data)
        except Exception as e:
            Logger.error(e, "(at line", e.__traceback__.tb_lineno,")")
        time2 = time.time()
        Logger.warn("Response time: %ss"%str(time2-time1))
        

    
    def set_cookie(self, key, val):
        self.header.set("Set-Cookie", "%s=%s; Expires=%s;", True)
    def set_header(self, val):
        v = str(val).split(":")
        if len(v) == 1:
            self.cache.append(val)
            return
        key = v[0]
        val = ':'.join(v[1:])
        self.cache.write(key, str(val)+"\r\n")
    def set_html(self, *val, **arg):
        #self.cache2.write(str(val))
        print(*val, **arg, file=self.cache2)
    def getGlobal(self):
        globals_var = {}
        globals_var['set_cookie'] = self.set_cookie
        globals_var["set_header"] = self.header.set
        globals_var["print"] = self.set_html
        globals_var['include'] = self.include
        globals_var['_POST'] = self.data['postdata']
        globals_var['_GET'] = self.data['getdata']
        globals_var['_REWRITE'] = self.data['rewritedata']
        globals_var['_COOKIE'] = self.data['cookie']
        globals_var['Logger'] = Logger
        globals_var['this'] = self
        globals_var['_FILE'] = {}
        globals_var["_DATA"] = {}
        return globals_var

    def updata(self, data):
        if 'boundary' in self.data:
            if data['path'][-3:] == '.py':
                #self.py(data, tocls(updata_exp(self.conn, "--"+data['boundary'])))
        
                pass
            x = updata_exp(self.conn, data['boundary'])
            self.py(data, {"_FILE":x[0], "_DATA":x[1]})
        #print(self.conn.recv(1024))
                
        self.conn.close()
        return

    def py(self, data, glo={}):
        if os.path.isfile(ServerPath+"/"+data['path']):
            ccc = ServerPath+"/"+data['path']
            with open(ccc, 'rb') as f:
                u = f.read()

                #j = chardet.detect(u)['encoding']
                #u = u.decode(j)
                
            self.header = Header()

            globals_var = self.getGlobal()
            self.var = globals_var

            for i in glo:
                self.var[i] = glo[i]
            h = {}
            try:
                u = compile(u, ccc, 'exec')
                exec(u, globals_var, h)
                del h, globals_var, u
            except Exception as e:
                header = Header()
                header.set("Content-Type", "text/html; charset=utf-8")
                
                self.conn.send(header.encode()+b'\r\n')
                self.err("codeerror", e)
                self.conn.close()
                return

            self.cache2.save()

            datas = self.header.encode()+b'\r\n'
            datas += self.cache2.read().encode()+b'\r\n\r\n'

            self.conn.send(datas)
            self.conn.close()
            #self.conn.shutdown(socket.SHUT_RDWR)

    def fl(self, data):
        if data['path'][-3:] == '.py':
            self.py(data)
            return
        if os.path.isfile(ServerPath+"/"+data['path']):
            header = Header()
            header.set("Content-Type", FileType(data['path']))
            header.set("Content-Length", os.path.getsize(ServerPath+"/"+data['path']))

            self.conn.send(b'HTTP/1.1 200 Ok!\r\n')
            self.conn.send(header.encode()+b'\r\n')

            with open(ServerPath+"/"+data['path'], 'rb') as f:
                b = f.read(1024*100)
                while not b == b'':
                    self.conn.send(b)
                    b = f.read(1024*100)

            self.conn.close()
        else:
            header = Header()
            self.conn.send(header.encode()+b'\r\n')
            
            self.err('404')
            self.conn.shutdown()

    def err(self, ty, x=''):
        if ty == 'codeerror':
            self.conn.send(b"<html><body><center><h1>Python Error</h1>")
            self.conn.send(b"<br><font color='red'>Error: </font>"+str(x).encode()+b"</body></html")
            return
        self.conn.send(ERRCODE(ty))

    #@profile
    def include(self, path):
        pathx=ServerPath+"/"+os.path.split(self.data['path'])[0]
        path = pathx+"/"+path

        if os.path.isfile(path):
            with open(path, 'r') as f:
                u = f.read()
                
            globals_var = self.getGlobal()
            s = {}

            exec(("import sys;sys.path.append('%s')\n"%pathx)+u, globals_var)

            name = os.path.split(path)[1].split('.')[0]
            self.var[name] = Module(dict_inone(s, globals_var))
        else:
            raise ImportError("Cannot find module in path: '%s'"%path)
            #print("Module cannot find.", file=sys.stderr)

class Module:
    def __init__(self, dicts):
        for i in dicts:
            self.__dict__[i] = dicts[i]
            
class Header:
    def __init__(self):
        self.headers = {}
        self.headers[0] = "HTTP/1.1 200 OK!"
        self.headers["Content-Encoding"] = "identity"
        self.headers["Server"] = SERVER+VERSION
        self.headers["Date"] = time.asctime()
        
    def set(self, key, val, diejia=False):
        if key in self.headers:
            if diejia:
                self.headers[key] += str(val)
                return
        self.headers[key] = str(val)
    def get(self, key, val):
        return self.headers.get(key)
    def encode(self):
        p = b''
        for i in self.headers:
            if type(i) == int:
                p+=self.headers[i].encode()
                p+=b'\r\n'
                continue
            p+=i.encode()+b":"+self.headers[i].encode()
            p+=b'\r\n'
        return p
class File_B:
    def __init__(self, trueFile=False):
        self.file = '' if not trueFile else None
    def write(self, data):
        self.file += data
    def save(self):
        pass
    def read(self):
        return self.file
class File_C:
    def __init__(self, trueFile=False):
        #self.file = '' if not trueFile else None
        self.file = {}
    def write(self, key, data):
        self.file[str(key)] = data
    def get(self, key):
        return self.file[key] if key in self.file else None
    def save(self):
        pass
    def read(self):
        txt = ''
        for i in self.file:
            if type(i) == int:
                txt += self.file[i]+'\r\n'
                continue
            
            txt += i+':'+self.file[i]+'\r\n'
        return txt
    def append(self, value):
        self.file[len(self.file)] = value

a=Server(ip='192.168.1.104')
a.start()
