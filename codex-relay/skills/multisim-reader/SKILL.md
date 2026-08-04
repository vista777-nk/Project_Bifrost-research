---
name: multisim-reader
description: Multisim 电路读取与仿真 — 打开设计文件、枚举元件、导出网表、运行仿真、采集输出数据。当用户提到 Multisim、电路仿真、SPICE、网表、.ms14 文件时使用。
---

# Multisim 电路读取与仿真

## 适用场景
- 用户提到 Multisim、电路仿真、SPICE 分析、网表导出
- 用户需要读取 `.ms14` 设计文件中的电路信息
- 用户需要运行瞬态/AC/DC 仿真并获取输出数据
- 用户想通过 AI 生成 SPICE netlist 并在 Multisim 中验证
- 用户提到"仿真""波形""Bode 图""工作点"等关键词

## 前置条件
- **仅 Windows** — Multisim COM Automation API 仅 Windows 平台可用
- NI Multisim 14.x 已安装并激活
- Python 环境需安装 `pywin32>=308`
- 若 Multisim COM 组件为 32-bit，必须使用 32-bit Python

## 可用工具速查
| 工具 | 用途 | 风险 |
|------|------|:---:|
| `list_adapters` | 确认 Multisim 适配器可用 | 🟢 低 |
| `run_action(app="multisim", ...)` | 执行电路操作 | 🟡 中 |
| `validate_result` | 校验仿真结果 | 🟢 低 |
| `collect_logs` | 收集日志和产物 | 🟢 低 |

## 支持的动作 (action_name)

| 动作 | 说明 | 关键参数 |
|------|------|---------|
| `read_circuit` | 打开设计并读取电路信息（元件、网络、探针） | `file_path` |
| `export_netlist` | 导出 SPICE 网表 | `file_path`, `output_file` |
| `run_simulation` | 运行仿真（瞬态/AC/DC） | `analysis_type`, `output_names`, `stop_time` |
| `get_output_data` | 采集仿真输出数据 | `output_name` |
| `list_components` | 枚举电路中所有元件 | `file_path` |

## 标准工作流

### 读取电路 + 导出网表
1. 调用 `list_adapters(filter="multisim")` — 确认 Multisim 可用
2. 调用 `run_action(app="multisim", action_name="read_circuit", parameters={"file_path": "<路径>"})`
3. 调用 `run_action(app="multisim", action_name="export_netlist", parameters={"file_path": "<路径>", "output_file": "<输出路径>"})`
4. 调用 `validate_result(action_id=<步骤3的action_id>)`

### 运行瞬态仿真
1. 调用 `list_adapters(filter="multisim")`
2. 调用 `run_action(app="multisim", action_name="read_circuit", parameters={"file_path": "<路径>"})`
3. 调用 `run_action(app="multisim", action_name="run_simulation", parameters={"analysis_type": "transient", "output_names": ["V(out)"], "stop_time": 0.01})`
4. 调用 `run_action(app="multisim", action_name="get_output_data", parameters={"output_name": "V(out)"})`

## 集成路径优先级
| 优先级 | 路径 | 说明 |
|:---:|------|------|
| 🥇 | COM Automation API (pywin32) | 完整电路操作、仿真控制、数据采集 |
| 🥈 | 命令行 netlist 仿真 | 批处理仿真，能力有限 |
| ❌ | .ms14 直接解析 | 专有二进制格式，不可行 |

## 重要限制与安全规则
- **修改前停止仿真**：修改元件参数前确保仿真已停止
- **快照保护**：建议所有修改走 `save_as`，不覆盖原设计文件
- **单位规范**：R/L/C 值使用 SI 基本单位（`1kΩ = 1000`, `10nF = 1e-8`）
- **枚举先行**：引用任何 RefDes/probe 名称前，先调用 `list_*` 枚举
- **32-bit Python**：若 Multisim COM 组件为 32-bit，需使用 32-bit Python 环境

## 可借鉴项目
- [Multisim-MCP](https://github.com/Last-emo-boy/Multisim-MCP) — 61 个 MCP 工具的 Multisim COM Automation 参考实现

## 何时停止问人
- Multisim 未安装或 COM 组件不可用时
- 设计文件不存在或格式不支持时
- 仿真不收敛或报错时 — 报告错误详情
- 连续 3 次重试失败时
