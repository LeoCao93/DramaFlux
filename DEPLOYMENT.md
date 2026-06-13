# DramaFlux 部署与联调运行手册

本文档面向本地部署、联调和协作排障场景，聚焦环境准备、配置、启动顺序、验证方式与安全注意事项。接口字段和更细的服务实现说明请分别参考 `services/api-server/README.md`、`services/signer-service/README.md` 与 `docs/troubleshooting.md`。

## 1. 适用范围

当前手册适用于 Windows 本地开发环境，覆盖以下运行链路：

- MuMu 模拟器与目标 App 准备
- Signer Service 启动与健康检查
- session 捕获
- API Server 启动与基础验证
- 可选前端 dev server 联调

默认本地地址：

| 组件 | 地址 |
|---|---|
| API Server | `http://127.0.0.1:18000` |
| Signer Service | `http://127.0.0.1:18001` |
| 前端 dev server | `http://127.0.0.1:5173` |

## 2. 环境要求

- Windows 10/11
- PowerShell 5.1 或更高版本
- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20.17+ 和 npm 11+，仅在执行前端 dev server 或构建 API 托管页时需要
- MuMu 模拟器 12，目标实例已启用 root
- 目标 App 已安装、已登录，并能正常打开搜索、榜单或详情页面
- Python `frida` 与 Android `frida-server` 版本完全一致

当前固定版本：

```text
frida == 16.7.19
```

## 3. 安装依赖

在仓库根目录执行：

```powershell
$env:UV_CACHE_DIR="$PWD\.uv-cache"
uv sync --all-packages
```

确认 Python 侧 Frida 版本：

```powershell
uv run python -c "import frida; print(frida.__version__)"
```

预期输出：

```text
16.7.19
```

## 4. 准备 MuMu、ADB、Frida 与 App

先启动 MuMu 和目标 App，再检查模拟器连接、root 与 Frida 二进制是否就绪。

以下路径仅为示例，请按本机安装位置调整：

- `D:\MuMu Player 12\shell\adb.exe`
- `services/signer-service/bin/frida-server-16.7.19-android-x86_64`

示例命令：

```powershell
& "D:\MuMu Player 12\shell\adb.exe" connect 127.0.0.1:16384
& "D:\MuMu Player 12\shell\adb.exe" devices -l
& "D:\MuMu Player 12\shell\adb.exe" -s 127.0.0.1:16384 shell "su -c id"
```

最后一条命令的输出应包含：

```text
uid=0(root)
```

将 Android x86_64 的 `frida-server` 放到仓库约定位置：

```text
services/signer-service/bin/frida-server-16.7.19-android-x86_64
```

不要提交 Frida 二进制、`.env`、`.local/`、session、cookie、token 或日志文件。

遇到 ADB、root、Frida 版本不一致或 App 进程异常时，优先查看 `docs/troubleshooting.md`。

## 5. 配置服务

### 5.1 配置 Signer Service

参考文件：

```text
services/signer-service/.env.example
```

以下命令默认在仓库根目录的 PowerShell 窗口执行。下面的本机路径仍然只是示例，请按实际安装位置调整：

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

说明：

- `HONGGUO_SIGNER_SERVICE_TOKEN` 用于保护 Signer API，生产或共享环境不要使用弱口令。
- `HONGGUO_SIGNER_FRIDA_SERVER_PATH` 推荐使用仓库相对位置拼接，例如 `$PWD\services\signer-service\bin\...`。

### 5.2 配置 API Server

参考文件：

```text
services/api-server/.env.example
```

在启动 API 的 PowerShell 窗口设置：

```powershell
$env:HONGGUO_API_SIGNER_URL="http://127.0.0.1:18001"
$env:HONGGUO_API_SIGNER_TOKEN="与 Signer Service 相同的随机长字符串"
$env:HONGGUO_API_SESSION_FILE="$PWD\.local\session.json"
$env:HONGGUO_API_TIMEOUT_SECONDS="30"
```

说明：

- `HONGGUO_API_SIGNER_TOKEN` 必须与 `HONGGUO_SIGNER_SERVICE_TOKEN` 一致。
- `HONGGUO_API_SESSION_FILE` 会保存本地 session 快照，不要提交；这里使用 `$PWD` 是为了明确锚定到仓库根目录。

## 6. 启动顺序

启动顺序以当前真实行为为准：

```text
MuMu / App
    ->
Signer Service
    ->
捕获 session
    ->
API Server
    ->
可选：前端 dev server
```

### 6.1 启动 Signer Service

在仓库根目录执行：

```powershell
.\services\signer-service\scripts\start.ps1
```

Signer 启动后验证：

```powershell
Invoke-RestMethod http://127.0.0.1:18001/v1/health
```

预期响应示例：

```json
{
  "ready": true,
  "app_pid": 22545
}
```

`app_pid` 会随 App 重启而变化。

### 6.2 捕获 session

保持 Signer Service 运行，在新的 PowerShell 窗口执行：

