# Bifrost 任务板

> 这是唯一的任务状态通道。能力事实见 [STATUS.md](STATUS.md)，协作规则见
> [COLLABORATION.md](COLLABORATION.md)。
> 最近更新：2026-10-30（DeepSeek）。

## 1. 使用规则

- 状态：`Proposed` / `Claimed` / `In Progress` / `Review` / `Done` / `Blocked`。
- 每人同一时刻最多 1 个 `In Progress`；同一文件只能有一个作者。
- 认领时填写：owner、验收命令；完成时填写证据路径。
- 默认直接在 `dev` 上小步提交，不自行创建任务分支；分支仅在用户明确要求时使用。
- 范围变化先改本表，再改代码；不得“顺手”扩大任务。
- 完成的任务保留在表中，不删除历史。

## 2. 当前任务

| ID | 优先级 | 任务 | 域 | Owner | 状态 | 验收命令 | 证据 |
|---|---|---|---|---|---|---|---|
| T-000 | P0 | 接手基线、状态事实源与协作纪律 | governance | DeepSeek | Done（2026-10-30） | 非硬件全量回归；文档链接可达 | 本文件、`STATUS.md`、提交 `48c0ee9` |
| T-001 | P1 | 在 DeepSeek/Kimi 实际客户端接入同一 MCP 并留证 | integration | 待认领 | Proposed | 六个工具可调用；记录客户端版本/配置/日期 | — |
| T-002 | P1 | 定义“导入工程拓扑编辑”的范围、样例与失败模式 | authoring | 待认领 | Proposed | 范围文档 + 真实样例 + 显式拒绝用例 | — |
| T-003 | P2 | Ruff 第一批：core/adapters 清零 | quality | 待认领 | Proposed | `ruff check .` 在 core/adapters 无新增；行为不变 | — |
| T-004 | P2 | mypy `core/` 清零 | quality | 待认领 | Proposed | `mypy core/` 通过；无行为变化 | — |
| T-005 | P2 | KiCad PCB 制造导出独立实机验收 | kicad | 待认领 | Proposed | 全新输出目录 + Gerber/BOM/DRC 产物与报告 | — |
| T-006 | P3 | 器件家族扩展（等待用户指定真实需求） | authoring | 待认领 | Proposed | 真实符号 + 持久化 + 连通性 + 电气验收 | — |
| T-007 | P3 | Hermes 执行层：完成或明确冻结 | hermes | 待认领 | Proposed | 用户决策 + 对应记录 | — |
| T-008 | P2 | 清理冗余历史文档、失效示例与占位文件 | governance | DeepSeek | Done（2026-10-30） | 链接可达；非硬件全量回归通过 | 待填提交 |

## 3. T-000 完成记录

- 建立 `AGENTS.md`：所有 agent 的强制入口、红线、DoD 与常用命令。
- 建立 `docs/STATUS.md`：当前能力、验证事实、工程债与优先级。
- 建立 `docs/COLLABORATION.md`：DeepSeek/Kimi 的认领、提交、审查、证据与冲突规则。
- 建立本任务板，并把历史交接文档标注为快照。
- 复核基线：非硬件测试 **186 passed, 1 skipped, 10 deselected**；
  Ruff **75 findings**；mypy `core/` **29 errors / 7 files**。
- 本次未重跑实机；2026-09-08 的历史验收保留在
  `output/native-acceptance-verified/`，不作为今日结论。
- 提交：`48c0ee9`（`docs(governance)`）。Kimi 首次会话需复核本文件与
  `COLLABORATION.md`，有异议先提给用户，不直接改写纪律。

## 4. 待用户决策

1. P1 先做 T-001（客户端接入）还是 T-002（导入工程拓扑编辑）。
2. 是否授权把本地提交推送到 `origin/dev`。
3. Kimi 客户端是否支持本地 stdio MCP；若不支持，采用哪种桥接。
4. T-007（Hermes）继续投入还是冻结。

## 5. 下一步建议

- 若优先“可用性”：先做 T-001，让两位 agent 都能直接调用现有能力。
- 若优先“产品价值”：先做 T-002，把导入工程的可编辑范围定义清楚，
  再按样例逐个实现，避免用“支持更多库”掩盖拓扑能力不足。
- 质量债（T-003/T-004）建议在每次功能任务中顺带清理所属模块，
  不做一次性大重构。
