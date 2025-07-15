


import socket
from Functions import dictToKvList, setLogFrs, FrameParser, HeaderParser, isNum, FileType, tryGetErrorDetail, kvListToDict, getBit, getRangeBit, toH1Format, dict_inone
from ParsingHTTPData import HeaderStructure, decodeGET, decodePOST, decodeCookie, decodeContentType, parsingCacheFile
from ServerConfig import ServerPath
from ServerConfig import *
from urllib import parse as uparse
from H2DataDispatch import DataDispatch
from Version import version
from Logger import setLog, Logger
from H1Response import ServerResponse
from Server import Server
import time
import typing
import traceback
import CacheModule as cm
import DispatchThread as DT

__all__ = ['HEADER_MODULE', 'MagicContent', 'FrameTypes', 'SettingsFrameParam',
           'JudgeH2', 'ServerResponseHTTP2', 'MainStream', 'Stream',
           'DataFrame', 'HeaderFrame', 'WindowUpdateFrame', 'PingFrame', 'SettingFrame']

Logger = Logger()
GZIP_ENCODING = False

HEADER_MODULE = {
            "getdata":     {},
            "postdata":    {},
            "rewritedata": {},
            "headers":     {},
            "path":        "",
            "language":    "",
            "cookie":      {}
}
MagicContent = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"
FrameTypes   = {
    '0' : 'Data',
    '1' : 'Headers',
    '2' : 'Priority',
    '3' : 'Rst_Stream',
    '4' : 'Settings',
    '5' : 'Push_Promise',
    '6' : 'Ping',
    '7' : 'GoAway',
    '8' : 'Window_Update',
    '9' : 'Continuation',
}
SettingsFrameParam = {
    "1" : "SETTINGS_HEADER_TABLE_SIZE",
    "2" : "SETTINGS_ENABLE_PUSH",
    "3" : "SETTINGS_MAX_CONCURRENT_STREAMS",
    "4" : "SETTINGS_INITAL_WINDOW_SIZE",
    "5" : "SETTINGS_MAX_FRAME_SIZE",
    "6" : "SETTINGS_MAX_HEADER_LIST_SIZE",
}
"""Type: 
            0x0 -> Data
            0x1 -> Headers
            0x2 -> Priority
            0x3 -> Rst_Stream
            0x4 -> Settings
            0x5 -> Push_Promise
            0x6 -> Ping
            0x7 -> GoAway
            0x8 -> Window_Update
            0x9 -> Continuation
"""



def JudgeH2(Conn):
    "通过连接判断是否进行 HTTP2 的升级请求"
    try:
        Conn.do_handshake()
    except Exception as e:
        return
    finally:
        try:
            if Conn.selected_alpn_protocol() == "h2":
                return True
            return False
        except:
            return False
        


