# PyWebServer
![PyWebServer](http://pws.himpqblog.cn/PyWebServer.png)
一个的 Python Web 项目，一位初中生闲着没事打着玩的东西  
请勿用于重要项目开发  
解码 HTTP2 部分使用了 hpack 模块，其余部分纯socket通讯  

//测试IP: [WNetdisk](http://114.55.116.36:99/WNetdisk/)  (由于IP办SSL没有免费渠道已经关闭了)  

[官网以及教程](http://pws.himpqblog.cn) 

## 安装和使用
打包下载源码，安装hpack模块
```
pip install hpack
```
OR  
```
pip install -r requirements.txt
```

启动服务器：  
```
python server.py
```

## 文件结构
第一次启动会在本地目录下新建**temp**和**pws_config.ini**。  
**ErrorPage**目录内存放**error.html**为当服务器遇到错误时读取使用的错误页面。  
**logs**目录存放有控制台日志、HTTP2的对话、访问记录。部分日志会在服务器重启后清空。  
**temp**目录存放用户上传文件的缓存，缓存会在Python文件执行完毕后删除。  

## 特性
* 在本地测试时访问延迟在**500ms**以内
* ETag 缓存无法在配置文件里直接关闭（懒得写），访问 Python 文件可以通过 `set_disable_etag(True)` 关闭服务器对 Python 文件的 ETag 缓存
* 当使用 ETag 缓存来缓存 Python 页面时服务器会先执行 Python 文件，再根据输出的信息的 sha1 值进行比对。
* 绑定域名功能已被注释掉
* 黑名单IP还未实现
* 对于 HTTP2 的支持较好，HTTP/1.1 可能有些许 bug
* 还有许多地方有待优化

### HTTP2
目前已支持HTTP2协议，需要在配置文件中的```support-protocols```项更改信息```(["spdy/3.1", "h2", "http/1.1"])```，并且开启HTTP2需要HTTPS证书。  
  
HTTP2基础功能完善，服务器推送未实现。 
可以通过更改配置文件中的**HTTP2**项内容来控制帧大小、初始流量窗口等。  
  
由于是测试版本，控制台界面会有很多没删掉的debug信息...
### 在 HTML 文档中使用 Python 代码
可以通过在HTML文档的任意位置加入注释：
```<!-- py -->```
表示执行文档中的 Python 代码。如：
```html
<html>
<head>
    <meta charset="UTF-8">
    <title>Python page</title>
</head>
<body>
    <?py
print("<h1>Hello World!</h1>")
?>
<!-- py -->
</body>
</html>
```
如 PHP 一样可以在任何 HTML 页面中插入代码（尽管后缀名非py，后缀名限制为htm和html），但仍需严格遵守缩进。  
您无法在一个缩进区块结束代码再在后面另起一段接上，因为除了变量相同，每个```<?py ... ?>```代码块都是独立执行的。
### 配置文件更新提醒
每个版本基本都会有配置文件的更新，由于 PWS 无法检测文件是否更新，需要手动将配置文件删除后再启动服务器重建。
## 更新日志
* [v1.0] fl 函数可能因为传输大数据而内存溢出  
2021-01-02 20:31
 
* [v3.2] 更新使得 ExpHttpData 模块中 exp_headers 的使用频率降低，同时该问题也是导致一段时间后应用CPU使用率骤增不减的原因  
2022-3-27 14:16

* [v4.2] 更新内容较多，修复各种英语语法问题，增添注释，使得代码更加易读  
修复很多影响性能的问题  
2022-5-28 18:30  

* [v4.7] 支持多进程，设置网页响应对象缓存大小，修复断点续传抽风问题。 
ETag 缓存支持设置最小计算缓存大小，小于该大小阈值的文件将不启用 ETag。  
2022-6-22 22:58  

* [v4.7] 关闭多进程（由于打包后多进程会突然开启数十个进程导致占用过高）  
2022-6-24 21:35

* [v4.7 beta] 初步支持 HTTP2协议  
2022-8-9 00:28

* [v4.9] 支持 HTTP2 的 POST, 文件上传(multipart/form-data)，并且增添新模式：  
在 .htm, .html后缀的文档中可以使用“<?py ... ?>”执行 Python 代码。  
2022-8-26 19:11  
支持在单端口上绑定HTTP,HTTPS功能，但访问HTTP会强制跳转HTTPS。  
2022-10-7 12:36
支持HTTP2特性流量窗口，更新有关HTTP2配置文件的内容
修复了多线程使得上传文件紊乱的问题
2023-6-15 00:29
