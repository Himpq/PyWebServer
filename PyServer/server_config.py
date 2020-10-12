import wmi
import pythoncom
import urllib.parse as uparse
import time
from threading import Thread
from http_returntype import *

#Status:
SAFEGUARD = 0 #维护
NORMAL = 1    #正常

ServerPath = 'A:/PyServer/Website'
InstallPath = "A:/PyServer/"

config = {
    "language-wrong-error"   : False,                                    #当 Accept-Language 请求的语言不在列表中返回 406 错误
    "ranges-download"        : True,                                    #断点续传，多用于多线程下载
    "default-page"           : ["index.html", "index.htm", "index.py"], #请求目录为"/"或"某文件夹/"时的默认返回页面
    "python"                 : True,                                    #开启Python支持（开启此才可查看py页面）
    "raise-error"            : True,                                    #当py页面出错时报错(关闭则返回503)
    "post-urldecode-encoding": "utf-8",                                 #解码POST时的固定编码，若有中文请替换为gb18030,无则替换为utf-8,不做修改替换为False

    "rewrite"                : { #伪静态
        "^/iii$" : {
            "to": ServerPath+"/xxx.py",
        }
        ,"^/forum-([0-9]+)-([0-9]+)-([0-9A-Za-z]+)\.html$":{
            "to": ServerPath+"/xxx.py",
            "get": "a=[0]&b=[1]&c=[2]"
        }
        ,"^/www$":{
            "to": ServerPath+"/wblog/index.py",
        }
    },

    "timeout": 30,                #(s) 超时未响应自动断开连接
    "sameip-request-count": 5,    #同一个ip在1秒内最多访问次数
    "clean-threadtime": 10,       #清理垃圾线程（需扫描线程池，可能占用较大资源）的时间间隔
    "reload_information_time": 5, #刷新服务器信息时间

    "server_status": NORMAL,             #服务器状态
    "use_pyfdb": True
}

support_languages = [
    "zh-cn",
    "zh",

    "en-us",
    "en"
]

black_list = [] #IP黑名单

http_errorcodes = {
    "503": ["Server Unavailable", "Server overload or maintenance in progress. Please wait for administrator to maintain or visit later."],
    "404": ["Not Found", "Page is not found."],
    "406": ['Language Error', 'The language is not supported by the server.'],

    'safeguard': ['Server Safeuard', "The server is being maintained."],
}
    

ERRPage = "HTTP/1.1 200 Ok!\r\nContent-Type: text/html\r\n\r\n<html><center><h1>%s %s</h1><h4>%s</h4><br><br><br><br><br><p>Power By PyServer</p></html>"
ERRPage_ = "<html><center><h1>%s %s</h1><h4>%s</h4><br><br><br><br><br><p>Power By PyServer</p></html>"
SaveMemory = 1024*1024*512 #预留内存(按照本机内存设定， 越低允许的访问数越多， 但可能会造成内存溢出)
server_memory = 0          #服务器当前空余内存（声明，请勿修改）

def isSupportLang(langs):
    for i in langs:
        if not i[0] in support_languages and not i[1] in support_languages:
            continue
        else:
            return True
    return False
def FileType(path):
    for i in return_filetype:
        v = return_filetype[i]
        if i == 'default':
            continue
        
        for i2 in v:
            if path[-len(i2)-1:].lower() == '.'+i2:
                return i.replace('.', '/', 1)

    return return_filetype['default'].replace('.', '/')
def ERRCODE(code, l=False):
    if not code in http_errorcodes:
        return b''
    if l:
        return (ERRPage % (code, http_errorcodes[code][0], http_errorcodes[code][1])).encode()
    return (ERRPage_ % (code, http_errorcodes[code][0], http_errorcodes[code][1])).encode()
def LEN_OF_BRACE(data): #[0] [1] [2]
    n = 0
    while 1:
        if '[%s]'%n in data:
            n += 1
            continue
        else:
            break
    return n
def BRACE_REPLACE(data, cf):
    for i in data:
        cf = cf.replace("[%s]"%i, data[i])
    return cf
def GET(url):
    if '?' in url:
        get = "?".join(url.split("?")[1:])
        #url = url.split("?")[0]

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
        return ar
    else:
        return {}
def GET_STRIFY(dic):
    t = ''
    dic = TO_DICT(dic)
    for i in dic:
        t += "%s=%s&"%(i, uparse.quote(dic[i]))
    return t[0:-1]
def TO_DICT(DIC):
    if DIC == None:
        return {}
    if type(DIC) == dict:
        return DIC
    narr = {}
    n = 0
    for i in DIC:
        narr[n] = i
        n += 1
    return narr
