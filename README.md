# PyWebServer
![PyWebServer](http://pws.himpqblog.cn/PyWebServer.png)
一个小巧的 Python Web 项目，一位初中生闲着没事打着玩的东西

[官网以及教程](http://pws.himpqblog.cn) 

## 安装和使用
打包下载源码（如果你有本地Python环境，仅需要安装 pathos 模块）  

启动服务器：  
```
python server.py
```

## 文件结构
第一次启动会在本地目录下新建**temp**和**pws_config.ini**。  
**ErrorPage**目录内存放**error.html**为当服务器遇到错误时读取使用的错误页面。  
**logs**目录只会存放一个日志文件，且久了日志文件的大小会非常大。

## 特性
* 在本地测试时访问延迟在**500ms**以内
* ETag 缓存无法直接关闭（懒得写），访问 Python 文件可以通过 `set_disable_etag(True)` 关闭服务器对 Python 文件的 ETag 缓存
* 当使用 ETag 缓存来缓存 Python 页面时服务器会先执行 Python 文件，再根据输出的信息的 sha1 值进行比对。
* 绑定域名功能已被注释掉
* 黑名单IP还未实现

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
