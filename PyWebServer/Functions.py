

from io import *
import json
from typing import Any
import gzip
import hashlib
import re
import time, os
import CacheModule as cm
import typing
import inspect, ctypes

HashCacheSize = 4096*1024*2


#获取文件的base64编码
def getFileBase64(path):
    import base64
    with open(path, 'rb') as f:
        return base64.b64encode(f.read())

#将通过include导入的模块转为对象
def toObject(dictobj):
    class Module:
        def __str__(self):
            return '<Module Object>'
        pass
    a = Module()
    for k in dictobj:
        v = dictobj[k]
        a.__setattr__(k, v)
    return a

#报错查询具体位置
class toIOObject:
    """A object that converts multiline string into sth similar to StringIO"""
    def __init__(self, strs):
        self.lines = strs.split("\n")
        self.index = 0
    def readline(self):
        self.index += 1
        return self.lines[self.index-1] if self.index-1 < len(self.lines) else ''
    def close(self):
        return
def tryGetErrorDetail(excStr, path, lineContent=None):
    """Get error detail from original path"""
    path = os.path.normpath(path)
    try:
        line=excStr.split("line")[-1].split(",")[0]
        line = int(line.strip())-1
    except:
        return excStr
    f       = open(path, 'r', encoding='utf-8') if not lineContent else toIOObject(lineContent)
    linenum = 0
    ctx = '<code>'
    while linenum <= line+3:
        if linenum in range(line-3, line+3):
            g = f.readline().replace("\n", "").replace("<", "&lt;").replace(">", "&gt")
            ctx += "{i: <4}|     {g}<br>".format(i=linenum, g=g)
        else:
            f.readline()
        linenum += 1
    ctx += '</code>'
    return excStr+"<br><br>FileName:%s<br><br>%s"%(path, ctx)

#Gzip 压缩函数
def gzip_encode(data:bytes):
    buf = BytesIO()
    f = gzip.GzipFile(mode='wb', fileobj=buf, compresslevel=9)
    f.write(data)
    f.close()
    buf.seek(0)
    return buf.read()

#Hash(md5) 函数
def getHash(content):
    sha1obj = hashlib.sha1()
    sha1obj.update(content)
    return sha1obj.hexdigest()
def getHashByFile(file:typing.IO):
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
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")
def stop_thread(thread):
    _async_raise(thread.ident, SystemExit)


#合并字典
def dict_inone(*arg):
    x = {}
    for i in arg:
        for f in i:
            x[f] = i[f]
    return x


#获取HTTP请求头的文件返回范围
def getRange(rangefield):
    if '-' in rangefield:
        x = rangefield.split("-")
        if x[1] == '':
            f1 = ''
        else:
            f1 = int(x[1])
        f = int(x[0])
        return [f,f1]
    else:
        try:
            int(rangefield)
        except:
            return [0,0]
        else:
            return int(rangefield), int(rangefield)

#洁净输出json
def prettyPrint(dictobj:dict, ret=False):
    import json
    return json.dumps(dictobj, indent=4)
    if isinstance(dictobj, dict):
        import json
        res = (json.dumps(dictobj, sort_keys=True, indent=4, separators=(',', ':')))
        if ret:
            return res
        else:
            print(res)
    elif isinstance(dictobj, list):
        print("   \n".join([(prettyPrint(i, 1) if isinstance(i, dict) else str(i)) for i in dictobj]))


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

#ini格式刷转JSON
def iniToJson(inipath):
    import configparser as cp
    cf             = cp.ConfigParser()
    result         = {}
    kv             = {}
    cf.optionxform = lambda option: option
    cf.readfp(open(inipath, encoding='utf-8'))
    scts = cf.sections()
    
    for i in scts:
        kv[i] = cf.items(i)
    for i in kv.keys():
        result[i] = {}
        for v in kv[i]:
            v  = list(v)
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

#获取文件的类型
def FileType(path):
    from FileTypes import return_filetype
    for filetype in return_filetype:
        suffixes = return_filetype[filetype]
        if filetype == 'default':
            continue
        for suffix in suffixes:
            if path[-len(suffix)-1:].lower() == '.'+suffix:
                return filetype.replace('.', '/', 1)
    return return_filetype['default'].replace('.', '/')


#判断是否是数字
def isNum(_str):
    try:
        int(_str)
    except:
        return False
    else:
        return int(_str)


#将[(key, val), ...]类型的list转为dict
def kvListToDict(fields:list) -> dict:
    dictobj = {}
    for key in fields:
        if key[0].lower() == 'cookie':
            if 'cookie' in [h.lower() for h in dictobj.keys()]:
                dictobj[key[0]] += '; '+key[1]
                continue
        dictobj[key[0]] = key[1]
    return dictobj

