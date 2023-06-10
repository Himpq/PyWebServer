# -*- encoding: utf-8 -*-
"""
    PyWebServer
    By Himpq| Created in 2020-10-12
"""

from Logger import Logger
from server_config import ServerPath, ip, port  #为了不再让Vscode这个沙雕报错
from server_config import *
from ParsingHTTPData import *
from stringParser import *
from functions import *
from Collection import *
import DispatchThread as DT
import socket
import time
import sys
import os
import re
import ssl
import re
import traceback
import H2Response as h2r

setDT(DT)

sys.path.append("./Plugins")

#sys.setrecursionlimit(3000)

from threading import Thread, Lock
ThreadLock = Lock()
Coll = Collection()

if not os.path.isdir("logs"):
    os.mkdir("logs")
    open("./logs/log.txt", 'w').close()

ssl._create_default_https_context = ssl._create_unverified_context

SERVER = "PWS"
VERSION = "/6.1"

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
        
        sslPath = config['ssl-path']
        self.ssl_context.load_cert_chain(certfile=sslPath[0], keyfile=sslPath[1], password=config['ssl-password'])
        self.ssl_context.load_verify_locations(sslPath[2])
        self.ssl_context.set_alpn_protocols(config['support-protocols'])
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

                obj  = ServerResponse(addr, ident, self)
                user = Thread(target=obj.response, args=(conn, self.coll))
                user.start()
                #DT.addThread(user)
                Logger.info("接收来自", addr, "的请求 | ID:", ident)  #, "线程状态:", user)
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
                print(traceback.format_exc())
                return
            except Exception as e:
                e2 = traceback.format_exc()
                print(e, e2)
                continue

    def start(self):
        Logger.comp("服务器启动。")
        Logger.info("Listening: %s:%s"%(self.ip, self.port))
        self.is_start = True

        #self.coll = mpt.MNG.dict({}) if config['use-multiprocessing'] else Coll#进程间使用Manager.dict以代替Collection
        self.coll = Coll

        self.socket = socket.socket()
        self.socket.bind((self.ip, self.port))
        self.socket.listen(self.maxlisten)
        
        self.accept_thread = Thread(target=self._accept)
        self.accept_thread.setDaemon(True)
        self.accept_thread.start()

    def stop(self):
        self.is_start = False
        self.socket.close()


