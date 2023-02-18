
from Logger import Logger
from functions import FileType, tryGetErrorDetail, prettyPrint, kvListToDict, getBit, getRangeBit, toH1Format, setLog, gzip_encode
from server_config import ServerPath
from server_config import *
import time
from threading import Thread, Lock
from ParsingHTTPData import decodeGET, decodePOST, decodeCookie, decodeContentType, parsingCacheFile
import CacheModule as cf

Logger = Logger()
DT     = None

def H2R_SetDT(dt):
    global DT
    DT = dt

ThreadLock = Lock()
GZIP_ENCODING = False

HEADER_MODULE = {
            "getdata":{},
            "postdata":{},
            "rewritedata":{},
            "headers": {},
            "path":"",
            "language":"",
            "cookie":{}
}

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
class ServerResponseHTTP2:
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
            0x9 -> Continuation"""
        
        
    def __init__(self, respH1, ident):
        self.ident = str(ident)
        self.self = respH1
        self.settings = {
            "SETTINGS_HEADER_TABLE_SIZE":     4096,
            "SETTINGS_MAX_CONCURRENT_STREAMS": 100,
            "SETTINGS_INITAL_WINDOW_SIZE":   65535,
            "SETTINGS_MAX_FRAME_SIZE":       2**14,   #16384,
            "SETTINGS_MAX_HEADER_LIST_SIZE": 16384,
        }
        self.initalWindowSize = 65535

        self.conn = socketProxy(self.self.conn, self)
        self.encoder = None
        self.decoder = None
        self.needNewH1Response = False
        self.streams = {}
        self.x  = 0
        self.uploadingStream = {}
        self.waitingPost     = {}
        self.streamCache     = {}
        self.priority        = 1

    def getSettings(self, key):
        if key == 'header_table_size':
            ret = self.settings.get(SettingsFrameParam['1'], None)
            return ret if ret else 65535
        elif key == 'max_header_list_size':
            ret = self.settings.get(SettingsFrameParam['6'], None)
            return ret if ret else 262144
        else:
            return self.settings.get(key)

    def response(self):
        MAGIC = self.conn.recv(24)
        if MAGIC == MagicContent:
            Logger.info("使用 http2 进行通讯")
            C = 0
            x = SettingFrame(self, self.conn, 0)
            #x.send()
            while 1:
                try:
                    frs = ParsingHTTP2Frame(self.conn, self)
                    if frs == 'stop':
                        return
                    if len(frs) == 0:
                        time.sleep(0.01)
                        continue
                    self.checkWindowSize()
                    for fs in frs:
                        #print("                   |SID         |Type     |    Length|     Flags|")
                        Logger.error("->", C, "接受到帧：", "SID:", fs['SID'], "TYPE:", fs['type'], "LENGTH:", fs['length'], "FLAGS:", fs['flags'])

                        ctx = ''
                        if fs['type'] == 'Settings':
                            ctx = str(fs['param'])
                        elif fs['type'] == 'Headers':
                            for i in fs['value']['header']:
                                ctx += '                    '+str(i)+': '+str(fs['value']['header'][i])+'\n'
                        elif fs['type'] == 'Data':
                            ctx = str(fs['value'])
                        elif fs['type'] == 'Window_Update':
                            ctx = str(fs['window_update'])
                            print("WindowUpdate---->", ctx)
                        else:
                            ctx = str(fs)
                        setLog("["+str(fs['SID'])+"] RECV_"+fs['type'].upper()+"_FRAME\n               --> content:\n                     "+(ctx[0:20] if not fs['type'] in ('Headers', "Settings", "Rst_Stream") else ctx)+"\n               --> stream id: "+str(fs['SID'])+"\n               --> flags: "+str(fs['flags'])+"\n               --> size: "+str(fs['length']), "./logs/h2.log", 0)
                        
                    Thread(target=self.respond, args=(frs,)).start()
                    #self.respond(frs)
                    C+=1
                except Exception as e:
                    import traceback
                    Logger.error(e, traceback.format_exc())
                    if "WinError" in str(e):
                        pass
                    continue

    def checkWindowSize(self):
        #Logger.warn("check update")
        if self.initalWindowSize*3/4 <= self.conn.recData:
            Logger.warn("超过Update的3/4")
            x = WindowUpdateFrame(self.conn, 0, self)
            x.send(65535*2)
            for i in self.uploadingStream.keys():
                x = WindowUpdateFrame(self.conn, i, self)
                x.send(65535*2)
                Logger.error("向", i, "发送！", self.conn.recData)
            self.conn.recData = 0
            #Logger.comp(self.conn.recData, self.initalWindowSize)
        
    def respond(self, frs):
        for f in frs:
            if f['type'] == "Settings":
                for key in f['param']:
                    self.settings[key] = f['param'][key]['valueTo']

                self.respondSetting(f)
            
            if f['type'] == "Headers":
                #DT.addThread(Thread(target=self.respondHeader, args=(f,)), 4)
                self.respondHeader(f)

            if f['type'] == "Ping":
                self.respondPing(f)
            
            if f['type'] == 'Rst_Stream':
                self.stopStream(f)
            
            if f['type'] == 'Data':
                self.respondData(f)

    def respondData(self, f):
        if not f['SID'] in self.streamCache.keys():
            self.streamCache[f['SID']] = cf.h2cachefile(save=(cf.MEMORY if self.streams.get(f['SID']) and self.streams.get(f['SID']).header and self.streams.get(f['SID']).header['value']['header']['method'].lower() == "post" and not decodeContentType(self.streams.get(f['SID']).header['value']['header'].get("content-type")).get("type", "").lower() == "multipart/form-data" else cf.DISK))

        self.streamCache[f['SID']].write(f['value'])
        if f['flags'] & 0x1 == 0x1:
            self.streamCache[f['SID']]._check()

            if self.streams.get(f['SID']):
                if self.streams.get(f['SID']).header:
                    h = self.streams.get(f['SID']).header
                    if h['value']['header']['method'].lower() == 'post' and not "multipart/form-data" in h['value']['header'].get("content-type", "").lower():
                        #POST 数据
                        self.streamCache[f['SID']].seek(0)
                        postdata = decodePOST(self.streamCache[f['SID']].read().decode("UTF-8"))
                        self.waitingPost[f['SID']] = postdata
                    elif "multipart/form-data" in h['value']['header'].get("content-type", "").lower():
                        #MULTIPART/FORM-DATA 数据
                        bd = decodeContentType(h['value']['header'].get("content-type", ""))["boundary"]
                        files, datas = parsingCacheFile(self.streamCache[f['SID']], bd)
                        self.uploadingStream[f['SID']] = files, datas
                        Logger.info(".....")

    def stopStream(self, f):
        if f['SID'] in self.streams.keys():
            self.streams[f['SID']].isClosed = True
            #del self.streams[f['SID']]
        
    def respondPing(self, f):
        try:
            print("接受到Ping 帧-->", f)
            x = PingFrame(self.conn, f["SID"], f, self)
            x.send(1)
            #self.goAway()
        except Exception as e:
            print(e)

    def uploadFile(self, f):
        sid = f['SID']
        self.uploadingStream[sid] = {}
        while 1:
            if len(self.uploadingStream[sid]) > 0:
                x = self.uploadingStream.get(f['SID'])
                del self.uploadingStream[f['SID']]
                return x
            time.sleep(0.001)

    def getPostData(self, sid):
        self.waitingPost[sid] = None
        while 1:
            if self.waitingPost[sid]:
                #del self.waitingPost[sid]
                Logger.error(self.waitingPost)
                return self.waitingPost[sid]
            time.sleep(0.001)

    def respondHeader(self, f):

        #print("即将发送 Header 与 Data 数据帧\n")
        
        path = f['value']['header'][':path']

        header = HeaderFrame(self.conn, f['SID'], self)
        #p.set("content-length", str(len(x.data)))
        header.set("content-type", FileType(path))

        f['value']['stream_id'] = f['SID']

        prettyPrint(f['value'])

        #if self.needNewH1Response:
            #self.needNewH1Response = False
        obj = self.self.clearEnvironment(self.self.conn, self.self.collection)
        #else:
            #obj = self.self

        obj.cachesize = self.getSettings("SETTINGS_MAX_FRAME_SIZE")
        self.streams[f['SID']] = H1toH2SocketStream(self.conn, f['SID'], self)
        self.streams[f['SID']].header = f

        obj.conn   = self.streams[f['SID']]
        obj.header = header


        f['value']['header'] = toH1Format(f['value']['header'])
        
        obj.data = HEADER_MODULE.copy()
        obj.data['cookie'] = {} if not f['value']['header'].get("cookie", None) else decodeCookie(f['value']['header'].get("cookie"))
        obj.data['path'] = f['value']['header']['path']
        obj.data['headers'] = f['value']['header']
        obj.data['getdata'] = f['value']['getdata']

        gloadd = {}

        #上传文件进行处理
        dctx = decodeContentType(obj.data['headers'].get("content-type"))
        if dctx.get("type") == "multipart/form-data" and dctx.get("boundary", None):
            file, data = self.uploadFile(f)
            gloadd["_FILE"], gloadd["_DATA"] = file, data
            Logger.error("---》", file, data)
        #Logger.comp(f['SID'], '-', dctx)
        #Logger.comp(f['SID'], f['value']['header']['path'][-3:])

        if f['value']['header'].get("method").lower() == 'post' and not dctx.get("boundary", ""):
            obj.data['postdata'] = self.getPostData(f['SID'])

        obj.inHTTP2  = True
        obj.http2Res = self

        Logger.warn("Choosing Response Method")

        if f['value']['header']['path'][-3:] == '.py':
            Logger.warn("PythonFileHandle()")
            obj.PythonFileHandle(obj.data, glo=gloadd,  onHeaderFinish=lambda: header.send(4), onEndCallback=lambda: self.streams[f['SID']].send(b'', 1))
            self.priority = obj.priority
        else:
            Logger.warn("CommonFileHandle()")
            obj.CommonFileHandle(obj.data,  onHeaderFinish=lambda: header.send(4), glo=gloadd)
        
        self.needNewH1Response = True

    
    def error(self, type_, exception='', detail='', conn=None):
        header = HeaderFrame(self.conn, conn.sid, self)

        if type_ == 'codeerror':
            header.set(":status", "500")
            #self.conn.send(header.encode()+self.SingleLineFeed)
            header.send(4)

            conn.send(b"<html><head><meta charset='utf-8'></head><body><center><h1>Python Error</h1>")
            detail = detail.replace("<", "&lt;").replace(">", "&gt")
            detail = tryGetErrorDetail(detail, ServerPath+"/"+conn.header['value']['header']['path'])
            conn.send(b"<br><font color='red'>Error: </font>"+str(exception).encode()+b"(at line "+str(exception.__traceback__.tb_lineno).encode("UTF-8")+\
                      b")<br></center><div style='margin:30px'>Detail:<br><div style='padding:30px;line-height: 2;'>"+detail.replace("\n", "<br>").encode()+\
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


    def respondSetting(self, f):
        if f['flags'] == 1:
            #设置确认
            #x = SettingFrame(self, self.conn, f['SID'])
            #x.send(f['SID'], 1, 0)
            return
            #pass
        elif f['param'].get(0, None) and f['param'].get(0, None).get("valueTo", None) == 0:
            return
        retFrame = SettingFrame(self, self.conn, f['SID'])
        #self.settings['SETTINGS_MAX_FRAME_SIZE'] = 2**20
        retFrame.send(f['SID'])
    
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
        #if not self.encoder:
            from hpack import Encoder
            x = Encoder()
            x.header_table_size = self.getSettings("header_table_size") #65536
            x.max_header_list_size = self.getSettings("max_header_list_size") #262144
            x.max_allowed_table_size = self.getSettings("header_table_size") #65536
            self.encoder = x
            return x
        #else:
            #return self.encoder



class socketProxy:
    def __init__(self, conn, res):
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
        #setLog("["+self.self.ident+"] < "+str(data), "./logs/h2.log")
        return data
    def makefile(self, t):
        return self.conn.makefile(t)
    def send(self, data, retry=5):

        def tsend():
            if self.isClosed:
                return
            self.proData += len(data)
            try:
                #setLog("["+self.self.ident+"] > "+str(data), "./logs/h2.log")
                #ThreadLock.acquire()
                DT.ThreadLock.acquire()
                self.conn.send(data)
                DT.ThreadLock.release()
            except Exception as e:
                if 1:
                    if retry == 0:
                        print("retry fell.")
                        Logger.error("关闭 socket:", e)
                        self.isClosed = True
                        self.self.goAway()
                        self.conn.close()
                        return
                    print("Retry...", retry, e)
                    self.send(data,  retry-1)
                    return

        tsend()

            
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
        print("于", self.sid, "发送 Window Update 帧")
        data = parsingRSID(R, increment)
        #print(data)
        self.conn.send(fh+data)
        setLog("["+str(self.sid)+"] SEND_WINDOW_UPDATE_FRAME\n               --> increment: "+str(increment), "./logs/h2.log", 0)

class PingFrame:
    def __init__(self, conn, sid, frame, s):
        self.self = s
        self.conn = conn
        self.data = frame['value']
        self.sid  = sid
    def send(self, flags = 1, R = 0):
        fh = int.to_bytes(8, 3, 'big')
        fh += int.to_bytes(6, 1, 'big')
        fh += int.to_bytes(flags, 1, 'big')
        fh += parsingRSID(R, self.sid)
        print("于", self.sid, "发送 Ping 帧", fh)
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
                    fc += int.to_bytes(int(getFrameId(i)), 2, byteorder='big')
                    fc += int.to_bytes(self.self.settings[i], 4, byteorder='big')
            if not Ctx:
                fc = b''
            fh += int.to_bytes(len(fc), 3, byteorder='big')
            fh += int.to_bytes(4, 1, byteorder='big')
            fh += int.to_bytes(flags, 1, byteorder='big')
            RSID = parsingRSID(R, self.sid)
            fh += RSID
            print("于",self.sid,"发送Settings帧")
            setLog("["+str(self.sid)+"] SEND_SETTINGS_FRAME\n               ---> settings' size: "+str(len(fc))+"\n               --> flag: "+str(flags)+"\n               --> Ctx: "+str(Ctx), "./logs/h2.log", 0)
            self.conn.send(fh+fc)
        except Exception as e:
            print("无法发送Setting帧：", e)
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
            if self.self.getSettings("SETTINGS_MAX_FRAME_SIZE") < len(self.data):
                d = self.data
                self.data = self.data[0:self.self.getSettings("SETTINGS_MAX_FRAME_SIZE")]
                d = d[self.self.getSettings("SETTINGS_MAX_FRAME_SIZE"):]
                frame = DataFrame(self.conn, d, self.sid, self.self, alreadyGzip=True)
                
            self.fh = len(self.data).to_bytes(3, 'big')     #Length
            self.fh += int(0).to_bytes(1, 'big')            #Type
            self.fh += int(flag).to_bytes(1, 'big')         #Flag
            self.fh += parsingRSID(r, self.sid)             #R and Stream ID

            #print("于", self.sid, "发送DATA FRAME!!!", len(self.data), flag)
            
            self.conn.send(self.fh+self.data)

            if frame:
                Logger.warn(self.sid, "无法完全发送，发送剩余部分：", len(d))
                frame.send(flag, r)

            setLog("["+str(self.sid)+"] SEND_DATA_FRAME\n               --> data size: "+str(len(self.data))+"\n               --> content:\n                    "+str(self.data)[0:20]+"\n               --> flag: "+str(flag)+"\n               --> stream id: "+str(self.sid), "./logs/h2.log", 0)       #LOG here--------------------------
        except Exception as e:
            import traceback
            print("无法发送Data帧：", e, traceback.format_exc())
            setLog("["+str(self.sid)+"] ERROR_IN_SENDING_DATA_FRAME\n               --> Error: "+str(e)+"\n               --> stream id"+str(self.sid), "./logs/h2.log", 0)
            #self.self.streams[self.sid].isClosed = True

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
            #if headerKey.lower() == "etag":
            #    return
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
            print("于", self.sid, "发送 Header Frame!!!", len(h), self.headers)
            #print(self.headers)
            #print(fh, h, self.conn)
            headerCtx = ''
            for i in self.headers:
                headerCtx += '                         '+str(i)+': '+str(self.headers[i])+'\n'
            setLog("["+str(self.sid)+"] SEND_HEADER_FRAME\n               --> header size: "+str(len(h))+"\n               --> encoder settings: "+str(self.self.settings)+"\n               --> flags: "+str(flag)+"\n               --> Headers:\n"+headerCtx+"               --> stream id: "+str(self.sid), "./logs/h2.log", 0) #-------- log here
            self.conn.send(fh+h)
        except Exception as e:
            print("无法发送Header帧：",e)
            setLog("["+str(self.sid)+"] ERROR_IN_SENDING_HEADER_FRAME\n               --> Error: "+str(e)+"\n               --> stream id: "+str(self.sid), "./logs/h2.log", 0)

class H1toH2SocketStream:
    def __init__(self, conn, sid, res, R = 0):
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
        #print("发送Data帧: Flag:", flag,"DataRaw:", data[0:20], "SID:", self.sid)
        #d = None
        #Logger.info(len(data), self.self.getSettings("SETTINGS_MAX_FRAME_SIZE"))
        #if len(data) >= self.self.getSettings("SETTINGS_MAX_FRAME_SIZE"):
        #    d = data
        #    data = d[0:self.self.getSettings("SETTINGS_MAX_FRAME_SIZE")]
        #    d = d[self.self.getSettings("SETTINGS_MAX_FRAME_SIZE"):]
        #ThreadLock.acquire()
        frame = DataFrame(self.conn, data, self.sid, self.self)
        frame.send(flag, self.R)
        #ThreadLock.release()
        #if d:
        #    self.send(d, flag)
    def makefile(self, x):
        return self.conn.makefile(x)
    def sendFrame(self, frameObj):
        if not self.isClosed:
            self.conn.send(frameObj.getContent())

def parsingRSID(R, SID):
    RSID = getRangeBit(int.to_bytes(SID, 4, byteorder='big'), 0, 32, byteorder='big')
    RSID = int(str(R)+RSID[1:], 2).to_bytes(4, byteorder='big')
    return RSID
def getFrameType(Id):
    return FrameTypes[str(Id)] if int(Id) >= 0 and int(Id) < 10 else Id
def getFrameId(Name):
    for i in SettingsFrameParam:
        if SettingsFrameParam[i] == Name:
            return i
    return Name
def getSFParam(Id):
    return SettingsFrameParam[str(Id)] if int(Id) > 0 and int(Id) < 7 else Id

def ParsingHTTP2Frame(conn, self, frames=None):
    if not isinstance(conn, bytes):
        try:
            cont = conn.recv(1024*1024)
        except Exception as e:
            return 'stop'
    else:
        cont = conn
    i = 0
    frames = [] if not frames else frames
    nF = {}
    #帧头
    if cont == b'':
        return frames

    print(cont)
    
    #print("FRAME_HEAD:",cont[0:9], cont)
    nF['length'] = int.from_bytes(cont[0:3], 'big')
    nF['type']   = getFrameType(cont[3])
    nF['ID']     = cont[3]
    nF["flags"] = cont[4]
    nF['R_SID'] = cont[5:9]
    nF['R'] = getBit(nF['R_SID'][0], 0, byteorder='big')
    nF['SID'] = int(getRangeBit(nF['R_SID'], 1, 32, byteorder='big'), 2)
    #print(nF)
    

    if nF["ID"] == 0:
        #Data帧
        nF["value"] = cont[9:nF['length']+9]
    elif nF["ID"] == 1:
        #Headers帧
        nF["value"] = ParsingHeadersFrame(cont[9:nF['length']+9], nF, self)
    elif nF['ID'] == 3:
        #Rst_Stream帧
        nF['value'] = cont[9:nF['length']+9]
    elif nF['ID'] == 4:
        #Settings帧
        nF['param'] = ParsingSettingParam(cont[9:nF["length"]+9])
    elif nF["ID"] == 6:
        #Ping 帧
        nF['value'] = cont[9:9+64]
    elif nF['ID'] == 7:
        #GoAway帧
        self.goAway()
        nF['value'] = cont[9:nF['length']+9]
    elif nF["ID"] == 8:
        #Window_Update帧
        nF["window_update"] = ParsingWindowUpdateParam(cont[9:nF['length']+9])
    cont = cont[nF['length']+9:]

    #print("-----------------------------------------------------------")
    #if nF['ID'] == 1:
    #    print("Header:", nF['value']['header'][':path'])
    #print(nF['type'], nF['length'], nF['SID'])
    #print("-----------------------------------------------------------")

    frames.append(nF)
    if not cont == b'':
        ParsingHTTP2Frame(cont, self, frames)
    return frames


def ParsingWindowUpdateParam(ctx):
    return int.from_bytes(ctx, 'big')

def ParsingHeadersFrame(ctx, fheader, self):
    frame = {}
    x = self.getNewHPackDecoder()
    try:
        if fheader['flags'] & 0x20 == 0x20:
            #存在 PROIRITY帧
            c = 1
            if fheader['flags'] & 0x8 == 0x8:
                #存在 PADDED 帧
                frame["pad-length"] = ctx[0]
                c = 0
            frame["E-SID"]      = str(ctx[1-c:5-c])
            frame["weight"]     = ctx[5-c]
            frame["header"]     = x.decode(ctx[6-c:])

            frame['header']     = kvListToDict(frame['header'])

            frame['header'][':path'], frame['getdata'] = decodeGET(frame['header'].get(":path", ""))

            Path = frame['header'][':path']
            
            if Path and Path[-1] == "/":
                realpath = ServerPath+"/"+Path
                for i in config['default-page']:
                    if os.path.isfile(realpath + "/" + i):
                        frame['header'][':path'] = Path+i
                        break

            #print("-------","于%s提取到的路径为:"%fheader['SID'],frame['header'][':path'], "-------", sep='\n')



    except Exception as e:
        import traceback
        Logger.error(e, traceback.format_exc())
        return frame
    return frame

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
    