class ServerResponseHTTP2:
    """This object is used to respond HTTP2 request"""
    def __init__(self, server: Server, addr, conn: socket.socket, ident):
        self.ident = str(ident)
        self.server = server
        self.ip = addr
        self.settings = {
            "SETTINGS_HEADER_TABLE_SIZE":            4096,
            "SETTINGS_MAX_CONCURRENT_STREAMS":        100,
            "SETTINGS_INITAL_WINDOW_SIZE":          65535,
            "SETTINGS_MAX_FRAME_SIZE":              2**14,   #16384,
            "SETTINGS_MAX_HEADER_LIST_SIZE":        16384,
            "client": {
                "SETTINGS_INITAL_WINDOW_SIZE":      65535,
            }
        }
        for k in http2settings:
            self.settings[k] = http2settings[k]
        
        self.dispatch          = DataDispatch()
        self.conn              = MainStream(conn, self)
        self.encoder           = None
        self.decoder           = None
        self.streams           = {}
        self.uploadingStream  = {}
        self.waitingPost      = {}
        self.streamCache      = {}
    
    def getSocket(self): return self.conn

    def getSettings(self, key):
        """Get setting value by using key"""
        if key == 'header_table_size':
            ret = self.settings.get(SettingsFrameParam['1'], None)
            return ret if ret else 65535
        elif key == 'max_header_list_size':
            ret = self.settings.get(SettingsFrameParam['6'], None)
            return ret if ret else 262144
        else:
            return self.settings.get(key)

    @DT.useThread(priority=3)
    def response(self):
        """Handle the frames (used to parsing frames or record frame information and stop streaming)"""
        print("Waiting for magic...")
        MAGIC     = self.conn.recv(24)
        print("WaitedMagic:", MAGIC)
        if MAGIC == MagicContent:
            Logger.info("使用 http2 进行通讯")
            C      = 0        #计数器
            self.sendSettings()
            while 1:
                try:
                    frames = ParsingHTTP2Frame(self.conn, self)       #解析HTTP2帧
                    setLogFrs(frames, self, Logger)

                    if frames == 'stop':
                        return
                    if len(frames) == 0:
                        time.sleep(0.01)
                        continue

                    self.respond(frames)
                    C += 1
                except Exception as e:
                    Logger.error(e, traceback.format_exc())
                    continue

    def sendSettings(self):
        wu = SettingFrame(self, self.conn, 0)
        wu.send()
        
    def respond(self, frames: list[FrameParser]):
        """Choose function to respond every frame"""
        if not self.server.isStart:
            self.goAway()
        for frame in frames:
            if frame.getType() == "Settings":
                self.respondSetting(frame)
            if frame.getType() == "Headers":
                self.respondHeader(frame)
                self.checkWindowSize()
            if frame.getType() == "Ping":
                self.respondPing(frame)
            if frame.getType() == 'Rst_Stream':
                self.stopStream(frame)
            if frame.getType() == 'Data':
                self.respondData(frame)
                self.checkWindowSize()
            if frame.getType() == 'Window_Update':
                self.respondWindowUpdate(frame)

    def respondData(self, dataframe:FrameParser, timeout=5000):
        """Respond data frame (usually uploaded data or post info)"""
        sid = dataframe.getStreamID()
        DT.newLock('file').acquire()
        if self.streamCache.get(sid) == None: #POST则使用内存存储信息，multipart/form-data则使用磁盘存储（下面这段这么长我也不知道我当时为什么会写成三元运算）
            self.streamCache[sid] = cm.h2cachefile(save=
                (
                    cm.MEMORY if self.streams.get(sid) and self.streams.get(sid).header and self.streams.get(sid).frame.get('method').lower() == "post" and not decodeContentType(self.streams.get(sid).header.get("content-type")).get("type").lower() == "multipart/form-data" else cm.DISK)
                )
        DT.newLock('file').release()

        self.streamCache[sid].write(dataframe.get())
        self.conn.recData += dataframe.getLength()

        if dataframe.getFlags() & 0x1 == 0x1:
            while not timeout == 0:
                if self.streams.get(sid) and self.streams.get(sid).frame:
                    break
                time.sleep(0.001)
                timeout -= 1
            else:
                Logger.error("Timeout:", dataframe)
                return
            
            if self.streams.get(sid) and self.streams.get(sid).frame:
                frame = self.streams.get(sid).frame
                if frame.get('method').lower() == 'post' and not "multipart/form-data" in frame.get("content-type", "").lower(): #POST 数据
                    self.streamCache[sid].seek(0)
                    postdata              = decodePOST(self.streamCache[sid].read().decode("UTF-8"))
                    self.waitingPost[sid] = postdata
                    Logger.info(f"{sid} 接收完毕 POST")

                elif "multipart/form-data" in frame.get("content-type", "").lower(): #MULTIPART/FORM-DATA 数据
                    bd                        = decodeContentType(frame.get("content-type", ""))["boundary"]
                    files, datas              = parsingCacheFile(self.streamCache[sid], bd)
                    self.uploadingStream[sid] = files, datas
                    Logger.info(f"{sid} 终止传输文件")

                else:
                    Logger.error(f"[{sid}] 未知的传输格式:", frame.get("content-type"))
                    return
                
            self.streamCache[sid].clean()
            del self.streamCache[sid]

    @DT.useThread()
    def checkWindowSize(self):
        """Send window size to client"""
        Logger.warn("检查 Window Size:", self.settings['SETTINGS_INITAL_WINDOW_SIZE'], self.conn.recData)
        if self.settings['SETTINGS_INITAL_WINDOW_SIZE'] <= self.conn.recData:
            mainstream = WindowUpdateFrame(self.conn, 0, self)
            mainstream.send(65536)
            for i in self.streams.keys():
                wuframe = WindowUpdateFrame(self.conn, i, self)
                wuframe.send(65536)
            self.conn.recData = 0

    @DT.useThread()
    def stopStream(self, frame):
        """Close a stream"""
        if frame.getStreamID() in self.streams.keys():
            self.streams[frame.getStreamID()].isClosed = True

    @DT.useThread()
    def respondWindowUpdate(self, windowFrame:FrameParser):
        if windowFrame.getStreamID() == 0:
            self.conn.window  += windowFrame.get()
            Logger.comp("Update main window size to", self.conn.window)
        else:
            stream = self.streams.get(windowFrame.SID)
            if stream:
                stream.window += windowFrame.get()
                Logger.comp("Update stream [%s]'s window size to %s"%(windowFrame.SID, stream.window))
        
    @DT.useThread()
    def respondPing(self, pingFrame):
        """Respond ping frame"""
        retFrame = PingFrame(self.conn, pingFrame.getStreamID(), pingFrame, self)
        retFrame.send(1)

    @DT.useThread(priority=2)
    def respondHeader(self, headerFrame:FrameParser):
        """Respond header frame using HTTP/1.1 Object (server.ServerResponse)"""
        from FileHandle import FileHandle
        path   = uparse.unquote(headerFrame.get(":path"))
        header = HeaderFrame(self.conn, headerFrame.getStreamID(), self)
        obj    = FileHandle(self, None, None, None, None, cm.FileCache(), True, collection=self.server.coll)

        setLog("[ HTTP2 ] IP: "+str(self.ip)+"   |   Path: "+path)

        #对新的响应对象提供数据环境
        self.streams[headerFrame.getStreamID()]        = Stream(self.conn, headerFrame.getStreamID(), self)
        self.streams[headerFrame.getStreamID()].frame  = headerFrame
        obj.cachesize = self.getSettings("SETTINGS_MAX_FRAME_SIZE")
        obj.conn                                       = self.streams[headerFrame.getStreamID()]
        obj.header                                     = header
        obj.frame                                      = headerFrame
        gloadd                                         = {}

        header.set("content-type", FileType(path))
        headerFrame.data.header = toH1Format(headerFrame.get().get())

        headerFrame.cookie = {} if not headerFrame.get("cookie") else decodeCookie(headerFrame.get("cookie"))
        
        HeaderData            = HeaderStructure()
        HeaderData['cookie']  = headerFrame.get("cookie")
        HeaderData['path']    = headerFrame.get("path")
        HeaderData['headers'] = headerFrame.get().get()
        HeaderData['getdata'] = headerFrame.get("getdata")

        obj.data = HeaderData

        file, data = None, None
        #上传文件进行处理
        dctx = decodeContentType(HeaderData['headers'].get("content-type"))
        if dctx.get("type") == "multipart/form-data" and dctx.get("boundary", None):
            file, data                       = self.uploadFile(headerFrame)
            gloadd["_FILE"], gloadd["_DATA"] = file, data
            p1, p2                           = file, [(k, len(data[k])) for k in data]
            Logger.info(f"[文件上传] FILE: {p1} | DATA: {p2} | SID: {headerFrame.getStreamID()}")

        #POST 请求处理
        if headerFrame.get("method").lower() == 'post' and not dctx.get("boundary", ""):
            HeaderData['postdata'] = self.getPostData(headerFrame.getStreamID())
            Logger.info(f"[POSTDATA] Post 成功获取到 Dataframe")

        #普通文件请求处理
        obj.isHTTP2  = True
        obj.http2Res = self
        
        def closeFile(isFinishHeader=False):
            """Close temp file when Python file execution is complete."""
            if isFinishHeader:
                enddata = DataFrame(self.conn, b'', headerFrame.SID, self)
                enddata.send(1)
            for file in gloadd.get("_FILE", {}):
                gloadd['_FILE'][file].cachefile.clean()
            for data in gloadd.get("_DATA", {}):
                if isinstance(gloadd['_DATA'][data], str):
                    continue
                gloadd['_DATA'][data].clean()

        gloadd = dict_inone(gloadd, {"_h2r":self, "_sid": headerFrame.SID, "_frame": headerFrame})
        
        if headerFrame.get('path')[-3:] == '.py':
            obj.PythonFileHandle(addEnv=gloadd, onHeaderFinish=lambda: header.send(4), onEndCallback=closeFile)
        else:
            obj.CommonFileHandle(glo=gloadd, onHeaderFinish=lambda: header.send(4))

        obj.closeAllCacheFiles(file) if file else 0

    @DT.useThread()
    def respondSetting(self, frame: FrameParser):
        """Update HTTP2 Settings that sent by client"""
        if frame.get(0) and frame.get(0).get("valueTo") == 0:
            return
        for key in frame.get():
            value = frame.get().get(key).get("valueTo")
            if str(key).upper() == 'SETTINGS_INITAL_WINDOW_SIZE':
                self.settings['client'][key.upper()] = value
                self.conn.window  += value
            else:
                if key == 0:
                    continue
                self.settings[key] = value
        retFrame = SettingFrame(self, self.conn, 0)
        retFrame.send(1)
    
    @DT.useThread()
    def goAway(self):
        """Say goodbye to this connection."""
        try:
            for i in self.streams:
                self.streams[i].isClosed = True
            self.conn.unwrap()
            self.conn.close()
        except:
            self.dispatch.STOP = True

    def error(self, type_, frame, exception='', detail='', conn=None, lineContent=None, redirect=""):
        """Respond the occurence of unexpected errors."""
        header = HeaderFrame(self.conn, conn.sid, self)
        conn   = conn if conn else self.conn
        path   = os.path.abspath(ServerPath+"/"+frame.get("path"))

        if redirect:
            header.set(":status", "301")
            header.set("location", redirect)
            header.set("content-length", "0")
            header.send(4)

            conn.send(b'', 1)
            return
        
        if type_ == 'codeerror':
            header.set(":status", "500")
            header.send(4)

            conn.send(b"<html><head><meta charset='utf-8'></head><body><center><h1>Python Error</h1>")
            detail = detail.replace("<", "&lt;").replace(">", "&gt")
            
            detail = tryGetErrorDetail(detail, path, lineContent)
            conn.send(b"<br><font color='red'>Error: </font>"+str(exception).encode()+b"(at line "+str(exception.__traceback__.tb_lineno if not type(exception) == str else "Unknown").encode("UTF-8")+\
                      b")<br></center><div style='margin:30px'>Detail:<br><div style='padding:30px;line-height: 2;'>"+detail.replace("\n", "<br>").replace(" ", "&ensp;").encode()+\
                      b"</div></div></body></html>")
            conn.send(b'', 1)
            return

        if not str(type_) in http_errorcodes:
            header.set(":status", "500")
            header.send(4)

            conn.send((ERRPage().format('500', type_, exception)).encode())
            conn.send(b'', 1)

        else:
            header.set(":status", str(type_))
            header.send(4)
            conn.send((ERRPage().format(type_, http_errorcodes[str(type_)][0], http_errorcodes[str(type_)][1])).encode())
            conn.send(b'', 1)

    def uploadFile(self, f):
        """Create a space to cache data uploaded by client."""
        sid = f.getStreamID()
        if self.uploadingStream.get(sid):
            return self.uploadingStream[sid]
        self.uploadingStream[sid] = []
        while 1:
            if len(self.uploadingStream[sid]) > 0:
                data = self.uploadingStream.get(sid)
                del self.uploadingStream[sid]
                return data
            time.sleep(0.001)

    def getPostData(self, sid):
        """Get POST Data from waiting list."""
        if self.waitingPost.get(sid):
            return self.waitingPost[sid]
        self.waitingPost[sid] = None
        while 1:
            if self.waitingPost[sid]:
                return self.waitingPost[sid]
            time.sleep(0.001)

    def getNewHPackDecoder(self):
        """Create a HPack.Decoder for decoding header."""
        if not self.decoder:
            from hpack import Decoder
            x = Decoder()
            x.header_table_size = self.getSettings("header_table_size") #65536
            x.max_header_list_size = self.getSettings("max_header_list_size") #262144
            x.max_allowed_table_size = self.getSettings("header_table_size") #65536
            self.decoder = x
            return x
        else:
            return self.decoder
    def getNewHPackEncoder(self):
            """Create a HPack.Encoder for encoding header."""
            from hpack import Encoder
            x = Encoder()
            x.header_table_size = self.getSettings("header_table_size") #65536
            x.max_header_list_size = self.getSettings("max_header_list_size") #262144
            x.max_allowed_table_size = self.getSettings("header_table_size") #65536
            self.encoder = x
            return x


