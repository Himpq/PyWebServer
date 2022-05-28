import urllib.parse as uparse
import CacheModule as cache

from server_config import *
from Logger import Logger
#from threading import Thread
#from functions import stop_thread
#from memory_profiler import *
#prof = profile
import time
import os
import threading
from functions import *

def profile(func):
    def x(*arg, **args):
        l = time.time()
        o = func(*arg, **args)
        p = time.time()
        with open("logs/log.txt", 'a') as f:
            f.write(time.ctime()+"-->:函数"+func.__name__+" 耗时:"+str(p-l)+";返回值:"+str(o)+"\n")
        return o
    return x
prof = profile


Logger = Logger()
abc = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
ott = '1234567890'
ope = '-=.'
quot = (b'"', b"'", "'", '"')

def toInt(integer):
    "将Accept-Language中的q值转换为具体数字"
    try:
        integer = integer.replace("q=", '')
        return float(integer)
    except:
        return 0

@prof
def parsingUpdateFile(connf, bd, conn):
    """该函数用于解析正在上传的文件(通过HTTPSOCKET连接)。
    connf: Connecting socket(makefile); bd=boundary; conn: Connecting socket"""

    caf = cache.cachefile()

    while not caf.endswith(b"--"+bd.encode()+b"--\r\n"):
        if getattr(conn, "_closed"):
            return ""
        d = connf.readline()
        if d == b'':
            break
        caf.write(d)
    connf.close()
    data = parsingCacheFile(caf, bd)
    return data

@prof
def parsingCacheFile(file, bd):
    """该函数用于解析已被储存到本地的用户上传文件。
    file: Cache uploaded files; bd=boundary: HTTP Uploaded Boundary"""

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
                if ctx == b'\r\n' or ctx == b'': #无信息/读取完毕自动停止解析
                    break

                ctx            = list(parsingHeaderLine(ctx.decode()))
                ctx[0]         = ctx[0].lower()
                header[ctx[0]] = ctx[1]

                if ctx[0].lower() == 'content-disposition':
                    #进行解析form-data表单中的 Content-Disposition 信息
                    contDisposition = ctx[1].split(";")
                    dispositionData = {}
                    for value in contDisposition:
                        if '=' in value:
                            keyVal = value.split("=")
                            if keyVal[1].strip()[0] in quot and keyVal[1].strip()[-1] in quot:
                                keyVal[1] = keyVal[1].strip()[1:-1]

                            dispositionData[keyVal[0].strip()] = keyVal[1]
                        else:
                            dispositionData['type'] = value
                    header[ctx[0]] = dispositionData

            if header.get("content-type"):
                cf = cache.cachefile()
                files[header.get('content-disposition')['name']] = {
                                                                    'cachefile':cf,
                                                                    'filename':header.get("content-disposition").get("name", "noNameFile")
                                                                   }

                #读取本地文件在 Boundary 之前的部分以此保存文件
                while True:
                    line = file.readline()
                    if line[len(line)-len(bd)-2:] == bd+b'\r\n':
                        file.seek(-len(bd)-2, 1)
                        break
                    elif line[len(line)-len(bd)-4:] == bd+b'--\r\n':
                        file.seek(-len(bd)-4, 1)
                        stop = True
                        break
                    
                    cf.write(line)
            else:
                ctx = b''
                while 1:
                    #读取本地文件在 Boundary 之前的部分以此解析表单内容
                    line = file.readline()

                    if line[len(line)-len(bd)-2:] == bd+b'\r\n':
                        file.seek(-len(bd)-2, 1)
                        break
                    elif line[len(line)-len(bd)-4:] == bd+b'--\r\n':
                        file.seek(-len(bd)-4, 1)
                        stop = True
                        break
                    elif line == b'':
                        break
                    ctx += line
                    
                datas[header.get('content-disposition')['name']] = ctx.decode()

    return files, datas

@prof
def parsingHeader(connf,conn):
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

        @profile
        def getContent():
            #获取HTTP头原始数据
            nonlocal content, headers, connf
            try:
                while not content[-4:] == b'\r\n\r\n':
                    if getattr(conn, "_closed"):
                        return ("", "")               #此时socket被关闭，正常来算应该报个错
                    try:
                        ctx = connf.readline()
                    except:
                        continue

                    if ctx == b'\r\n' or ctx == b'':  #无信息退出，以免导致高cpu占用(长连接)
                        break
                    
                    parsedLine = parsingHeaderLine(ctx.decode())
                    
                    if len(parsedLine) == 3:
                        headers[parsedLine[0][0]] = parsedLine[0][1]
                        headers[parsedLine[1][0]] = parsedLine[1][1]
                    else:
                        headers[parsedLine[0]] = parsedLine[1]
                    if parsedLine == b'':
                        break

                    content += ctx
            except Exception as e:
                print("Error in parsing header:", e)
                content = b''
            
        #防止读取HTTP请求头超时
        getctxThread = threading.Thread(target=getContent)
        getctxThread.start()
        getctxThread.join(config['timeout'])
        if getctxThread.is_alive():
            stop_thread(getctxThread)
            return content, headers


        if headers.get("content-type", "") == 'application/x-www-form-urlencoded':
            if headers.get("method", "") == "POST":
                if headers.get("content-length", ""):
                    #读取POST信息，目前没有做内存溢出的保护
                    length = headers.get("content-length")

                    headers['postdata'] = decodePOST(connf.read(length).decode())
                else:
                    headers['postdata'] = decodePOST(connf.readline().decode())
        
        if headers.get("path",""):
            #解析GET数据并存储于getdata中
            headers['path'], headers['getdata'] = decodeGET(headers.get("path"))
        return content, headers

@profile
def decodePOST(line):
    "解析POST数据"
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
    "解析GET数据"
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
def parsingHeaderLine(i):
    "用于解析一行HTTP Header。 i: string(http header)"
    if i == '':
        return ['', '']
    x = i.split(":")
    
    if i[0:3].upper() == 'GET' or i[0:4].upper() == 'POST':
        method = "GET" if i[0:3].upper() == 'GET' else "POST"

        o = i.split(' ')
        return ["path", uparse.unquote(o[1])],['method', method],1

    elif i[0:9].upper() == 'USER-AGENT':
        agent = ':'.join(i.split(':')[1:]).strip()
        return ['user-agent', agent]
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
                    key = g[0].strip()
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
            return [i.split(":")[0].strip().lower(),':'.join(i.split(":")[1:]).strip()]
        else:
            return ['', '']
