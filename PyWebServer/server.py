# -*- encoding: utf-8 -*-
"""
    PyWebServer
    By Himpq| Created in 2020-10-12
"""

from Logger import Logger
from server_config import ServerPath, ip, port
from server_config import *
from ParsingHTTPData import *
from functions import *
from Collection import *
import socket
import time
import sys
import os
import re
import ssl
import re
#sys.setrecursionlimit(3000)

import mpthread as mpt

Coll = Collection()

if not os.path.isdir("logs"):
    os.mkdir("logs")
    open("logs/log.txt", 'w').close()

ssl._create_default_https_context = ssl._create_unverified_context

SERVER = "PWS"
VERSION = "/4.7"

def startThreadByMPT(thr):
    if not config['use-multiprocessing']:
        thr.start()
    else:
        mpt.Threadings.append(thr)

#服务器
class Server:
    def __init__(self, ip='localhost', port=80, maxlisten=128):
        self.is_start = False
        self.ip = ip
        self.port = port
        self.maxlisten = maxlisten
        self.tpool = {}
        self.ssl = False

    def open_SSL(self):
        self.ssl = True
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23) #SSLv23
        sslPath = config['config']['sslpath']
        self.ssl_context.load_cert_chain(certfile=sslPath[0], keyfile=sslPath[1])
        #self.ssl_context.load_verify_locations(sslpath[2])
        #self.ssl_context.verify_mode = ssl.CERT_REQUIRED
        
    '''def __setattr__(self, key, val):
        if 'is_start' in self.__dict__ and self.is_start:
            raise KeyError("Cannot change any arguments when server is running.")
        self.__dict__[key] = val'''

    def _accept(self):
        ident = 0
        while self.is_start:
            try:
                conn, addr = self.socket.accept()

                if self.ssl:
                    conn = self.ssl_context.wrap_socket(conn, server_side=True)

                obj  = ServerResponse(addr, ident)
                user = mpt.Thread(target=obj.response, args=(conn, self.coll))
                startThreadByMPT(user)
                Logger.info("接收来自", addr, "的请求 | ID:", ident)
                #print("Recv from",addr, "| Ident:", ident)
                #self.tpool[ident] = [user, obj]
                ident += 1
            except KeyboardInterrupt as e:
                print("Exit by keyboard.")
                return
            except SystemError as e:
                print("Exit by system error.", e)
                return
            except OSError as e:
                print("[Server] Exit by >>", e)
                return
            except Exception as e:
                import traceback
                e2 = traceback.format_exc()
                print(e, e2)
                continue

    def start(self):
        Logger.comp("服务器启动。")
        Logger.info("Listening: %s:%s"%(self.ip, self.port))
        self.is_start = True

        self.coll = mpt.MNG.dict({}) if config['use-multiprocessing'] else Coll#进程间使用Manager.dict以代替Collection

        self.socket = socket.socket()
        self.socket.bind((self.ip, self.port))
        self.socket.listen(self.maxlisten)
        
        self.accept_thread = mpt.Thread(target=self._accept)
        self.accept_thread.setDaemon(True)
        self.accept_thread.start()

    def stop(self):
        self.is_start = False
        self.socket.close()

