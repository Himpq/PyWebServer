from ServerConfig import *
from Server import Logger, Coll
from Functions import *
import re
import traceback
from H1Response import Header
from ParsingHTTPData import *

# Import module type (ServerResponse.include)
MODULE = 'module'
VAR    = 'var'


class Module:
    def __init__(self, dicts, filePath, name):
        self.__filePath = filePath
        self.__name     = name
        for i in dicts:
            self.__dict__[i] = dicts[i]
    
    def __str__(self):
        return f"<PWSModule '{self.__name}' from '{os.path.abspath(self.__filePath)}'>"
    def __repr__(self):
        return self.__str__()

class FileHandle:
    def __init__(self, master, conn, connfile, header, data, cache, isHTTP2 = False, PyCloseConnection = False, ETagMode = True):
        self.isHTTP2      = isHTTP2
        self.globals      = {}
        self.streamOutput = False
        self.master       = master
        
        self.cachesize              = config['cachesize']
        self.collection             = Coll
        self.header                 = header
        self.data                   = data
        self.cache                  = cache
        self.conn                   = conn
        self.connfile               = connfile
        self.Py_CloseConnection     = PyCloseConnection
        self.LineFeed               = b''
        self.SingleLineFeed         = b'\r\n'
        self.ETagMode               = ETagMode
        self._PyVariables           = None
        self.frame                  = None

    def getFrame(self):
        return self.frame

    def uploadFile(self):
        if not self.data['headers'].get("boundary"):
            Logger.error("No boundary.")
            return
        
        Logger.error(self.master.ident, "Parsing uploading data.")
        uploadFiles = parsingUploadFile(self.data['headers']['boundary'], self.connfile)
        
        
        if not self.data['path'][-3:] == '.py':
            self.CommonFileHandle(glo={"_FILE": uploadFiles[0], "_DATA": uploadFiles[1]})
            return
        
        if len(uploadFiles) == 0:
            uploaddict = {}
        else:
            uploaddict = {"_FILE": uploadFiles[0], "_DATA": uploadFiles[1]}
            
        self.PythonFileHandle(addEnv = uploaddict)
        return

    def PyInHtmlHandle(self, glo={}, onHeaderFinish=None):
        realpath = ServerPath+"/"+self.data['path']
        if not os.path.isfile(realpath):
            self.err(404)
            return
        
        with open(realpath, 'r', encoding='UTF-8') as f:
            content = f.read()

        if not "<!-- py -->" in content:
            self.CommonFileHandle(onHeaderFinish, False)
            return
        
        if config['python'] == False:
            return

        if self.Py_CloseConnection:
            self.header.remove("connection")
            self.header.remove("keep-alive")
            self.header.set("connection", "close")
        
        pycodes = re.findall(r"(<\?py)(.*?)(\?>)", content, flags=re.S)

        self.getGlobalVariables(onHeaderFinish)

        del self._PyVariables['print']
        del self._PyVariables['finish_header']

        outputContents = {}
        ID   = 0
        
        def _print(*arg, **args):
            nonlocal outputContents, ID
            content = " ".join([str(i) for i in arg])

            if outputContents.get(ID):
                outputContents[ID] += content
                return
            outputContents[ID] = content
        
        self._PyVariables          = dict_inone(self._PyVariables, glo)
        self._PyVariables['print'] = _print

        self.header.set("content-type", "text/html")

        #执行代码
        for codeStructure in pycodes:
            code = codeStructure[1]
            if len(code.split("\n")) == 1: #单行代码
                code = code.lstrip()
            try:
                code = self.encodePyCode(code)
                exec(code, self._PyVariables, self._PyVariables)
                content = content.replace("".join(codeStructure), outputContents.get(ID, ""), 1)
            except Exception as e:
                self.err("codeerror", e, traceback.format_exc(), lineContent="".join(codeStructure))
                return
            ID += 1

        encodeData = content.encode("UTF-8")
        self.header.set("Content-Length", str(len(encodeData)))
        
        if self.isHTTP2:
            onHeaderFinish() if onHeaderFinish else None
        else:
            self.conn.send(self.header.encode()+self.SingleLineFeed)
        self.conn.send(encodeData)

        if self.isHTTP2:
            self.conn.send(self.LineFeed, 1)

    def CommonFileHandle(self, onHeaderFinish=None, retToPy=True, glo={}):
        realpath = ServerPath+"/"+self.data['path']

        if self.data['path'][-3:] == '.py':
            self.PythonFileHandle(addEnv=glo)
            return
        if self.data['path'][-4:] in ('html', '.htm') and retToPy:
            self.PyInHtmlHandle(onHeaderFinish=onHeaderFinish, glo=glo)
            return
        if not os.path.isfile(realpath):
            self.err(404)
            return
        
        Logger.info("Using Common file handle", self.data['path'])

        totalSize  = os.path.getsize(realpath)  #文件总大小(Total Size)
        size       = totalSize                  #断点续传需要返回的大小（初始值为文件总大小）

        if 'range' in self.data['headers']: 
            #断点续传功能
            ranges = getRange(self.data['headers']['range'].split("=")[1].strip())

            size = (ranges[1] + 1 if not ranges[1] == '' else size) - ranges[0]
            self.header.set("Content-Range", "bytes %s-%s/%s"%(ranges[0], ranges[1] if not ranges[1] == '' else totalSize-1, totalSize))     
            self.header.set(0, "HTTP/1.1 206 Partial Content")

        self.header.set("Content-Type",   FileType(self.data['path']))
        self.header.set("Content-Length", "%s"%size)
        
        file = open(realpath, 'rb')

        if not  'range' in self.data['headers']:
            Mode304 = False
            if not os.path.getsize(realpath) >= config['maxsize-for-etag']: #判断文件大小是否大于配置中设置的最大大小，否则不使用ETag浪费服务器资源。
                ETag       = getHashByFile(open(realpath, 'rb'))
                ClientETag = self.data['headers'].get('if-none-match')
                if ClientETag and ClientETag == ETag:
                    self.header.set(0, "HTTP/1.1 304 Not Modified")
                    self.header.remove("Content-Length")
                    Mode304 = True
                    if self.isHTTP2:
                        onHeaderFinish = lambda: self.header.send(5)
                else:
                    self.header.set("ETag", ETag)

            if not self.isHTTP2: #发送响应头
                headerEncode = self.header.encode()+self.SingleLineFeed
                self.conn.send(headerEncode)
            else:
                onHeaderFinish() if onHeaderFinish else 1

            if not Mode304:  #客户端没有进行缓存
                cont = file.read(self.cachesize)
                while not cont == b'':
                    self.conn.sendall(cont, 0) if self.isHTTP2 else \
                    self.conn.sendall(cont)
                    cont = file.read(self.cachesize)
                self.conn.send(self.LineFeed, 1) if self.isHTTP2 else 0

            file.close()
            return
        
        #断点续传
        if not self.isHTTP2:
            headerEncode = self.header.encode()+self.SingleLineFeed
            self.conn.send(headerEncode)
        else:
            onHeaderFinish() if onHeaderFinish else 0
        
        file.seek(ranges[0])

        CacheSize     = self.cachesize
        readTotalSize = size         #断点续传内容的总大小
        numOfRead     = (readTotalSize // CacheSize) if readTotalSize > CacheSize else 1
        end           = (readTotalSize - numOfRead * CacheSize) if readTotalSize > CacheSize else 0

        if readTotalSize < CacheSize:#缓存部分大于返回的数据大小
            CacheSize = readTotalSize

        for i in range(numOfRead+1):
            try:
                d = file.read(CacheSize if not i == numOfRead else end)
                self.conn.sendall(d)
            except Exception as e:
                file.close()
                return
            
        if self.isHTTP2:
            self.conn.send(self.LineFeed, 1)
        else:
            self.conn.send(self.LineFeed) if not self.LineFeed == b'' else None
        file.close()
        return
    
    def check(self):
        #设置上用户自定义的响应头
        headersetting = opts.get("headers")

        for i in headersetting:
            #matchFile = re.findall(i, realpath)
            #if matchFile:
             #   header_head = headersetting[i]
             #   self.header.set(header_head[0], header_head[1])
             pass


    def PythonFileHandle(self, addEnv={}, onHeaderFinish=None, onEndCallback=None):
        conn          = self.conn
        header        = self.header
        realpath = ServerPath+"/"+self.data['path']

        if not os.path.isfile(ServerPath+"/"+self.data['path']):
            self.err(404)
            return
        
        if config['python'] == False: #判断配置文件是否禁用了 Python web功能
            return
        
        Logger.info("Using Python Handle")

        if self.Py_CloseConnection:
            self.header.remove("connection")
            self.header.remove("keep-alive")
            self.header.set("connection", "close")

        with open(realpath, 'rb') as f:
            PythonFileCode = b"import sys;sys.path.append('./Libs');del sys;\n"+f.read()
            PythonFileCode = self.encodePyCode(PythonFileCode)

        #配置环境变量
        self.getGlobalVariables(onHeaderFinish)

        for i in addEnv:
            self._PyVariables[i] = addEnv[i]

        #执行 Python web 文件
        try:
            codeCompile = compile(PythonFileCode, '', 'exec')
            exec(codeCompile, self._PyVariables)
            onEndCallback(self.streamOutput) if onEndCallback else None

        except Exception as e:
            self.err("codeerror", e, traceback.format_exc())
            return

        if self.streamOutput:  #如果没有执行 Server.finish_header 函数就直接将数据输出
            return
        
        self.cache.save()
        pythonPrintContent = self.cache.read().encode()

        header.set("Content-Length", str(len(pythonPrintContent)))

        Mode304 = False
        if self.ETagMode:    #ETag 缓存
            ETag       = getHash(pythonPrintContent)
            ClientETag = self.data['headers'].get('if-none-match')

            if ClientETag and ClientETag == ETag:
                header.set(0, "HTTP/1.1 304 Not Modified")
                header.remove("Content-Length")
                Mode304 = True
                if self.isHTTP2:
                    onHeaderFinish = lambda: header.send(5)
            else:
                header.set("ETag", ETag)

        if not self.isHTTP2:  #发送响应头
            self.conn.send(header.encode() + self.SingleLineFeed)
        else:
            onHeaderFinish() if onHeaderFinish else 1

        sendData = (pythonPrintContent if not Mode304 else b"")+self.LineFeed

        if not len(sendData) >= self.cachesize:
            conn.send(sendData)
            conn.send(b'', 1) if self.isHTTP2 else 0
            return
        
        sendTimes = len(sendData) // self.cachesize
        endSize   = len(sendData) - sendTimes * self.cachesize
        for i in range(sendTimes):
            NowData = sendData[self.cachesize*i: self.cachesize*(i+1)]
            conn.send(NowData)

        conn.send(sendData[-endSize:])
        conn.send(b'', 1) if self.isHTTP2 else 0

    def generateGlobalsVariable(self, onHeaderFinish = None):
        globals_var = {}
        globals_var['set_cookie']          = self.set_cookie
        
        globals_var['finish_header']       = lambda: self.finish_header(onHeaderFinish)
        globals_var["print"]               = lambda *arg, **args: self.printToSocketOrCache(*arg, **args)
        globals_var['get_response_header'] = lambda: self.header.headers

        globals_var['set_statuscode']      = self.set_statuscode
        globals_var["set_header"]          = self.header.set

        globals_var['get_priority']        = self.get_priority
        globals_var['set_priority']        = self.set_priority
        
        globals_var['isHTTP2']             = self.isHTTP2
        globals_var['include']             = self.include
        globals_var['set_disable_etag']    = self.set_disable_etag
        globals_var['_POST']               = self.data['postdata']
        globals_var['_GET']                = self.data['getdata']
        globals_var['_COOKIE']             = self.data['cookie']
        globals_var['_HEADER']             = self.data['headers']
        globals_var['Logger']              = Logger
        globals_var['this']                = self
        globals_var['_FILE']               = {}
        globals_var["_DATA"]               = {}
        globals_var["_COLL"]               = self.collection
        globals_var['MODULE']       = "module" # Import module type
        globals_var['VAR']          = "var" 

        return globals_var
    
    def getGlobalVariables(self, *arg, **kwargs):
        if self._PyVariables == None:
            self._PyVariables = self.generateGlobalsVariable(*arg, **kwargs).copy()
        return self._PyVariables

    def set_cookie(self, cookieName, cookieValue, expires=1800, attributes: dict=None):
        """Set cookie fields"""
        attrStr = ""
        if type(attributes) == dict:
            for key in attributes:
                attrStr += key+("="+attributes[key] if attributes[key] else "")+"; "
        self.header.set("set-cookie",
                       f"{cookieName}={cookieValue}; Expires={expires}; {attrStr}",
                        append=True)

    def set_priority(self, priority=1):
        """Set stream priority"""
        if self.isHTTP2:
            self.conn.priority = priority
    
    def get_priority(self):
        """Get stream priority"""
        return self.conn.priority if self.isHTTP2 else None

    def set_header(self, key, val):
        """Set header fields"""
        self.header.setDirectly(key,val)

    def set_statuscode(self, code, content):
        """Set the status code of the response"""
        self.header.set(0, "HTTP/1.1 "+str(code)+" "+content)

    def set_html(self, *val, **arg):
        """Set cached page information"""
        print(*list(val), **arg, file=self.cache)

    def encodePyCode(self, code):
        if type(code) == bytes:
            retByte = True
            code    = code.decode("UTF-8")
        else:
            retByte = False

        # 1.使用PWS的include导入模块
        code = encodeIncludeCode(code)
        
        return code if not retByte else code.encode("UTF-8")

    def include(self, filePath, includeType = MODULE, useDirPath = True, asName = None):
        """Import module from path"""
        useDirPath = ServerPath+"/"+os.path.split(self.data['path'])[0]+"/" if useDirPath else ""
        filePath   = useDirPath+filePath
        if not os.path.isfile(filePath):
            self.err("codeerror", "Cannot find module in path: '%s'"%os.path.abspath(filePath))
            return
        
        with open(filePath, 'r', encoding='utf-8') as f:
            code = self.encodePyCode(f.read())
        
        globals_var = self.getGlobalVariables()

        exec(("import sys;sys.path.append(r'%s')\n"%useDirPath)+code, globals_var)
        if includeType == MODULE:
            name                    = os.path.split(filePath)[1].split('.')[0] if not asName else str(asName)
            self._PyVariables[name] = Module(globals_var, filePath, name)
            return self._PyVariables[name]
        
        elif includeType == VAR:
            for k in globals_var:
                self._PyVariables[k] = globals_var[k]
            return

        self.err("codeerror", "Unknown include type: "+str(includeType))

    def finish_header(self, onHeaderFinish=None):
        """用于结束设置 HTTP响应头，将 print 函数输出对象转为 socket 连接"""
        if self.isHTTP2:
            onHeaderFinish() if onHeaderFinish else None
        else:
            headerdata = self.header.encode()+self.SingleLineFeed
            self.conn.sendall(headerdata)
        self.streamOutput = True
        data        = self.cache.read().encode()
        self.conn.send(data) if not len(data) == 0 else None

    def printToSocketOrCache(self, *arg, **args):
        "判断是否使用了 finish_header 以 print 直接向 socket 输出"
        if not self.streamOutput:
            self.set_html(*arg, **args)  
        else:
            sep = b" " if not args.get("sep") else args.get("sep")
            end = b""  if not args.get("end") else args.get("end")
            
            for i in range(len(arg)):
                try:
                    v = arg[i]
                    self.conn.send(v+(sep if not i == len(arg)-1 else b''))
                except Exception as e:
                    Logger.error("Sending data without cache error.")
                    Logger.error(e)
            try:
                self.conn.send(end)
            except:
                return

    def set_disable_etag(self, disable):
        if disable:
            self.ETagMode = False
        else:
            self.ETagMode = True

    def err(self, type_, exception='', detail='', lineContent=''):
        if not self.isHTTP2:

            header = Header()
            header.set("Content-Type","text/html")
            header.set("Connection", "close")

            if type_ == 'codeerror':
                detail = detail.replace("<", "&lt;").replace(">", "&gt")
                detail = tryGetErrorDetail(detail, ServerPath+"/"+self.data['path'], lineContent)
                data = (b"<html><head><meta charset='utf-8'></head><body><center><h1>Python Error</h1>"+\
                        b"<br><font color='red'>Error: </font>"+str(exception).encode()+b"(at line "+str(exception.__traceback__.tb_lineno).encode("UTF-8")+\
                        b")<br></center><div style='margin:30px'>Detail:<br><div style='padding:30px;line-height: 2;'>"+detail.replace("\n", "<br>").encode()+\
                        b"</div></div></body></html>")
                if not self.streamOutput:
                    header.set(0, "HTTP/1.1 500 Code Error")
                    header.set("Content-Length", str(len(data)))
                    self.conn.send(header.encode()+self.SingleLineFeed)
                self.conn.send(data)
                return

            if not str(type_) in http_errorcodes:
                header.set(0, "HTTP/1.1 500 Service Error")
                self.conn.send(header.encode()+self.SingleLineFeed)
                self.conn.send((ERRPage().format('500', type_, exception)).encode())

            else:
                header.set(0, "HTTP/1.1 %s %s"%(type_, http_errorcodes[str(type_)][0]))
                ErrorPage = (ERRPage().format(type_, http_errorcodes[str(type_)][0], http_errorcodes[str(type_)][1])).encode()
                header.set("Content-Length", str(len(ErrorPage)))
                self.conn.send(header.encode()+self.SingleLineFeed)
                self.conn.send(ErrorPage)

            self.conn.close()
        else:
            self.master.error(type_, self.getFrame(), exception, detail, self.conn, lineContent)
            Logger.error(f'''页面错误:
    Type: {type_}
    Exception: {exception}
    Path: {self.data['path']}
    Line: {lineContent}
    Detail:
{detail}''')
