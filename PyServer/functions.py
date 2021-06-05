import inspect, ctypes

#停止线程函数
def _async_raise(tid, exctype):
    """Raises an exception in the threads with id tid"""
    if not inspect.isclass(exctype):
        raise TypeError("Only types can be raised (not instances)")
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(tid), ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")
def stop_thread(thread):
    _async_raise(thread.ident, SystemExit)

#删除一个对象的所有东西
def DeleteObjectAllProperties(objectInstance):
    if not objectInstance:
        return
    listPro =[key for key in objectInstance.__dict__.keys()]
    for key in listPro:
        objectInstance.__delattr__(key)

#合并字典
def dict_inone(*arg):
    x = {}
    for i in arg:
        for f in i:
            x[f] = i[f]
    return x

#获取HTTP请求头的文件返回范围
def getRange(xd):
    if '-' in xd:
        x = xd.split("-")
        if x[1] == '':
            f1 = ''
        else:
            f1 = int(x[1])
        f = int(x[0])
        return [f,f1]
    else:
        try:
            int(xd)
        except:
            return [0,0]
        else:
            return int(xd), int(xd)

#ini格式刷转JSON
def iniToJson(inipath):
    import configparser as cp
    cf = cp.ConfigParser()
    cf.optionxform = lambda option: option
    cf.read(inipath)
    jsons1 = {}
    result = {}
    kv = {}
    scts = cf.sections()
    for i in scts:
        kv[i] = cf.items(i)
    for i in kv.keys():
        result[i] = {}
        for v in kv[i]:
            vf = v[1].strip()
            if vf == '':
                vf = None
            elif vf == 'true':
                vf = True
            elif vf == 'false':
                vf = False
            elif not isNum(vf) == False:
                vf = isNum(vf)
            elif vf[0] == '(' and vf[-1] == ')':
                try:
                    vf = eval(vf)
                except:
                    pass
            result[i][v[0]] = vf
            
    return result
#洁净输出json
def prettyPrint(j):
    import json
    print(json.dumps(j, sort_keys=True, indent=4, separators=(',', ':')))
#是否是一个ipv4地址
def isIPv4(domain):
    if len(domain.split(".")) == 4:
        for i in domain.split("."):
            try:
                int(i)
            except:
                return False
        return True
    return False

#获取文件的类型
def FileType(path):
    from http_returntype import return_filetype
    for i in return_filetype:
        v = return_filetype[i]
        if i == 'default':
            continue
        for i2 in v:
            if path[-len(i2)-1:].lower() == '.'+i2:
                return i.replace('.', '/', 1)
    return return_filetype['default'].replace('.', '/')

#判断是否是数字
def isNum(st):
    try:
        int(st)
    except:
        return False
    else:
        return int(st)
