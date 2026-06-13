# DramaFlux Signer Service

`services/signer-service` 是 DramaFlux 的设备侧签名服务，负责连接 MuMu、校验 root、启动并维护 Frida、attach 红果 App 进程，并为 API Server 提供动态签名和 session 捕获能力。

## 它负责什么

- 发现并连接 MuMu 实例
- 校验目标实例的 root 能力
- 部署并启动匹配版本的 `frida-server`
- attach 红果 App 进程并加载 `oracle.js`
- 提供动态签名、session 捕获和手工重连接口
- 通过 Watchdog 监测 App PID、Frida session 和脚本状态

## 它不负责什么

- 搜索、排行、详情、视频地址解析
- API Server 的业务缓存与路由
- DRM / CENC 解密
- 作为匿名公网签名代理暴露

这些业务逻辑属于 API Server 或上游平台。

## 项目结构与模块说明

```text
services/signer-service
├── scripts/
│   ├── start.ps1              # 启动 Signer Service
│   └── check_environment.ps1  # 检查 MuMu / ADB / Frida / token 环境
├── src/hongguo_signer/
│   ├── main.py                # FastAPI 入口与路由挂载
│   ├── bootstrap_app.py       # 组装设备、Frida 和 Watchdog
│   ├── config.py              # pydantic-settings 配置
│   ├── security.py            # Bearer Token 和 header allowlist
│   ├── device/
│   │   ├── adb.py             # ADB 调用封装
│   │   ├── manager.py         # 设备与实例管理
│   │   └── mumu_cli.py        # MuMu 命令行适配
│   └── frida_runtime/
│       ├── bootstrap.py       # Frida 启动与附着初始化
│       ├── manager.py         # Frida session 管理
│       ├── watchdog.py        # 进程 / session / 脚本守护
│       └── oracle.js          # 注入到 App 中的脚本
├── tests/                     # 单测、集成测试与 live tests
└── .env.example               # 本地配置样例
```

模块职责可以这样理解：

- `bootstrap_app.py` 负责把 MuMu、ADB、root、Frida 和 Watchdog 串起来
- `device/` 只负责设备发现、连接和命令执行
- `frida_runtime/` 只负责 Frida 生命周期、脚本加载和健康守护
- `security.py` 负责请求鉴权和允许的 header 白名单
- `main.py` 只暴露 HTTP 接口，不承载设备细节

## 静态架构图

```text
API Server
     │
     │  POST /v1/sign
     │  POST /v1/session/capture
     │  POST /v1/admin/reconnect
     ▼
Signer Service (18001)
     ├── Bearer Token 鉴权
     ├── security.py header allowlist
     ├── device manager
     │     ├── MuMu 实例发现
     │     ├── ADB 连接
     │     └── root 检查
     ├── frida bootstrap / manager
     │     ├── 部署 frida-server
     │     ├── attach 红果 App 进程
     │     └── load oracle.js
     └── watchdog
           ├── 监测 App PID
           ├── 监测 Frida session
           └── 失效后触发 reconnect

Signer Service ──> 返回签名头 / session snapshot
```

## 公开接口

Signer Service 当前只提供以下 HTTP 接口：

```text
GET  /v1/health
POST /v1/sign
POST /v1/session/capture
POST /v1/admin/reconnect
```

除 `/v1/health` 外，其余接口都需要 Bearer Token。

### `/v1/health`

返回当前 readiness 和 App PID。

### `/v1/sign`

输入最终 URL 和请求头，返回签名后的安全头。

### `/v1/session/capture`

捕获一次自然网络请求并保存为 session snapshot。该接口只接受来自 `fqnovel.com` 的可信请求，并会过滤允许的 query/header 字段。

### `/v1/admin/reconnect`

在 App 重启、Frida detached 或脚本失效后，尝试重新 attach。

## 配置

参考文件：

```text
services/signer-service/.env.example
```

常用环境变量：

```dotenv
HONGGUO_SIGNER_MUMU_HOME=D:\MuMu Player 12
HONGGUO_SIGNER_VMINDEX=0
HONGGUO_SIGNER_PACKAGE_NAME=com.phoenix.read
HONGGUO_SIGNER_FRIDA_HOST=127.0.0.1
HONGGUO_SIGNER_FRIDA_PORT=27042
HONGGUO_SIGNER_FRIDA_SERVER_PATH=services/signer-service/bin/frida-server-16.7.19-android-x86_64
HONGGUO_SIGNER_FRIDA_REMOTE_PATH=/data/local/tmp/frida-server
HONGGUO_SIGNER_WATCHDOG_INTERVAL=15
HONGGUO_SIGNER_SERVICE_TOKEN=local-development
```

说明：

- `HONGGUO_SIGNER_SERVICE_TOKEN` 保护签名接口和 session 捕获接口
- `HONGGUO_SIGNER_FRIDA_SERVER_PATH` 需要与 Python 侧 Frida 版本一致
- `HONGGUO_SIGNER_FRIDA_REMOTE_PATH` 是部署到 Android 设备内的路径
- `HONGGUO_SIGNER_WATCHDOG_INTERVAL` 默认 15 秒

## 快速开始

在仓库根目录安装依赖：

```powershell
$env:UV_CACHE_DIR="$PWD\.uv-cache"
uv sync --all-packages
```

准备 token 并启动服务：

```powershell
$env:HONGGUO_SIGNER_SERVICE_TOKEN="<your-token>"
.\services\signer-service\scripts\start.ps1
```

启动脚本会自动：

1. 发现 MuMu 实例
2. 连接 ADB 并检查 root
3. 确认红果 App 正在运行
4. 部署并启动 `frida-server`
5. attach 红果 App 并加载 `oracle.js`
6. 启动 Watchdog 和 HTTP 服务

## 验证

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:18001/v1/health
```

预期响应：

```json
{
  "ready": true,
  "app_pid": 22545
}
```

如果 `ready` 是 `false`，优先检查：

- MuMu 是否启动
- 红果 App 是否在运行
- ADB 是否连接到正确实例
- Python Frida 与 Android `frida-server` 是否都是 `16.7.19`

## 典型流程

1. 启动 MuMu 和红果 App
2. 启动 Signer Service
3. 通过 API Server 捕获 session
4. 由 API Server 调用 `/v1/sign` 处理业务请求
5. App 重启或 Frida detached 时，调用 `/v1/admin/reconnect`

## 测试

```powershell
$env:UV_CACHE_DIR="$PWD\.uv-cache"
uv sync --all-packages
uv run pytest services/signer-service/tests -q
uv run ruff check services/signer-service
```

真实签名和真实 session 捕获的 live tests 默认跳过；只有在环境已经就绪时才启用。

## 安全与边界

- 服务默认只监听 `127.0.0.1`
- Signer Service 不应作为匿名公网服务暴露
- 不要提交 `.env`、`.local/`、session、cookie、token、日志或 Frida 二进制
- 公开接口只返回允许的签名头和 session 快照，不保存短期动态签名状态

## 常见问题

### `ready=false`

先确认红果 App 仍在运行，再尝试 `/v1/admin/reconnect`。

### Frida 版本不一致

确认：

```powershell
uv run --project services/signer-service python -c "import frida; print(frida.__version__)"
& "D:\MuMu Player 12\shell\adb.exe" -s 127.0.0.1:16384 shell "su -c '/data/local/tmp/frida-server --version'"
```

两边都应为 `16.7.19`。

### session 捕获超时

在捕获等待期间，主动在红果 App 中打开搜索、榜单或详情页，触发一次自然网络请求。

更完整的部署与排障说明见：

```text
DEPLOYMENT.md
docs/troubleshooting.md
```
