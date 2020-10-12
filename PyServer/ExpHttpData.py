"""
    PyServer
    Himpq|2020-10-12
"""

import urllib.parse as uparse
import urllib.parse
import CacheModule as cache

from server_config import *

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

#def tocls(cn):
def savefile(file, search: bytes, save):
    b = 0
    t = 0

    #file.seek(0)
    r = file.read(1024)
    while not r == b'':
        if search in r:
            save.write(r.split(search)[0])
            l = len(r.split(search)[1])
            file.seek(-l, 1)
            save.save()
            break
        else:
            save.write(r)
        r = file.read(1024)
    ###########BUG: 当分割线处于1024缓存的分割末端，不会被监测到
from memory_profiler import profile
@profile
def savefile(file, search, save) -> None:
    r = file.readline()
    while 1:
        #print(search, r)
        if search in r:
            break
        save.write(r)
        r = file.readline()
    del r
def updata_exp(conn, bd):
    az = {}
    arr = {}
    caf = cache.cachefile()

    while not caf.endswith(b"--"+bd.encode()+b"--\r\n"):
        caf.write(conn.recv(1024*4))


    data = exp_updata(caf, bd)
    #print(">>>>>>", data)
    return data

def exp_updata(file, bd):
    file.save()
    file.seek(0)

    files = {}
    datas = {}

    if not file.read(len("--"+bd)) == b'--'+bd.encode():
        return {}

    stop = False
    while not stop:
        content = ''
        filedata = {}
        while not content.endswith('\r\n\r\n'):
            content += file.read(1).decode()

        filedata = exp_http(content)
        if 'content-disposition' in filedata:
            cd = filedata['content-disposition']
            if 'filename' in cd and 'name' in cd:
                cf = cache.cachefile()
                files[cd['name']] = {}
                files[cd['name']]['cachefile'] = cf

                #while not cf.endswith(b"--"+bd.encode()):
                #    cf.write(file.read(1))
                #cf.delete(len(b'--'+bd.encode())+4)
                savefile(file, b'--'+bd.encode(), cf)
                file.seek(-4, 1)
                cf.seek(-2, 1)
                if cf.read() == b'\r\n':
                    cf.delete(2)
                if file.read(2) == b'--':
                    break
                else:
                    file.file.seek(-2, 1)
            else:
                x = ''
                #while not x.endswith('--'+bd):
                #    x += file.read(1).decode()
                #datas[cd['name']] = x[0:len(x)-len('\r\n--'+bd)]
                while 1:
                    r = file.readline()
                    if bd.encode() in r:
                        break
                    x += r.decode()
                datas[cd['name']] = x
                file.seek(-4, 1)

                if x[-2:] == '\r\n':
                    datas[cd['name']] = x[0:-2]
                if file.read(2) == b'--':
                    break
                else:
                    file.file.seek(-2, 1)
        else:
            break

    return files, datas      

def exp_http(ctx):
    ctx = ctx.split("\r\n")
    x = {}
    n = 0
    for i in ctx:
        if ":" in i:
            kvs = i.split(":")
            key, val = kvs[0].strip(), ':'.join(kvs[1:]).strip()
            if ';' in val:
                gval = val.split(";")
                n2 = 0
                arr = {}
                for ix in gval:
                    kvas = ix.split("=")
                    if len(kvas) == 1:
                        val2 = ix.strip()
                        key2 = n2
                        n2 += 1
                    else:
                        key2, val2 = kvas[0].strip(), "=".join(kvas[1:]).strip()
                    arr[key2] = val2 if not val2[0] in ("'",'"') and not val2[-1] in ('"', "'") else val2[1:-1]
                val = arr
                x[key.lower()] = val
            else:
                x[key.lower()] = val
        else:
            x[n] = i.strip()
            n += 1
    return x
    
def updata_exp2(conn, bd):
    zz = {}
    arr = {}
    content = ''
    while not content.endswith('\r\n\r\n'):
        x = conn.recv(1)
        content += x.decode()

    bd = '--'+bd
    sp = content.replace(bd, '')
    sp = content.split("\r\n")
    for i in sp:
        i = i.strip()
        if i == '':
            continue
        if i[0:19].lower() == 'content-disposition':
            val = i[19:].replace(":","",1).lstrip()

            if ';' in val:
                sp2 = val.split(";")

                for ix in sp2:
                    if "=" in ix:
                        k = ix.split("=")
                        ke, va = k[0].strip(), '='.join(k[1:]).strip()
                        arr[ke]=va
                    else:
                        arr['content-disposition']=ix

        elif i[0:12].lower() == 'content-type':
            arr['type'] = i[12:].replace(":","",1).strip()

    cafile = cache.cachefile()
    while not cafile.endswith(bd.encode()):
        cafile.write(conn.recv(1))
    
    cafile.delete(len(bd))
    arr['file'] = cafile
    zz[arr['name']] = arr
    return zz
    