class MainStream:         #Main stream
    def __init__(self, conn, res:ServerResponseHTTP2):
        self.conn     = conn
        self.recData  = 0
        self.isClosed = False
        self.unwrap   = conn.unwrap
        self.close    = conn.close
        self.sendall  = self.send
        self.self     = res
        self._closed  = False
        self.window   = res.settings.get("SETTINGS_INITAL_WINDOW_SIZE")
        self.dispatch = res.dispatch

    def recv(self, size):
        data = self.conn.recv(size)
        if len(data) == 0:
            return b''
        return data
    
    def makefile(self, t):
        return self.conn.makefile(t)
    
    def send(self, data, priority=1, retry=5):
        if self.isClosed:
            return
        try:
            ret = self.dispatch.get(self, priority)
            self.conn.send(data)
            ret.release()
        except Exception as e:
            if 1:
                if retry == 0:
                    Logger.error("关闭 socket:", e)
                    self.isClosed = True
                    self.self.goAway()
                    self.conn.close()
                    return
                self.send(data,  retry-1)
                return

class Stream:
    def __init__(self, conn, sid, res:ServerResponseHTTP2, R = 0):
        self.R        = R
        self.conn     = conn
        self.sid      = sid
        self.sendall  = self.send
        self.self     = res
        self.isClosed = False
        self.header   = None
        self.window   = res.settings.get("client").get("SETTINGS_INITAL_WINDOW_SIZE")
        self.priority = 1
        self.dispatch = res.dispatch

    def setPriority(self, priority = 1):
        self.priority = priority

    def send(self, data, flag=0):
        if self.isClosed:
            return
        frame = DataFrame(self.conn, data, self.sid, self.self, stream=self)
        frame.send(flag, self.R)

    def makefile(self, x):
        return self.conn.makefile(x)
    
    def sendFrame(self, frameObj):
        if not self.isClosed:
            self.conn.send(frameObj.getContent(), priority=self.priority)
            

