import urllib.parse as uparse
import CacheModule as cache

from server_config import *
from Logger import Logger
from threading import Thread
from functions import stop_thread
#from memory_profiler import *
#prof = profile
import time

def profile(func):
    def x(*arg, **args):
        #l = time.time()
        o = func(*arg, **args)
        #p = time.time()
        #with open("logs/log.txt", 'a') as f:
        #    f.write(time.ctime()+"-->:函数"+func.__name__+" 耗时:"+str(p-l)+";返回值:"+str(o)+"\n")
        return o
    return x
prof = profile
Logger = Logger()
abc = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
ott = '1234567890'
ope = '-=.'
import os, mmap

def toInt(integer):
    try:
        integer = integer.replace("q=", '')
        return float(integer)
    except:
        return 0

@prof
def updata_exp(connf, bd, conn):
    az = {}
    arr = {}
    caf = cache.cachefile()

    while not caf.endswith(b"--"+bd.encode()+b"--\r\n"):
        if getattr(conn, "_closed"):
            return ""
        d = connf.readline()
        if d == b'':
            break
        caf.write(d)
    connf.close()
    data = exp_updata(caf, bd)
    return data

@prof
def exp_updata(file, bd):
    file.save()
    file.seek(0)

    files = {}
    datas = {}

    bd = b"--"+bd.encode()
    stop = False
    while not stop:
        content = file.readline()
        header = {}
        if content == bd+b"--\r\n":
            break
        if content == bd+b'\r\n':

            while 1:
                ctx = file.readline().strip()
                if ctx == b'\r\n' or ctx == b'': #无信息
                    break
                ctx = list(exp_headers(ctx.decode()))
                ctx[0] = ctx[0].lower()
                header[ctx[0]] = ctx[1]
                if ctx[0].lower() == 'content-disposition':
                    i = ctx[1].split(";")
                    g = {}
                    for x in i:
                        if '=' in x:
                            o = x.split("=")
                            u = (b'"', b"'", "'", '"')

                            if o[1].strip()[0] in u and o[1].strip()[-1] in u:
                                o[1] = o[1].strip()[1:-1]

                            g[o[0].strip()] = o[1]
                        else:
                            g['type'] = x
                    header[ctx[0]] = g

            if header.get("content-type"):
                cf = cache.cachefile()
                files[header.get('content-disposition')['name']] = {'cachefile':cf,
                                                                    'filename':header.get("content-disposition")['name']}

                while True:
                    d = file.readline()
                    if d[len(d)-len(bd)-2:] == bd+b'\r\n':
                        file.seek(-len(bd)-2, 1)
                        break
                    elif d[len(d)-len(bd)-4:] == bd+b'--\r\n':
                        file.seek(-len(bd)-4, 1)
                        stop = True
                        break
                    
                    cf.write(d)
            else:
                ctx = b''
                while 1:
                    dx = file.readline()
                    d = dx
                    if d[len(d)-len(bd)-2:] == bd+b'\r\n':
                        file.seek(-len(bd)-2, 1)
                        break
                    elif d[len(d)-len(bd)-4:] == bd+b'--\r\n':
                        file.seek(-len(bd)-4, 1)
                        stop = True
                        break
                    elif dx == b'':
                        break
                    ctx += d
                    
                datas[header.get('content-disposition')['name']] = ctx.decode()
        else:
            pass
    return files, datas            

@profile
def QZ(da):
    arr = []
    z = ['']

    n = 0
    while len(da) > n:
        v = da[n]
        if v in abc or v in ott or v in ope:
            z[-1] += v
        if v == ';' or v == ',' or v == ':':
            z.append('')
        n += 1
    return z

@profile
def FZ(da):
    da = da[1:]
    lang = []
    for i in da:
        if 'q=' in i:
            g = lang.copy()[::-1]
            f = []

            n = -1
            for i2 in g:
                n += 1
                if not type(i2) == list:
                    f.append(i2)
                else:
                    break
            f.append(toInt(i.replace('q=','')))
            if len(f) < 3:
                f.insert(1, '')
            lang.append(f)
        else:
            lang.append(i)
    p = []
    for i in lang:
        if type(i) == list:
            p.append(i)
    return p

@profile
def PX(da):
    leng = len(da)
    while leng > 0:
        for i in range(leng - 1):
            if da[i][2] < da[i+1][2]:
                da[i], da[i+1] = da[i+1], da[i]
        leng -= 1
    return da

