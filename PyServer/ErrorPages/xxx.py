import datetime, os, chardet

'''document.setHeader("WDNMD", "Sure.")

document.write("<h1>Power By LeavesServer</h1>")
d = document.time.now()
d = document.time.add(d, 3600)
d = document.time.ctime(d)

document.write("""
<form action='' method='post'>
<input type='text' name='ee1'>
<input type='text' name='ee2'>
<input type='text' name='ee3'>
<input type='submit'>
</form>""")

if 2 in document.requests_data['getdata']:
    p = document.requests_data['getdata'][2]
    if os.path.isfile(document.server_path+"/"+p+'.html'):
        with open(document.server_path+"/"+p+'.html', 'rb') as f:
            x = f.read()
            f = chardet.detect(x)
            x = x.decode(f['encoding'])
            document.write(x)
    else:
        document.write("<h2>Do not find the page.</h2>")

document.write("Args: <font color='blue'>",document.requests_data,'</font>')
document.write("Arg", _POST, _GET, _COOKIE)

#document.write("<script>location.href='./index.html';</script>")
'''
set_header("Content-Type","text/html")

print("<h1>555</h1>",'<form action="" method="post" enctype="multipart/form-data"><input name="dafile" type="text"><input name="2dafile" type="file"><input name="file" type="file"><input type="submit"></form>')
print("<form action='' method='post'><input type='text' name='xxx'><input type='submit'></form>")
if not len(_FILE) == 0:
    _FILE['file']['cachefile'].seek(0)
    print("READ",_FILE['file']['cachefile'].read(10),end='<br>')
    _FILE['file']['cachefile'].move("A:/xxx.jpg")
print(_POST, _GET, _REWRITE, _FILE, _DATA, sep="<br>")
