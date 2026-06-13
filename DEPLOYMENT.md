# 部署与使用指南

本文档说明如何在 Windows 本地部署 Hongguo Local Server，并通过 REST API
和开放平台 Web 页面访问搜索、榜单、剧集详情和视频模型。

项目包含两个独立服务：

- `Signer Service`：管理 MuMu、ADB、Frida、App attach、动态签名和 session 捕获。
- `API Server`：调用 Signer 完成上游请求，提供业务 REST API，并托管开放平台 Web 页面。

默认监听地址：

| 服务 | 地址 |
|---|---|
| API Server | `http://127.0.0.1:18000` |
| Signer Service | `http://127.0.0.1:18001` |
| Frida Server | `127.0.0.1:27042` |

前端开发态地址：

| 工程 | 地址 |
|---|---|
| `services/api-server/web` Vite dev server | `http://127.0.0.1:5173` |

## 1. 环境要求

- Windows 10/11 和 PowerShell 5.1 或更高版本。
- Python 3.10 或更高版本。
- [uv](https://docs.astral.sh/uv/)。
- MuMu 模拟器 12，目标实例已启用 root。
- 红果免费短剧 App，包名默认为 `com.phoenix.read`。
- App 已登录，并能够正常访问搜索、榜单或详情页面。
- Python `frida` 与 Android `frida-server` 版本完全一致。

项目当前固定使用：

```text
frida == 16.7.19
```

将 Android x86_64 二进制文件放到：

```text
services/signer-service/bin/frida-server-16.7.19-android-x86_64
```

不要将 Frida 二进制文件提交到 Git。

## 2. 安装依赖

在项目根目录执行：

```powershell
$env:UV_CACHE_DIR="$PWD\.uv-cache"
uv sync --all-packages
```

确认 Python 侧 Frida 版本：

```powershell
uv run python -c "import frida; print(frida.__version__)"
```

输出应为：

```text
16.7.19
```

## 3. 准备 MuMu

启动 MuMu 和红果 App，然后检查实例是否可连接。下面路径是默认示例；如果 MuMu
安装在其他目录，请替换为实际路径。

```powershell
& "D:\MuMu Player 12\shell\adb.exe" connect 127.0.0.1:16384
& "D:\MuMu Player 12\shell\adb.exe" devices -l
```

检查 root：

```powershell
& "D:\MuMu Player 12\shell\adb.exe" `
  -s 127.0.0.1:16384 shell "su -c id"
```

输出中应包含：

```text
uid=0(root)
```

## 4. 配置服务

### 4.1 Signer Service

可参考：

```text
services/signer-service/.env.example
```

在启动 Signer 的 PowerShell 窗口设置环境变量：

```powershell
$env:HONGGUO_SIGNER_MUMU_HOME="D:\MuMu Player 12"
$env:HONGGUO_SIGNER_VMINDEX="0"
$env:HONGGUO_SIGNER_PACKAGE_NAME="com.phoenix.read"
$env:HONGGUO_SIGNER_FRIDA_HOST="127.0.0.1"
$env:HONGGUO_SIGNER_FRIDA_PORT="27042"
$env:HONGGUO_SIGNER_FRIDA_SERVER_PATH="$PWD\services\signer-service\bin\frida-server-16.7.19-android-x86_64"
$env:HONGGUO_SIGNER_FRIDA_REMOTE_PATH="/data/local/tmp/frida-server"
$env:HONGGUO_SIGNER_WATCHDOG_INTERVAL="15"
$env:HONGGUO_SIGNER_SERVICE_TOKEN="请替换为随机长字符串"
```

`HONGGUO_SIGNER_SERVICE_TOKEN` 是 API Server 与 Signer Service 之间的 Bearer
Token。生产或共享环境中不要使用默认值。

### 4.2 API Server

在启动 API 的 PowerShell 窗口设置：

```powershell
$env:HONGGUO_API_SIGNER_URL="http://127.0.0.1:18001"
$env:HONGGUO_API_SIGNER_TOKEN="与 Signer Service 相同的随机长字符串"
$env:HONGGUO_API_SESSION_FILE=".local/session.json"
$env:HONGGUO_API_TIMEOUT_SECONDS="30"
```

不要提交 `.env`、`.local/session.json`、cookie、token 或其他本地运行状态。

## 5. 启动服务

启动顺序必须是：

```text
MuMu 和红果 App
        ↓
Signer Service
        ↓
捕获 session
        ↓
API Server
        ↓
可选：前端 dev server
```

### 5.1 启动 Signer Service

在项目根目录执行：

```powershell
.\services\signer-service\scripts\start.ps1
```

启动脚本会检查 MuMu、部署并启动匹配版本的 `frida-server`、attach 红果进程，
然后启动 Watchdog 和 HTTP 服务。

在另一个 PowerShell 窗口检查：

```powershell
Invoke-RestMethod http://127.0.0.1:18001/v1/health
```

正常结果应包含：

```json
{
  "ready": true,
  "app_pid": 22545
}
```

`app_pid` 会随 App 重启而变化。

### 5.2 捕获 session

保持 Signer Service 运行，在新的 PowerShell 窗口执行：

```powershell
$env:HONGGUO_API_SIGNER_TOKEN="与 Signer Service 相同的随机长字符串"
.\services\api-server\scripts\capture_session.ps1
```

脚本等待期间，在红果 App 中打开搜索、榜单或详情页面，触发一次自然网络请求。
捕获成功后会生成：

```text
.local/session.json
```

该文件可能包含设备标识、cookie 和 token，不得提交、记录或对外分享。

如需覆盖参数：

```powershell
.\services\api-server\scripts\capture_session.ps1 `
  -SignerUrl "http://127.0.0.1:18001" `
  -Token "与 Signer Service 相同的随机长字符串" `
  -OutputPath ".local/session.json" `
  -TimeoutMs 30000
```

### 5.3 启动 API Server

确保当前 PowerShell 已设置 API 环境变量，然后执行：

```powershell
.\services\api-server\scripts\start.ps1
```

检查 API：

```powershell
Invoke-RestMethod http://127.0.0.1:18000/health
```

预期响应：

```json
{
  "server": "ready"
}
```

如果已经构建过前端静态资源，API Server 还会直接托管这些页面：

- `http://127.0.0.1:18000/`
- `http://127.0.0.1:18000/docs`
- `http://127.0.0.1:18000/pricing`

### 5.4 启动前端开发服务器

开放平台前端源码位于：

```text
services/api-server/web
```

首次安装依赖：

```powershell
Set-Location services/api-server/web
npm install
```

启动 Vite dev server：

```powershell
npm run dev -- --host 127.0.0.1 --port 5173
```

默认访问地址：

```text
http://127.0.0.1:5173
```

本地开发时，Vite 已代理：

- `/api` -> `http://127.0.0.1:18000`
- `/health` -> `http://127.0.0.1:18000`

因此前后端联调通常需要同时运行：

1. `services/signer-service`
2. `services/api-server`
3. `services/api-server/web` 的 `npm run dev`

## 6. 使用 REST API

### 搜索

```powershell
Invoke-RestMethod `
  "http://127.0.0.1:18000/api/search?q=妈妈&page=1&page_size=30"
```

### 最新内容

```powershell
Invoke-RestMethod `
  "http://127.0.0.1:18000/api/latest?genre=short_play&today_only=true&page=1&page_size=30"
```

`genre` 支持：

```text
short_play
comic_series
ai_series
```

### 榜单

```powershell
Invoke-RestMethod `
  "http://127.0.0.1:18000/api/rank?board=hot&page=1&page_size=30"
```

`board` 支持：

```text
recommend
hot
new
must_watch
followed
hot_search
```

### 剧集详情

```powershell
Invoke-RestMethod `
  "http://127.0.0.1:18000/api/books/7647789981687106622"
```

### 单独获取剧集列表

```powershell
Invoke-RestMethod `
  "http://127.0.0.1:18000/api/books/7647789981687106622/episodes"
```

### 获取视频模型

从剧集列表取得 `video_id` 后调用：

```powershell
Invoke-RestMethod `
  "http://127.0.0.1:18000/api/videos/7647791950459849790?quality=1080p&fast=true"
```

`quality` 支持：

```text
360p
480p
540p
720p
1080p
```

`fast=true` 允许命中视频模型缓存；`fast=false` 请求新的视频模型，但不会关闭加密
检查。

成功响应包含所选清晰度和播放 URL：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "video_id": "7647791950459849790",
    "vid": "model-video-id",
    "vod_id": "stream-video-id",
    "requested_quality": "1080p",
    "selected_quality": "1080p",
    "url": "https://example.invalid/video.mp4",
    "backup_url": null,
    "encrypted": false,
    "expires_at": null
  },
  "cached": false,
  "request_id": "19f9550e-5b77-4131-850d-768ee73f4c95"
}
```

## 7. 视频播放地址

当前 `/api/videos/{video_id}` 会返回红果 APP 提供的播放地址。`data.url` 可以直接给播放器、下载器或复制到浏览器使用。

如果上游返回的是加密流，响应里的 `encrypted` 会标记为 `true`；这表示 URL 对应的文件仍然是 CENC 加密 MP4，能下载但不代表普通播放器可以直接解码。

当上游没有返回有效播放地址时，API 才会返回错误。

## 8. 常见错误

| HTTP | 错误码 | 处理方式 |
|---:|---|---|
| 400 | `invalid_cursor` | 丢弃无效 cursor，从第一页重新请求 |
| 401 | `session_expired` | 在 App 中触发请求并重新捕获 session |
| 404 | `book_not_found` | 检查 `series_id` |
| 404 | `video_not_found` | 检查剧集返回的 `video_id` |
| 422 | `encrypted_stream_unsupported` | 仅作兼容保留；当前接口优先返回播放地址 |
| 429 | `risk_controlled` | 降低频率，稍后重试并检查 session |
| 502 | `upstream_invalid_response` | 检查 App 版本、session 和上游响应变化 |
| 503 | `session_missing` | 执行 session 捕获脚本 |
| 503 | `signer_unavailable` | 检查 Signer、MuMu、Frida 和 Bearer Token |
| 504 | `upstream_timeout` | 检查网络和 `HONGGUO_API_TIMEOUT_SECONDS` |

更完整的排查步骤见：

```text
docs/troubleshooting.md
```

## 9. 安全与远程部署

- 两个服务默认只监听 `127.0.0.1`。
- Signer Service 拥有动态签名能力，不得作为匿名公网服务暴露。
- 不要公开 `.local/session.json`、cookie、token、签名 Header 或完整签名 URL。
- 远程部署时，应通过私有网络、SSH 隧道或带认证的反向代理访问。
- Signer 与 API 必须使用相同的强随机 Bearer Token。
- 不要把 Signer Service 与 API Server 合并为允许外部直接传入任意 URL 的签名代理。

## 10. 开发验证

普通离线验证不需要启动 MuMu：

```powershell
$env:UV_CACHE_DIR="$PWD\.uv-cache"
uv run ruff check .
uv run pytest -q
```

前端部分：

```powershell
Set-Location services/api-server/web
npm test
npm run typecheck
npm run build
Set-Location ..\..\..
```

live tests 默认跳过。只有环境已经就绪且明确需要真实上游验证时才执行：

```powershell
$env:HONGGUO_RUN_LIVE_TESTS="1"
$env:HONGGUO_LIVE_SERIES_ID="实际可用的 series_id"
uv run pytest services/api-server/tests/live services/signer-service/tests/live -v
```

## 11. 停止服务

分别在 API Server 和 Signer Service 的 PowerShell 窗口按 `Ctrl+C`。

下次启动时，如果 `.local/session.json` 仍然有效，可以直接启动两个服务；遇到
`session_missing` 或 `session_expired` 时重新捕获 session。