@prof
def exp(connf,conn):
        content = b''
        headers = {
            "getdata":{},
            "postdata":{},
            "rewritedata":{},
            "headers": {},
            "path":"",
            "language":"",
            "cookie":{}
        }

        a = connf 

        @profile
        def xs():
            nonlocal content, headers, a
            try:
                while not content[-4:] == b'\r\n\r\n':
                    if getattr(conn, "_closed"):
                        return ("", "") #Should be raise error
                    try:
                        ctx = a.readline()
                    except:
                        continue

                    if ctx == b'\r\n' or ctx == b'':#无信息不调用
                        break
                    
                    xx = exp_headers(ctx.decode())
                    if len(xx) == 3:
                        headers[xx[0][0]] = xx[0][1]
                        headers[xx[1][0]] = xx[1][1]
                    else:
                        headers[xx[0]] = xx[1]
                    if xx == b'':
                        break

                    content += ctx
            except Exception as e:
                print("An error in exp http data:",e)
                content = b''
            
                
        xs()

        if headers.get("content-type", "") == 'application/x-www-form-urlencoded':
            if headers.get("method", "") == "POST":
                if headers.get("content-length", ""):
                    length = headers.get("content-length")

                    headers['postdata'] = decodePOST(a.read(length).decode())
                else:
                    headers['postdata'] = decodePOST(a.readline().decode())
        
        if headers.get("path",""):
            headers['path'], headers['getdata'] = decodeGET(headers.get("path"))
        return content, headers

@profile
def decodePOST(line):
    if line.strip() == '':
        return {}
    arr = {}
    lines = line.split("&")
    for i in lines:
        key = i.split("=")[0]
        val = i.split("=")[1]
        val = val.replace("+", " ")

        arr[key] = uparse.unquote(val)
    return arr

@profile
def decodeGET(line):
    if not "?" in line:
        return line, {}
    get = "?".join(line.split("?")[1:])
    path = line.split("?")[0]
    arr = {}

    get = get.split("&")
    n = -1
    for i in get:
        if '=' in i:
            kv = i.split("=")
            key = kv[0]
            val = uparse.unquote("=".join(kv[1:]))
            arr[key] = val
        else:
            n += 1
            arr[n] = uparse.unquote(i)
    return path, arr
            
@prof
def exp_headers(i):
    if i == '':
        return ['', '']
    x = i.split(":")
    
    if i[0:3].upper() == 'GET' or i[0:4].upper() == 'POST':
        method = "GET" if i[0:3].upper() == 'GET' else "POST"

        o = i.split(' ')
        return ["path", uparse.unquote(o[1])],['method', method],1

    elif i[0:9].upper() == 'USER-AGENT':
        agent = ':'.join(i.split(':')[1:]).strip()
        return ['user_agent', agent]
    elif i[0:5].upper() == 'RANGE':
        rangeee = ':'.join(i.split(':')[1:]).strip()
        return ['range', rangeee]
    elif i[0:4].upper() == 'HOST':
        host = ':'.join(i.split(":")[1:]).strip()
        return ['host', host]
    elif i[0:10].upper() == 'CONNECTION':
        conn = ':'.join(i.split(":")[1:]).strip()
        return ['connection', conn]
    elif i[0:14].upper() == 'CONTENT-LENGTH':
        return ['content-length', int(i.split(":")[1].strip())]
    
    #elif i[0:15].upper() == 'ACCEPT-LANGUAGE':
    #    lang = ':'.join(i.split(":")[1:]).strip()
    #    qz = FZ(QZ(lang))
    #    return ['language', qz]
    elif i[0:6].upper() == 'COOKIE':
        cookies = ':'.join(i.split(":")[1:]).strip()
        cookies = cookies.split(";")
        kv = {}
            
        for i in cookies:
                if '=' in i:
                    g = i.split("=")
                    key = g[0]
                    val = '='.join(g[1:])
                    kv[key] = val
        return ['cookie', kv]
    elif i[0:12].upper() == 'CONTENT-TYPE':
        val = ':'.join(i.split(":")[1:])
        if '=' in val:
            x = val.split("=")
            return [['content-type',x[0].replace("boundary","").replace(";","").strip()], ['boundary', x[1].strip()],1]
        return 'content-type', val.strip()
    else:
        if ":" in i:
            return [i.split(":")[0].strip(),':'.join(i.split(":")[1:]).strip()]
        else:
            return ['', '']
