
from Logger import Logger
from functions import FrameParser, HeaderParser, STR, priorityHigh, isNum, FileType, tryGetErrorDetail, prettyPrint, kvListToDict, getBit, getRangeBit, toH1Format, setLog, gzip_encode, initLogThread
from server_config import ServerPath
from server_config import *
import time
from threading import Thread, Lock
from ParsingHTTPData import decodeGET, decodePOST, decodeCookie, decodeContentType, parsingCacheFile
import CacheModule as cf
import traceback
import DispatchThread as DT

Logger        = Logger()
ThreadLock    = Lock()
GZIP_ENCODING = False

import server

initLogThread()

HEADER_MODULE = {
            "getdata":{},
            "postdata":{},
            "rewritedata":{},
            "headers": {},
            "path":"",
            "language":"",
            "cookie":{}
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
            0x9 -> Continuatio
n"""



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
        
def setLogFrs(frames, self):
    for frame in frames:
        if isinstance(frame, str):
            Logger.error("String type frame!:", frame)
            continue
        Logger.comp("-"*70)
        Logger.comp(" [{0: <3}] Recv Frame: | TYPE: {1: <13} | LEN: {2: <7} | flags: {3}".format(
            frame.getStreamID(),
            frame.getType(),
            frame.getLength(),
            frame.getFlags()
        ))
        ctx = ''
        adds = ''

        if frame.getType() == 'Headers':
            Logger.error(f"      View Path:", frame.get(":path"))
        
        if frame.getType() == 'Settings':
            ctx = str(frame.get())

        elif frame.getType() == 'Headers':
            for i in frame.get():
                ctx += str(i)+': '+str(frame.get().get(i))+'\n                              '
            ctx = ctx[0:-len("'\n                              '")]

        elif frame.getType() == 'Data':
            ctx = str(frame.get())
            adds = '\n               -->  window_size: '+str(self.conn.recData)

        elif frame.getType() == 'Window_Update':
            ctx = str(frame.get())

        else:
            ctx = str(frame)

        ctx = ctx[0:50] if not frame.getType() in ("Headers", "Settings", "Rst_Stream") else ctx
         
        setLog(
           f"""[{frame.getStreamID()}] RECV_{frame.getType().upper()}_FRAME
               -->  stream_id: {frame.getStreamID()}
               -->  flags: {frame.getFlags()}
               -->  size: {frame.getLength()}{adds}
               -->  content:
                              {ctx}\n
""", "./logs/h2.log", 0)

class ServerResponseHTTP2:
    def __init__(self, respH1:server.ServerResponse, ident):
        self.ident = str(ident)
        self.self = respH1
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

        self.conn = SocketRecorder(self.self.conn, self)
        self.encoder = None
        self.decoder = None
        self.needNewH1Response = False
        self.streams = {}
        self.uploadingStream = {}
        self.waitingPost     = {}
        self.streamCache     = {}
        self.priority        = 1

    def getSettings(self, key):
        "Get settings by using key"
        if key == 'header_table_size':
            ret = self.settings.get(SettingsFrameParam['1'], None)
            return ret if ret else 65535
        elif key == 'max_header_list_size':
            ret = self.settings.get(SettingsFrameParam['6'], None)
            return ret if ret else 262144
        else:
            return self.settings.get(key)

    def response(self):
        "Handle the frames"
        MAGIC = self.conn.recv(24)
        if MAGIC == MagicContent:
            Logger.info("使用 http2 进行通讯")
            C      = 0        #计数器
            self.sendSettings()
            while 1:
                try:
                    frame = ParsingHTTP2Frame(self.conn, self)       #解析HTTP2帧
                    setLogFrs(frame, self)
                    if frame == 'stop':
                        return
                    if len(frame) == 0:
                        time.sleep(0.01)
                        continue
                    self.checkWindowSize()
                    Thread(target=self.respond, args=(frame,)).start()
                    C += 1
                except Exception as e:
                    Logger.error(e, traceback.format_exc())
                    continue

    def sendSettings(self):
        wu = SettingFrame(self, self.self.conn, 0)
        wu.send()

    def checkWindowSize(self):
        #更新流量窗口
        if self.settings['SETTINGS_INITAL_WINDOW_SIZE']*3/4 <= self.conn.recData:
            mainstream = WindowUpdateFrame(self.conn, 0, self)
            mainstream.send(65535)
            for i in self.uploadingStream.keys():
                wuframe = WindowUpdateFrame(self.conn, i, self)
                wuframe.send(65535)
            self.conn.recData = 0
        
    def respond(self, frames):
        for frame in frames:
            if frame.getType() == "Settings":
                for key in frame.get():
                    value = frame.get().get(key).get("valueTo")
                    if str(key).upper() == 'SETTINGS_INITAL_WINDOW_SIZE':
                        self.settings['client'][key.upper()] = value
                        Logger.warn("Client update inital window size:", value)
                    else:
                        if key == 0:
                            continue
                        self.settings[key] = value
                self.respondSetting(frame)
            if frame.getType() == "Headers":
                self.respondHeader(frame)
            if frame.getType() == "Ping":
                self.respondPing(frame)
            if frame.getType() == 'Rst_Stream':
                self.stopStream(frame)
            if frame.getType() == 'Data':
                self.respondData(frame)

    def respondData(self, dataframe):
        if not dataframe.getStreamID() in self.streamCache.keys():
            #POST则使用内存存储信息，multipart/form-data则使用磁盘存储
            self.streamCache[dataframe.getStreamID()] = cf.h2cachefile(save=
                                                               (cf.MEMORY if self.streams.get(dataframe.getStreamID()) and self.streams.get(dataframe.getStreamID()).header and self.streams.get(dataframe.getStreamID()).frame.get('method').lower() == "post" and not decodeContentType(self.streams.get(dataframe.getStreamID()).header.get("content-type")).get("type").lower() == "multipart/form-data" else cf.DISK))
        self.streamCache[dataframe.getStreamID()].write(dataframe.get())

        if dataframe.getFlags() & 0x1 == 0x1:
            #结束文件传输标识
            if self.streams.get(dataframe.getStreamID()) and self.streams.get(dataframe.getStreamID()).frame:
                frame = self.streams.get(dataframe.getStreamID()).frame
                if frame.get('method').lower() == 'post' and not "multipart/form-data" in frame.get("content-type", "").lower():
                    #POST 数据
                    self.streamCache[dataframe.getStreamID()].seek(0)
                    postdata = decodePOST(self.streamCache[dataframe.getStreamID()].read().decode("UTF-8"))
                    self.waitingPost[dataframe.getStreamID()] = postdata
                elif "multipart/form-data" in frame.get("content-type", "").lower():
                    #MULTIPART/FORM-DATA 数据
                    bd           = decodeContentType(frame.get("content-type", ""))["boundary"]
                    files, datas = parsingCacheFile(self.streamCache[dataframe.getStreamID()], bd)
                    self.uploadingStream[dataframe.getStreamID()] = files, datas
                    Logger.info(f"{dataframe.getStreamID()} 终止传输文件")
            self.streamCache[dataframe.getStreamID()].clean()

    def stopStream(self, f):
        if f.getStreamID() in self.streams.keys():
            self.streams[f.getStreamID()].isClosed = True
        
    def respondPing(self, f):
        try:
            retFrame = PingFrame(self.conn, f.getStreamID(), f, self)
            retFrame.send(1)
        except Exception as e:
            pass

    def uploadFile(self, f):
        sid = f.getStreamID()
        self.uploadingStream[sid] = {}
        while 1:
            if len(self.uploadingStream[sid]) > 0:
                data = self.uploadingStream.get(f.getStreamID())
                del self.uploadingStream[f.getStreamID()]
                return data
            time.sleep(0.001)

    def getPostData(self, sid):
        self.waitingPost[sid] = None
        while 1:
            if self.waitingPost[sid]:
                #del self.waitingPost[sid]
                Logger.error(self.waitingPost)
                return self.waitingPost[sid]
            time.sleep(0.001)

    def respondHeader(self, headerframe):
        "Respond header frame and send data frame to client"

        #f['value']['stream_id'] = f['SID']
        path                    = headerframe.get(":path")
        header                  = HeaderFrame(self.conn, headerframe.getStreamID(), self)

        header.set("content-type", FileType(path))
        
        obj = self.self.clearEnvironment(self.self.conn, self.self.collection, headerframe)

        #对新的响应对象提供数据环境

        obj.cachesize = self.getSettings("SETTINGS_MAX_FRAME_SIZE")
        self.streams[headerframe.getStreamID()] = H1toH2SocketStream(self.conn, headerframe.getStreamID(), self)
        self.streams[headerframe.getStreamID()].frame = headerframe

        obj.conn   = self.streams[headerframe.getStreamID()]
        obj.header = header
        gloadd     = {}

        headerframe.data.header = toH1Format(headerframe.get().get())
        
        obj.data = HEADER_MODULE.copy()
        obj.data['cookie'] = {} if not headerframe.get("cookie") else decodeCookie(headerframe.get("cookie"))
        obj.data['path'] = headerframe.get("path")
        obj.data['headers'] = headerframe.get().get()
        obj.data['getdata'] = headerframe.get("getdata")

        #上传文件进行处理

        dctx = decodeContentType(obj.data['headers'].get("content-type"))
        if dctx.get("type") == "multipart/form-data" and dctx.get("boundary", None):
            file, data = self.uploadFile(headerframe)
            gloadd["_FILE"], gloadd["_DATA"] = file, data
            
            p1, p2 = file, [(k, len(data[k])) for k in data]
            Logger.error(f"[文件上传] FILE: {p1} | DATA: {p2} | SID: {headerframe.getStreamID()}")

        #POST 请求处理
        if headerframe.get("method").lower() == 'post' and not dctx.get("boundary", ""):
            obj.data['postdata'] = self.getPostData(headerframe.getStreamID())


        #普通文件请求处理
        obj.inHTTP2  = True
        obj.http2Res = self
        
        def closeFile():
            print(gloadd.get("_FILE"))
            for file in gloadd.get("_FILE", {}):
                gloadd['_FILE'][file].cachefile.clean()
            for data in gloadd.get("_DATA", {}):
                if isinstance(gloadd['_DATA'][data], str):
                    continue
                gloadd['_DATA'][data].clean()

        if headerframe.get('path')[-3:] == '.py':
            obj.PythonFileHandle(obj.data, glo=gloadd, onHeaderFinish=lambda: header.send(4), onEndCallback=closeFile)
            self.priority = obj.priority
        else:
            obj.CommonFileHandle(obj.data, glo=gloadd, onHeaderFinish=lambda: header.send(4))
        
        self.needNewH1Response = True

    
    def error(self, type_, frame, exception='', detail='', conn=None):
        "处理服务器故障"
        header = HeaderFrame(self.conn, conn.sid, self)
        conn   = conn if conn else self.conn
        if type_ == 'codeerror':
            header.set(":status", "500")
            header.send(4)

            conn.send(b"<html><head><meta charset='utf-8'></head><body><center><h1>Python Error</h1>")
            detail = detail.replace("<", "&lt;").replace(">", "&gt")
            
            detail = tryGetErrorDetail(detail, ServerPath+"/"+frame.get("path"))
            conn.send(b"<br><font color='red'>Error: </font>"+str(exception).encode()+b"(at line "+str(exception.__traceback__.tb_lineno).encode("UTF-8")+\
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


    def respondSetting(self, frame):
        "更新HTTP2的Settings"
        if frame.get(0) and frame.get(0).get("valueTo") == 0:
            return
        #for key in f.get():
        #    self.settings[key] = f.get(key)['valueTo']
        retFrame = SettingFrame(self, self.conn, 0)
        retFrame.send(1)
    
    def goAway(self):
        try:
            for i in self.streams:
                self.streams[i].isClosed = True
            self.conn.unwrap()
            self.conn.close()
        except:
            pass

    def getNewHPackDecoder(self):
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
            from hpack import Encoder
            x = Encoder()
            x.header_table_size = self.getSettings("header_table_size") #65536
            x.max_header_list_size = self.getSettings("max_header_list_size") #262144
            x.max_allowed_table_size = self.getSettings("header_table_size") #65536
            self.encoder = x
            return x



class SocketRecorder:
    def __init__(self, conn, res):
        "用于记录收发数据量\nconn: socket conn; res: ServerResponseHTTP2 object"
        self.conn = conn
        self.proData = 0
        self.recData = 0
        self.isClosed = False
        self.unwrap = conn.unwrap
        self.close = conn.close
        self.sendall = self.send
        self.self = res
        self._closed = False
    def recv(self, size):
        data = self.conn.recv(size)
        if len(data) == 0:
            return b''
        self.recData += len(data)
        return data
    def makefile(self, t):
        return self.conn.makefile(t)
    def send(self, data, retry=5):
        if self.isClosed:
            return
        self.proData += len(data)
        try:
            DT.ThreadLock.acquire()
            self.conn.send(data)
            DT.ThreadLock.release()
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

            
class WindowUpdateFrame:
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


class PingFrame:
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


class SettingFrame:
    def __init__(self, res, conn, sid):
        self.self = res
        self.conn = conn
        self.sid = sid
    def send(self, flags=0, R=0, Ctx=True):
        if not self.sid == 0 and self.self.streams[self.sid].isClosed:
                return
        try:
            fh = b''
            fc = b''
            if not flags == 1:
                for i in self.self.settings:
                    if isNum(i) == False:
                        continue
                    fc += int.to_bytes(int(getFrameId(i)), 2, byteorder='big')
                    fc += int.to_bytes(self.self.settings[i], 4, byteorder='big')
            if not Ctx:
                fc = b''
            fh += int.to_bytes(len(fc), 3, byteorder='big')
            fh += int.to_bytes(4, 1, byteorder='big')
            fh += int.to_bytes(flags, 1, byteorder='big')
            RSID = parsingRSID(R, self.sid)
            fh += RSID
            setLog(f"""[{self.sid}] SEND_SETTINGS_FRAME
               -->  settings' size: {len(fc)}
               -->  flags: {flags}
               -->  content:
                              {fc}\n\n""", "./logs/h2.log", 0)
            
            self.conn.send(fh+fc)
        except Exception as e:
            Logger.error("无法发送Setting帧:", e)


class DataFrame:
    def __init__(self, conn, data, sid, res, alreadyGzip=False):
        self.conn = conn
        self.data = data
        self.sid = sid
        self.self = res
    def send(self, flag, r=0):
        try:
            if not self.self.streams.get(self.sid) or self.self.streams[self.sid].isClosed:
                return
            frame = None

            #判断数据大小和最大帧大小，并考虑分段发送数据
            if self.self.getSettings("SETTINGS_MAX_FRAME_SIZE") < len(self.data):
                d = self.data
                self.data = self.data[0:self.self.getSettings("SETTINGS_MAX_FRAME_SIZE")]
                d = d[self.self.getSettings("SETTINGS_MAX_FRAME_SIZE"):]
                frame = DataFrame(self.conn, d, self.sid, self.self, alreadyGzip=True)
                
            self.fh = len(self.data).to_bytes(3, 'big')     #Length
            self.fh += int(0).to_bytes(1, 'big')            #Type
            self.fh += int(flag).to_bytes(1, 'big')         #Flag
            self.fh += parsingRSID(r, self.sid)             #R and Stream ID
            
            self.conn.send(self.fh+self.data)

            if frame:
                Logger.warn(self.sid, "无法完全发送，发送剩余部分：", len(d))
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


class HeaderFrame:
    def __init__(self, conn, streamId, res):
        self.self = res
        self.conn = conn
        self.sid  = streamId
        self.headers = {}
        self.headers[":status"] = '200'
        self.headers["content-type"] = "text/html;charset=UTF-8"
        self.headers["server"] = "PWS/6.1 With HTTP2"
        self.headers["date"] = ""
        self.headers['accept-ranges'] = 'bytes'

    def set(self, headerKey, headerValue, dj=False):
        if headerKey == 0:
            self.headers[':status'] = headerValue.split(" ")[1]
        else:
            if headerKey.lower() in ["connection"]:
                return
            if self.headers.get(headerKey.lower()):
                if dj:
                    self.headers[headerKey.lower()] += headerValue
                    return
            self.headers[headerKey.lower()] = headerValue

    def remove(self, headerKey):
        if headerKey in self.headers.keys():
            del self.headers[headerKey]

    def send(self, flag = 0, R = 0):
        try:
            if self.self.streams[self.sid].isClosed:
                return
            self.headers["date"] = time.ctime()

            d = self.self.getNewHPackEncoder()
            h = d.encode(self.headers)
            fh = int.to_bytes(len(h), 3, 'big')   #Length
            fh += int.to_bytes(1, 1, 'big')       #Type
            fh += int.to_bytes(flag, 1, 'big')    #Flag
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



class H1toH2SocketStream:
    def __init__(self, conn, sid, res, R = 0):
        "用于将HTTP1.1的传输方式转为帧传输\nconn: socket conn; sid: stream id; res: ServerResponseHTTP2 object; R: data frame R"
        self.R = R
        self.conn = conn
        self.sid = sid
        self.sendall = self.send
        self.self = res
        self.isClosed = False
        self.header = None

    def send(self, data, flag=0):
        if self.isClosed:
            return
        frame = DataFrame(self.conn, data, self.sid, self.self)
        frame.send(flag, self.R)

    def makefile(self, x):
        return self.conn.makefile(x)
    
    def sendFrame(self, frameObj):
        if not self.isClosed:
            self.conn.send(frameObj.getContent())



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

def ParsingHTTP2Frame(conn, self, frames=None):
    "接收帧数据并转换为字典\nconn: socket conn; self: ServerResponseHTTP2 object;"
    if not isinstance(conn, bytes):
        try:
            cont = conn.recv(1024*1024)
        except Exception as e:
            return 'stop'
    else:
        cont = conn

    frames = [] if not frames else frames
    frame  = FrameParser()

    #帧头
    if cont == b'':
        return frames

    frame.length = int.from_bytes(cont[0:3], 'big')
    frame.type   = getFrameType(cont[3])
    frame.typeID = cont[3]
    frame.flags  = cont[4]
    frame.R_SID  = cont[5:9]
    frame.R      = getBit(frame.R_SID[0], 0, byteorder='big')
    frame.SID    = int(getRangeBit(frame.R_SID, 1, 32, byteorder='big'), 2)
    
    ctx9 = cont[9:frame.length+9]
    if frame.getID() == 0:   #Data帧
        #frame["value"] = ctx9
        frame.data = ctx9
    elif frame.getID() == 1: #Headers帧
        #frame["value"] = ParsingHeadersFrame(ctx9, frame, self)
        frame.data = ParsingHeadersFrame(ctx9, frame, self)
    elif frame.getID() == 3: #Rst_Stream帧
        #frame['value'] = ctx9
        frame.data = ctx9
    elif frame.getID() == 4: #Settings帧
        #frame['param'] = ParsingSettingParam(ctx9)
        frame.data = ParsingSettingParam(ctx9)
    elif frame.getID() == 6: #Ping 帧
        #frame['value'] = cont[9:9+64]
        frame.data = cont[9:9+64]
    elif frame.getID() == 7: #GoAway帧
        self.goAway()
        #frame['value'] = ctx9
        frame.data = ctx9
    elif frame.getID() == 8: #Window_Update帧
        #frame["window_update"] = ParsingWindowUpdateParam(ctx9)
        frame.data = ParsingWindowUpdateParam(ctx9)

    nextframe = cont[frame.length+9:]

    frames.append(frame)

    if not cont == b'':
        ParsingHTTP2Frame(nextframe, self, frames)

    return frames


def ParsingWindowUpdateParam(ctx):
    return int.from_bytes(ctx, 'big')

def ParsingHeadersFrame(ctx, frame, self):
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

            '''header["E-SID"]      = str(ctx[1-c:5-c]) #E + StreamDependency
            header["weight"]     = ctx[5-c]
            header["header"]     = decoder.decode(ctx[6-c:])
            header['header']     = kvListToDict(header['header'])
            header['header'][':path'], header['getdata'] = decodeGET(header['header'].get(":path", ""))
            Path = header['header'][':path']'''
            header.isPriority = True
            header.esdp       = str(ctx[1-c:5-c])
            header.weight     = ctx[5-c]
            
            head = decoder.decode(ctx[6-c:])
            head = kvListToDict(head)
            head[':path'], head['getdata'] = decodeGET(head[':path'])

            header.header = head
            Path = header.getHeader(":path")

        else:
            #header['header'] = decoder.decode(ctx[0:])
            #header['header'] = kvListToDict(header['header'])
            #header['header'][':path'], header['getdata'] = decodeGET(header['header'].get(":path", ""))
            #Path = header['header'][':path']
            header.header = kvListToDict(decoder.decode(ctx[0:]))
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
    params = {}
    TypeId = int.from_bytes(ctx[0:2], 'big')
    Type   = getSFParam(TypeId)
    params[Type] = {}
    value = ctx[2:6]
    valueTo = int.from_bytes(value, 'big')
    params[Type] = {"value": str(value), "valueTo": valueTo}

    if ctx[6:8] == b'\x00\x00':
        return params
    if not len(ctx[6:]) == 0:
        params.update(ParsingSettingParam(ctx[6:]))
        return params
    return params