#将dict转为[(key, val), ...]类型的list
def dictToKvList(dictobj:dict, toStr=False) -> typing.List[typing.Tuple[str, str], ]:
    listobj = []
    for key in dictobj:
        val = dictobj[key]
        if not type(key) == str and toStr:
            key = str(key)
        if isinstance(val, (list, tuple)):
            for i in val:
                listobj.append((key, i))
            continue
        listobj.append((key, val if not toStr else str(val)))
    return listobj


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
def toH1Format(header:dict) -> dict:
    p = {}
    for i in header:
        if i == ':authority':
            p['host'] = header[i]
        elif i == ':path':
            p['path'] = header[i]
        elif i == ':method':
            p['method'] = header[i]
        else:
            p[i] = header[i]
    return p



class STRING:
    """An inheritable class for formatting objects into strings."""
    def __str__(self):
        c = self.__class__.__name__+"("
        for key in self.__dict__:
            if key == 'data':
                if self.__class__.__name__ == 'FrameParser' and self.getType() == 'Data':
                    continue
            c += f"{key}={getattr(self, key)} "
        c = c[0:-1]+")"
        return c
    def __repr__(self):
        return self.__str__()


class FrameParser(STRING):
    """Frame structure class"""
    def __init__(self, length:int=None, _type:str=None, ID:int=None, flags:int=None, R_SID=None, R=None, SID=None, IP=("", "")):
        self.length = length
        self.type   = _type
        self.typeID = ID
        self.flags  = flags
        self.R_SID  = R_SID   #R标记 + SID
        self.R      = R
        self.SID    = SID
        self.data   = None
        self.IP     = IP

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
    def getIP(self):
        return self.IP
    
class HeaderParser(STRING):
    """Header frame structure class"""
    def __init__(self, frame:FrameParser=None, header:dict=None, priority=False, weight=None, e_streamdependency=None):
        self.frame  = frame
        self.header = header
        
        self.isPriority = priority
        self.weight     = weight
        self.esdp       = e_streamdependency  #E标记 + Stream Dependency
    
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
        """Uploaded file structure class"""
        self.filename = filename
        self.cachefile = cachefile
    def getFile(self):
        return self.cachefile
    def getName(self):
        return self.filename
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
    """Uploaded files structure class (a collection of UploadFileObject)"""
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
    def __repr__(self):
        return self.__str__()
    def get(self, k, d=None):
        return getattr(self, k, d)
    
class UploadDatasObject(UploadFilesObject):
    """Uploaded datas structure class(a collection of form information transmitted through multipart/form-data)"""
    pass