```powershell
$env:HONGGUO_API_SIGNER_TOKEN="与 Signer Service 相同的随机长字符串"
.\services\api-server\scripts\capture_session.ps1
```

执行后在 App 内触发一次自然请求，例如打开搜索、榜单或详情页面。成功后会生成：

```text
.local/session.json
```

如需覆盖默认参数，可显式传参：

```powershell
.\services\api-server\scripts\capture_session.ps1 `
  -SignerUrl "http://127.0.0.1:18001" `
  -Token "与 Signer Service 相同的随机长字符串" `
  -OutputPath ".local/session.json" `
  -TimeoutMs 30000
```

### 6.3 启动 API Server

确保 API 所需环境变量已经设置，然后执行：

```powershell
.\services\api-server\scripts\start.ps1
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:18000/health
```

预期响应：

```json
{
  "server": "ready"
}
```

说明：

- `http://127.0.0.1:18000/health` 只代表 API 进程可用，不代表 Signer、session 或业务链路已经完全可用。
- 若健康检查通过但业务请求失败，优先检查 Signer、session 和上游响应。

如果前端静态资源已构建，API Server 还会托管以下页面：

- `http://127.0.0.1:18000/`
- `http://127.0.0.1:18000/docs`
- `http://127.0.0.1:18000/pricing`

### 6.4 可选：启动前端 dev server

前端源码位于：

```text
services/api-server/web
```

首次安装依赖：

```powershell
Set-Location services/api-server/web
npm install
```

启动开发服务器：

```powershell
npm run dev -- --host 127.0.0.1 --port 5173
```

访问地址：

```text
http://127.0.0.1:5173
```

说明：

- 这一步需要 Node.js 和 npm。
- 如果只是验证后端部署，可以跳过这一节。

## 7. 验证 API 与 Web

这里分两层验证，避免把进程健康误当成端到端可用。

1. 进程健康
   - Signer 健康检查：`http://127.0.0.1:18001/v1/health`
   - API 健康检查：`http://127.0.0.1:18000/health`
   - 若前端静态资源已构建，再检查 API 托管页面：`http://127.0.0.1:18000/`
   - 若需要前端联调，再检查前端 dev server：`http://127.0.0.1:5173`

2. 端到端可用
   - 至少成功执行一次业务 API 调用并得到 `code=200`
   - 对于详情类接口，先用搜索结果拿到实际 `series_id` 或 `video_id` 再调用，不要依赖固定样例 ID

```powershell
Invoke-RestMethod "http://127.0.0.1:18000/api/search?q=妈妈&page=1&page_size=30"
```

如果这里只是验证部署链路，不需要把所有业务接口逐个调用一遍；更完整的接口说明请看 `services/api-server/README.md`。

## 8. 前后端联调

当前前端开发态默认通过 Vite 代理后端接口，API Server 托管页与 dev server 是两种不同入口：

- `/api` -> `http://127.0.0.1:18000`
- `/health` -> `http://127.0.0.1:18000`

因此本地联调通常需要同时运行：

1. MuMu 与目标 App
2. `services/signer-service`
3. `services/api-server`
4. `services/api-server/web` 的 `npm run dev`（可选）

联调时一般只需要记住两件事：

- 前端开发页：`http://127.0.0.1:5173`
- API 托管页：`http://127.0.0.1:18000/`

通过浏览器或 PowerShell 验证 `/health` 与 `/api/*` 即可；更细的页面和接口说明分别看 `services/api-server/README.md`。

## 9. 排障入口

部署阶段常见问题包括：

- ADB 不可用或连错实例
- root 权限不可用
- Frida 版本不一致
- App PID 变化导致 Signer 未 ready
- session 捕获超时或已过期

排障步骤请优先参考：

```text
docs/troubleshooting.md
```

如果是服务内部行为、配置字段或 API 语义问题，再回看：

- `services/signer-service/README.md`
- `services/api-server/README.md`

## 10. 安全与远程访问

- 两个服务默认只监听 `127.0.0.1`。
- Signer Service 具备动态签名能力，不应作为匿名公网服务暴露。
- 不要泄露 `.local/session.json`、cookie、token、签名 Header 或完整签名 URL。
- API 与 Signer 必须使用相同的强随机 Bearer Token。
- 如需远程访问，优先使用私有网络、SSH 隧道或带认证的反向代理。
- 不要把 Signer 改造成允许外部直接传入任意 URL 的通用签名代理。

## 11. 停止与重启

停止服务时，分别在 API Server、Signer Service 和前端 dev server 的 PowerShell 窗口按 `Ctrl+C`。

重启建议：

1. 如果 App 或 Frida 状态异常，先确认 MuMu 与 App 正常，再重启 Signer。
2. 如果出现 `session_missing` 或 `session_expired`，重新执行 session 捕获。
3. 如果 `.local/session.json` 仍然有效，可直接重启 API Server 和前端 dev server。
