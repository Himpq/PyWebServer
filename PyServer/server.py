# -*- encoding: utf-8 -*-
"""
    PyServer
    By Himpq|2020-10-12
"""
from threading import Thread
from Logger import Logger
from server_config import *
from ExpHttpData import *
from functions import *
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
#import chardet
import inspect
import ctypes
import ssl, gzip
from io import *
from memory_profiler import *

prof = profile

def profile(func):
    def x(*arg, **args):
        l = time.time()
        o = func(*arg, **args)
        p = time.time()
        #sys.stderr.write("===========\n函数"+func.__name__+" 耗时:"+str(p-l)+"\n==========\n")
        return o
    return x

ssl._create_default_https_context = ssl._create_unverified_context

SERVER = "PyServer"
VERSION = "/2.1.31"


def gzip_encode(data):
    buf = BytesIO()
    f = gzip.GzipFile(mode='wb', fileobj=buf)
    f.write(data)
    f.close()
    buf.seek(0)
    return buf.read()

#服务器
class Server:
    @profile
    def __init__(self, ip='localhost', port=80, maxlisten=128):
        self.is_start = False
        self.ip = ip
        self.port = port
        self.maxlisten = maxlisten
        self.tpool = {}
        self.ssl = False

    def open_SSL(self):
        self.ssl = True
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        self.ssl_context.load_cert_chain(certfile=sslpath[0], keyfile=sslpath[1])
        #self.ssl_context.load_verify_locations(sslpath[2])
        #self.ssl_context.verify_mode = ssl.CERT_REQUIRED
        
    def __setattr__(self, key, val):
        if 'is_start' in self.__dict__ and self.is_start:
            raise KeyError("Cannot change any arguments when server is running.")
        self.__dict__[key] = val

    def _accept(self):
        ident = 0
        while 1:
            try:
                conn, addr = self.socket.accept()
                if self.ssl:
                    co = conn
                    conn = self.ssl_context.wrap_socket(co, server_side=True)
                se = ServerResponse
                arg = se(conn, addr, ident, self)
                user = Thread(target=arg.response)
                user.start()
                print("Recv from",addr)
                self.tpool[ident] = [user, se]
                ident += 1
            except Exception as e:
                print(e)
                continue

            #time.sleep(0.01)

    def _res(self):
        while 1:
            time.sleep(0.1)
            try:
                for i in list(self.tpool.keys()):
                    if self.tpool[i][0].is_alive():
                        continue
                    #self.tpool.pop(i)
                    del self.tpool[i]
            except:
                continue

    def _ke(self):
        while 1:
            Logger.info("Server alive.")
            time.sleep(10)

    def start(self):
        self.socket = socket.socket()
        self.socket.bind((self.ip, self.port))
        self.socket.listen(self.maxlisten)
        self.accept_thread = Thread(target=self._accept)
        self.accept_thread.start()
        self.clear_thread = Thread(target=self._res)
        self.clear_thread.start()
        #self.keep_alive = Thread(target=self._ke)
        #self.keep_alive.start()
        Logger.comp("Server is running from now on.")
        self.is_start = True

    def stop(self):
        stop_thread(self.accept_thread)
        stop_thread(self.clear_thread)
        self.socket.close()

