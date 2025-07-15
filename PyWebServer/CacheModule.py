
import os
import random
import time
import io


DISK   = 0x1
MEMORY = 0x4

def randomGenerateFileName():
    s = time.ctime()
    g = time.asctime()
    return str(hash(s))[0:8].replace("-", str(random.randint(0, 9)))+str(hash(g))[0:8]+str(random.randint(0, 99999))

def returnRandomName(checkpath):
    "checkpath: './test/%.temp'"
    while 1:
        s = randomGenerateFileName()
        if os.path.isfile(checkpath.replace("%", s)):
            continue
        return s

class h2cachefile:
    def __init__(self, path="./temp", save=DISK):
        self.saveType = save
        if save == DISK:
            s = returnRandomName(path+"/%.temp")
            self.path = path+"/"+s+".temp"
            self.file = open(self.path, 'wb')
            self.file.close()
            self.file = open(self.path, 'wb+')
        else:
            self.file = io.BytesIO()
            self.path = ''
        self.writelen = 0
        self.uploadFinish = False
        self.moveTo = []
    def _check(self):
        "将文件移动到moveTo列表元素的路径处"
        for i in self.moveTo:
            try:
                self.file.seek(0)
                with open(i, 'wb') as f:
                    f.write(self.file.read())
            except Exception as e:
                print("Move file error:", e)

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
        if os.path.isfile(self.path):
            try:
                self.file.close()
            except:
                pass
            os.remove(self.path) if self.saveType == DISK else None
    def seek(self, seek, offset=0):
        self.file.seek(seek, offset)
    def readline(self):
        return self.file.readline()
    def move(self, path):
        self.moveTo.append(path)
    

class cachefile:
    def __init__(self, path='./temp'):
        rdname = returnRandomName(path+"/%.temp")
        self.path = path+"/"+rdname+".temp"
        self.originPath = self.path
        self.file = open(self.path,'wb')
        self.file.close()
        self.file = open(self.path,'wb+')
        self.writelen = 0
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
    def close(self):
        self.file.close()
    def clean(self):
        if os.path.isfile(self.originPath):
            try:
                self.file.close()
            except:
                pass
            os.remove(self.originPath)
    def seek(self, x, offset=0):
        self.file.seek(x, offset)
    def readline(self):
        return self.file.readline()
    def move(self, path):
        try:
            self.seek(0)
            r=self.read(1024*4)
            with open(path, 'wb') as f:
                while not r==b'':
                    f.write(r)
                    r = self.read(1024*4)
            self.clean()
            self.file = open(path, 'ab+')
            self.path = path
        except Exception as e:
            print("Move file error:",e, path)
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

class FileCache:
    def __init__(self, trueFile=False):
        self.file = '' if not trueFile else None
    def write(self, data):
        self.file += data
    def save(self):
        pass
    def read(self):
        return self.file

if __name__ == "__main__":
    g = cachefile()
    p = h2cachefile(save=DISK)

    g.write(b"WC")
    p.write(b"WCTOO")

    g.save()
    p.save()

    g.seek(0)
    p.seek(0)

    print(g, p)
    print(g.read(), p.read())

    g.write(b'WC2')
    p.write(b'wc3')

    g.save()
    p.save()

    g.seek(0)
    p.seek(0)

    print(g.read(), p.read())

    g.clean()
    p.clean()
