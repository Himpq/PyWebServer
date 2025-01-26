import os

def createTempDir():
    if not os.path.isdir("./temp"):
        os.mkdir("./temp")

def createConfig(iniPath = "./pws_config.ini"):
    

    if not os.path.isfile(iniPath):
        with open(iniPath, 'w', encoding='utf-8') as f:
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
timeout=60
keep-alive-max=20
cachesize=409600
server-status=NORMAL
errorpage-path=./ErrorPages/error.html
ssl-path=('cert.crt','key.key','ca.crt')
ssl-password=
ssl-dohandshake=true
enable-etag=true
maxsize-for-etag=(1024*1024*100)
support-protocols=(["spdy/3.1", "h2", "http/1.1"])
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
