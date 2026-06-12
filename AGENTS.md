# Codex 开发指南

## 沟通与范围

- 与用户沟通、进度更新、提问和最终答复默认使用简体中文。
- 代码标识符、命令、路径、协议字段和必要技术术语保留原文。
- 先阅读相关代码和文档，再修改；保持改动聚焦，不做无关重构。
- 运行细节参见根目录及各服务 README，故障排查参见 `docs/troubleshooting.md`。

## 项目结构

- `services/api-server`：FastAPI 业务 API，负责 session、上游请求、解析、缓存和错误映射。
- `services/signer-service`：负责 MuMu、ADB、Frida、App attach、动态签名和 session 捕获。
- `packages/hongguo-contracts`：仅存放两个服务共享的版本化 HTTP 数据模型。
- API Server 不得引入设备或 Frida 实现；Signer Service 不承担搜索、详情等业务解析。
- 跨服务协议变更应先修改 contracts，并同步更新双方实现和测试。

## 开发约定

- 使用 Python 3.10+、`uv`、Pydantic v2、pytest 和 Ruff；遵循现有模块与依赖注入模式。
- 路由层只做参数校验、服务调用和响应包装；上游数据转换放在对应 parser。
- 配置通过 `pydantic-settings` 和 `HONGGUO_*` 环境变量管理，不硬编码本地路径或凭据。
- 上游请求必须先确定最终 URL、Header 和请求体，再调用 Signer；签名后不得修改签名材料。
- Python `frida` 与 Android `frida-server` 版本必须完全一致，当前固定为 `16.7.19`。
- 行为、接口或配置变化时，同步更新测试、`.env.example` 和相关文档。

## 验证

```powershell
$env:UV_CACHE_DIR="$PWD\.uv-cache"
uv sync --all-packages
uv run ruff check .
uv run pytest -q
```

- 修改范围较小时先运行对应目录或测试文件，再运行完整离线验证。
- live tests 默认跳过；仅在用户明确要求且环境就绪时设置 `HONGGUO_RUN_LIVE_TESTS=1`。
- 不为通过测试而削弱断言、吞掉异常或绕过真实行为。

## 安全

- 不提交或输出 `.local/`、session、cookie、token、签名 Header、完整签名 URL 或私有响应正文。
- 不提交 `.env`、Frida 二进制文件、日志或其他本地运行状态；仅维护脱敏的 `.env.example`。
- 保持 Header allowlist、受信任域名校验、Bearer Token 和签名操作串行化约束。
- 服务默认只监听回环地址；不得把 Signer 作为匿名公网服务暴露。
- 项目不实现离线 X-Argus/X-Gorgon 算法，也不实现 DRM/CENC 解密。

## Git 与提交

- 执行 Git 历史、提交或推送操作前，先确认 `.git` 存在且当前目录属于仓库。
- 命令失败或目录不是 Git 仓库时，如实说明，不得伪造提交、推送或测试结果。
- 提交前检查 `git status` 和 diff，区分本次修改与用户已有修改，只暂存任务相关文件。
- 未经明确授权，不回滚、覆盖或删除用户已有改动；禁止使用破坏性 Git 命令。
- 提交信息使用简洁中文和准确前缀，如 `feat`、`fix`、`style`、`docs`、`refactor`、
  `test` 或 `chore`。
