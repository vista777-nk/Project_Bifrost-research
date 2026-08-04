# 09 — Hermes 集成方案（AI 可读版）

> **前置阅读**：`07-gap-analysis.md`、`08-agent-skills-standard.md`
> **用途**：定义未来如何将 codex-relay 的能力移植到 Hermes 开源模型生态

---

## 1. 关键认知修正

**Hermes 不是 Codex。** Hermes 是由 Nous Research 开发的一系列开源 LLM，没有"插件系统"。

Codex 的"插件" ≈ Hermes 的 "function calling prompt engineering"

所以"移植到 Hermes"不是改插件格式，而是：
1. 保持 Core 层和 Adapters 不变
2. 新增一个 **Hermes Tool Wrapper**，把 Core 的工具包装成 Hermes function calling 格式
3. 用 Hermes 的 GOAP 推理模板增强任务规划能力

---

## 2. Hermes Function Calling 格式

### 2.1 工具定义（OpenAI 兼容）

```python
# hermes_tools.py — Hermes 专用的工具包装层

from core.domain import Action, ActionResult
from core.actions import ActionExecutor

def get_hermes_tools() -> list[dict]:
    """返回 Hermes 兼容的工具定义列表"""
    return [
        {
            "type": "function",
            "function": {
                "name": "list_adapters",
                "description": "列出当前可用的工业软件适配器及其状态和可用动作",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filter": {
                            "type": "string",
                            "description": "按名称过滤: kicad, stm32, ti, solidworks。空字符串表示全部",
                            "default": ""
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_action",
                "description": "执行一个结构化工业软件动作",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app": {"type": "string", "description": "目标软件: kicad, stm32, ti, solidworks"},
                        "action_name": {"type": "string", "description": "动作名称"},
                        "parameters": {"type": "object", "description": "动作参数"},
                        "mode": {"type": "string", "enum": ["dry_run", "normal", "force"], "default": "normal"}
                    },
                    "required": ["app", "action_name"]
                }
            }
        },
        # ... 其余工具同 MCP 工具定义
    ]
```

### 2.2 系统提示格式

```
<|im_start|>system
You are a function calling AI model. You are provided with function signatures within <tools></tools> XML tags.
You may call one or more functions to assist with the user query.
Don't make assumptions about what values to plug into functions.
For each function call return a JSON object with function name and arguments within <tool_call></tool_call> XML tags.
Use <scratch_pad></scratch_pad> XML tags to record your reasoning and planning before you call the functions.

<tools>
[{"type": "function", "function": {"name": "list_adapters", ...}}, ...]
</tools>
<|im_end>
```

### 2.3 工具调用和响应格式

```
<|im_start|>assistant
<scratch_pad>
Goal: 导出 KiCad 工程的 Gerber 文件并检查 DRC
Actions:
  - adapter_status = functions.list_adapters(filter="kicad")
  - open_result = functions.run_action(app="kicad", action_name="open_project", ...)
  - gerber_result = functions.run_action(app="kicad", action_name="export_gerber", ...)
  - drc_result = functions.run_action(app="kicad", action_name="run_drc", ...)
  - validation = functions.validate_result(action_id=gerber_result.action_id)
Observation: None
Reflection: 计划覆盖了从确认适配器到验证的完整流程。需要先确认 KiCad 可用。
</scratch_pad>
<tool_call>
{"name": "list_adapters", "arguments": {"filter": "kicad"}}
</tool_call><|im_end>

<|im_start|>tool
<tool_response>
{"name": "list_adapters", "content": {"success": true, "adapters": [{"name": "kicad", "available": true, ...}]}}
</tool_response><|im_end>
```

---

## 3. GOAP 推理框架

### 3.1 什么是 GOAP

Goal Oriented Action Planning — 目标导向动作规划。Hermes-3 引入。

```
Goal:       重新陈述用户目标
Actions:    列出需要调用的函数和参数（Python 风格伪代码）
Observation: 工具返回结果摘要
Reflection:  评估工具相关性、参数完备性、任务状态
```

### 3.2 在 SKILL.md 中嵌入 GOAP 模板

我们可以在每个 skill 的 SKILL.md 中加入 GOAP 模板，让使用 Hermes 的 Agent 能更好地规划：