class ServerResponse:
    def __init__(self, conn, ip, ident, server):
        
        self.server = server
        self.ident = ident
        self.conn = conn
        self.connfile = conn.makefile('rb')
        self.ip = ip
        self.cachesize = 4096
        self.cache2 = File_B()

        Logger.comp("响应IP: ", ip)
        self.runin = ''
        self._DATA = {}
        self._FILE = {}

        self.status = 'in init func.'

        '''try:
            #self.response()
            pass
        except Exception as e:
            Logger.warn(e)
        finally:
            try:
                self.connfile.close()
                self.conn.close()
            except:
                pass
            try:
                while 1:
                    stop_thread(self.server.tpool[self.ident][0])
            except:
                pass
        #stop_thread(server.tpool[ident+1])'''

    def response(self):
        time1 = time.time()
        self.status = 'in response func.'
        self.data = ''
        self.ysdata = ''
        def getx():
            ysdata , data = exp(self.connfile)
            self.data = data
            self.ysdata = ysdata
        self.getdatathread = Thread(target=getx)
        self.getdatathread.start()
        n = 0
        x = False
        while self.ysdata == '' or self.data == '':
            if n == 1500:
                try:
                    stop_thread(self.getdatathread)
                except:
                    pass
                finally:
                    x= True
                    break
            n += 1
            time.sleep(0.01)
        if x:
            print("Time out.")
            return 0

        data = self.data
        ysdata = self.ysdata
        if data.get("host") == None or data.get("path") == None:
            return
        Logger.info("请求路径: ", data['host'] + data['path'])

        if not data.get("host", None) in bind_domains and not isIPv4(data.get("host")):
            self.err("内部错误", "未绑定的域名，请在配置中添加。")
            return

        if data.get("content-type", None) == 'multipart/form-data':
            self.updata(data)
        else:
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

        Logger.comp("响应结束。响应时间: %ss"%(time2-time1))
        self.status = 'kill me.'

        
        try:
                self.connfile.close()
                self.conn.close()
        except:
                pass
        
    def set_cookie(self, key, val, expires=3600):
        self.header.set("Set-Cookie", "%s=%s; Expires=%s;"%(key, val, expires), True)
    def set_header(self, key, val):
        self.header.set(key, str(val))
    def set_statuscode(self, code, content): #404, File not found
        self.header.set(0, "HTTP/1.1 "+str(code)+" "+content)
    def set_html(self, *val, **arg):
        #self.cache2.write(str(val))
        print(*val, **arg, file=self.cache2)
    def getGlobal(self):
        globals_var = {}
        globals_var['set_cookie'] = self.set_cookie
        globals_var["set_header"] = self.header.set
        globals_var['set_statuscode'] = self.set_statuscode
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

    @profile
    def updata(self, data):
        self.status = 'in updata func.'
        if data.get("boundary"):
            if data['path'][-3:] == '.py':
                x = updata_exp(self.connfile, data['boundary'])
                if not len(x) == 0:
                    do = {"_FILE":x[0], "_DATA":x[1]}
                else:
                    do = {}
                self.py(data, do)
                return
            x = updata_exp(self.connfile, data['boundary'])
            self.py(data, {"_FILE":x[0], "_DATA":x[1]})
        return

    @profile
    def py(self, data, glo={}):
        self.status = 'in py func.'

        if config['python'] == False:
            return
        if os.path.isfile(ServerPath+"/"+data['path']):
            ccc = ServerPath+"/"+data['path']
            with open(ccc, 'rb') as f:
                #"import os; os.chdir('{0}'); del os;\n".format(ServerPath+"/"+os.path.split(data['path'])[0]).encode()+
                u = f.read()
                
            self.header = Header()
            globals_var = self.getGlobal().copy()
            self.var = globals_var

            for i in glo:
                self.var[i] = glo[i]

            try:
                u = compile(u, '', 'exec')
                exec(u, self.var)

                del globals_var, u
            except Exception as e:
                self.err("codeerror", e)
                return

            self.cache2.save()

            datas = self.header.encode()+b'\r\n'
            datas += self.cache2.read().encode()+b'\r\n\r\n'

            self.conn.send(datas)
        else:
            self.err("404")

    @profile
    def fl(self, data):
        self.status = 'in fl func.'
        if data['path'][-3:] == '.py':
            self.py(data)
            return
        if os.path.isfile(ServerPath+"/"+data['path']):
            tsize = os.path.getsize(ServerPath+"/"+data['path'])
            size = tsize
            header = Header()

            if 'range' in data:
                ranges = getRange(data['range'].split("=")[1].strip())

                size = (ranges[1] + 1 if not ranges[1] == '' else size) - ranges[0]
                header.set("Content-Range", "bytes %s-%s/%s"%(ranges[0], ranges[1] if not ranges[1] == '' else tsize-1, tsize))     
                header.set(0, "HTTP/1.1 206 Partial Content")
                    
            header.set("Content-Type", FileType(data['path']))
            header.set("Content-Length", "%s"%(size if not 'range' in data else (ranges[1] if not ranges[1] == '' else tsize)-ranges[0]))
            #header.set("Content-Encoding", "gzip")

            #self.conn.send(header.encode()+b'\r\n')
            h = header.encode()+b'\r\n'

            with open(ServerPath+"/"+data['path'], 'rb') as f:
                if 'range' in data:
                    f.seek(ranges[0])
                    d = f.read((ranges[1] if not ranges[1] == '' else tsize) + 1)
                    self.conn.send(h+d)
                    return

                try:
                    x = f.read()
                    self.conn.sendall(h+x)

                except Exception as e:
                    print(e)
                    
                    
        else:
            self.err('404')

    @profile
    def err(self, ty, x=''):
        header = Header()
        header.set("Content-Type","text/html")
        if ty == 'codeerror':
            header.set(0, "HTTP/1.1 500 Code Error")
            self.conn.send(header.encode()+b'\r\n')
            self.conn.send(b"<html><body><center><h1>Python Error</h1>")
            self.conn.send(b"<br><font color='red'>Error: </font>"+str(x).encode()+b"(at line "+str(x.__traceback__.tb_lineno).encode()+b")</body></html>")
            return
        if not str(ty) in http_errorcodes:
            header.set(0, "HTTP/1.1 500 Service Error")
            self.conn.send(header.encode()+b'\r\n')
            self.conn.send((ERRPage % ('500', ty, x)).encode())
        else:
            header.set(0, "HTTP/1.1 %s %s"%(ty, http_errorcodes[str(ty)][0]))
            self.conn.send(header.encode()+b'\r\n')
            self.conn.send((ERRPage % (ty, http_errorcodes[str(ty)][0], http_errorcodes[str(ty)][1])).encode())

    @profile
    def include(self, path):
        pathx=ServerPath+"/"+os.path.split(self.data['path'])[0]
        path = pathx+"/"+path

        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                u = f.read()
                
            #globals_var = self.getGlobal()
            globals_var = self.var
            s = {}

            exec(("import sys;sys.path.append('%s')\n"%pathx)+u, globals_var)

            """name = os.path.split(path)[1].split('.')[0]
            self.var[name] = Module(dict_inone(s, globals_var))"""
            x = dict_inone(s, globals_var)
            for i in x:
                self.var[i] = x[i]
        else:
            self.err("codeerror", "Cannot find module in path: '%s'"%path)

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
        self.headers["Accept-Ranges"] = "bytes"
        
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

a=Server(ip='IP')
a.start()

#OPEN WITH SSL
b=Server(ip='IP', port=443)
b.open_SSL()
b.start()

