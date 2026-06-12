# AGENTS.md 开发指南实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 在仓库根目录创建不超过 80 行的中文 `AGENTS.md`。

**方案：** 仅记录项目边界、开发命令、测试、安全、沟通和 Git 规范；具体运行细节引用现有文档。

**技术栈：** Markdown、uv、pytest、Ruff、Git

---

### 任务 1：创建并验证 AGENTS.md

**文件：**
- 创建：`AGENTS.md`

- [x] **步骤 1：创建文档**

写入项目概览、架构边界、常用命令、开发与测试要求、安全红线、中文沟通和 Git 提交规范。

- [x] **步骤 2：检查文档**

运行：`(Get-Content AGENTS.md).Count`

预期：输出不大于 `80`。

- [x] **步骤 3：执行离线验证**

运行：`uv run ruff check .`

预期：退出码为 `0`。

运行：`uv run pytest -q`

预期：退出码为 `0`，live tests 保持跳过。

- [x] **步骤 4：检查并提交**

运行：`git diff --check` 和 `git status --short`，确认只包含计划内文件。

提交：`docs: 添加 Codex 开发指南`
