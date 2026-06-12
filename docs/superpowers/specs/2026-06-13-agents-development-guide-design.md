# AGENTS.md 开发指南设计

## 目标

在仓库根目录创建 `AGENTS.md`，为 Codex 提供简洁、明确且贴合本项目的开发与验证规范。
最终文件以必要规则为主，目标控制在 80 行以内。

## 适用对象

本指南面向在该 monorepo 中工作的编码 Agent。内容应能独立指导开发，但不重复根目录及各服务
README 中已有的详细运行说明。

只记录高频且会直接影响开发决策的内容。接口清单、完整环境变量说明、启动细节和故障排查应引用
现有 README 或 `docs/troubleshooting.md`，不在 `AGENTS.md` 中展开。

## 内容结构

指南包含以下内容：

1. 仓库用途，以及 `api-server`、`signer-service` 和 `hongguo-contracts` 的职责边界。
2. 支持的工具链，以及规范的 `uv`、`pytest`、Ruff 命令。
3. 路由、传输层、解析器、配置、共享 contracts 和依赖组装的实现约定。
4. 测试要求，包括针对性测试、完整离线验证和显式启用的 live tests。
5. session 数据、服务 token、签名请求材料、回环地址监听、Header allowlist 和 Frida
   二进制文件的安全规则。
6. Codex 的沟通、文档维护和变更管理要求。
7. Git 仓库检查、工作区保护和提交信息规范。

## 核心规则

- 保持服务边界：API Server 不承担设备或 Frida 职责，Signer Service 不承担业务数据解析。
- 必须先构造最终的上游 URL、Header 和请求体，再请求签名；签名后不得修改已参与签名的内容。
- Python Frida 与 Android `frida-server` 必须固定为完全相同的版本。
- 不得提交或泄露捕获的 session、凭据、token、私有请求材料、本地二进制文件或 `.local`
  运行状态。
- 优先使用确定性的单元测试和集成测试。只有显式设置 `HONGGUO_RUN_LIVE_TESTS=1` 时才运行
  live tests。
- 与用户沟通、汇报进度、提出问题和给出最终答复时使用简体中文。代码标识符、命令、路径、
  协议字段和约定俗成的技术术语保留原文。
- 变更应保持聚焦并遵循现有模式；行为或接口变化时同步更新测试和文档。
- 执行 Git 操作前，确认当前目录属于 Git 仓库。仓库不存在或命令失败时，不得声称提交或
  推送成功。
- 提交前检查 `git status`，区分 Agent 产生的变更与用户已有变更；只暂存本次任务相关文件，
  未经明确授权不得丢弃无关改动。
- 提交信息使用简洁中文，并选择准确的 Conventional Commit 前缀：`feat`、`fix`、`style`、
  `docs` 或 `refactor`。当 `test`、`chore` 或其他既有前缀更准确时，应优先采用更准确的类型。

## 验证方式

完成 `AGENTS.md` 后：

- 确认文档引用的路径和命令在仓库中真实存在。
- 运行 `uv run ruff check .`。
- 运行 `uv run pytest -q`。
- 检查最终 diff，确认没有意外包含敏感信息、重复 README 内容，或写入与当前代码冲突的规范。
- 检查文件行数不超过 80 行；如超出，应优先合并重复规则或改为引用现有文档。

## 非目标

- 替代各服务 README 或 troubleshooting 文档。
- 罗列所有 HTTP 接口或环境变量。
- 默认启用 live tests，或要求普通验证必须启动模拟器。
- 修改源代码、依赖、运行配置或现有架构。