class Frame:
    def __init__(self):
        """Create a frame structure that waiting to be sent."""
    def send(self, *arg, **args):
        """Encode frame data and send it."""

class WindowUpdateFrame(Frame):
    def __init__(self, conn, sid, res):
        self.self = res
        self.conn = conn
        self.sid  = sid
    def send(self, increment=0, R=0):
        fh  = int.to_bytes(4, 3, 'big')
        fh += int.to_bytes(8, 1, 'big')
        fh += int.to_bytes(0, 1, 'big')
        fh += parsingRSID(R, self.sid)
        data = parsingRSID(R, increment)
        self.conn.send(fh+data)
        setLog(f"""[{self.sid}] SEND_WINDOW_UPDATE_FRAME
               --> increment: {increment}\n\n""", "./logs/h2.log", 0)


class PingFrame(Frame):
    def __init__(self, conn, sid, frame, s):
        self.self = s
        self.conn = conn
        self.data = frame.get()
        self.sid  = sid
    def send(self, flags = 1, R = 0):
        fh = int.to_bytes(8, 3, 'big')
        fh += int.to_bytes(6, 1, 'big')
        fh += int.to_bytes(flags, 1, 'big')
        fh += parsingRSID(R, self.sid)
        self.conn.send(fh+self.data)


class SettingFrame(Frame):
    def __init__(self, h2response: ServerResponseHTTP2, conn, sid):
        self.self = h2response
        self.conn = conn
        self.sid  = sid
    def send(self, flags=0, R=0, Ctx=True):
        if not self.sid == 0 and self.self.streams[self.sid].isClosed:
                return
        try:
            frameHeader = b''
            frameContent = b''
            if not flags == 1:
                for i in self.self.settings:
                    if isNum(i) == False:
                        continue
                    frameContent += int.to_bytes(int(getFrameId(i)), 2, byteorder='big')
                    frameContent += int.to_bytes(self.self.settings[i], 4, byteorder='big')
            if not Ctx:
                frameContent = b''
            frameHeader += int.to_bytes(len(frameContent), 3, byteorder='big')
            frameHeader += int.to_bytes(4, 1, byteorder='big')
            frameHeader += int.to_bytes(flags, 1, byteorder='big')
            RSID = parsingRSID(R, self.sid)
            frameHeader += RSID
            setLog(f"""[{self.sid}] SEND_SETTINGS_FRAME
               -->  settings' size: {len(frameContent)}
               -->  flags: {flags}
               -->  content:
                              {frameContent}\n\n""", "./logs/h2.log", 0)
            
            self.conn.send(frameHeader+frameContent)
        except Exception as e:
            Logger.error("无法发送Setting帧:", e)