class ServerResponse:
    # HTTP/1.1 的响应
    def __init__(self, ip, ident, server):
        
        self.server = server
        self.ident = ident  #没啥用
        
        self.ip = ip
        self.cachesize = config['cachesize']
        
        self.ETagMode = True
        self.runin = ''
        self.status = 'in init func.'
        self.inHTTP2 = False
        self.http2Res = None
        self.finish = False
        self.enableGzip = False
        self.priority = 1
        self.frame = None   #HTTP2 Feature

    def getFrame(self) -> h2r.FrameParser:
        return self.frame if self.frame else {}
    
    def clearEnvironment(self, conn, coll, frame, isSelf=False):
        if isSelf:
            newObj = self
            newObj.conn = conn #
            newObj.connfile = conn.makefile('rb') #
        else:
            newObj = ServerResponse(self.ip, self.ident, self.server)
        newObj.collection = coll
        newObj.frame  = frame
        newObj.cache2 = FileCache()
        newObj.header = Header()
        newObj.finish = False
        newObj.LineFeed = b''
        newObj.SingleLineFeed = b'\r\n'
        newObj.PythonFileCloseConnect = False
        return newObj

    def response(self, conn, coll, already_keep_alive=0):
        if not self.server == None and self.server.ssl and not self.inHTTP2 and not isinstance(conn, ssl.SSLSocket):# and not isinstance(conn, ssl.SSLSocket):
            #进行 SSL 判断
            dup = conn.dup()
            try:
                useHTTPS = True
                sslconn = self.server.ssl_context.wrap_socket(conn, server_side=True, do_handshake_on_connect=config['ssl-doshakehand'])
            except ssl.SSLError as e:
                if "CERTIFICATE_UNKNOWN" in str(e):
                    Logger.warn("证书存在问题：", str(e))
                    return
                elif "http request" in str(e):
                    Logger.warn("客户端正在请求 HTTP。")
                    useHTTPS = False
                    try:
                        ctx = dup.recv(1024).decode()
                    except:
                        return
                    header = parsingHeaderByString(ctx, noMethod=True)
                    dup.send(b'HTTP/1.1 302 Do this!\r\nlocation:https://'+((str(setting['ssljump-domain']).encode()+b':'+str(self.server.port).encode()) if not header.get("headers").get('host') else header['headers'].get("host").encode())+(b'/' if not header.get("path") else b'/'+header.get('path').encode())+b'\r\n\r\n<h1>HELLO!</h1>\r\n\r\n')
                    dup.close()
                    return
                else:
                    Logger.error("证书存在严重问题：", e)
                    return
            else:
                if useHTTPS:
                    conn = sslconn

        #self.clearEnvironment(conn, coll, self.frame, True)
        self.conn       = conn
        self.collection = coll

        Logger.comp("[长连接] 响应:", self.ip) if already_keep_alive else Logger.comp("响应IP: ", self.ip)

        #判断是否是 HTTP2 连接，如果是就交由H2R模块进行处理
        if h2r.JudgeH2(self.conn):
            #Logger.info(self.conn.selected_alpn_protocol())
            h2r.ServerResponseHTTP2(self, self.ident).response()
            self.inHTTP2 = True
            return

        time1 = time.time()
        self.status = 'in response func.'
        self.data   = '' #处理数据(处理后的list(即py文件中的_DATA))
        self.ysdata = '' #原始数据(未经处理的请求头)(bytes->string)
        def getx():
            self.ysdata , self.data = parsingHeader(self.connfile, self.conn)
            
        self.getdatathread = Thread(target=getx)
        self.getdatathread.start()

        #判断连接是否超时，超时就炸了它
        self.getdatathread.join(config['timeout'])
        if self.ysdata == '' and (self.data == '' or self.data == HEADER_MODULE) and self.getdatathread.is_alive():
            try:
                stop_thread(self.getdatathread)
            except Exception as e:
                print("Cannot stop thread because of", e)
            Logger.error(self.ip[0], "超时:", ("YSData:", self.ysdata, "Data:", self.data == '', "ThreadIsAlive", self.getdatathread.is_alive()))
            self.conn.send(b'\r\n\r\n')
            self.conn.shutdown(socket.SHUT_WR)
            self.conn.shutdown(socket.SHUT_RD)
            self.connfile.close()
            self.conn.close()
  
            return 0

        if self.data['headers'].get("host") == None or self.data.get("path") == None:
            return

        #Logger.warn(self.data)
        #Logger.warn(self.ysdata)
        Logger.info("请求路径: ", self.data['headers']['host'] + self.data['path'])

        setLog("IP:"+str(self.ip)+"|Path:"+self.data['headers']['host'] + self.data['path'])

        #绑定域名功能，停用。
        #if not self.data.get("host", None) in bind_domains and not isIPv4(self.data.get("host")):
        #    self.err("内部错误", "未绑定的域名，请在配置中添加。")
        #    return

        #判断是否是长连接
        if (self.data['headers'].get("connection") == 'keep-alive' or already_keep_alive) and not self.PythonFileCloseConnect:
            self.header.set("connection", 'keep-alive')
            self.header.set("keep-alive", "timeout="+str(config['timeout'])+", max="+str(config['keep-alive-max']))
            self.header.set(":ResponseTimes", str(already_keep_alive))
            #Logger.warn(self.data)
        else:
            self.header.set("connection", "close")
        
        #判断是否是表单信息
        ThreadLock.acquire()
        if self.data['headers'].get("content-type", None) == 'multipart/form-data':
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
                import traceback
                Logger.error(e, "(at line", e.__traceback__.tb_lineno,")")
                Logger.error(traceback.format_exc())
        ThreadLock.release()
        time2 = time.time()

        Logger.comp("响应结束。响应时间: %ss"%(time2-time1))
        self.status = 'kill me.'

        try:
                if (self.data['headers'].get("connection") == 'keep-alive' or already_keep_alive) and not self.PythonFileCloseConnect:
                    if not already_keep_alive >= int(config['keep-alive-max']):
                        res = ServerResponse(self.ip, self.ident, self.server)
                        thr = Thread(target=res.response, args=(self.conn, self.collection, already_keep_alive+1))
                        thr.start()
                    else:
                        self.conn.send(b'\r\n\r\n')
                        self.conn.shutdown(socket.SHUT_WR)
                        self.conn.shutdown(socket.SHUT_RD)
                        self.connfile.close()
                        self.conn.close()
                        Logger.warn("[长连接] 最大单链接处理上限。")
                        return
                else:
                #防止连接关闭出错
                    self.connfile.close()
                    self.conn.close()
                    return
        except Exception as e:
                import traceback
                print(e, traceback.format_exc())
        
    def set_cookie(self, key, val, expires=3600):
        self.header.set("set-cookie", "%s=%s; Expires=%s;"%(key, val, expires), True)
    def set_header(self, key, val):
        self.header.set(key, str(val))
    def set_statuscode(self, code, content): #404, File not found
        self.header.set(0, "HTTP/1.1 "+str(code)+" "+content)
    def set_html(self, *val, **arg):
        val = list(val)
        #for i in range(len(val)):
        #    if(isinstance(val[i], str)):
        #        val[i] = ParseString(val[i], self.var)
        print(*val, **arg, file=self.cache2)
    def finish_send(self, onEC):
        onEC() if onEC else None
    def getGlobal(self, onHF=None, onEC=None):
        globals_var = {}
        globals_var['set_cookie']       = self.set_cookie
        globals_var["set_header"]       = self.header.set
        globals_var['finish_header']    = lambda: self.finish_header(onHF)
        globals_var['finish_send']      = lambda: self.finish_send(onEC)
        globals_var['set_statuscode']   = self.set_statuscode
        globals_var['set_priority']     = self.setPriority
        globals_var["print"]            = lambda *arg, **args: self.printToSocketOrCache(*arg, **args)
        globals_var['isHTTP2']          = self.inHTTP2
        globals_var['include']          = lambda path: self.include(path)
        globals_var['set_disable_etag'] = self.setDisableETag
        globals_var['_POST']            = self.data['postdata']
        globals_var['_GET']             = self.data['getdata']
        globals_var['_REWRITE']         = self.data['rewritedata']
        globals_var['_COOKIE']          = self.data['cookie']
        globals_var['_HEADER']          = self.data['headers']
        globals_var['Logger']           = Logger
        globals_var['this']             = self
        globals_var['_FILE']            = {}
        globals_var["_DATA"]            = {}
        globals_var["_COLL"]            = self.collection

        return globals_var

    def uploadFile(self, data):
        self.status = 'in uploadFile func.'
        if data['headers'].get("boundary"):
            if data['path'][-3:] == '.py':
                x = parsingUpdateFile(self.connfile, data['headers']['boundary'], self.conn, data)
                if not len(x) == 0:
                    do = {"_FILE":x[0], "_DATA":x[1]}
                else:
                    do = {}
                self.PythonFileHandle(data, do)
                return
            x = parsingUpdateFile(self.connfile, data['headers']['boundary'], self.conn, data)
            self.CommonFileHandle(data, glo={"_FILE":x[0], "_DATA":x[1]})
        return


    @priorityHigh
    def PythonFileHandle(self, data, glo={}, onHeaderFinish=None, onEndCallback=None):
        conn = self.conn

        self.priority = 0.2
        header        = self.header
        self.status   = 'in PythonFileHandle func.'

        if config['python'] == False:
            #判断配置文件是否禁用了 Python web功能
            return

        if self.PythonFileCloseConnect: #not self.inHTTP2:
            self.header.remove("connection")
            self.header.remove("keep-alive")
            self.header.set("connection", "close")
            self.PythonFileCloseConnect = True

        if os.path.isfile(ServerPath+"/"+data['path']):
            realpath = ServerPath+"/"+data['path']
            with open(realpath, 'rb') as f:
                #下面注释添加在 f.read() 之前用于给被执行的 Python web 文件提供该文件目录下的环境（由于是在 server.py中执行所以没有目标目录下的变量）
                #但是由于已经有了 Server.include 方法导入目标目录下的 Python 模块所以可以注释掉
                # "import os; os.chdir('{0}'); del os;\n".format(ServerPath+"/"+os.path.split(data['path'])[0]).encode()+
                PythonFileCode = b"import sys;sys.path.append('./Plugins');del sys;\n"+f.read()


            #设置上用户自定义的响应头
            headersetting = opts.get("headers")

            for i in headersetting:
                matchFile = re.findall(i, realpath)
                if matchFile:
                    header_head = headersetting[i]
                    header.set(header_head[0], header_head[1]);

            #配置环境变量
            globals_var = self.getGlobal(onHeaderFinish, onEndCallback).copy()
            self.var = globals_var

            for i in glo:
                self.var[i] = glo[i]

            #执行 Python web 文件
            try:
                codeCompile = compile(PythonFileCode, '', 'exec')
                exec(codeCompile, self.var)

                onEndCallback() if onEndCallback else None
                Logger.error("CODE FINISH")

                del globals_var, PythonFileCode
            except Exception as e:
                self.err("codeerror", e, traceback.format_exc())
                return

            if not self.finish:
                #如果没有执行 Server.finish_header 函数就直接将数据输出
                self.cache2.save()
                pythonPrintContent = self.cache2.read().encode()
                
                #ETag 缓存
                Mode304 = False
                if self.ETagMode:
                    ETag    = getHash(pythonPrintContent)
                    ClientETag = data['headers'].get('if-none-match')
                    if ClientETag and ClientETag == ETag:
                        header.set(0, "HTTP/1.1 304 Not Modified")
                        header.remove("content-length")
                        Mode304 = True
                        if self.inHTTP2:
                            onHeaderFinish = lambda: header.send(5)
                    else:
                        header.set("ETag", ETag)

                datas = b''
                if not self.inHTTP2:
                    header.set("content-length", len(pythonPrintContent))
                    datas = header.encode()+self.SingleLineFeed
                else:
                    onHeaderFinish() if onHeaderFinish else 1
                datas += (pythonPrintContent if not Mode304 else b"")+self.LineFeed

                if len(datas) >= self.cachesize:
                    sendTimes = len(datas) // self.cachesize
                    endSize   = len(datas) - sendTimes * self.cachesize
                    for i in range(sendTimes):
                        NowData = datas[self.cachesize*i: self.cachesize*(i+1)]
                        conn.send(NowData)

                    conn.send(datas[-endSize:])
                    conn.send(self.LineFeed)
                else:
                    conn.send(datas)
                    conn.send(self.LineFeed)

                if self.inHTTP2:
                    conn.send(b'', 1)
        else:
            self.err("404")


    def PyInHtmlHandle(self, data, glo={}, onHeaderFinish=None):
        self.priority = 0.2
        realpath = ServerPath+"/"+data['path']

        if os.path.isfile(realpath):
            with open(realpath, 'r', encoding='UTF-8') as f:
                content = f.read()
            
            if not "<!-- py -->" in content:
                self.CommonFileHandle(data, onHeaderFinish, False)
                return

            if self.PythonFileCloseConnect: #not self.inHTTP2:
                self.header.remove("connection")
                self.header.remove("keep-alive")
                self.header.set("connection", "close")
                self.PythonFileCloseConnect = True
            
            M = r"(<\?py)(.*?)(\?>)"
            pycodes = re.findall(M, content, flags=re.S)

            env = self.getGlobal(onHeaderFinish, None)
            self.var = env

            del self.var['print']
            del self.var['finish_header']

            ctxs = {}
            ID   = 0
            
            def p(*arg, **args):
                nonlocal ctxs, ID
                p = ''
                for i in arg:
                    p += str(i)+" "
                if ctxs.get(ID, None):
                    ctxs[ID] += p
                    return
                ctxs[ID] = p

            self.var['print'] = p
            self.var = dict_inone(self.var, glo)

            self.header.set("content-type", "text/html")

            #Logger.error(pycodes)

            for code in pycodes:
                c   = code[1]
                if len(c.split("\n")) == 1: #单行代码
                    c = c.lstrip()
                exec(c, self.var)
                content = content.replace(code[0]+code[1]+code[2], ctxs.get(ID, ""), 1)

                ID += 1
            
            if self.inHTTP2:
                onHeaderFinish() if onHeaderFinish else None
            else:
                self.conn.send(self.header.encode()+self.SingleLineFeed)
            self.conn.send(content.encode("UTF-8"))

            if self.inHTTP2:
                self.conn.send(self.LineFeed, 1)


    def CommonFileHandle(self, data,  onHeaderFinish=None, retToPy=True, glo={}):
        header = self.header
        conn = self.conn
        self.status = 'in CommonFileHandle func.'

        if data['path'][-3:] == '.py':
            self.PythonFileHandle(data, glo=glo)
            return
        
        if data['path'][-4:] in ('html', '.htm') and retToPy:
            self.PyInHtmlHandle(data, onHeaderFinish=onHeaderFinish, glo=glo)
            return

        realpath = ServerPath+"/"+data['path']
        if os.path.isfile(realpath):
            tsize = os.path.getsize(realpath)  #文件总大小(Total Size)
            size = tsize                       #断点续传需要返回的大小（初始值为文件总大小）
            Logger.comp('->', realpath, size)

            #print(data)

            if 'range' in data['headers']: 
                #断点续传功能
                ranges = getRange(data['headers']['range'].split("=")[1].strip())

                size = (ranges[1] + 1 if not ranges[1] == '' else size) - ranges[0]
                header.set("Content-Range", "bytes %s-%s/%s"%(ranges[0], ranges[1] if not ranges[1] == '' else tsize-1, tsize))     
                header.set(0, "HTTP/1.1 206 Partial Content")
                    
            header.set("Content-Type", FileType(data['path']))
            header.set("Content-Length", "%s"%(size if not 'range' in data['headers'] else (ranges[1]+1 if not ranges[1] == '' else tsize)-ranges[0]))

            #用户自定义头信息
            headersetting = opts.get("headers")

            for i in headersetting:
                matchFile = re.findall(i, realpath)
                if matchFile:
                    header_head = headersetting[i]
                    header.set(header_head[0], header_head[1])
            
            with open(realpath, 'rb') as f:
                if 'range' in data['headers']:
                    #断点续传
                    
                    if not self.inHTTP2:
                        h = header.encode()+self.SingleLineFeed
                        conn.send(h)
                    else:
                        onHeaderFinish() if onHeaderFinish else 1
                        #Logger.info("onFinishHeader in Range!")
                    
                    f.seek(ranges[0])

                    CacheSize = self.cachesize

                    readTotalSize = ((ranges[1] + 1) if not ranges[1] == '' else tsize) - ranges[0] #需要从 ranges[0] 读取到的部分
                    numOfRead     = (readTotalSize // CacheSize) if readTotalSize > CacheSize else 1
                    end           = (readTotalSize - numOfRead*CacheSize) if readTotalSize > CacheSize else 0

                    if readTotalSize < CacheSize:
                        CacheSize = readTotalSize

                    #totalSend = 0
                    for i in range(numOfRead+1):
                        try:
                            d = f.read(CacheSize if not i == numOfRead else end)
                            conn.sendall(d)
                            #totalSend += len(d)
                            #print("SEND", len(d), totalSend, readTotalSize, numOfRead, end, ranges)
                        except Exception as e:
                            if getattr(conn, "_closed"):
                                f.close()
                                return
                    f.close()
                    if self.inHTTP2:
                        conn.send(self.LineFeed, 1)
                        return
                    conn.send(self.LineFeed) if not self.LineFeed == b'' else None
                    return

                try:
                    #ETag缓存，非断点续传，担心内存溢出，使用缓存读法编出ETag
                    Mode304 = False
                    if not os.path.getsize(realpath) >= config['maxsize-for-etag']:
                        #判断文件大小是否大于配置中设置的最大大小，否则不使用ETag浪费服务器资源。
                        ETag       = getHashByFile(open(realpath, 'rb'))
                        ClientETag = data['headers'].get('if-none-match')
                        if ClientETag and ClientETag == ETag:
                            header.set(0, "HTTP/1.1 304 Not Modified")
                            header.remove("Content-Length")
                            Mode304 = True
                            if self.inHTTP2:
                                onHeaderFinish = lambda: header.send(5)
                        else:
                            header.set("ETag", ETag)

                    #发送响应头
                    if not self.inHTTP2:
                        h = header.encode()+self.SingleLineFeed
                        conn.send(h)
                    else:
                        onHeaderFinish() if onHeaderFinish else 1

                    if not Mode304:
                        #客户端没有进行缓存
                        #Logger.info(self.inHTTP2)
                        cont = f.read(self.cachesize)
                        while not cont == b'':
                            if self.inHTTP2:
                                conn.sendall(cont, 0)
                            else:
                                conn.sendall(cont)
                            cont = f.read(self.cachesize)
                        if self.inHTTP2:
                            conn.send(self.LineFeed, 1)
                        
                    if not self.inHTTP2:
                        conn.send(self.LineFeed) if not self.LineFeed == b'' else None
                    
                    f.close()
                except Exception as e:
                    Logger.error("[CommonFileHandle] >> ", e)
                    print(traceback.format_exc())
                    f.close()
                    
                    
        else:
            self.err("404")


    def err(self, type_, exception='', detail=''):
        if not self.inHTTP2:

            header = Header()
            header.set("Content-Type","text/html")

            if type_ == 'codeerror':
                if not self.finish:
                    header.set(0, "HTTP/1.1 500 Code Error")
                    self.conn.send(header.encode()+self.SingleLineFeed)

                self.conn.send(b"<html><head><meta charset='utf-8'></head><body><center><h1>Python Error</h1>")
                detail = detail.replace("<", "&lt;").replace(">", "&gt")
                detail = tryGetErrorDetail(detail, ServerPath+"/"+self.data['path'])
                self.conn.send(b"<br><font color='red'>Error: </font>"+str(exception).encode()+b"(at line "+str(exception.__traceback__.tb_lineno).encode("UTF-8")+\
                               b")<br></center><div style='margin:30px'>Detail:<br><div style='padding:30px;line-height: 2;'>"+detail.replace("\n", "<br>").encode()+\
                               b"</div></div></body></html>")
                return

            if not str(type_) in http_errorcodes:
                header.set(0, "HTTP/1.1 500 Service Error")
                self.conn.send(header.encode()+self.SingleLineFeed)
                self.conn.send((ERRPage().format('500', type_, exception)).encode())

            else:
                header.set(0, "HTTP/1.1 %s %s"%(type_, http_errorcodes[str(type_)][0]))
                self.conn.send(header.encode()+self.SingleLineFeed)
                self.conn.send((ERRPage().format(type_, http_errorcodes[str(type_)][0], http_errorcodes[str(type_)][1])).encode())
        else:
            self.http2Res.error(type_, self.getFrame(), exception, detail, self.conn)
            #Logger.error("页面错误:", type_, exception, detail, self.data['path'])
            Logger.error(f'''页面错误:
    Type: {type_}
    Exception: {exception}
    Path: {self.data['path']}
    Detail:
{detail}''')


    def include(self, path):
        pathx=ServerPath+"/"+os.path.split(self.data['path'])[0]
        path = pathx+"/"+path

        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                u = f.read()
                
            #globals_var = self.getGlobal()
            if "var" in self.__dict__:
                globals_var = self.var
            else:
                globals_var = self.getGlobal()

            s = {}

            exec(("import sys;sys.path.append('%s')\n"%pathx)+u, globals_var)

            """name = os.path.split(path)[1].split('.')[0]
            self.var[name] = Module(dict_inone(s, globals_var))"""
            x = dict_inone(s, globals_var)
            for i in x:
                self.var[i] = x[i]
        else:
            self.err("codeerror", "Cannot find module in path: '%s'"%path)

    def finish_header(self, onHeaderFinish=None):
        """用于结束设置 HTTP响应头，将 print 函数输出对象转为 socket 连接"""
        Logger.info("Finish header.")
        conn = self.conn
        if self.inHTTP2:
            onHeaderFinish() if onHeaderFinish else None
        else:
            h = self.header.encode()+self.SingleLineFeed
            conn.sendall(h)
        self.finish = True
        data = self.cache2.read().encode()
        conn.send(data) if not len(data) == 0 else None


    def setPriority(self, priority=1):
        """用于设置线程优先级，方便调度"""
        self.priority = priority
        

    def printToSocketOrCache(self, *arg, **args):
        "判断是否使用了 finish_header 以 print 直接向 socket 输出"
        conn = self.conn
        if not self.finish:
            self.set_html(*arg, **args)  
        else:
            sep = b" " if not args.get("sep") else args.get("sep")
            end = b"\r\n" if not args.get("end") else args.get("end")
            
            for i in range(len(arg)):
                v = arg[i]
                try:
                    conn.send(v+(sep if not i == len(arg)-1 else b''))
                    #conn.send(end)
                except:
                    if getattr(self.conn, "_closed", False):
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
        self.headers[0] = "HTTP/1.1 200 OK"
        self.headers["accept-ranges"] = "bytes"
        self.headers["connection"] = 'keep-alive'
        self.headers["Content-Encoding"] = "identity"
        self.headers["Transer-Encoding"] = "identity"
        self.headers["date"] = time.asctime()
        self.headers["server"] = SERVER+VERSION
        
    def set(self, key, val, diejia=False):
        if key in self.headers:
            if diejia:
                self.headers[key] += str(val)
                return
        self.headers[key] = str(val)
    def remove(self, key):
        try:
            del self.headers[key]
        except:
            return
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
    a.open_SSL() if setting['ssl'] else None
    a.start()

if __name__ == '__main__':
    #mpt.start() if config['use-multiprocessing'] else None

    test()
    Logger.warn("[Server] MainPID:", os.getpid())

    #防止不开启多进程导致主进程马上就屎了（因为线程使用守护线程）
    a.accept_thread.join()
    input("ERROR")
