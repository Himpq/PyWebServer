
"""
    PyWebServer
    By Himpq | Created in 2020-10-12
"""

from Logger import Logger, setLog, initLogThread
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
        """
        判断并处理 SSL/TLS 连接。

        Args:
            conn: 当前的 socket 连接对象。
        
        Returns:
            处理后的连接对象（可能是原始连接或 SSL 包装后的连接）。
        """
        if self.ssl and not isinstance(conn, ssl.SSLSocket):
            Logger.error("First connect. Need to check SSL.", conn)
            try:
                # 复制原始连接以备处理错误时恢复使用
                dup = conn.dup()
                use_https = True

                # 尝试将连接升级为 SSL/TLS
                ssl_conn = self.ssl_context.wrap_socket(
                    conn, 
                    server_side=True, 
                    do_handshake_on_connect=config.get('ssl-dohandshake', True)
                )
            except ssl.SSLError as e:
                # 处理 SSL 错误
                if "CERTIFICATE_UNKNOWN" in str(e):
                    Logger.warn("Certificate issue: ", str(e))
                    return None  # 不返回连接，避免继续操作无效的 SSL 连接
                elif "http request" in str(e):
                    Logger.warn("Client is making an HTTP request.")
                    use_https = False

                    try:
                        # 恢复原始连接并解析请求头
                        conn = dup
                        ctx = conn.recv(1024).decode()
                        header = parsingHeaderByString(ctx, noMethod=True)

                        # 生成 302 跳转响应
                        redirect_host = (
                            str(setting['ssljump-domain']).encode() + b':' + str(self.port).encode()
                            if not header.get("headers", {}).get('host') 
                            else header['headers'].get("host").encode() + b':' + str(self.port).encode()
                        )
                        redirect_path = (
                            b'/'
                            if not header.get("path") 
                            else b'/' + header.get('path').encode()
                        )
                        response = (
                            b'HTTP/1.1 302 Found\r\n'
                            b'Connection: close\r\n'
                            b'Location: https://' + redirect_host + redirect_path + 
                            b'\r\n\r\n<h1>Redirecting to HTTPS!</h1>\r\n\r\n'
                        )
                        conn.send(response)
                    except Exception as recv_err:
                        Logger.error("Error handling HTTP request: ", recv_err)
                    finally:
                        # 确保连接关闭
                        conn.close()
                    return None
                else:
                    Logger.error("Severe SSL issue: ", e)
                    return None
            else:
                # 如果 SSL 连接成功，将其替换为新连接
                if use_https:
                    conn = ssl_conn

        return conn

    
    def _accept(self):
        self.ident = 0
        
        while self.isStart:
            
            # try:
                self.ident += 1
                
                conn, addr = self.socket.accept()
                
                self.createResponse(conn, addr, self.ident)
            
            # except Exception as e:
                # Logger.error(e, "at accept function.")
                # continue

    @DT.useThread(priority=2)
    def createResponse(self, conn, addr, ident):
        from H1Response import ServerResponse
        from H2Response import ServerResponseHTTP2, JudgeH2
        
        conn = self.judgeSSL(conn) if self.ssl else conn
                
        if conn == None:
            return

        if JudgeH2(conn):
            http2response = ServerResponseHTTP2(self, addr, conn, ident)
            http2response.response()
            return

        obj        = ServerResponse(addr, ident, self, conn)
        # globals()['obj'][ident] = obj

        user       = Thread(target=obj.response)
        DT.addThread(user, useLock=False)

        Logger.info("[HTTP1.1] 接收来自", addr, "的请求 | ID:", ident)
        

    def start(self):
        Logger.comp("服务器启动。")
        Logger.info("Listening: %s:%s"%(self.ip, self.port))
        self.isStart  = True
        self.coll     = Coll

        self.socket   = socket.socket()
        self.socket.bind((self.ip, self.port))
        
        # if self.ssl:
            # self.oSocket = self.socket
            # self.socket = self.ssl_context.wrap_socket(self.socket, server_side=True, do_handshake_on_connect=config['ssl-dohandshake'])
        # else:
            # self.oSocket = self.socket

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