class DataFrame(Frame):
    def __init__(self, conn, data, sid, h2response: ServerResponseHTTP2, stream=None):
        self.conn   = conn
        self.data   = data
        self.sid    = sid
        self.stream = stream
        self.self   = h2response
        if stream == None:
            self.stream = h2response.streams.get(sid)

    def send(self, flag, r=0):
        try:
            if not self.self.streams.get(self.sid) or self.self.streams[self.sid].isClosed:
                return
            frame  = None
            frame2 = None   

            #判断数据大小和最大帧大小，并考虑分段发送数据
            if self.self.getSettings("SETTINGS_MAX_FRAME_SIZE") < len(self.data):
                nextData, self.data = self.data[self.self.getSettings("SETTINGS_MAX_FRAME_SIZE"):], self.data[0:self.self.getSettings("SETTINGS_MAX_FRAME_SIZE")]
                frame = DataFrame(self.conn, nextData, self.sid, self.self, stream=self.stream)

            while self.conn.window <= 0:
                time.sleep(0.001)

            if not self.stream == None:
                if self.stream.window < len(self.data):
                    while self.stream.window == 0:
                        time.sleep(0.001)
                    nextD, self.data = self.data[self.stream.window:], self.data[0:self.stream.window]
                    frame2 = DataFrame(self.conn, nextD, self.sid, self.self, stream=self.stream)
                    
            self.fh  = len(self.data).to_bytes(3, 'big')     #Length
            self.fh += int(0).to_bytes(1, 'big')            #Type
            self.fh += int(flag).to_bytes(1, 'big')         #Flag
            self.fh += parsingRSID(r, self.sid)             #R and Stream ID

            self.conn.send(self.fh+self.data, priority=self.stream.priority)

            self.stream.window -= len(self.data)
            self.conn.window   -= len(self.data)

            if frame2:
                frame2.send(flag, r)

            if frame:
                frame.send(flag, r)

            setLog(f"""[{self.sid}] SEND_DATA_FRAME
               -->  data size: {len(self.data)}
               -->  flags: {flag}
               -->  content:
                              {self.data[0:20]} ...\n\n""", "./logs/h2.log", 0)
            
        except Exception as e:
            import traceback
            Logger.error("无法发送 Data 帧:", e, traceback.format_exc())
            setLog(f"""[{self.sid}] ERROR IN SENDING_DATA_FRAME
               -->  error: {e}
               -->  details: {traceback.format_exc()}
               -->  stream_id: {self.sid}\n\n""", "./logs/h2.log", 0)


