import inspect, ctypes
from io import *
import gzip
import hashlib
import time, os
from typing import Any
from log import *
import threading
import CacheModule as cm
import typing

HashCacheSize = 4096*1024*2
LOG = False
NOT_RECORDED_FUNCTIONS = ['parsingHeaderLine']
DT = None

def setDT(dt):
    globals()["DT"] = dt


 #优先执行的线程
def priorityHigh(f):
    def func(*arg, **args):
        thread = threading.Thread(target=f, args=arg, kwargs=args)
        DT.addThread(thread, 2)
    return func

#获取文件的base64编码
def getFileBase64(path):
    import base64
    with open(path, 'rb') as f:
        return base64.b64encode(f.read())


#将通过include导入的模块转为对象
def toObject(dic):
    class Module:
        def __str__(self):
            return '<Module Object>'
        pass
    a = Module()
    for k in dic:
        v = dic[k]
        a.__setattr__(k, v)
    return a


#日志函数
def profile(func):
    def x(*arg, **args):
        if not func.__name__ in NOT_RECORDED_FUNCTIONS and LOG:
            l = time.time()
            o = func(*arg, **args)
            p = time.time()
            #with open("./logs/funclog.txt", 'a') as f:
            #    f.write(time.ctime()+"-->:函数"+func.__name__+" 耗时:"+str(p-l)+";返回值:"+str(o)+"\n")
            setLog("")
        else:
            o = func(*arg, **args)
        return o
    return x


#报错查询具体位置
def tryGetErrorDetail(s, path):
    with open(path, 'r', encoding='UTF-8') as f:
        try:
            x=s.split("line")[-1].split(",")[0]
            x = int(x.strip())-1
        except:
            return s
        #for i in range(x):
        #    ctx = f.readline()
        #    if i+1 == x:

        i   = 0
        ctx = '<code>'
        while i <= x+3:
            if i in range(x-3, x+3):
                g = f.readline().replace("\n", "").replace("<", "&lt;").replace(">", "&gt")
                ctx += "{i: <4}|     {g}<br>".format(i=i, g=g)
            else:
                f.readline()
            i += 1
        ctx += '</code>'
        return s+"<br><br>FileName:%s<br><br>%s"%(path, ctx)
        #return s

#Gzip 压缩函数
def gzip_encode(data):
    buf = BytesIO()
    f = gzip.GzipFile(mode='wb', fileobj=buf)
    f.write(data)
    f.close()
    buf.seek(0)
    return buf.read()

#Hash(md5) 函数
def getHash(content):
    sha1obj = hashlib.sha1()
    sha1obj.update(content)
    return sha1obj.hexdigest()
def getHashByFile(file):
    sha1obj = hashlib.sha1()
    content = file.read(HashCacheSize)
    while not content == b'':
        sha1obj.update(content)
        content = file.read(HashCacheSize)
    file.close()
    return sha1obj.hexdigest()


#停止线程函数
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


#删除一个对象的所有东西
def DeleteObjectAllProperties(objectInstance):
    if not objectInstance:
        return
    listPro =[key for key in objectInstance.__dict__.keys()]
    for key in listPro:
        objectInstance.__delattr__(key)


#合并字典
def dict_inone(*arg):
    x = {}
    for i in arg:
        for f in i:
            x[f] = i[f]
    return x


#获取HTTP请求头的文件返回范围
def getRange(xd):
    if '-' in xd:
        x = xd.split("-")
        if x[1] == '':
            f1 = ''
        else:
            f1 = int(x[1])
        f = int(x[0])
        return [f,f1]
    else:
        try:
            int(xd)
        except:
            return [0,0]
        else:
            return int(xd), int(xd)


#ini格式刷转JSON
def iniToJson(inipath):
    import configparser as cp
    cf = cp.ConfigParser()
    cf.optionxform = lambda option: option
    cf.readfp(open(inipath, encoding='utf-8'))
    result = {}
    kv = {}
    scts = cf.sections()
    for i in scts:
        kv[i] = cf.items(i)
    for i in kv.keys():
        result[i] = {}
        for v in kv[i]:
            v = list(v)
            vf = v[1].strip()
            if vf == '':
                vf = None
            elif vf == 'true':
                vf = True
            elif vf == 'false':
                vf = False
            elif not isNum(vf) == False:
                vf = isNum(vf)
            elif vf[0] == '(' and vf[-1] == ')':
                try:
                    vf = eval(vf)
                except Exception as e:
                    print("[ Value:", vf," ] Occurs when parsing:", e)
            if v[0][0] == '(' and v[0][-1] == ')':
                try:
                    v[0] = eval(v[0])
                except Exception as e:
                    print("[ Key:", v[0], "] Occurs when parsing:", e)
            result[i][v[0]] = vf
    return result