def encodeIncludeCode(code):
    code    = code.replace("from IgnoreVariable import *", "", 1)

    # from xxx import * # USING_PWS_INCLUDE RELATIVE_PATH ./dir/" (通过相对路径导入)
    imports = re.findall(r"from (.*?) import \*(.*?)# USING_PWS_INCLUDE RELATIVE_PATH \"(.*?)\"", code)
    for arg in imports:
        originCode = f"from {arg[0]} import *{arg[1]}# USING_PWS_INCLUDE RELATIVE_PATH \"{arg[2]}\""
        changeCode = f"include('{arg[2]}/{arg[0]}.py', VAR, useDirPath=True)"
        code = code.replace(originCode, changeCode, 1)

    # import xxx (as xxx) # USING_PWS_INCLUDE RELATIVE_PATH "./dir/" (通过相对路径导入)
    imports = re.findall(r"import (.*?)# USING_PWS_INCLUDE RELATIVE_PATH \"(.*?)\"", code)
    for arg in imports:
        originCode = f"import {arg[0]}# USING_PWS_INCLUDE RELATIVE_PATH \"{arg[1]}\""
        arg    = list(arg)
        arg[0] = arg[0].strip()
        asName = arg[0].split("as")
        if len(asName) > 1:
            arg[0] = asName[0].strip()
            asName = '"'+"as".join(asName[1:]).strip()+'"'
        else:
            asName = None
        changeCode = f"include('{arg[1]}/{arg[0]}.py', MODULE, asName={asName})"
        code = code.replace(originCode, changeCode, 1)

    

    # from xxx import * # USING_PWS_INCLUDE "./Website/dir/" (通过绝对路径导入)
    imports = re.findall(r"from (.*?) import \*(.*?)# USING_PWS_INCLUDE(.*?)\"(.*?)\"", code)
    for arg in imports:
        originCode = f"from {arg[0]} import *{arg[1]}# USING_PWS_INCLUDE{arg[2]}\"{arg[3]}\""
        changeCode = f"include('{arg[3]}/{arg[0]}.py', VAR, useDirPath=False)"
        code = code.replace(originCode, changeCode, 1)

    # from xxx import * # USING_PWS_INCLUDE (通过相对路径导入)
    imports = re.findall(r"from (.*?) import \*(.*?)# USING_PWS_INCLUDE", code)
    for moduleName in imports:
        originCode = f"from {moduleName[0]} import *{moduleName[1]}# USING_PWS_INCLUDE"
        changeCode = f"include('{moduleName[0]}.py', VAR)"
        code = code.replace(originCode, changeCode, 1)

    # import xxx # USING_PWS_INCLUDE "./Website/dir/" (通过相对路径导入)
    imports = re.findall(r"import (.*?)# USING_PWS_INCLUDE(.*?)\"(.*?)\"", code)
    for arg in imports:
        originCode = f"import {arg[0]}# USING_PWS_INCLUDE{arg[1]}\"{arg[2]}\""
        arg    = list(arg)
        arg[0] = arg[0].strip()
        asName = arg[0].split("as")
        if len(asName) > 1:
            arg[0] = asName[0].strip()
            asName = '"'+"as".join(asName[1:]).strip()+'"'
        else:
            asName = None
        changeCode = f"include('{arg[2]}/{arg[0]}.py', MODULE, asName={asName}, useDirPath=False)"
        code = code.replace(originCode, changeCode, 1)
    
    # import xxx # USING_PWS_INCLUDE (通过相对路径导入)
    imports = re.findall(r"import (.*?)# USING_PWS_INCLUDE", code)
    for arg in imports:
        moduleName = arg.strip()
        asName = moduleName.split("as")
        if len(asName) > 1:
            moduleName = asName[0].strip()
            asName = '"'+"as".join(asName[1:]).strip()+'"'
        else:
            asName = None
        originCode = f"import {arg}# USING_PWS_INCLUDE"
        changeCode = f"include('{moduleName}.py', MODULE, asName={asName})"
        code = code.replace(originCode, changeCode, 1)

    return code

def setLogFrs(frames:typing.List[FrameParser, ], self, Logger):
    """Record each frames"""
    for frame in frames:
        if isinstance(frame, str):
            Logger.error("String type frame!:", frame)
            continue
        if not frame.getType() == "Data":
            Logger.comp("-"*70)
            Logger.comp(" [{0: <3}] Recv Frame: | TYPE: {1: <13} | LEN: {2: <7} | flags: {3}".format(
                frame.getStreamID(),
                frame.getType(),
                frame.getLength(),
                frame.getFlags()
            ))

        ctx  = ''
        adds = ''

        if frame.getType() == 'Headers':
            Logger.info(f"      View Path:", frame.get(":path"))
        
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
        from Logger import setLog
        setLog(
           f"""[{frame.getStreamID()}] RECV_{frame.getType().upper()}_FRAME
               -->  stream_id: {frame.getStreamID()}
               -->  flags: {frame.getFlags()}
               -->  size: {frame.getLength()}{adds}
               -->  content:
                              {ctx}\n
""", "./logs/h2.log", 0)


g = {'getdata': {}, 'postdata': {}, 'rewritedata': {}, 'headers': {'path': '/', 'method': 'GET', 'host': 'localhost:5050', 'connection': 'keep-alive', 'cache-control': 'max-age=0', 'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="114", "Microsoft Edge";v="114"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"', 'upgrade-insecure-requests': '1', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.79', 'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7', 'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'navigate', 'sec-fetch-user': '?1', 'sec-fetch-dest': 'document', 'referer': 'http://localhost:5050/userprof.py', 'accept-encoding': 'gzip, deflate, br', 'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6', 'cookie': {'User_LOGIN': 'Himpqd4dbe1cce09b169659ec259fdc6b8eca'}, 'if-none-match': '3bd2e98dc37a02a74353d59b091a699ec1b005dc', 'content-length': '4640', 'content-type': 'multipart/form-data', 'boundary': '----WebKitFormBoundary4lRAOPD5C4705JCK', 'x-requested-with': 'XMLHttpRequest', 'origin': 'http://localhost:5050'}, 'path': '/', 'language': '', 'cookie': {'User_LOGIN': 'Himpqd4dbe1cce09b169659ec259fdc6b8eca'}, '_originPath': '/'}
#prettyPrint(g)