class HeaderFrame(Frame):
    def __init__(self, conn, streamId, h2response):
        self.self                     = h2response
        self.conn                     = conn
        self.sid                      = streamId
        self.headers                  = {}
        self.ignorelist               = ["connection"]

        self.headers[":status"]       = '200'
        self.headers["content-type"]  = "text/html;charset=UTF-8"
        self.headers["server"]        = version
        self.headers["date"]          = ""
        self.headers['accept-ranges'] = 'bytes'

    def setDirectly(self, key, val):
        self.headers[key] = val

    def set(self, headerKey, headerValue, superpose=False, append=False):
        """Superpose is to overlay text on the same field, append is to create a new field."""
        assert (superpose and not append) or (not superpose and append) or (not superpose and not append), 'Superpose cannot be used with append.'

        if headerKey == 0:
            self.headers[':status'] = headerValue.split(" ")[1]
        else:
            headerKey = str(headerKey)
            if headerKey.lower() in self.ignorelist:
                return
            if append:
                if not headerKey.lower() in [h.lower() for h in self.headers.keys()]:
                    self.headers[headerKey] = []
                self.headers[headerKey].append(headerValue)
                return
            if self.headers.get(headerKey.lower()) and superpose:
                self.headers[headerKey.lower()] += headerValue
                return
            self.headers[headerKey.lower()] = headerValue

    def remove(self, headerKey):
        """Remove information from header."""
        if headerKey in self.headers.keys():
            del self.headers[headerKey]

    def toList(self):
        """Convert header into a list."""
        return dictToKvList(self.headers, True)

    def send(self, flag = 0, R = 0):
        try:
            if self.self.streams[self.sid].isClosed:
                return
            self.headers["date"] = time.ctime()

            d = self.self.getNewHPackEncoder()
            h = d.encode(self.toList())
                
            fh = int.to_bytes(len(h), 3, 'big')   # Length
            fh += int.to_bytes(1, 1, 'big')       # Type
            fh += int.to_bytes(flag, 1, 'big')    # Flag
            fh += parsingRSID(R, self.sid)

            headerCtx = ''
            for i in self.headers:
                headerCtx += '                         '+str(i)+': '+str(self.headers[i])+'\n'

            setLog(f"""[{self.sid}] SEND_HEADER_FRAME
               -->  header size: {len(h)}
               -->  encoder settings: {self.self.settings}
               -->  flags: {flag}
               -->  stream_id: {self.sid}
               -->  headers:\n{headerCtx}\n\n""", './logs/h2.log', 0)
            self.conn.send(fh+h)
        except Exception as e:
            Logger.error("无法发送 Header 帧:", e)
            setLog(f"""[{self.sid}] ERROR IN SENDING_HEADER_FRAME
               -->  error: {e}
               -->  stream_id: {self.sid}\n\n""", "./logs/h2.log", 0)
            

