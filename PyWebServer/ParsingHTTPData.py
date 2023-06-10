import socket
import urllib.parse as uparse
import CacheModule as cache

from server_config import *
from Logger import Logger

import time
import os
import threading
from functions import *
import ssl as sslm
import typing

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

@profile
def parsingUpdateFile(connf:socket.socket, boundary:str, conn:socket.socket, data:str):
    """该函数用于解析正在上传的文件(通过HTTPSOCKET连接)。"""

    caf = cache.cachefile()

    while not caf.endswith(b"--"+boundary.encode()+b"--\r\n"):
        d = connf.readline()
        if d == b'':
            break
        caf.write(d)
    
    #connf.close()

    data = parsingCacheFile(caf, boundary)
    return data

@profile
def parsingCacheFile(file:typing.Union[cm.cachefile, cm.h2cachefile], boundary:str):
    """该函数用于解析已被储存到本地的用户上传文件。"""
    
    file.save()
    file.seek(0)

    files = {}
    datas = {}

    boundary = b"--"+boundary.encode()
    stop = False
    while not stop:
        content = file.readline()
        header = {}
        if content == b'':
            break
        
        if content == boundary+b"--\r\n":
            break
        
        if content == boundary+b'\r\n':
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
                    if line[len(line)-len(boundary)-2:] == boundary+b'\r\n':
                        file.seek(-len(boundary)-2, 1)
                        break
                    elif line[len(line)-len(boundary)-4:] == boundary+b'--\r\n':
                        file.seek(-len(boundary)-4, 1)
                        stop = True
                        break
                    
                    cf.write(line)
            else:
                ctx = b''
                while 1:
                    #读取本地文件在 Boundary 之前的部分以此解析表单内容
                    line = file.readline()

                    if line[len(line)-len(boundary)-2:] == boundary+b'\r\n':
                        file.seek(-len(boundary)-2, 1)
                        break
                    elif line[len(line)-len(boundary)-4:] == boundary+b'--\r\n':
                        file.seek(-len(boundary)-4, 1)
                        stop = True
                        break
                    elif line == b'':
                        break
                    ctx += line
                    
                datas[header.get('content-disposition')['name']] = ctx.strip().decode()
    
    cfiles = {}
    for i in files:
        cfiles[i] = UploadFileObject(files[i]['filename'], files[i]['cachefile'])
    return UploadFilesObject(cfiles), UploadDatasObject(datas)

HEADER_MODULE = {
            "getdata":{},
            "postdata":{},
            "rewritedata":{},
            "headers": {},
            "path":"",
            "language":"",
            "cookie":{}
}

@profile
def parsingHeaderByString(content, noMethod=False):
    """从字符串解析Header信息"""
    headers = HEADER_MODULE.copy()
    for line in content.split("\r\n"):
        #print("line", line)
        parsedLine = parsingHeaderLine(line, noMethod)
        #print(parsedLine)

        if len(parsedLine) == 3:
            if parsedLine[0][0] == "path":
                headers['path'] = parsedLine[0][1]
                headers['headers'][parsedLine[0][0]] = parsedLine[0][1]
                headers['headers'][parsedLine[1][0]] = parsedLine[1][1]
        else:
            headers['headers'][parsedLine[0]] = parsedLine[1]
    return headers