```markdown
## GOAP 推理模板

当使用 Hermes 模型时，按以下 GOAP 结构规划任务：

<scratch_pad>
Goal: {在此重新陈述用户的具体目标}
Actions:
  - adapter_status = functions.list_adapters(filter="{目标软件}")
  - result = functions.run_action(app="{目标软件}", action_name="{动作名}", parameters={参数})
  - validation = functions.validate_result(action_id=result.action_id)
  - logs = functions.collect_logs(action_id=result.action_id)
Observation: {执行后填入每个工具返回的关键信息}
Reflection: {评估：所有步骤是否完成、是否有错误、是否需要人工介入}
</scratch_pad>
```

---

## 4. 架构对比

```
Codex 路径:
  User → Codex Agent → Skill (codex-relay/skills/kicad-pcb/SKILL.md)
                         ↓
                       MCP Server (codex-relay/codex_plugin/mcp/server.py)
                         ↓
                       Core (codex-relay/core/)
                         ↓
                       Adapter (codex-relay/adapters/kicad/)

Hermes 路径:
  User → Hermes Model → GOAP Prompt (含 tools 定义)
                         ↓
                       Hermes Tool Wrapper (hermes-relay/tools.py)
                         ↓
                       Core (codex-relay/core/)          ← 同一套！跨目录导入
                         ↓
                       Adapter (codex-relay/adapters/kicad/)  ← 同一套！
```

**关键：Core 和 Adapters 完全复用。** 只变"调用协议层"。

`hermes-relay/` 通过 `import sys; sys.path.insert(0, '../codex-relay')` 或 pip editable install 导入 `codex-relay` 的 Core 和 Adapters。

---

## 5. 实现路线图

### Phase H1：Hermes Tool Wrapper

```python
# hermes_integration/
# ├── __init__.py
# ├── tools.py          # 工具定义 + 执行调度
# ├── prompts.py        # 系统提示生成
# └── goap_templates.py # GOAP 模板管理

class HermesToolWrapper:
    """将 Core 的工具包装为 Hermes function calling 格式"""
    
    def get_tool_definitions(self) -> list[dict]:
        """返回 OpenAI 兼容的工具定义"""
        ...
    
    def execute_tool_call(self, name: str, arguments: dict) -> dict:
        """执行工具调用，返回结构化结果"""
        # 内部调用 core.actions.ActionExecutor
        ...
    
    def build_system_prompt(self, skill_name: str = None) -> str:
        """构建包含 tools 定义和 GOAP 指令的系统提示"""
        ...
```

### Phase H2：GOAP 模板引擎

```python
class GOAPTemplate:
    """GOAP 推理模板"""
    
    def render(self, goal: str, tools: list[dict], skill_context: str) -> str:
        """渲染 GOAP scratch_pad 模板"""
        ...
```

### Phase H3：多模型支持

```python
SUPPORTED_MODELS = {
    "hermes-3": {"format": "chatml", "goap": True},
    "hermes-2-pro": {"format": "chatml", "goap": False},
    "llama-3": {"format": "llama3", "goap": False},
}
```

---

## 6. 与 Codex Skill 的协同

在 Hermes 模式下，我们仍然可以利用 SKILL.md 中的内容：

1. 提取 SKILL.md 的 YAML frontmatter → 构建工具描述
2. 提取 "GOAP 推理模板" 部分 → 注入系统提示
3. 提取 "标准工作流" 部分 → 生成 few-shot 示例
4. 提取 "安全规则" 部分 → 添加约束提示

```python
class SkillLoader:
    """从 SKILL.md 提取结构化信息"""
    
    def load_for_hermes(self, skill_path: str) -> dict:
        """加载 skill 并转换为 Hermes 可用格式"""
        frontmatter, body = self.parse_skill_md(skill_path)
        return {
            "tool_hints": self.extract_tool_references(body),
            "goap_template": self.extract_goap_template(body),
            "fewshot_examples": self.extract_workflow_examples(body),
            "safety_rules": self.extract_safety_rules(body),
        }
```

---

## 7. 总结

| 维度 | Codex 做法 | Hermes 做法 |
|------|-----------|------------|
| 工具注册 | MCP Server protocol | 系统提示中的 JSON schema |
| 工具调用 | MCP tools/call | `<tool_call>` XML 标签 |
| 任务规划 | Skill 文档引导 | GOAP scratch_pad |
| 插件分发 | Marketplace | 模型权重 + prompt |
| Core 层 | 相同 | 相同 |
| Adapter 层 | 相同 | 相同 |

**结论**：先做好 Codex 插件（Phase 1-2），Hermes 集成只需加一个薄包装层（~500 行代码），无需重写任何 Core 或 Adapter 代码。这是原始企划"先 Codex 后 Hermes"策略的技术基础。
