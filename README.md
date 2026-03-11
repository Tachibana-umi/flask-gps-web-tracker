# Web GPS Track Demo

一个基于 Flask + SQLite 的简单 Web 应用，用于采集浏览器定位并在地图上展示运动轨迹。

![示例1](/demo_for_test/graphic0.png)
![示例2](/demo_for_test/graphic1.png)

## 项目简介

这是一个用于学习 Web 开发的练习项目，实现了浏览器定位数据的采集、存储与可视化。

主要功能包括：

- 浏览器获取 GPS 定位信息
- 实时绘制运动轨迹
- 使用 Kalman Filter 对轨迹进行平滑处理
- 将定位数据存储到 SQLite 数据库
- 通过 Flask 提供后端接口
- 根据登录行为将与用户关联的数据进行储存

## 技术栈

前端：
- HTML
- CSS
- JavaScript

后端：
- Flask

数据库：
- SQLite

## 项目结构
```
project/
│
├─ static/          # 前端资源
│   ├─ favicon.ico
│   ├─ index.html
│   ├─ script.js
│   ├─ style.css
│   └─ kalman_fliter/   #kalmam库
│           ├─kalman.js
│           └─kalman.min.js
│
├─ app.db           # SQLite数据库
├─ web.py           #flask后端      
│
└─ README.md
```

## 运行方法

### 1.克隆仓库
在终端运行
```bash
git clone https://github.com/tachibana-umi/flask-gps-web-tracker.git
```

### 2.环境准备
确保你的python版本支持flask，后在终端运行
```bash
pip install flask
```

### 3.启动程序
运行程序
```bash
python web.py
```
程序运行后服务器会运行在`http://127.0.0.1:5000`。

### 4.移动端访问
*建议通过移动端访问，经体验笔记本电脑的GPS定位精度一般在100m左右，而这通常会被当做无效数据而被处理掉，以至于地图上迟迟不见marker。*<br>

由于手机浏览器获取 GPS 权限严格要求 HTTPS 环境，故要使用内网穿透工具将本地 5000 端口映射到公网，下面以ngrok为例:<br>

#### 第一步：注册与下载
1. 访问 <a href="https://ngrok.com/" target="_blank">Ngrok 官网</a>，注册一个免费账号。
2. 登录后，在 Dashboard 下载对应你操作系统的 Ngrok 客户端（Windows 为 `.zip`，解压后是一个 `ngrok.exe` 文件）。

#### 第二步：配置 AuthToken (身份认证)
这是为了告诉 Ngrok 服务器你是合法用户。
1. 在 Ngrok 网页后台的 "Getting Started" -> "Your Authtoken" 中复制你的专属 Token。
2. 打开终端（命令提示符/PowerShell），进入 `ngrok.exe` 所在的目录，运行以下命令（只需运行一次，它会保存在本地）：
```bash
ngrok config add-authtoken 你的专属Token
```
#### 第三步：使用方法 (日常启动流程)
**前提条件**<br>
确保你的 Python Flask 服务已经启动，并且正在监听本地的某个端口（以 5000 端口为例）:
<br>
打开 `ngrok.exe` 并输入
```
ngrok http 5000
```
运行成功后，终端会变成一个监控界面，找到 Forwarding 这一行：
```Plaintext
Session Status                online
Account                       YourName (Plan: Free)
Version                       3.x.x
Region                        United States (us)
Forwarding                    [https://xxxx-xxxx.ngrok-free.app](https://xxxx-xxxx.ngrok-free.app) -> http://localhost:5000
```
`https://xxxx-xxxx.ngrok-free.app`就是你的公网地址，随后通过移动设备的浏览器访问即可 

*（建议使用谷歌浏览器）*



## 后续优化打算

- [ ] 让用户直观访问历史轨迹，展示历史轨迹连线
- [ ] 单次轨迹快速导出为 GPX / CSV 文件
- [ ] 接口速率限制，防止恶意频繁调用
- [ ] 断网时将失败数据暂存至 localStorage / IndexedDB，网络恢复后自动重传
- [ ] 按时间段筛选轨迹
- [ ]  PWA 化，支持添加到手机桌面并在弱网环境下正常使用
- [ ] 尝试vue等成熟的前端框架


## 依赖项目

本项目中的卡尔曼滤波实现参考并使用了以下开源项目:

kalmanjs  
https://github.com/wouterbulten/kalmanjs

作者：Wouter Bulten  
协议：MIT License
