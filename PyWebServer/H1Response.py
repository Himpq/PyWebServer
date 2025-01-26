from Server import Server, Collection, DT, Logger, setLog
from ServerConfig import *
from Functions import FrameParser
from ParsingHTTPData import *
from threading import Thread
from Version import *
import traceback
import CacheModule as cm
import time


# Import module type (ServerResponse.include)
MODULE = 'module'
VAR    = 'var'

class Header:
    def __init__(self):
        self.headers = {}
        self.headers[0]                  = "HTTP/1.1 200 OK"
        self.headers["accept-ranges"]    = "bytes"
        self.headers["connection"]       = 'keep-alive'
        self.headers["Content-Encoding"] = "identity"
        self.headers["Transer-Encoding"] = "identity"
        self.headers["date"]             = time.asctime()
        self.headers["server"]           = version

    def setDirectly(self, key, val):
        self.headers[key] = val
        
    def set(self, key, val, superpose=False, append=False):
        """Superpose is to overlay text on the same field, append is to create a new field."""
        assert (superpose and not append) or (not superpose and append) or (not superpose and not append), 'Superpose cannot be used with append.'

        if key in self.headers:
            if superpose:
                self.headers[key] += str(val)
                return
            
        if append:
            if not key in [str(h).lower() for h in self.headers.keys()]:
                self.headers[key] = []
            self.headers[key].append(str(val))
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
        for key in self.headers:
            val = self.headers[key]
            if type(key) == int:
                p+=val.encode()
                p+=b'\r\n'
                continue
            if type(val) == list:
                for v in val:
                    p+=key.encode()+b":"+v.encode()
                    p+=b'\r\n'
                continue
            if not type(val) == str:
                val = str(val)
            if not type(key) == str:
                key = str(key)
                
            p+=key.encode()+b":"+val.encode()
            p+=b'\r\n'
        return p

class ServerResponse:
    def __init__(self, ip, ident, server:Server, conn):
        """Respond the request of HTTP/1.1"""
        

        self.server = server
        self.ident  = ident
        
        self.ip                 = ip
        self.cache              = cm.FileCache()
        self.header             = Header()
        self.LineFeed           = b''
        self.SingleLineFeed     = b'\r\n'
        self.Py_CloseConnection = False
        self.collection         = server.coll
        self.conn               = conn
        self.connfile           = conn.makefile('rb')

        self.data:         typing.Union[HeaderStructure, None] = None
        self.originalData: bytes                               = None

    def initFileHandle(self):
        from FileHandle import FileHandle
        self.fileHandle = FileHandle(self, self.conn, self.connfile, self.header, None, self.cache, False)
        self.fileHandle.Py_CloseConnection = self.Py_CloseConnection
        self.fileHandle.data               = self.data
        self.fileHandle.originalData       = self.originalData

    def response(self, alreadyKeepAlive=0):

        if not self.getHTTPHeader():
            return

        if self.data['headers'].get("host") == None or self.data.get("path") == None: #无请求路径
            Logger.error("No path and host. quit.")
            return
        
        self.initFileHandle()

        Logger.info(self.ident, "请求路径: ", self.data['headers']['host'] + self.data['path'])
        setLog("[HTTP1.1] IP: "+str(self.ip)+"   |   Path: "+self.data['headers']['host'] + self.data['path'])

        
        if (self.data['headers'].get("connection") == 'keep-alive' or alreadyKeepAlive) and not self.Py_CloseConnection: #判断是否是长连接
            self.header.set("connection", 'keep-alive')
            self.header.set("keep-alive", "timeout="+str(config['timeout'])+", max="+str(config['keep-alive-max']))
        else:
            self.header.set("connection", "close")

        self.chooseMethod()

        Logger.comp(self.ident, "响应结束。")

        if not self.data.headers.get("connection") == 'keep-alive' or self.Py_CloseConnection:
            Logger.warn("Close connection.")
            self.conn.close()
            return
        
        if not alreadyKeepAlive >= int(config['keep-alive-max']):
            Logger.info("Preparing next long connection...")
            newRes = ServerResponse(self.ip, self.ident, self.server, self.conn)
            # newRes.response(alreadyKeepAlive+1)
            DT.addThread(newRes.response(alreadyKeepAlive+1))
        else:
            self.conn.close()
            Logger.warn("[长连接] 最大单链接处理上限。")


    def getHTTPHeader(self):
        def getHTTPContent():
            self.originalData, self.data = parsingHeader(self.connfile)
            
        self.getdatathread = Thread(target=getHTTPContent)
        self.getdatathread.start()
        self.getdatathread.join(config['timeout'])

        if self.originalData == None and (self.data == None or self.data.path == None):
            try:
                stop_thread(self.getdatathread)
                self.conn.send(b'\r\n\r\n')
                self.conn.close()
            except Exception as e:
                pass
            Logger.error(self.ip[0], "超时:", ("OData:", self.originalData, "Data:", self.data == '', "ThreadStat", self.getdatathread.is_alive()))
            return
        return True

    def chooseMethod(self):
        realpath = ServerPath+"/"+self.data['path']
        if self.data['headers'].get("content-type", None) == 'multipart/form-data':
            Logger.info(self.ident, "上传文件:",self.data['path'])
            self.fileHandle.uploadFile()
            return
        
        if os.path.isfile(realpath) and self.data['path'][-3:] == '.py':
            #如果是PythonWeb文件
            self.fileHandle.PythonFileHandle()
        elif os.path.isdir(realpath):
            #如果请求路径为一个文件夹
            for i in config['default-page']:
                if os.path.isfile(realpath+'/'+i):
                    self.data['path'] = self.data['path']+'/'+i
                    break
            if i[-3:] == '.py':
                self.fileHandle.PythonFileHandle()
            else:
                self.fileHandle.CommonFileHandle()
        else:
            self.fileHandle.CommonFileHandle()
