# Hongguo Local Server

完整的环境准备、启动顺序、接口示例和故障处理见
[部署与使用指南](DEPLOYMENT.md)。

本项目由两个可独立部署的 Python 服务组成：

- `signer-service`：管理 MuMu、ADB、root、frida-server 和 `oracle.js`。
- `api-server`：保存会话、构造签名请求并提供搜索、上新、排行、详情、视频接口，以及托管开放平台 Web 页面。
- `hongguo-contracts`：只保存两个服务之间的版本化 HTTP 数据模型。

前端 Web 工程位于：

```text
services/api-server/web
```

常用访问地址：

- 开发态前端：`http://127.0.0.1:5173`
- API Server 托管页面：`http://127.0.0.1:18000/`
- Signer Service：`http://127.0.0.1:18001`

## 本地启动

要求 Python 3.10+、uv、MuMu 12，且红果应用已登录并保持运行。

```powershell
$env:UV_CACHE_DIR="D:\Codex\hongguo-video\.uv-cache"
uv sync --all-packages
```

视频接口直接返回红果 APP 给出的播放地址，`data.url` 可直接交给播放器或下载器；若上游给到的是加密流，会通过 `encrypted` 标记出来。

将与 Python `frida` 版本完全一致的 Android x86_64 二进制放到：

```text
services/signer-service/bin/frida-server-<version>-android-x86_64
```

启动 Signer：

```powershell
$env:HONGGUO_SIGNER_SERVICE_TOKEN="请替换为随机长字符串"
$env:HONGGUO_SIGNER_SERVICE_TOKEN
.\services\signer-service\scripts\start.ps1
```

捕获会话时，在红果 App 内触发一次列表或详情请求：

```powershell
$env:HONGGUO_API_SIGNER_TOKEN=$env:HONGGUO_SIGNER_SERVICE_TOKEN
.\services\api-server\scripts\capture_session.ps1
```

启动 API：

```powershell
.\services\api-server\scripts\start.ps1
```

如需联调前端，再开一个 PowerShell 窗口启动 Web dev server：

```powershell
Set-Location services/api-server/web
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

验证：

```powershell
Invoke-RestMethod http://127.0.0.1:18000/health
Invoke-RestMethod "http://127.0.0.1:18000/api/search?q=妈妈"
Invoke-WebRequest http://127.0.0.1:18000/ -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:5173/ -UseBasicParsing
```

服务默认只监听回环地址。不要把 Signer 作为匿名公网签名服务。

## 接口

```text
GET /api/search?q=&cursor=
GET /api/latest?genre=short_play&today_only=true&cursor=
GET /api/rank?board=hot&cursor=
GET /api/books/{series_id}
GET /api/books/{series_id}/episodes
GET /api/videos/{video_id}?quality=1080p
```

本项目不实现 X-Argus/X-Gorgon 的离线算法，也不处理 DRM/CENC 解密；`/api/videos/{video_id}` 返回红果 APP 提供的播放地址。