def parsingRSID(R, SID):
    "将R标记和StreamID整理为一个4字节数据"
    RSID = getRangeBit(int.to_bytes(SID, 4, byteorder='big'), 0, 32, byteorder='big')
    RSID = int(str(R)+RSID[1:], 2).to_bytes(4, byteorder='big')
    return RSID


def getFrameType(Id):
    "通过ID获取帧类型"
    return FrameTypes[str(Id)] if int(Id) >= 0 and int(Id) < 10 else Id


def getFrameId(Name):
    "通过帧类型获取ID"
    for i in SettingsFrameParam:
        if SettingsFrameParam[i] == Name:
            return i
    return Name


def getSFParam(Id):
    "通过Setting帧的keyID获取设置的项"
    return SettingsFrameParam[str(Id)] if int(Id) > 0 and int(Id) < 7 else Id


def ParsingHTTP2Frame(conn, self:ServerResponseHTTP2, frames=None) -> typing.List[FrameParser, ]:
    "接收帧数据并转换为字典"
    if not isinstance(conn, bytes):
        try:
            cont = conn.recv(1024*1024)
        except Exception as e:
            return 'stop'
    else:
        cont = conn

    frames = [] if not frames else frames
    frame  = FrameParser()

    if cont == b'':
        return frames

    frame.length = int.from_bytes(cont[0:3], 'big')
    frame.type   = getFrameType(cont[3])
    frame.typeID = cont[3]
    frame.flags  = cont[4]
    frame.R_SID  = cont[5:9]
    frame.R      = getBit(frame.R_SID[0], 0, byteorder='big')
    frame.SID    = int(getRangeBit(frame.R_SID, 1, 32, byteorder='big'), 2)
    frame.IP     = self.ip
    
    ctx9 = cont[9:frame.length+9]
    if frame.getID() == 0:   #Data帧
        frame.data = ctx9
    elif frame.getID() == 1: #Headers帧
        frame.data = ParsingHeadersFrame(ctx9, frame, self)
    elif frame.getID() == 3: #Rst_Stream帧
        frame.data = ctx9
    elif frame.getID() == 4: #Settings帧
        frame.data = ParsingSettingParam(ctx9)
    elif frame.getID() == 6: #Ping 帧
        frame.data = cont[9:9+64]
    elif frame.getID() == 7: #GoAway帧
        self.goAway()
        frame.data = ctx9
    elif frame.getID() == 8: #Window_Update帧
        frame.data = ParsingWindowUpdateParam(ctx9)

    nextframe = cont[frame.length+9:]
    frames.append(frame)
    if not cont == b'':
        ParsingHTTP2Frame(nextframe, self, frames)
    return frames


