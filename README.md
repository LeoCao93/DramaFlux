# Hongguo Local Server

本项目由两个可独立部署的 Python 服务组成：

- `signer-service`：管理 MuMu、ADB、root、frida-server 和 `oracle.js`。
- `api-server`：保存会话、构造签名请求并提供搜索、上新、排行、详情和视频接口。
- `hongguo-contracts`：只保存两个服务之间的版本化 HTTP 数据模型。

## 本地启动

要求 Python 3.10+、uv、MuMu 12，且红果应用已登录并保持运行。

```powershell
$env:UV_CACHE_DIR="D:\Codex\hongguo-video\.uv-cache"
uv sync --all-packages
```

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

验证：

```powershell
Invoke-RestMethod http://127.0.0.1:18000/health
Invoke-RestMethod "http://127.0.0.1:18000/api/search?q=妈妈"
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

本项目不实现 X-Argus/X-Gorgon 的离线算法，也不处理 DRM/CENC 解密。