@profile
def parsingHeader(connf:socket.SocketIO, conn:socket.socket):
    """从socket链接解析Header信息"""
    content = b''
    headers = HEADER_MODULE.copy()

    @profile
    def getContent():
        #获取HTTP头原始数据
        nonlocal content, headers, connf
        try:
            while 1:
                if content[-4:] == b'\r\n\r\n':
                    print("QUIT BECAUSE", content)
                    print("NEXT READ:", connf.readline())
                    break
                    
                ctx = b''
                try:
                    ctx = connf.readline()
                except sslm.SSLError as e:
                    if "CERTIFICATE_UNKNOWN" in str(e):
                        Logger.warn("证书错误:", str(e).split("]")[1])
                    else:
                        Logger.error("证书严重错误:", e)
                        break
                except Exception as e:
                    Logger.error("QUIT:", e)
                    break #-> continue   读取失败，退出读取

                if ctx == b'\r\n' or ctx.strip() == b'':  #无信息退出，以免导致高cpu占用(长连接)
                    #print("QUIT BECAUSE EMPTY CONTENT-->", ctx)
                    break
                
                parsedLine = parsingHeaderLine(ctx.decode())

                    
                    
                if len(parsedLine) == 3:
                    if parsedLine[0][0] == "path":
                        headers['path'] = parsedLine[0][1]
                    headers['headers'][parsedLine[0][0]] = parsedLine[0][1]
                    headers['headers'][parsedLine[1][0]] = parsedLine[1][1]
                else:
                    headers['headers'][parsedLine[0]] = parsedLine[1]
                if parsedLine == b'':
                    break

                content += ctx
        except Exception as e:
            print("Error in parsing header:", e)
            content = b''
            
    #防止读取HTTP请求头超时
    #getctxThread = threading.Thread(target=getContent)
    #getctxThread.start()
    #getctxThread.join(config['timeout'])
    #if getctxThread.is_alive():
    #    stop_thread(getctxThread)
    #    return content, headers
    getContent()

    if headers['headers'].get("content-type", "") == 'application/x-www-form-urlencoded':
        if headers['headers'].get("method", "") == "POST":
            if headers['headers'].get("content-length", ""):
                #读取POST信息，目前没有做内存溢出的保护
                length = int(headers['headers'].get("content-length"))

                headers['postdata'] = decodePOST(connf.read(length).decode())
            else:
                headers['postdata'] = decodePOST(connf.readline().decode())
        
    if headers['headers'].get("path",""):
        #解析GET数据并存储于getdata中
        headers['_originPath'] = headers['path']
        headers['path'], headers['getdata'] = decodeGET(headers.get("path"))
        
    return content, headers

def decodeContentType(ctx):
    "解析 Content-Type 数据"
    if ctx == None:
        return {"type":None, "boundary":None}

    ctx = ctx.split(";")
    tp, bd = None, None
    for i in range(len(ctx)):
        if i == 0:
            tp = ctx[i]
        elif i == 1:
            bd = ctx[i]
    if bd and "=" in bd:
        bd = bd.split("=")[1]
    return {"type":tp, "boundary":bd}

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
    
@profile            
def decodeCookie(ctx):
    "解析 Cookie 数据"
    cookies = ctx.split(";")
    kv = {}

    for i in cookies:
            if '=' in i:
                g = i.split("=")
                key = g[0].strip()
                val = '='.join(g[1:])
                kv[key] = val
    return kv

@profile
def parsingHeaderLine(line, noMethod=False):
    "用于解析一行HTTP Header。 i: string(http header), noMethod: bool(因wrap_socket丢失的GET/POST信息)"
    if line == '':
        return ['', '']
    x = line.split(":")
    
    if line[0:3].upper() == 'GET' or line[0:4].upper() == 'POST':
        method = "GET" if line[0:3].upper() == 'GET' else "POST"

        o = line.split(' ')
        return ["path", uparse.unquote(o[1])],['method', method],1
    
    elif line[0:6].upper() == 'COOKIE':
        cookies = ':'.join(line.split(":")[1:]).strip()
        cookies = cookies.split(";")
        kv = {}
            
        for line in cookies:
                if '=' in line:
                    g = line.split("=")
                    key = g[0].strip()
                    val = '='.join(g[1:])
                    kv[key] = val
        return ['cookie', kv]
    
    elif line[0:12].upper() == 'CONTENT-TYPE':
        val = ':'.join(line.split(":")[1:])
        if '=' in val:
            x = val.split("=")
            return [['content-type',x[0].replace("boundary","").replace(";","").strip()], ['boundary', x[1].strip()],1]
        return 'content-type', val.strip()
    else:
        if ":" in line:
            return [line.split(":")[0].strip().lower(),':'.join(line.split(":")[1:]).strip()]
        else:
            if noMethod:
                if " " in line and "HTTP/1.1" in line:
                    ret = line.split(' ')
                    path = ret[ret.index("HTTP/1.1")-1]
                    return ['path', uparse.unquote(path)], ['method', None], 1
            return ['', '']
