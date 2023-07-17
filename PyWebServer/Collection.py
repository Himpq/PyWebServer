
from threading import Thread
from ServerConfig import config

class CollValue:
    def __init__(self, key, val, expire=config['collection-expire-time']):
        self.key = key
        self.value = val
        self.expire = expire
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self.value)
    
class Collection(dict):
    '''用于多个 Python 页面交流信息
    如同 ASP 的 application 一样
    使用 "_COLL" 在 Python Web 文件中使用
    由于多进程，_COLL无法使用,由 multiprocess.Manager.dict 代替（反正功能一毛一样）'''

    def __init__(self):
        super().__init__()

    def getSession(self):
        return self.get("_SESSION", {})
    
    def __setitem__(self, key, val):
        return self.set(key,  val)
    
    def __getitem__(self, key):
        return self.get(key)
    
    def set(self, key, val):
        if key == "_SESSION":
            super().__setitem__(key, val)
        else:
            super().__setitem__(key, CollValue(key, val))

        
    def get(self, key, default=None):
        if key == '_SESSION':
            return super().get(key)
        else:
            if super().get(key) == None:
                return default
            return super().get(key).value
    
    def getObj(self, key):
        return super().get(key)

