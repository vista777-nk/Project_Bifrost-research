# AGENTS.md — Bifrost agent 强制入口

本文件是所有 AI agent（当前为 DeepSeek 与 Kimi）进入本仓库的入口。
开始任何任务前，必须按顺序阅读以下文件；只读聊天记录或旧交接文档不足以开始工作。

## 1. 必读顺序

1. 本文件。
2. [docs/STATUS.md](docs/STATUS.md) — 当前能力与验证结果的唯一事实源。
3. [docs/WORKBOARD.md](docs/WORKBOARD.md) — 当前任务、负责人、状态与下一步。
4. [docs/COLLABORATION.md](docs/COLLABORATION.md) — 协作纪律全文。
5. 与任务相关的决策与手册：
   - [TDR-002 原生电路范围](docs/decisions/TDR-002-circuit-authoring-scope.md)
   - [原生电路作者手册](docs/10-circuit-authoring.md)

`docs/HANDOFF_DEEPSEEK_KIMI.md` 只是历史快照，不得当作当前状态。
当前事实只认 `docs/STATUS.md`。

## 2. 红线（不可协商）

- 禁止鼠标、键盘、GUI 控制自动化，包括以 UIA 等方式绕过限制。
- 禁止覆盖原始输入文件；默认写入独立的新修订；覆盖必须走现有确认机制。
- 禁止静默丢弃不认识的器件、字段或版本；必须显式报错。
- 禁止用 mock、单测、文件存在或历史报告冒充实机验收；禁止伪造测试结果。
- 禁止未经用户授权推送、改写已提交历史、修改全局 Git 身份。
- 禁止擅自缩小 TDR-002 的产品范围（读取、导出、仿真不能替代原生电路设计与编辑）。

## 3. 唯一协作通道

- 任务状态只写在 `docs/WORKBOARD.md`；能力事实只写在 `docs/STATUS.md`。
- 认领任务：先运行 `git status --short --branch`，确认没有未提交的他人改动；
  在 WORKBOARD 写入任务行（ID、owner、验收命令），然后直接在 `dev` 上小步提交。
  不要自行创建任务分支；只有用户明确要求时才建分支。
- 每人同一时刻最多 1 个 In Progress 任务；同一文件同一时刻只能有一个作者。
- 跨域改动先在 WORKBOARD 标注，并征得该域默认主责同意；无法达成一致时交用户裁决。

## 4. 完成定义（DoD）

一项任务只有同时满足以下条件才算完成：

1. 改动范围与 WORKBOARD 中登记的一致，没有顺手夹带无关修改。
2. 新增或更新对应测试；纯文档任务除外。
3. `CHANGELOG.md` 的 `Unreleased` 有记录。
4. 非硬件全量回归通过。
5. 涉及能力或边界变化时，更新 `docs/STATUS.md`。
6. 在 WORKBOARD 写入结果与证据路径（命令、输出摘要、产物目录）。
7. 提交信息包含 `Agent: deepseek` 或 `Agent: kimi` trailer。

实机能力必须附当天的命令输出和产物；没有当天运行就写“未验证”，
不得引用旧报告充当今日结果。

## 5. 常用命令

```powershell
# 非硬件全量回归（接手基线：186 passed, 1 skipped, 10 deselected）
.\.venv-codex\Scripts\python.exe -m pytest tests/ -m "not hardware"

# Lint（用 ruff.exe；本机 `python -m ruff` 无输出）
.\.venv-codex\Scripts\ruff.exe check . --output-format concise

# 类型检查
.\.venv-codex\Scripts\python.exe -m mypy core/

# MCP stdio 冒烟（需要已有本机配置）
.\.venv-codex\Scripts\python.exe -m codex_plugin.mcp.smoke --config "$HOME\plugins\codex-relay\.mcp.json"

# 两软件原生验收（实机，使用全新输出目录）
$handoffOutput = Join-Path 'output' ('handoff-' + [guid]::NewGuid().ToString('N'))
.\.venv-codex\Scripts\python.exe scripts/verify_native_authoring.py --config "$HOME\plugins\codex-relay\.mcp.json" --output-dir $handoffOutput
```

## 6. 冲突与不确定

- 文档冲突的解释顺序：用户最新指令 > `STATUS.md` > TDR > 作者手册 > 历史文档。
- 事实冲突以可复现命令为准；不可复现的结论降级为“未验证”。
- 不确定就停下来问用户，不要猜需求，不要扩大范围，不要用“顺手重构”代替交付。

## 7. 对用户的回复格式

固定四段，中文、简短：

1. **现状**：任务处于什么状态。
2. **本次改动**：改了哪些文件/能力。
3. **验证**：命令与结果；未验证项明确写出。
4. **下一步**：下一项任务，以及需要用户决策的事项。
