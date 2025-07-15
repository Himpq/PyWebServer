# PyWebServer
![PyWebServer](https://raw.githubusercontent.com/Himpq/PyWebServer/refs/heads/main/PyWebServer/Website/PyWebServer.png)

一个基于 Python 的简单 Web 服务器项目，个人学习练习作品。

**注意：请勿用于重要项目开发**

解码 HTTP2 Header Frame 部分使用了 hpack 模块，其余部分纯 socket 通讯。

## 安装和使用

### 环境要求
- Python 3.6+

### 安装步骤

1. 下载源码并安装依赖：
```bash
pip install hpack
```
或
```bash
pip install -r requirements.txt
```

2. 启动服务器：
```bash
python server.py
```

## 文件结构

第一次启动会在本地目录下新建 `temp` 和 `pws_config.ini`。

```
PyWebServer/
├── Website/               # 页面文件存放处
├── server.py              # 主服务器文件
├── ErrorPage/
│   └── error.html         # 错误页面模板
├── logs/                  # 日志目录
│   ├── logger.log         # 控制台日志
│   ├── h2.log             # HTTP2 对话日志
│   ├── view.log           # 访问日志
├── temp/                  # 临时文件目录
└── pws_config.ini         # 配置文件
```

### 目录说明

- **ErrorPage**：存放 `error.html` 错误页面模板
- **logs**：存放控制台日志、HTTP2 对话记录、访问记录等，部分日志会在服务器重启后清空
- **temp**：存放用户上传文件的缓存，缓存会在 Python 文件执行完毕后删除

## 主要特性

### 性能
- 支持 ETag 缓存机制
- 当使用 ETag 缓存来缓存 Python 页面时，服务器会先执行 Python 文件，再根据输出信息的 sha1 值进行比对

### 协议支持
- 对 HTTP2 的支持较好，HTTP/1.1 可能有些许 bug
- 支持 HTTPS 加密传输

### HTTP2 支持
目前已支持 HTTP2 协议，需要在配置文件中的 `support-protocols` 项更改信息 `["spdy/3.1", "h2", "http/1.1"]`，并且开启 HTTP2 需要 HTTPS 证书。

HTTP2 基础功能完善，服务器推送未实现。可以通过更改配置文件中的 **HTTP2** 项内容来控制帧大小、初始流量窗口等。

由于是测试版本，控制台界面会有很多没删掉的 debug 信息。

### 在 HTML 文档中使用 Python 代码

可以通过在 HTML 文档的任意位置加入注释 `<!-- py -->` 表示执行文档中的 Python 代码：

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

如 PHP 一样可以在任何 HTML 页面中插入代码（尽管后缀名非 py，后缀名限制为 htm 和 html），但仍需严格遵守缩进。

您无法在一个缩进区块结束代码再在后面另起一段接上，因为除了变量相同，每个 `<?py ... ?>` 代码块都是独立执行的。

### 魔术导入

可以通过以下方式使用 include 函数：

```python
from ModuleName import *    # USING_PWS_INCLUDE
import ModuleName as Name   # USING_PWS_INCLUDE
from ModuleName import *    # USING_PWS_INCLUDE "C:/PythonModules/"
import ModuleName as Name   # USING_PWS_INCLUDE "C:/PythonModules/"
import ModuleName           # USING_PWS_INCLUDE "C:/PythonModules/"
```

上面五行在执行过程中将会被替换为：

```python
include('ModuleName.py', VAR)
include('ModuleName.py', MODULE, asName="Name")
include('C:/PythonModules//ModuleName.py', VAR, useDirPath=False)
include('C:/PythonModules//ModuleName.py', MODULE, asName="Name", useDirPath=False)
include('C:/PythonModules//ModuleName.py', MODULE, asName=None, useDirPath=False)
```

## 配置说明

### ETag 缓存配置
ETag 缓存无法在配置文件里直接关闭，访问 Python 文件可以通过 `set_disable_etag(True)` 关闭服务器对 Python 文件的 ETag 缓存。

### 已知限制
- 绑定域名功能已被注释掉
- 黑名单 IP 还未实现
- 还有许多地方有待优化

## 配置文件更新提醒

每个版本基本都会有配置文件的更新，由于 PWS 无法检测文件是否更新，需要手动将配置文件删除后再启动服务器重建。

## 更新日志

### v8.2 (当前版本)
- 修复了 Linux 下 Logger 的日志错误
- 修复了 Collection 传参过程被拷贝的问题
- 修复了 H2Response 中 HTTP2 的流量窗口更新对已经存在的 POST 流失效的问题
- 修复了 H1Response 响应过程中 socket 的 fd 未释放的问题，避免了 Too many open files 错误

### v8.1
修复了 HTTP/1.1 的长连接响应问题，统一了文件命名方式。  
更新了导入模块的方式，现在使用 "include" 方法导入模块默认为导入一个集合而非变量的方式。  
新增魔术导入的方式。  
*2023-7-18 00:38*

### v4.9
支持 HTTP2 的 POST, 文件上传(multipart/form-data)，并且增添新模式：  
在 .htm, .html 后缀的文档中可以使用 "<?py ... ?>" 执行 Python 代码。  
*2022-8-26 19:11*  

支持在单端口上绑定 HTTP,HTTPS 功能，但访问 HTTP 会强制跳转 HTTPS。  
*2022-10-7 12:36*

支持 HTTP2 特性流量窗口，更新有关 HTTP2 配置文件的内容。  
修复了多线程使得上传文件紊乱的问题。  
*2023-6-15 00:29*

### v4.7
支持多进程，设置网页响应对象缓存大小，修复断点续传抽风问题。  
ETag 缓存支持设置最小计算缓存大小，小于该大小阈值的文件将不启用 ETag。  
*2022-6-22 22:58*

关闭多进程（由于打包后多进程会突然开启数十个进程导致占用过高）  
*2022-6-24 21:35*

**v4.7 beta** 初步支持 HTTP2 协议  
*2022-8-9 00:28*

### v4.2
更新内容较多，修复各种英语语法问题，增添注释，使得代码更加易读。  
修复很多影响性能的问题。  
*2022-5-28 18:30*

### v3.2
更新使得 ExpHttpData 模块中 exp_headers 的使用频率降低，同时该问题也是导致一段时间后应用 CPU 使用率骤增不减的原因。  
*2022-3-27 14:16*

### v1.0
fl 函数可能因为传输大数据而内存溢出。  
*2021-01-02 20:31*

---

这是一个个人学习项目，如有问题欢迎提出。
