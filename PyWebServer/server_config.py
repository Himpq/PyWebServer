import os
from functions import iniToJson, prettyPrint

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

[config]
language-wrong-error=false
ranges-download=true
default-page=('index.html','index.htm','index.py')
python=true
raise-error=true
timeout=5
cachesize=409600
sameip-request-count=5
server_status=NORMAL
errorpagePath=./ErrorPages/error.html
sslpath=('cert.crt','key.key','ca.crt')
maxsize-for-etag = (1024*1024*100)

[black_list]
blacklist=

[bind_domains]
domains=

[http_errorcodes]
503=('Server Unavailable','Server overload or maintenance in progress. Please wait for administrator to maintain or visit later.')
404=('Not Found','Page is not found.')
406=('Language Error','The language is not supported by the server.')
safeguard=('Server Safeuard','The server is being maintained.')

[headers]
.(flv|gif|jpg|jpeg|png|ico|swf)$=('Cache-control', 'max-age=2592000')
""".format(os.path.abspath("./Website"), os.path.abspath("./")))

opts = iniToJson("./pws_config.ini")

#Status:
SAFEGUARD = 0 #维护
NORMAL = 1    #正常

config = {}
http_errorcodes = {}

for i in opts['setting'].keys():
    globals()[i] = opts['setting'][i]

for i in opts['config']:
    config[i] = opts['config'][i]
#prettyPrint(config)

for i in opts['http_errorcodes']:
    http_errorcodes[i] = opts['http_errorcodes'][i]
#prettyPrint(http_errorcodes)

black_list = [] #IP黑名单
bind_domains = [] #绑定的域名


ERRPagePath = "./ErrorPages/error.html"
ERRPageStr = open(ERRPagePath,'r').read()
ERRPage = lambda:ERRPageStr
def __printContent():
    import json
    print(json.dumps(opts, sort_keys=True, indent=4, separators=(',', ':')))
    print(config)

#__printContent()
