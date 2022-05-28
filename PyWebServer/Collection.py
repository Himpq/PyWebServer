
class Collection:
    #用于多个 Python 页面交流信息
    #如同 ASP 的 application 一样
    #使用 "_COLL" 在 Python Web 文件中使用

    def __init__(self):
        self._coll = {}
    def set(self, k, v):
        self._coll[k] = v
    def get(self, k):
        return self._coll.get(k)
    def clean(self):
        self._coll = {}
