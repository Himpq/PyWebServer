

import os
from functions import iniToJson, prettyPrint

if not os.path.isfile("./pws_config.ini"):
    with open("./pws_config.ini", 'w') as f:
        f.write("; PyWebServer Config\n")
        f.write("""
[setting]
ServerPath={0}
InstallPath={1}
ip=192.168.1.112
port=80
ssl=false

[config]
language-wrong-error=false
ranges-download=true
default-page=('index.html','index.htm','index.py')
python=true
raise-error=true
timeout=30
sameip-request-count=5
clean-threadtime=10
server_status=NORMAL
errorpagePath=./ErrorPages/error.html
sslpath=('cert.crt','key.key','ca.crt')

[black_list]
blacklist=

[bind_domains]
domains=

[http_errorcodes]
503=('Server Unavailable','Server overload or maintenance in progress. Please wait for administrator to maintain or visit later.')
404=('Not Found','Page is not found.')
406=('Language Error','The language is not supported by the server.')
safeguard=('Server Safeuard','The server is being maintained.')


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
prettyPrint(config)

for i in opts['http_errorcodes']:
    http_errorcodes[i] = opts['http_errorcodes'][i]
prettyPrint(http_errorcodes)

black_list = [] #IP黑名单
bind_domains = [] #绑定的域名


ERRPagePath = "./ErrorPages/error.html"
ERRPage = lambda:open(ERRPagePath,'r').read()