class ServerResponse:
    def __init__(self, ip, ident, server=None):
        
        #self.server = server
        self.ident = ident  #没啥用
        
        self.ip = ip
        self.cachesize = 4096
        
        self.ETagMode = True

        Logger.comp("响应IP: ", ip)
        self.runin = ''
        self.finish = False
        self._DATA = {}
        self._FILE = {}

        self.status = 'in init func.'

    def response(self, conn, coll=None):
        self.collection = coll
        self.conn = conn
        self.connfile = conn.makefile('rb')
        self.cache2 = FileCache()

        time1 = time.time()
        self.status = 'in response func.'
        self.data   = '' #处理数据(处理后的list(即py文件中的_DATA))
        self.ysdata = '' #原始数据(未经处理的请求头)(bytes->string)
        def getx():
            self.ysdata , self.data = parsingHeader(self.connfile, self.conn)
            
        self.getdatathread = mpt.Thread(target=getx)
        self.getdatathread.start()

        #判断连接是否超时，超时就炸了它（15s)
        self.getdatathread.join(config['timeout'])
        if self.ysdata == '' or self.data == '' or self.getdatathread.is_alive():
            try:
                stop_thread(self.getdatathread)
            except:
                pass
            print("Time out.")
            self.conn.close()
            self.connfile.close()
            return 0

        if self.data.get("host") == None or self.data.get("path") == None:
            return
        Logger.info("请求路径: ", self.data['host'] + self.data['path'])

        #绑定域名功能，停用。
        #if not self.data.get("host", None) in bind_domains and not isIPv4(self.data.get("host")):
        #    self.err("内部错误", "未绑定的域名，请在配置中添加。")
        #    return
        #print(self.data)
        #判断是否是表单信息
        if self.data.get("content-type", None) == 'multipart/form-data':
            self.uploadFile(self.data)
        else:
            try:
                realpath = ServerPath+"/"+self.data['path']

                if os.path.isfile(realpath) and self.data['path'][-3:] == '.py':
                    #如果是PythonWeb文件
                    self.PythonFileHandle(self.data)
                elif os.path.isdir(realpath):
                    #如果请求路径为一个文件夹
                    for i in config['default-page']:
                        if os.path.isfile(realpath+'/'+i):
                            self.data['path'] = self.data['path']+'/'+i
                            break
                    if i[-3:] == '.py':
                        self.PythonFileHandle(self.data)
                    else:
                        self.CommonFileHandle(self.data)
                else:
                    self.CommonFileHandle(self.data)

            except Exception as e:
                Logger.error(e, "(at line", e.__traceback__.tb_lineno,")")

        time2 = time.time()

        Logger.comp("响应结束。响应时间: %ss"%(time2-time1))
        self.status = 'kill me.'

        try:
                #防止连接关闭出错
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
        print(*val, **arg, file=self.cache2)
    def getGlobal(self):
        globals_var = {}
        globals_var['set_cookie']       = self.set_cookie
        globals_var["set_header"]       = self.header.set
        globals_var['finish_header']    = self.finish_header
        globals_var['set_statuscode']   = self.set_statuscode
        globals_var["print"]            = self.FinishReturn
        globals_var['include']          = self.include
        globals_var['set_disable_etag'] = self.setDisableETag
        globals_var['_POST']            = self.data['postdata']
        globals_var['_GET']             = self.data['getdata']
        globals_var['_REWRITE']         = self.data['rewritedata']
        globals_var['_COOKIE']          = self.data['cookie']
        globals_var['_HEADER']          = self.data
        globals_var['Logger']           = Logger
        globals_var['this']             = self
        globals_var['_FILE']            = {}
        globals_var["_DATA"]            = {}
        globals_var["_COLL"]            = self.collection

        return globals_var

    @profile
    def uploadFile(self, data):
        self.status = 'in uploadFile func.'
        if data.get("boundary"):
            if data['path'][-3:] == '.py':
                x = parsingUpdateFile(self.connfile, data['boundary'], self.conn)
                if not len(x) == 0:
                    do = {"_FILE":x[0], "_DATA":x[1]}
                else:
                    do = {}
                self.PythonFileHandle(data, do)
                return
            x = parsingUpdateFile(self.connfile, data['boundary'], self.conn)
            self.PythonFileHandle(data, {"_FILE":x[0], "_DATA":x[1]})
        return

    @profile
    def PythonFileHandle(self, data, glo={}):
        self.status = 'in PythonFileHandle func.'

        if config['python'] == False:
            #判断配置文件是否禁用了 Python web功能
            return

        if os.path.isfile(ServerPath+"/"+data['path']):
            realpath = ServerPath+"/"+data['path']
            with open(realpath, 'rb') as f:
                #下面注释添加在 f.read() 之前用于给被执行的 Python web 文件提供该文件目录下的环境（由于是在 server.py中执行所以没有目标目录下的变量）
                #但是由于已经有了 Server.include 方法导入目标目录下的 Python 模块所以可以注释掉
                # "import os; os.chdir('{0}'); del os;\n".format(ServerPath+"/"+os.path.split(data['path'])[0]).encode()+
                PythonFileCode = f.read()
                
            self.header = Header()

            #设置上用户自定义的响应头
            headersetting = opts.get("headers")

            for i in headersetting:
                matchFile = re.findall(i, realpath)
                if matchFile:
                    header_head = headersetting[i]
                    self.header.set(header_head[0], header_head[1]);

            #配置环境变量
            globals_var = self.getGlobal().copy()
            self.var = globals_var

            for i in glo:
                self.var[i] = glo[i]

            #执行 Python web 文件
            try:
                codeCompile = compile(PythonFileCode, '', 'exec')
                exec(codeCompile, self.var)

                del globals_var, PythonFileCode
            except Exception as e:
                self.err("codeerror", e)
                return

            if not self.finish:
                #如果没有执行 Server.finish_header 函数就直接将数据输出
                self.cache2.save()
                pythonPrintContent = self.cache2.read().encode()
                
                #ETag 缓存
                Mode304 = False
                if self.ETagMode:
                    ETag    = getHash(pythonPrintContent)
                    ClientETag = data.get('if-none-match')
                    if ClientETag and ClientETag == ETag:
                        self.header.set(0, "HTTP/1.1 304 Not Modified")
                        Mode304 = True
                    else:
                        self.header.set("ETag", ETag)

                datas = self.header.encode()+b'\r\n'
                datas += (pythonPrintContent if not Mode304 else b"")+b'\r\n\r\n'

                self.conn.sendall(datas)
        else:
            self.err("404")

    @profile
    def CommonFileHandle(self, data):
        self.status = 'in CommonFileHandle func.'

        if data['path'][-3:] == '.py':
            self.PythonFileHandle(data)
            return

        realpath = ServerPath+"/"+data['path']
        if os.path.isfile(realpath):
            tsize = os.path.getsize(realpath)  #文件总大小(Total Size)
            size = tsize                       #断点续传需要返回的大小（初始值为文件总大小）
            header = Header()

            #print(data)

            if 'range' in data: 
                #断点续传功能
                ranges = getRange(data['range'].split("=")[1].strip())

                size = (ranges[1] + 1 if not ranges[1] == '' else size) - ranges[0]
                header.set("Content-Range", "bytes %s-%s/%s"%(ranges[0], ranges[1] if not ranges[1] == '' else tsize-1, tsize))     
                header.set(0, "HTTP/1.1 206 Partial Content")
                    
            header.set("Content-Type", FileType(data['path']))
            header.set("Content-Length", "%s"%(size if not 'range' in data else (ranges[1]+1 if not ranges[1] == '' else tsize)-ranges[0]))

            #用户自定义头信息
            headersetting = opts.get("headers")

            for i in headersetting:
                matchFile = re.findall(i, realpath)
                if matchFile:
                    header_head = headersetting[i]
                    header.set(header_head[0], header_head[1])

            with open(realpath, 'rb') as f:
                if 'range' in data:
                    #断点续传
                    h = header.encode()+b'\r\n'
                    self.conn.send(h)

                    f.seek(ranges[0])

                    CacheSize = config['cachesize']

                    readTotalSize = ((ranges[1] + 1) if not ranges[1] == '' else tsize) - ranges[0] #需要从 ranges[0] 读取到的部分
                    numOfRead     = (readTotalSize // CacheSize) if readTotalSize-ranges[0] > CacheSize else 1
                    end           = (readTotalSize - numOfRead*CacheSize) if readTotalSize-ranges[0] > CacheSize else 0

                    if readTotalSize < CacheSize:
                        CacheSize = readTotalSize

                    for i in range(numOfRead+1):
                        try:
                            d = f.read(CacheSize if not i == numOfRead else end)
                            self.conn.send(d)
                        except:
                            if getattr(self.conn, '_closed'):
                                return
                            continue
                    return

                try:
                    #ETag缓存，非断点续传，担心内存溢出，使用缓存读法编出ETag
                    Mode304 = False
                    if not os.path.getsize(realpath) >= config['maxsize-for-etag']:
                        #判断文件大小是否大于配置中设置的最大大小，否则不使用ETag浪费服务器资源。
                        ETag       = getHashByFile(open(realpath, 'rb'))
                        ClientETag = data.get('if-none-match')
                        if ClientETag and ClientETag == ETag:
                            header.set(0, "HTTP/1.1 304 Not Modified")
                            Mode304 = True
                        else:
                            header.set("ETag", ETag)

                    #发送响应头
                    h = header.encode()+b'\r\n'
                    self.conn.send(h)

                    if not Mode304:
                        #客户端没有进行缓存
                        cont = f.read(config['cachesize'])
                        while not cont == b'':
                            self.conn.sendall(cont)
                            cont = f.read(config['cachesize'])
                    self.conn.send(b'\r\n')

                except Exception as e:
                    Logger.error("[CommonFileHandle] >> ", e)
                    
                    
        else:
            self.err("404")

    @profile
    def err(self, ty, x=''):
        header = Header()
        header.set("Content-Type","text/html")
        if ty == 'codeerror':
            if not self.finish:
                header.set(0, "HTTP/1.1 500 Code Error")
                self.conn.send(header.encode()+b'\r\n')
            self.conn.send(b"<html><body><center><h1>Python Error</h1>")
            self.conn.send(b"<br><font color='red'>Error: </font>"+str(x).encode()+b"(at line "+str(x.__traceback__.tb_lineno).encode()+b")</body></html>")
            return
        if not str(ty) in http_errorcodes:
            header.set(0, "HTTP/1.1 500 Service Error")
            self.conn.send(header.encode()+b'\r\n')
            self.conn.send((ERRPage().format('500', ty, x)).encode())
        else:
            header.set(0, "HTTP/1.1 %s %s"%(ty, http_errorcodes[str(ty)][0]))
            self.conn.send(header.encode()+b'\r\n')
            self.conn.send((ERRPage().format(ty, http_errorcodes[str(ty)][0], http_errorcodes[str(ty)][1])).encode())

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

    def finish_header(self):        
        """用于结束设置 HTTP响应头，将 print 函数输出对象转为 socket 连接"""
        h = self.header.encode()+b'\r\n'
        self.conn.sendall(h)
        self.finish = True
        print("Finish header.")
    def FinishReturn(self, *arg, **args):
        "判断是否使用了 finish_header 以 print 直接向 socket 输出"
        if not self.finish:
            self.set_html(*arg, **args)  
        else:
            sep = b" " if not args.get("sep") else args.get("sep")
            end = b"\r\n" if not args.get("end") else args.get("end")
            
            for i in range(len(arg)):
                v = arg[i]
                try:
                    self.conn.send(v+(sep if not i == len(arg)-1 else b''))
                except:
                    if getattr(self.conn, "_closed"):
                        return
                    continue
    def setDisableETag(self, disabled):
        if disabled:
            self.ETagMode = False
        else:
            self.ETagMode = True

class Module:
    def __init__(self, dicts):
        for i in dicts:
            self.__dict__[i] = dicts[i]
            
class Header:
    def __init__(self):
        self.headers = {}
        self.headers[0] = "HTTP/1.1 200 OK!"
        self.headers["Accept-Ranges"] = "bytes"
        self.headers["Connection"] = 'close'
        self.headers["Content-Encoding"] = "identity"
        self.headers["Date"] = time.asctime()
        self.headers["Server"] = SERVER+VERSION
        
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

    
class FileCache:
    def __init__(self, trueFile=False):
        self.file = '' if not trueFile else None
    def write(self, data):
        self.file += data
    def save(self):
        pass
    def read(self):
        return self.file

a = None
def test():
    global a
    a=Server(ip=ip, port=port)
    a.start()

if __name__ == '__main__':
    mpt.start() if config['use-multiprocessing'] else None

    test()
    Logger.warn("[Server] MainPID:", os.getpid())

    #防止不开启多进程导致主进程马上就屎了（因为线程使用守护线程）
    a.accept_thread.join() if not config['use-multiprocessing'] else None  