def updata_exp2(conn, boundary):
    arr = {}
    o = ''
    while not o.endswith('\r\n\r\n'):
        x =conn.recv(1)
        #print(x, end='')
        o += x.decode()

    l = o.split(boundary)
    for i in l:
        if ':' in i:
            ars = i.split(":")
            ars[0] = ars[0].strip()
            arr[ars[0]] = ':'.join(ars[1:]).strip()
            if ';' in arr[ars[0]]:
                ks = arr[ars[0]].split(";")
                x = {}
                n = 0
                for i in ks:
                    o = i.split("=")
                    if len(o) == 1:
                        x[n] = o
                        n += 1
                    else:
                        o[0] = o[0].strip()
                        x[o[0]] = '='.join(o[1:]).strip()
                arr[ars[0]] = x
    return arr

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

def PX(da):
    leng = len(da)
    while leng > 0:
        for i in range(leng - 1):
            if da[i][2] < da[i+1][2]:
                da[i], da[i+1] = da[i+1], da[i]
        leng -= 1
    return da

def exp2(conn):
    lx = 0
    content = ''
    '''file = conn.makefile(mode='rb')
    j = 0
    while not j == 2:
        r = file.readline()
        if r.strip() == b'':
            j += 1
        else:
            content += r.decode()'''
    #content = conn.recv(1024).decode()
            
    while not content.endswith("\r\n\r\n"):
        content += conn.recv(1).decode()
    #print(content)
    return content
    

def exp(data2):
    data2 = data2.encode()
    data = data2.decode()
    data = data.split('\r\n')
    arr = {
        'getdata':{},
        'postdata':{},
        'rewritedata':{},
        'path': '',
        'language': "",
        'cookie':{}
    }
    n = -1
    for i in data:
        n += 1
        upper = '' if n == 0 else data[n]
        if i == '' or len(i) < 4:
            continue

        if i[0:3].upper() == 'GET' or i[0:4].upper() == 'POST':
            arr['method'] = "GET" if i[0:3].upper() == 'GET' else "POST"

            o = i.split(' ')
            arr['path'] = urllib.parse.unquote(o[1])
            arr['http_version'] = o[2]
        elif i[0:9].upper() == 'USER-AGENT':
            agent = ':'.join(i.split(':')[1:])
            arr['user_agent'] = agent
        elif i[0:4].upper() == 'HOST':
            host = ':'.join(i.split(":")[1:]).strip()
            arr['host'] = host
        elif i[0:10].upper() == 'CONNECTION':
            conn = ':'.join(i.split(":")[1:]).strip()
            arr['connection'] = conn
        elif i[0:15].upper() == 'ACCEPT-LANGUAGE':
            lang = ':'.join(i.split(":")[1:]).strip()
            qz = FZ(QZ(lang))
            arr['language'] = PX(qz)
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
            arr['cookie'] = kv
        elif i[0:19].upper() == "CONTENT-DISPOSITION":
            v = i[0:19].replace(":", "", 1)
            v = v.split(";")
            arr['ct_disposition'] = {}
            
            for i in v[1:]:
                if len(i.split("=")) == 1:
                    arr['ct_disposition']['type'] = i
                else:
                    key = i.split('=')
                    val = "=".join(key[1:]).strip()
                    key = key[0].strip()
                    arr['ct_disposition'][key] = val
        elif i[0:12].upper() == 'CONTENT-TYPE':
            k = i[12:].replace(":","",1).strip()
            k = k.split(";")
            for ix in k:
                if len(ix.split("=")) == 1:
                    arr['content_type'] = ix
                else:
                    key = ix.split("=")
                    val = "=".join(key[1:]).strip()
                    key = key[0].lstrip()
                    arr[key] = val

    if 'method' in arr and arr['method'] == 'POST':
        pt = data2.decode().split("\r\n\r\n")
        if len(pt) >= 2:
            y = pt[len(pt)-1]
            x = y.split("&")
            psdata = {}

            for i in x:
                kv = i.split("=")

                #value解码
                key = kv[0]
                if config["post-urldecode-encoding"] == False:
                    val = '='.join(kv[1:])
                    val = val.replace("+", " ")
                else:
                    val = uparse.unquote('='.join(kv[1:]), encoding=config["post-urldecode-encoding"])

                psdata[key] = val
            arr['postdata'] = psdata

    if 'path' in arr and '?' in arr['path']:
        get = "?".join(arr['path'].split("?")[1:])
        arr['path'] = arr['path'].split("?")[0]

        get = get.split("&")
        ar = {}
        n = -1
        for i in get:
            if '=' in i:
                kv = i.split('=')
                key = kv[0]
                val = uparse.unquote(uparse.unquote('='.join(kv[1:]), encoding=config["post-urldecode-encoding"]), encoding=config["post-urldecode-encoding"])

                ar[key] = val
            else:
                n += 1
                ar[n] = i
        arr['getdata'] = ar
    return arr