#洁净输出json
def prettyPrint(j, ret=False):
    if isinstance(j, dict):
        import json
        res = (json.dumps(j, sort_keys=True, indent=4, separators=(',', ':')))
        if ret:
            return res
        else:
            print(res)
    elif isinstance(j, list):
        #print(j)
        print("   \n".join([(prettyPrint(i, 1) if isinstance(i, dict) else str(i)) for i in j]))


#是否是一个ipv4地址
def isIPv4(domain):
    if len(domain.split(".")) == 4:
        for i in domain.split("."):
            try:
                int(i)
            except:
                return False
        return True
    return False


#获取文件的类型
def FileType(path):
    from http_returntype import return_filetype
    for i in return_filetype:
        v = return_filetype[i]
        if i == 'default':
            continue
        for i2 in v:
            if path[-len(i2)-1:].lower() == '.'+i2:
                return i.replace('.', '/', 1)
    return return_filetype['default'].replace('.', '/')


#判断是否是数字
def isNum(st):
    try:
        int(st)
    except:
        return False
    else:
        return int(st)


#将[(key, val), ...]类型的list转为dict
def kvListToDict(v):
    d = {}
    for i in v:
        d[i[0]] = i[1]
    return d


#获取一个字节中某一位比特
def getBit(byteNum, i, byteorder):
    return (byteNum >> (i if byteorder == 'little' else 7-i)) & 1

#获取一个字节中第from_位比特到to位比特的字符串
def getRangeBit(b, from_, to, byteorder):
    x = ''
    for i in b:
        for n in (list(range(8)) if byteorder == 'little' else list(range(8))[::-1]):
            x += str(getBit(i, n, 'little'))
    return x[from_: to]

#将HTTP2解析的数据转换为HTTP1.1的格式
def toH1Format(x):
    p = {}
    for i in x:
        if i == ':authority':
            p['host'] = x[i]
        elif i == ':path':
            p['path'] = x[i]
        elif i == ':method':
            p['method'] = x[i]
        else:
            p[i] = x[i]
    return p


class STR:
    def __str__(self):
        c = self.__class__.__name__+"("
        for key in self.__dict__:
            c += f"{key}={getattr(self, key)} "
        c = c[0:-1]+")"
        return c


class FrameParser(STR):
    def __init__(self, length=None, _type=None, ID=None, flags=None, R_SID=None, R=None, SID=None):
        self.length = length
        self.type   = _type
        self.typeID = ID
        self.flags  = flags
        self.R_SID  = R_SID   #R标记+SID
        self.R      = R
        self.SID    = SID
        self.data   = None

    def get(self, key=None, val=None):
        if self.getType() == 'Data':
            return self.data
        if key in self.__dict__:
            return self.__dict__.get(key)
        if self.getType() == "Headers" and key:
            return self.data.get(key, val)
        if isinstance(self.data, dict) and key in self.data:
            return self.data.get(key, val)
        return self.data
        
    def getType(self):
        return self.type
    def getStreamID(self):
        return self.SID
    def getR(self):
        return self.R
    def getFlags(self):
        return self.flags
    def getID(self):
        return self.typeID
    def getLength(self):
        return self.length
    
class HeaderParser(STR):
    def __init__(self, frame=None, header=None, priority=False, weight=None, esdp=None):
        "frame: FrameParser object; header: a dict; priority: whether enable E; weight: weight; esdp: E+StreamDependency"
        self.frame  = frame
        self.header = header
        
        self.isPriority = priority
        self.weight     = weight
        self.esdp       = esdp
    
    def getHeader(self, key):
        return self.header.get(key)
    def getWeight(self):
        return self.weight
    def getEStreamDependency(self):
        return self.esdp
    def get(self, key=None, val=None):
        if key:
            return self.header.get(key, val)
        return self.header
    def __iter__(self):
        return iter(self.header)
    



class UploadFileObject:
    def __init__(self, filename, cachefile: typing.Union[cm.h2cachefile, cm.cachefile]):
        self.filename = filename
        self.cachefile = cachefile
    def getFile(self):
        return self.cachefile
    def __getitem__(self, key):
        if getattr(self, key):
            return getattr(self, key)
    def __str__(self):
        return f"UploadFileObject(filename={self.filename} cachepath={self.cachefile.path})"
    def __repr__(self):
        return self.__str__()
    def __getattribute__(self, key):
        return object.__getattribute__(self, key)

class UploadFilesObject:
    def __init__(self, files):
        self.dict = files
        for i in files:
            setattr(self, i, files[i])
    def __getitem__(self, k):
        return getattr(self, k)
    def __len__(self):
        return len(self.dict)
    def __iter__(self):
        return iter(self.dict)
    def __str__(self):
        return str(self.dict)
    def get(self, k, d=None):
        return getattr(self, k, d)
    
class UploadDatasObject(UploadFilesObject):
    pass
