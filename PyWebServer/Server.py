
"""
    PyWebServer
    By Himpq | Created in 2020-10-12
"""

from Logger import Logger, setLog, initLogThread
from ServerConfig import ServerPath, ip, port
from ServerConfig import *
from ParsingHTTPData import *
from Functions import *
from Collection import *
from threading import Thread, enumerate
from Version import *
import DispatchThread as DT
import socket
import os
import ssl
import traceback


ssl._create_default_https_context = ssl._create_unverified_context
Coll                              = Collection()


if __name__ == "__main__":
    initLogThread()
    DT.init()

class Server:
    def __init__(self, ip='localhost', port=80, maxlisten=128):
        self.isStart   = False
        self.ip        = ip
        self.port      = port
        self.maxlisten = maxlisten
        self.tpool     = {}
        self.ssl       = False

    def openSSL(self):
        self.ssl = True
        sslPath  = config['ssl-path']
        self.ssl_context                 = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        self.ssl_context.maximum_version = ssl.TLSVersion.TLSv1_3
        self.ssl_context.load_cert_chain(certfile=sslPath[0], keyfile=sslPath[1], password=config['ssl-password'])
        self.ssl_context.load_verify_locations(sslPath[2])
        self.ssl_context.set_alpn_protocols(config['support-protocols'])

    def judgeSSL(self, conn):
        if isinstance(conn, ssl.SSLSocket):
            return conn
        dup = conn.dup()
        try:
            sslconn = self.ssl_context.wrap_socket(conn, True, config['ssl-dohandshake'])
            print(sslconn)
            return sslconn
        except ssl.SSLError as e:
            jumpURL = str(setting['ssljump-domain']).encode()+b':'+str(self.port).encode()
            redirectContent = b'HTTP/1.1 302 Found\r\nConnection: close\r\nLocation: https://'+jumpURL+b'\r\n\r\n'
            
            dup.send(redirectContent)
            dup.close()

    def judgeSSL2(self, conn):
        if self.ssl and not isinstance(conn, ssl.SSLSocket):
            #进行 SSL 判断
            Logger.error("First connect. need to check ssl.", conn)
            dup = conn.dup()
            try:
                useHTTPS = True
                sslconn  = self.ssl_context.wrap_socket(conn, server_side=True, do_handshake_on_connect=config['ssl-dohandshake'])
            except ssl.SSLError as e:
                if "CERTIFICATE_UNKNOWN" in str(e):
                    Logger.warn("证书存在问题：", str(e))
                    return
                elif "http request" in str(e):
                    Logger.warn("客户端正在请求 HTTP。")
                    useHTTPS = False
                    try:
                        ctx = dup.recv(1024).decode()
                    except:
                        return
                    header = parsingHeaderByString(ctx, noMethod=True)
                    dup.send(b'HTTP/1.1 302 Do this!\r\nconnection: close\r\nlocation:https://'+((str(setting['ssljump-domain']).encode()+b':'+str(self.server.port).encode()) if not header.get("headers").get('host') else header['headers'].get("host").encode())+(b'/' if not header.get("path") else b'/'+header.get('path').encode())+b'\r\n\r\n<h1>HELLO!</h1>\r\n\r\n')
                    dup.close()
                    return conn
                else:
                    Logger.error("证书存在严重问题：", e)
                    return
            else:
                if useHTTPS:
                    conn = sslconn
        return conn
    
    def _accept(self):
        ident = 0
        from H1Response import ServerResponse
        from H2Response import ServerResponseHTTP2, JudgeH2
        while self.isStart:
            ident += 1
            try:
                conn, addr = self.socket.accept()
                conn = self.judgeSSL2(conn) if self.ssl else conn
                
                if conn == None:
                    continue

                if JudgeH2(conn):
                    http2response = ServerResponseHTTP2(self, addr, conn, ident)
                    http2response.response()
                    continue

                obj        = ServerResponse(addr, ident, self, conn)
                globals()['obj'][ident] = obj

                user       = Thread(target=obj.response)
                DT.addThread(user, useLock=False)

                Logger.info("接收来自", addr, "的请求 | ID:", ident)
            
            except Exception as e:
                Logger.error(e)
                return

    def start(self):
        Logger.comp("服务器启动。")
        Logger.info("Listening: %s:%s"%(self.ip, self.port))
        self.isStart  = True
        self.coll     = Coll

        self.socket   = socket.socket()
        self.socket.bind((self.ip, self.port))
        self.socket.listen(self.maxlisten)
        
        self.acceptThread = Thread(target=self._accept)
        self.acceptThread.setDaemon(True)
        self.acceptThread.start()

    def stop(self):
        self.isStart = False
        self.socket.close()

server = None
obj = {}
def startServer():
    global server
    server=Server(ip=ip, port=port)
    server.openSSL() if setting['ssl'] else None
    server.start()

if __name__ == '__main__':

    startServer()
    Logger.comp("[Server] MainPID:", os.getpid())

    while 1:
        try:
            g = input(">>> ")
            if g.strip() == '':
                continue
            print(eval(g))
        except Exception as e:
            print(e)
