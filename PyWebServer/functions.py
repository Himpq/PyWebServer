import inspect, ctypes
from io import *
import gzip
import hashlib
import time, os

HashCacheSize = 4096*1024*2
LOG = False
NOT_RECORDED_FUNCTIONS = ['parsingHeaderLine']
PluginManager = None

def Functions_SetPluginManager(PluginManager):
    globals()["PluginManager"] = PluginManager

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
        #PluginManager.FindWay(func.__name__, arg, args)

        if not func.__name__ in NOT_RECORDED_FUNCTIONS and LOG:
            l = time.time()
            o = func(*arg, **args)
            p = time.time()
            with open("logs/log.txt", 'a') as f:
                f.write(time.ctime()+"-->:函数"+func.__name__+" 耗时:"+str(p-l)+";返回值:"+str(o)+"\n")
        else:
            o = func(*arg, **args)
        return o
    return x
def setLog(content, file='./logs/view.log', showTime=True):
    with open(file, 'a', encoding='utf-8') as f:
        x = "["+time.ctime()+"] "
        if not showTime:
            x = ''
        f.write(x+content+"\n")
#报错查询具体位置
def tryGetErrorDetail(s, path):
    with open(path, 'r', encoding='UTF-8') as f:
        try:
            x=s.split("line")[-1].split(",")[0]
            x = int(x.strip())
        except:
            return s
        for i in range(x):
            ctx = f.readline()
            if i+1 == x:
                return s+"<br><br>FileName:%s<br><br>%s: %s"%(path, x, ctx)
        return s

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
    jsons1 = {}
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
def getRangeBit(b, from_, to, byteorder):
    x = ''
    for i in b:
        for n in (list(range(8)) if byteorder == 'little' else list(range(8))[::-1]):
            x += str(getBit(i, n, 'little'))
    return x[from_: to]

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
