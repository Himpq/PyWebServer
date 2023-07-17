
import typing 
import sys

sys.path.append("../")

from Collection import Collection
from IgnoreVariable import *
from H2Response import ServerResponseHTTP2, HeaderFrame
from ServerConfig import config
from Functions import FrameParser
import time
import hashlib
import random

__all__ = ['generateToken', 'Session']

cleanerThr = None

def generateToken(IP, Coll):
    while 1:
        _hash = hashlib.sha256()
        _hash.update(time.ctime().encode())
        _hash.update(str(random.randint(0, 0xffff)).encode())
        _hash.update(IP.encode())
        token = _hash.hexdigest()

        if token in Coll:
            continue
        return token

class Session:
    @typing.overload
    def __init__(self, setCookie: typing.Callable, requestFrame: FrameParser, Coll: Collection, key, val):
        "Use 'set_cookie' function to set a session."
    @typing.overload
    def __init__(self, respondFrame:HeaderFrame, requestFrame: FrameParser, Coll: Collection, key, val):
        "Use 'headerFrame' object to set a session."

    def __init__(self, arg: typing.Union[typing.Callable, ServerResponseHTTP2], reqFrame:FrameParser, Coll: Collection, key, val, expire=1800):
        if "HeaderFrame" in str(arg):
            _set = arg.set_cookie
        else:
            _set = arg

        if not "_SESSION" in Coll:
            Coll["_SESSION"] = {}
        
        if not reqFrame.get("cookie").get("JSESSIONID"):
            token = generateToken(reqFrame.getIP()[0], Coll)
        else:
            token = reqFrame.get("cookie").get("JSESSIONID")

        if not token in Coll['_SESSION']:
            Coll['_SESSION'][token] = {
                "__expire__": config['session-expire-time']
            }
            _set("JSESSIONID", token, attributes={"HttpOnly":"", "Secure": ""})

        Coll['_SESSION'][token][key] = {
            "val": val
        }
    
    def get(token, key, Coll):
        return Coll.get("_SESSION", {}).get(token, {}).get(key, {"val":None}).get("val")
    
    def set(key, val, expire=1800):
        """请使用魔术注释导入 Session 模块再使用本函数。"""
        if globals().get("set_cookie") == None or globals().get("_frame") == None or globals().get("_COLL") == None:
            raise Exception("Import Session module in a right way or use __init__.")
        return Session(set_cookie, _frame, _COLL, key, val, expire)
