
import os
from Functions import iniToJson, prettyPrint
from ConfigCreator import *

createTempDir()
createConfig()

ServerPath = None
InstallPath = None
ip, port = None, None
ERRPage = None
config = {}
setting = {}
http_errorcodes = {}
http2settings = {}
opts = None

black_list = [] #IP黑名单
bind_domains = [] #绑定的域名

logger = None

defaultIniPath = "./pws_config.ini"

def initConfig(iniPath = defaultIniPath):
    global ServerPath, InstallPath, ip, port, ERRPage, config, setting, http_errorcodes
    global http2settings, black_list, bind_domains, logger, defaultErrorPage, opts
    opts = iniToJson(iniPath)

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

    defaultErrorPage = '''<html>
    <head>
        <meta charset="UTF-8">
        <meta name='viewport' content='width=device-width'>
        <title>{1} - {0}</title>
    </head>
    <body>

        <div style='font-family: Microsoft JhengHei;'>
            <center>
                <span>
                    <img src='/PyWebServer.png' style='width: 40%;'>
                </span>
            </center>
            <div  style='margin-left:20%;'>
                <h1>{0} {1}</h1>
                <p>{2}</p>
            </div>
        </div>

    </body>
    </html>
        
    '''

    ERRPagePath = config['errorpage-path']
    if os.path.isfile(ERRPagePath):
        ERRPageStr = open(ERRPagePath,'r').read()
        
    else:
        ERRPageStr = defaultErrorPage

    ERRPage = lambda:ERRPageStr

initConfig()

def __printContent():
    import json
    print(json.dumps(opts, sort_keys=True, indent=4, separators=(',', ':')))

if __name__ == "__main__":
    __printContent()
