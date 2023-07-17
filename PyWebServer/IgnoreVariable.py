
from Logger     import Logger
from Server     import ServerResponse
from Collection import Collection
from Functions  import UploadDatasObject, UploadFilesObject, FrameParser
from H2Response import ServerResponseHTTP2

__all__ = ['set_cookie', 'set_header', 'finish_header', 'set_statuscode', 'get_response_header', 'get_priority', 'set_priority', 'print', 'include',
           'set_disable_etag', 
           'isHTTP2', 'Logger', 'this', '_POST', '_GET', '_h2r', '_frame', '_sid', '_COOKIE', '_FILE', '_DATA', '_COLL', '_HEADER', "VAR", "MODULE"]

VAR    = "var"
MODULE = "module"

isHTTP2 : bool                = None
Logger  : Logger              = None
this    : ServerResponse      = None

_POST   : dict                = {}
_GET    : dict                = {}
_COOKIE : dict                = {}
_HEADER : dict                = None
_FILE   : UploadFilesObject   = None
_DATA   : UploadDatasObject   = None
_COLL   : Collection          = None
_sid    : int                 = None
_frame  : FrameParser         = None
_h2r    : ServerResponseHTTP2 = None


def set_cookie(self, cookieName, cookieValue, expires=1800, 
               attributes: dict=None):                       """设置、添加 Cookie"""
def set_header(self, key, val):                              """设置头部字段"""
def finish_header(self):                                     """用于结束设置 HTTP 响应头并将 print 函数输出对象转为 socket 连接"""
def set_statuscode(self, code, content):                     """设置 HTTP 状态码"""
def get_response_header(self) -> dict:                       """获取当前文件的响应头"""
def get_priority(self) -> int:                               """获取当前流的优先级"""
def set_priority(self, priority=1):                          """设置当前流的优先级"""
def print(self, *arg, **args):                               """判断是否使用了 finish_header 以 print 直接向 socket 输出"""
def include(self, filePath, includeType = MODULE,
            useDirPath = True,
            asName = None):                                  """使用 PWS 的 include 导入模块"""
def set_disable_etag(self, disable):                         """关闭或启用 ETag 模式"""
