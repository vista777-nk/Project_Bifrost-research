---
name: kicad-pcb
description: Create and edit supported KiCad 8 native schematics, inspect PCB projects, export Gerber/BOM, and run checks through Bifrost. Use for KiCad, .kicad_sch, .kicad_pcb, Gerber, ERC, DRC, or BOM requests.
---

# KiCad PCB 工作流

## Native Schematic Authoring

Use `run_action(app="kicad", ...)`; never control desktop input.
The writer targets KiCad 8/schema 20231120 and real Device:R/C/L and
Simulation_SPICE:VDC symbols. This is schematic authoring; PCB placement and
routing are separate capabilities and are not implemented by these actions.

- `find_components`: optional `query`; returns supported library IDs and units.
- `create_schematic`: `output_file` ending in `.kicad_sch`, and `circuit`.
- `inspect_schematic`: `input_file`; returns `circuit` and `input_sha256`.
- `edit_schematic`: `input_file`, distinct `output_file`, latest
  `expected_input_sha256`, and `changes`.

`circuit.components` contains up to 128 objects: `reference`, `kind`
(`R`, `C`, `L`, `VDC`), numeric SI `value`, optional `x_mm`/`y_mm`, `rotation`
(0/90/180/270), and `pins` mapping `"1"`/`"2"` to ASCII net identifiers or null.
Net `"0"` means ground. New placements snap to the native 1.27 mm grid.

Each change has `op`: `set_value` (`reference,value`), `remove` (`reference`),
`replace` (`reference,kind,value`), `move` (`reference,x_mm,y_mm`), `rotate`
(`reference,rotation`), `connect` (`reference,pin,net`), `disconnect`
(`reference,pin`), or `add` (`component`, the complete component object).

Review batches with `preview_action`: before/after circuits are validated,
while native validation remains pending until execution. Successful writes
include native pin/net comparison and ERC results. Inspect `verification`;
an editable artifact with ERC violations is not an electrically clean design.
Use `validate_result` to check the artifact checksum after publication.

Topology edits currently require a single-sheet Bifrost-authored schematic.
Supported imported schematics accept value edits; unsupported symbols, buses,
hierarchy, mirrors, or topology labels fail explicitly. Preserve that boundary
and report limitations instead of silently replacing or dropping native objects.
The source is never overwritten. Existing revision destinations require the
relay's confirmation; use prior explicit authorization where applicable.

## 适用场景
- 用户提到 KiCad、PCB 设计、Gerber 文件、DRC 检查、BOM 导出
- 用户需要从 `.kicad_pcb` 工程导出制造文件
- 用户需要检查 PCB 设计是否有设计规则违规
- 用户提到"打样""制版""Gerber 导出"等关键词

## 前置条件
- KiCad 8.x 已安装（本适配器针对 8.0.9 版本验证）
- 目标工程文件（`.kicad_pro` / `.kicad_pcb` / `.kicad_sch`）存在且可访问

## 可用工具速查
| 工具 | 用途 | 风险 |
|------|------|:---:|
| `list_adapters` | 确认 KiCad 适配器可用 | 🟢 低 |
| `run_action(app="kicad", ...)` | 执行具体 KiCad 动作 | 🟡 中 |
| `validate_result` | 校验导出结果 | 🟢 低 |
| `collect_logs` | 收集日志和产物 | 🟢 低 |

## 支持的动作 (action_name)

| 动作 | 说明 | 首选路径 | 关键参数 |
|------|------|---------|---------|
| `open_project` | 打开 KiCad 工程 | pcbnew Python API | `project_path` |
| `export_gerber` | 导出 Gerber 制造文件 | kicad-cli 或 pcbnew | `project_path`, `output_dir` |
| `export_bom` | 导出物料清单 | `kicad-cli sch export bom` | `schematic_path`, `output_file` |
| `run_drc` | 运行设计规则检查 | `kicad-cli pcb drc --format json` | `project_path`, `output_file` |
| `collect_artifacts` | 收集产物文件列表 | 文件系统遍历 | `output_dir` |

## 标准工作流

### 导出 Gerber + DRC 检查（最常用）
1. 调用 `list_adapters(filter="kicad")` — 确认 KiCad 可用
2. 调用 `run_action(app="kicad", action_name="open_project", parameters={"project_path": "<路径>"})`
3. 调用 `run_action(app="kicad", action_name="export_gerber", parameters={"project_path": "<路径>", "output_dir": "<输出目录>"})`
4. 调用 `run_action(app="kicad", action_name="run_drc", parameters={"project_path": "<路径>"})`
5. 调用 `validate_result(action_id=<步骤3的action_id>)` — 检查 Gerber 文件
6. 调用 `validate_result(action_id=<步骤4的action_id>)` — 检查 DRC 结果
7. 调用 `collect_logs(task_id=<任务ID>)` — 收集全部日志和产物列表

### 仅导出 BOM
1. 调用 `list_adapters(filter="kicad")`
2. 调用 `run_action(app="kicad", action_name="export_bom", parameters={"schematic_path": "<.kicad_sch 路径>", "output_file": "<输出CSV路径>"})`
3. 调用 `validate_result(action_id=...)`

## 集成路径优先级
| 优先级 | 路径 | 适用场景 |
|:---:|------|---------|
| 🥇 | pcbnew Python API | 需要内存中操作 board 对象时 |
| 🥈 | kicad-cli | 单步导出/DRC/BOM，更稳定 |
| ❌ | GUI 自动化 | 永不使用 |

## 何时停止问人
- DRC 发现违规时 — 列出违规项，**不要自动忽略**
- 工程文件不存在时 — 报告路径错误
- KiCad 未安装或版本不兼容时
- 导出文件会覆盖已有文件时 — 询问是否覆盖
- 连续 3 次重试失败时
