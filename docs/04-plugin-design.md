# 04 — Codex 插件层设计（AI 可读版）

> **前置阅读**：`03-tools-design.md`
> **后续阅读**：`05-implementation-plan.md`
> **用途**：定义 Codex 插件的 Skill 文档和 MCP Server 的具体实现规范
> **遵循标准**：[Agent Skills](https://agentskills.io/) + [Agent Plugin](https://agentskills.io/specification/agent-plugin)

---

## 1. 插件层总览

Codex 插件位于 `codex-relay/` 目录下，包含三层：

```
codex-relay/                         ← Codex 插件根目录（仅 Codex 专属文件）
├── plugin.json                      # Agent Plugin 清单
├── .mcp.json                        # MCP Server 配置（独立文件）
├── skills/                          # Skill 集合（9 个 skill 文件夹）
│   ├── kicad-pcb/SKILL.md           #   YAML frontmatter + Markdown
│   ├── multisim-reader/SKILL.md
│   ├── cubeide-build/SKILL.md
│   ├── ccs-flash/SKILL.md
│   ├── keil-build/SKILL.md
│   ├── solidworks-cad/SKILL.md
│   ├── autocad-dwg/SKILL.md
│   ├── stm32-flash/SKILL.md         #   向后兼容
│   └── relay-core/SKILL.md          #   通用中继工具
└── codex_plugin/                    # Python 包（MCP Server 实现）
    ├── __init__.py
    └── mcp/
        ├── server.py                #   MCP Server 入口
        ├── tools.py                 #   工具实现
        └── schemas.py               #   JSON Schema 生成

项目根目录（框架无关，Codex + Hermes 共享）：
├── core/                            # 核心引擎（domain/actions/validators/errors）
├── adapters/                        # 软件适配器（8 个）
├── tests/                           # 统一测试
└── examples/                        # 使用示例
```

> **关键设计**：`core/` 和 `adapters/` 位于**项目根目录**，不依赖 Codex。`codex_plugin` 与 `hermes-relay/` 均直接从根目录导入它们。

---

## 2. plugin.json 设计（Agent Plugin 格式）

遵循 [Agent Plugin 开放标准](https://agentskills.io/specification/agent-plugin)，放在 `codex-relay/plugin.json`：

```json
{
  "$schema": "https://agentskills.io/spec/agent-plugin/v1.json",
  "name": "bifrost-codex",
  "version": "0.1.0",
  "description": "工业软件中继适配层 — Codex 插件。安全稳定地操作 KiCad、STM32、TI 和 SolidWorks。",
  "author": {
    "name": "项目作者"
  },
  "homepage": "https://github.com/vista777-nk/Project_Bifrost-research",
  "repository": "https://github.com/vista777-nk/Project_Bifrost-research",
  "license": "MIT",
  "keywords": [
    "kicad", "stm32", "pcb", "firmware",
    "industrial", "eda", "embedded",
    "solidworks", "cad", "automation"
  ],
  "extensions": {
    "com.openai": {
      "skills": "./skills/",
      "mcpServers": "./.mcp.json",
      "interface": {
        "displayName": "Bifrost — Codex Relay",
        "shortDescription": "工业软件中继适配层",
        "longDescription": "让 Codex 安全稳定地调用 KiCad（PCB设计/DRC/Gerber导出）、STM32（固件烧录/校验）、TI（芯片烧录）和 SolidWorks（CAD操作）等工业软件。",
        "developerName": "项目作者",
        "category": "Developer Tools",
        "capabilities": ["Interactive", "Read", "Write"],
        "defaultPrompt": "导出 KiCad 工程的 Gerber 文件并运行 DRC 检查",
        "brandColor": "#2563EB",
        "composerIcon": "./assets/icon.png",
        "logo": "./assets/logo.png"
      }
    }
  }
}
```

> **注意**：`skills` 和 `mcpServers` 是路径字符串（指向目录），不是内联数组。Skill 发现由 Agent 根据 `SKILL.md` 的 YAML frontmatter 中的 `name` + `description` 自动完成。

### 2.1 `.mcp.json` 设计

放在 `codex-relay/.mcp.json`：

```json
{
  "mcpServers": {
    "bifrost-codex": {
      "command": "python",
      "args": ["-m", "codex_plugin.mcp.server"],
      "env": {
        "BIFROST_HOME": "${pluginRoot}"
      }
    }
  }
}
```

---

## 3. MCP Server 实现规范

### 3.1 server.py — 入口文件

```python
"""
codex-relay MCP Server
工业软件中继适配层的 MCP 协议接口
"""

import mcp.server.stdio
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationCapabilities
from .tools import register_all_tools

def create_server() -> Server:
    """创建并配置 MCP Server 实例"""
    server = Server("codex-relay")

    # 注册所有工具
    register_all_tools(server)

    return server

async def main():
    """MCP Server 主入口"""
    server = create_server()
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationCapabilities(
                sampling={},
                experimental={},
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### 3.2 tools.py — 工具实现

```python
"""
MCP 工具实现
每个工具 = 一个 async 函数，用 @server.tool() 装饰
"""

from mcp.server import Server
from core.domain import ActionResult, ValidationReport
from core.actions import ActionExecutor
from core.validators import ResultValidator

def register_all_tools(server: Server):
    """注册所有工具到 MCP Server"""

    @server.tool()
    async def list_adapters(filter: str = "") -> dict:
        """列出可用的软件适配器及其状态"""
        # 实现见下文伪代码
        ...

    @server.tool()
    async def run_action(
        app: str,
        action_name: str,
        parameters: dict = {},
        mode: str = "normal",
        task_id: str = "",
        timeout_seconds: int = 300,
        retry_on_failure: bool = True,
    ) -> dict:
        """执行一个结构化动作"""
        ...

    @server.tool()
    async def validate_result(action_id: str, checks: list[str] = []) -> dict:
        """校验动作执行结果"""
        ...

    @server.tool()
    async def collect_logs(
        action_id: str = "",
        task_id: str = "",
        include_raw_output: bool = False,
        format: str = "json",
    ) -> dict:
        """收集日志和产物"""
        ...

    @server.tool()
    async def confirm_action(action_id: str, confirm: bool, reason: str = "") -> dict:
        """确认或取消一个高风险动作"""
        ...

    @server.tool()
    async def preview_action(app: str, action_name: str, parameters: dict = {}) -> dict:
        """预览动作效果（dry-run）"""
        ...
```

### 3.3 schemas.py — JSON Schema 导出

使用 pydantic 的 `.model_json_schema()` 方法自动生成工具的输入输出 JSON Schema，注册到 MCP 协议中。

---

## 4. Skill 文档设计

遵循 [Agent Skills 开放标准](https://agentskills.io/)：每个 skill 是一个文件夹，内含 `SKILL.md`（YAML frontmatter + Markdown body）。

### 4.1 Skill 目录结构

```
codex-relay/skills/
├── kicad-pcb/                     # KiCad PCB 工作流
│   └── SKILL.md
├── multisim-reader/               # Multisim 电路读取/网表导出
│   └── SKILL.md
├── cubeide-build/                 # STM32CubeIDE 编译/烧录
│   └── SKILL.md
├── ccs-flash/                     # TI CCS 烧录/调试
│   └── SKILL.md
├── keil-build/                    # Keil MDK 编译/烧录
│   └── SKILL.md
├── solidworks-cad/                # SolidWorks CAD 工作流
│   └── SKILL.md
├── autocad-dwg/                   # AutoCAD DWG 批处理
│   └── SKILL.md
├── stm32-flash/                   # STM32 烧录（向后兼容）
│   └── SKILL.md
└── relay-core/                    # 通用中继工具
    └── SKILL.md
```

### 4.2 SKILL.md 格式（以 `kicad-pcb/SKILL.md` 为例）

```markdown
---
name: kicad-pcb
description: KiCad PCB 工作流 — 打开工程、导出 Gerber/BOM、运行 DRC、收集产物。当用户需要操作 KiCad 或处理 PCB 设计文件时使用。
---

# KiCad PCB 工作流

## 适用场景
- 用户提到 KiCad、PCB、Gerber、DRC、BOM、电路板
- 用户需要导出 PCB 生产文件
- 用户需要检查 PCB 设计规则

## 前置条件
- KiCad 8.0+ 已安装
- 工程文件 (.kicad_pro / .kicad_pcb) 存在

## 标准工作流

### W1: 导出 Gerber + DRC 检查
1. `list_adapters(filter="kicad")` — 确认 KiCad 可用
2. `run_action(app="kicad", action_name="open_project", parameters={"project_path": "<用户提供>"})`
3. `run_action(app="kicad", action_name="export_gerber", parameters={"output_dir": "<自动生成>"})`
4. `run_action(app="kicad", action_name="run_drc", parameters={})`
5. `validate_result(action_id="<步骤3的action_id>")`
6. 向用户报告结果

### W2: 导出 BOM
1. `run_action(app="kicad", action_name="export_bom", parameters={"format": "csv"})`
2. 向用户报告产物路径

## 安全规则
- ⚠️ DRC 发现错误时必须告知用户，不要自动忽略
- ⚠️ 覆盖已有 Gerber 文件前需确认
- ✅ 只读操作（打开工程、导出）可以自动执行

## GOAP 推理模板（Hermes 兼容）
<scratch_pad>
Goal: {用户目标}
Actions:
  - adapter_status = functions.list_adapters(filter="kicad")
  - result = functions.run_action(app="kicad", action_name="{动作}", ...)
  - validation = functions.validate_result(action_id=result.action_id)
Observation: {执行结果}
Reflection: {分析}
</scratch_pad>
```

### 4.3 `relay-core/SKILL.md`（通用工具 skill）

```markdown
---
name: relay-core
description: Bifrost 通用中继操作 — 列出适配器、确认高风险动作、收集日志。当需要了解 codex-relay 系统状态或执行通用管理操作时使用。
---

# 通用中继工具

## 适用场景
- 查看当前可用的工业软件适配器
- 确认或取消高风险操作
- 收集执行日志和产物

## 工具速查
| 工具 | 用途 | 何时使用 |
|------|------|---------|
| list_adapters | 列出可用软件适配器 | 任何实际操作前必调用 |
| confirm_action | 确认高风险操作 | 收到 confirmation_required 时 |
| collect_logs | 收集日志 | 出错时或任务结束时 |
| preview_action | 预览效果 | 不确定后果时在 run_action 前调用 |
```

---

## 5. 插件与 Core 的关系

```
codex-relay/codex_plugin/mcp/server.py
  →  import codex_plugin.mcp.tools
      →  import core.actions.ActionExecutor    # 根目录 core/
      →  import core.validators.ResultValidator
      →  import core.domain                    # 所有 pydantic 数据模型
      →  import adapters.base                  # 根目录 adapters/

codex-relay/codex_plugin/mcp/schemas.py
  →  import core.domain                        # 用于生成 JSON Schema

# 未来 Hermes 集成：
hermes-relay/tools.py
  →  import core.actions.ActionExecutor        # 同一套 Core！
  →  import core.domain
  →  import adapters.base
```

**依赖方向严格单向**：`codex_plugin` → `core` → `adapters`。Core 不知道任何上层框架的存在。

---

## 6. 开发与调试

### 本地调试 MCP Server
```bash
# 在 codex-relay/ 目录下运行
cd codex-relay

# 方式1: 用 MCP Inspector
npx @modelcontextprotocol/inspector python -m codex_plugin.mcp.server

# 方式2: 直接 stdio 测试
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python -m codex_plugin.mcp.server
```

### 单元测试
```bash
pytest tests/test_mcp_server.py -v
```

---

## 7. 下一步

继续阅读 `05-implementation-plan.md` — 分阶段实现计划。