def ParsingWindowUpdateParam(ctx):
    return int.from_bytes(ctx, 'big')


def ParsingHeadersFrame(ctx, frame, self:ServerResponseHTTP2):
    header  = HeaderParser()
    decoder = self.getNewHPackDecoder()

    try:
        if frame.getFlags() & 0x20 == 0x20:
            #存在 PRIORITY 标记
            c = 1
            if frame.getFlags() & 0x8 == 0x8:
                #存在 PADDED 标记
                header["pad-length"] = ctx[0]
                c = 0
            header.isPriority = True
            header.esdp       = str(ctx[1-c:5-c])
            header.weight     = ctx[5-c]
            
            head = decoder.decode(ctx[6-c:])
            head = kvListToDict(head)
            head[':path'] = uparse.unquote(head[':path'])
            head[':path'], head['getdata'] = decodeGET(head[':path'])
            head['method'] = head[':method']

            header.header = head
            Path = header.getHeader(":path")

        else:
            header.header = kvListToDict(decoder.decode(ctx[0:]))
            header.header[':path'] = uparse.unquote(header.header[':path'])
            header.header[':path'], header.header['getdata'] = decodeGET(header.getHeader(":path"))
            Path = header.getHeader(":path")
        
        if Path and Path[-1] == "/":
                realpath = ServerPath+"/"+Path
                for i in config['default-page']:
                    if os.path.isfile(realpath + "/" + i):
                        header.header[':path'] = Path+i
                        break

    except Exception as e:
        Logger.error(e, traceback.format_exc())
        return header
    
    return header


def ParsingSettingParam(ctx):
    params       = {}
    TypeId       = int.from_bytes(ctx[0:2], 'big')
    Type         = getSFParam(TypeId)
    params[Type] = {}
    value        = ctx[2:6]
    valueTo      = int.from_bytes(value, 'big')
    params[Type] = {"value": str(value), "valueTo": valueTo}

    if ctx[6:8] == b'\x00\x00':
        return params
    if not len(ctx[6:]) == 0:
        params.update(ParsingSettingParam(ctx[6:]))
        return params
    return params


