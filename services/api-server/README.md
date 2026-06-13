# DramaFlux API Server

`services/api-server` 是 DramaFlux 的业务服务层，负责把本地 session、Signer Service 和上游内容接口串成稳定的 HTTP API，同时托管开放平台 Web 页面。

## 它负责什么

- 对外提供稳定的业务 API
- 读取本地 session 快照
- 调用 Signer Service 获取动态签名结果
- 请求并解析上游内容接口
- 托管 `services/api-server/web` 构建后的 Web 页面

## 它不负责什么

- 设备控制、ADB、Frida 注入
- 动态签名算法实现
- DRM / CENC 解密
- 搜索、详情、排行等业务解析以外的设备侧逻辑

这些能力分别由 `services/signer-service` 和上游服务承担。

## 项目结构与模块说明

```text
services/api-server
├── scripts/
│   ├── start.ps1            # 启动 API Server
│   └── capture_session.ps1   # 通过 Signer Service 捕获 session
├── src/hongguo_api/
│   ├── main.py              # FastAPI 入口，挂载文档页与路由
│   ├── bootstrap_app.py     # 组装 session、Signer、上游 client 和缓存
│   ├── config.py            # pydantic-settings 配置
│   ├── errors.py            # 错误映射与统一异常
│   ├── cache.py             # 响应缓存
│   ├── pagination.py        # 分页参数与分页结果
│   ├── models.py            # 共享数据模型
│   ├── api/
│   │   ├── routes.py        # 业务路由
│   │   └── schemas.py       # 请求/响应 schema
│   ├── session/
│   │   ├── parser.py        # session 文件解析
│   │   └── storage.py       # session 读写与状态判断
│   ├── signer/
│   │   └── client.py        # 调用 Signer Service
│   ├── upstream/
│   │   ├── client.py        # 组装上游请求
│   │   └── transport.py     # 带签名的 HTTP transport
│   ├── parsers/             # search/latest/rank/detail/video 解析
│   └── web.py               # 托管前端静态资源与页面路由
├── web/                     # Vite + React 开放平台前端
└── tests/                   # 单测、集成测试与 live tests
```

模块之间的职责很简单：

- `bootstrap_app.py` 把配置、session、Signer 和上游 client 串起来
- `api/routes.py` 只负责参数校验、服务调用和响应包装
- `parsers/` 专门做上游响应转换，避免路由层变胖
- `session/` 只处理本地 session 文件，不碰业务解析
- `web/` 是独立前端，API Server 只负责托管构建产物和页面入口

## 静态架构图

```text
浏览器 / 前端
     │
     ├── Web dev server (5173)
     │        │ 代理 /api、/health
     │        ▼
     │   API Server (18000)
     │        ├── /health
     │        ├── /api/search, /api/latest, /api/rank
     │        ├── /api/books/{series_id}
     │        ├── /api/books/{series_id}/episodes
     │        ├── /api/videos/{video_id}
     │        ├── session storage (.local/session.json)
     │        ├── Signer client (18001)
     │        └── upstream client + parsers + cache
     │
     └── 托管静态页面
              ├── /
              ├── /docs
              └── /pricing

API Server ──> Signer Service (18001) ──> 返回签名头 / session snapshot
API Server ──> 上游内容服务 ──> 解析为统一业务模型
```

## 公开接口

当前公开业务接口如下：

```text
GET /health
GET /api/search?q=&page=&page_size=&cursor=
GET /api/latest?genre=short_play&today_only=true&page=&page_size=&cursor=
GET /api/rank?board=hot&page=&page_size=&cursor=
GET /api/books/{series_id}
GET /api/books/{series_id}/episodes
GET /api/videos/{video_id}?quality=1080p&fast=true
```

Health、OpenAPI 与 Web 页面相关入口：

```text
GET /health
GET /internal/docs
GET /redoc
GET /openapi.json
GET /
GET /docs
GET /pricing
```

