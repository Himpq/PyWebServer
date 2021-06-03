
import urllib.parse as uparse
import time,os
from threading import Thread
from http_returntype import *

if not os.path.isfile("./pws_config.ini"):
    with open("./pws_config.ini", 'w') as f:
        f.write("- PyWebServer Config\n")
        f.write("""
ServerPath={0}
InstallPath={1}
ip=192.168.1.112
port=80
ssl=false

[config]
language-wrong-error=false
ranges-download=true
default-page='index.html','index.htm','index.py'
python=true
raise-error=true
timeout=30
sameip-request-count=5
clean-threadtime=10
server_status=NORMAL
errorpagePath=./ErrorPages/error.html
sslpath='cert.crt','key.key','ca.crt'

[black_list]

[bind_domains]
localhost

[http_errorcodes]
503='Server Unavailable','Server overload or maintenance in progress. Please wait for administrator to maintain or visit later.'
404='Not Found','Page is not found.'
406='Language Error','The language is not supported by the server.'
safeguard='Server Safeuard','The server is being maintained.'


""".format(os.path.abspath("./Website"), os.path.abspath("./")))

#Status:
SAFEGUARD = 0 #维护
NORMAL = 1    #正常

ServerPath = os.path.abspath("./Website")
InstallPath = os.path.abspath("./")

config = {
    "language-wrong-error"   : False,                                    #当 Accept-Language 请求的语言不在列表中返回 406 错误
    "ranges-download"        : True,                                    #断点续传，多用于多线程下载
    "default-page"           : ["index.html", "index.htm", "index.py"], #请求目录为"/"或"某文件夹/"时的默认返回页面
    "python"                 : True,                                    #开启Python支持（开启此才可查看py页面）
    "raise-error"            : True,                                    #当py页面出错时报错(关闭则返回503)

    "timeout": 30,                #(s) 超时未响应自动断开连接
    "sameip-request-count": 5,    #同一个ip在1秒内最多访问次数
    "clean-threadtime": 10,       #清理垃圾线程（需扫描线程池，可能占用较大资源）的时间间隔
    "reload-information-time": 5, #刷新服务器信息时间

    "server_status": NORMAL,             #服务器状态
}
black_list = [] #IP黑名单
bind_domains = [] #绑定的域名
http_errorcodes = {
    "503": ["Server Unavailable", "Server overload or maintenance in progress. Please wait for administrator to maintain or visit later."],
    "404": ["Not Found", "Page is not found."],
    "406": ['Language Error', 'The language is not supported by the server.'],

    'safeguard': ['Server Safeuard', "The server is being maintained."],
}
ERRPagePath = "./ErrorPages/error.html"
sslpath = ['cert.crt', 'key.key', 'ca.crt']




ERRPage = lambda:open(ERRPagePath,'r').read()
def isIPv4(domain):
    if len(domain.split(".")) == 4:
        for i in domain.split("."):
            try:
                int(i)
            except:
                return False
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
