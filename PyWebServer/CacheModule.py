# Cache Module
# By Himpq
import os
import random
import threading
import time
import io
nx=0

DISK = 0x1
MEMORY = 0x4

from Logger import Logger
Logger = Logger("CacheF")

class h2cachefile:
    def __init__(self, path="./temp", save=DISK):
        global nx
        self.saveType = save
        if save == DISK:
            self.path = path+"/"+str(nx)+".temp"
            self.file = open(self.path, 'wb')
            self.file.close()
            self.file = open(self.path, 'wb+')
            nx += 1
        else:
            self.file = io.BytesIO()
            self.path = ''
        self.writelen = 0
        self.uploadFinish = False
        self.moveTo = []
    def _check(self):
        for i in self.moveTo:
            try:
                self.file.seek(0)
                with open(i, 'wb') as f:
                    f.write(self.file.read())
            except Exception as e:
                Logger.error("Move file error:", e)
        
    def write(self, ctx):
        assert type(ctx) == bytes, "Must be a bytes type like."
        #assert self.uploadFinish, "File is still uploading."
        self.file.write(ctx)
        self.writelen += len(ctx)
    def read(self, m=-1):
        return self.file.read(m)
    def endwith(self, s):
        assert type(s) == bytes, "Need a byte type."
        if self.writelen - len(s) < 0:
            return False
        self.file.seek(self.writelen - len(s))
        return s == self.read()
    def save(self):
        if self.saveType == DISK:
            self.file.close()
            self.file = open(self.path, 'ab+')
    def clean(self):
        self.file.close()
        os.remove(self.path) if self.saveType == DISK else None
    def seek(self, seek, offset=0):
        self.file.seek(seek, offset)
    def readline(self):
        return self.file.readline()
    def move(self, path):
        self.moveTo.append(path)
    

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
