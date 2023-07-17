
import os
from Functions import iniToJson, prettyPrint

if os.path.isdir(",/temp"):
    os.mkdir("./temp")

if not os.path.isfile("./pws_config.ini"):
    with open("./pws_config.ini", 'w', encoding='utf-8') as f:
        f.write("; PyWebServer Config\n")
        f.write("""
[setting]
ServerPath={0}
InstallPath={1}
ip=("")
port=80
ssl=false
ssljump-domain=localhost

[config]
ranges-download=true
default-page=('index.html','index.htm','index.py')
python=true
raise-error=true
timeout=5
keep-alive-max=20
cachesize=409600
server-status=NORMAL
errorpage-path=./ErrorPages/error.html
ssl-path=('cert.crt','key.key','ca.crt')
ssl-password=
ssl-dohandshake=true
maxsize-for-etag=(1024*1024*100)
support-protocols=(["spdy/3.1", "http/1.1"])
threadpool-maxsize=100
collection-expire-time=300
session-expire-time=600

[black_list]
blacklist=

[http_errorcodes]
503=('Server Unavailable','Server overload or maintenance in progress. Please wait for administrator to maintain or visit later.')
404=('Not Found','Page is not found.')
safeguard=('Server Safeuard','The server is being maintained.')

[headers]
.(flv|gif|jpg|jpeg|png|ico|swf)$=('Cache-control', 'max-age=2592000')

[HTTP2]
SETTINGS_HEADER_TABLE_SIZE=4096
SETTINGS_MAX_CONCURRENT_STREAMS=100
SETTINGS_INITAL_WINDOW_SIZE=65535
SETTINGS_MAX_FRAME_SIZE=16384
SETTINGS_MAX_HEADER_LIST_SIZE=16384

[logger]
# types: complete, info, warning, error
ignore_list=([])

""".format(os.path.abspath("./Website"), os.path.abspath("./")))

ServerPath = None
InstallPath = None

opts = iniToJson("./pws_config.ini")

#Status:
SAFEGUARD = 0 #维护
NORMAL = 1    #正常

config = {}
setting = {}
http_errorcodes = {}
http2settings = {}

#[setting]内容会定义于全局变量
for i in opts['setting'].keys():
    globals()[i] = opts['setting'][i]
    setting[i]   = opts['setting'][i]

for i in opts['config']:
#[config]内容会定义于dict config
    config[i] = opts['config'][i]


for i in opts['http_errorcodes']:
#[http_errorcodes]会定义于dict http_errorcodes
    http_errorcodes[i] = opts['http_errorcodes'][i]

for i in opts['HTTP2']:
    http2settings[i] = int(opts['HTTP2'][i])

logger = opts['logger']


black_list = [] #IP黑名单
bind_domains = [] #绑定的域名


ERRPagePath = config['errorpage-path']
ERRPageStr = open(ERRPagePath,'r').read()
ERRPage = lambda:ERRPageStr

def __printContent():
    import json
    print(json.dumps(opts, sort_keys=True, indent=4, separators=(',', ':')))

if __name__ == "__main__":
    __printContent()