其中 `/internal/docs`、`/redoc`、`/openapi.json` 是服务内部文档入口，`/`、`/docs`、`/pricing` 是托管的 Web 页面。

## Web 前端

前端源码位于：

```text
services/api-server/web
```

开发态通过 Vite 运行：

```text
http://127.0.0.1:5173
```

本地开发时，Vite 会把以下请求代理到 API Server：

- `/api` -> `http://127.0.0.1:18000`
- `/health` -> `http://127.0.0.1:18000`

API Server 也会托管构建后的前端资源：

- `http://127.0.0.1:18000/`
- `http://127.0.0.1:18000/docs`
- `http://127.0.0.1:18000/pricing`

## 配置

参考文件：

```text
services/api-server/.env.example
```

常用环境变量：

```dotenv
HONGGUO_API_SIGNER_URL=http://127.0.0.1:18001
HONGGUO_API_SIGNER_TOKEN=local-development
HONGGUO_API_SESSION_FILE=.local/session.json
HONGGUO_API_TIMEOUT_SECONDS=30
```

说明：

- `HONGGUO_API_SIGNER_URL` 指向 Signer Service
- `HONGGUO_API_SIGNER_TOKEN` 必须与 Signer Service 使用同一 token
- `HONGGUO_API_SESSION_FILE` 保存本地 session 快照
- `HONGGUO_API_TIMEOUT_SECONDS` 控制上游请求超时

## 快速开始

在仓库根目录安装依赖：

```powershell
$env:UV_CACHE_DIR="$PWD\.uv-cache"
uv sync --all-packages
```

准备共享 token 并启动 Signer Service：

```powershell
$env:HONGGUO_SIGNER_SERVICE_TOKEN="<your-token>"
$env:HONGGUO_API_SIGNER_TOKEN=$env:HONGGUO_SIGNER_SERVICE_TOKEN
.\services\signer-service\scripts\start.ps1
```

捕获一次 session：

```powershell
$env:HONGGUO_API_SIGNER_TOKEN="<same-token-as-signer>"
.\services\api-server\scripts\capture_session.ps1
```

`capture_session.ps1` 默认读取 `HONGGUO_API_SIGNER_TOKEN`，也可以显式传 `-Token`；无论哪种方式，都必须与 Signer Service 使用同一 token。

启动 API Server：

```powershell
.\services\api-server\scripts\start.ps1
```

如果需要前端热更新，再启动 Web dev server：

```powershell
Set-Location services/api-server/web
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

## 验证

最小验证顺序：

1. `http://127.0.0.1:18001/v1/health`
2. `http://127.0.0.1:18000/health`
3. `http://127.0.0.1:18000/`
4. `http://127.0.0.1:5173`

建议再执行一次业务 API 调用确认链路可用：

```powershell
Invoke-RestMethod "http://127.0.0.1:18000/api/search?q=妈妈&page=1&page_size=30"
```

如果你要验证详情或视频接口，先从搜索结果里拿真实 `series_id` / `video_id`，不要依赖固定样例 ID。

## 开发验证

```powershell
$env:UV_CACHE_DIR="$PWD\.uv-cache"
uv run ruff check services/api-server
uv run pytest services/api-server/tests -q
```

前端部分：

```powershell
Set-Location services/api-server/web
npm test
npm run typecheck
npm run build
```

## 代码边界

- API Server 不引入设备控制或 Frida 实现
- 协议变化先改 `packages/hongguo-contracts`
- 业务路由、缓存、session 读取、Signer 调用和上游解析都在 `services/api-server` 内完成

## 常见问题

- `session_missing` 或 `session_expired` 时，先重新捕获 session
- `signer_unavailable` 时，检查 Signer Service、MuMu、Frida 和 token 是否一致
- `upstream_timeout` 时，检查网络和 `HONGGUO_API_TIMEOUT_SECONDS`

更完整的排障说明见：

```text
docs/troubleshooting.md
```
