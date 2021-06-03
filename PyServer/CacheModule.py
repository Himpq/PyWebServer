# Cache Module
# By Himpq
import os
import random

class Counter:
    def __init__(self):
        self.s = 0
    def get(self):
        return self.s
    def next(self):
        self.s+=1

nx=0

class cachefile:
    def __init__(self, path='./temp'):
        global nx
        n = nx
        self.file = open(path+"/"+str(n)+".temp",'wb')
        self.file.close()
        self.file = open(path+"/"+str(n)+".temp",'wb+')

        self.writelen = 0
        self.path = path+"/"+str(nx)+".temp"

        nx+=1
    def write(self, ctx):
        assert type(ctx) == bytes, "Must be a bytes type like."
        self.file.write(ctx)
        self.writelen += len(ctx)
    def read(self, m=-1):
        return self.file.read(m)
    def endswith(self, s):
        assert type(s) == bytes, "Need a byte type string."
        if self.writelen-len(s) < 0:
            return False
        self.file.seek(self.writelen-len(s))
        return s == self.read()
    def save(self):
        self.file.close()
        self.file = open(self.path, 'ab+')
    def clean(self):
        self.file.close()
        os.remove(self.path)
    def seek(self, x, offset=0):
        #assert not x<0, "x must be > 0"
        self.file.seek(x, offset)
    def readline(self):
        return self.file.readline()
    def move(self, path):
        self.seek(0)
        r=self.read(1024*4)
        with open(path, 'wb') as f:
            while not r==b'':
                f.write(r)
                r = self.read(1024*4)
        self.file.close()
        os.remove(self.path)
        self.file = open(path, 'ab+')
        self.path = path
            
    def delete(self, length):
        """delete length(end)"""
        upseek = self.file.tell()
        self.file.seek(0) #begin
        maxlen = self.writelen-length
        self.writelen -= length

        cache = cachefile()
        while not cache.writelen == self.writelen:
            cache.write(self.file.read(1))
        self.file.truncate()

        r = cache.read(1024)
        while not r == b'':
            self.file.write(r)
            r = cache.read(1024)
        cache.clean()

        try:
            self.file.seek(upseek)
        except:
            pass
        
        
class CF:
    def __init__(self, file, path):
        self.file = file
        self.path = path
        self.seek = 0
    def write(self, content):
        self.file.write(content)
    def read(self, ma=-1):
        return self.file.read(ma)

nums = 0
count = Counter()

def new(path='./temp'):
    a = str(nums)
    file = open(path+"/%s.tmp"%a, 'wb')
    file.close()
    file = open(path+"/%s.tmp"%a, 'wb+')
    
    return CF(file, path+"/%s.tmp"%a)

def whilewith(func, file:CF, length=1024):
    file.file.seek(0)
    while 1:
        r = file.read(length)
        if r == b'':
            return
        func(r)

def clean(file:CF):
    file.file.close()
    n = 0
    '''while 1:
        if n > 1000000:
            print("无法清除缓存文件: %s"%file.path)
            break
        n += 1
        try:
            os.remove(file.path)
        except PermissionError as e:
            continue
        else:
            break'''
    os.remove(file.path)
