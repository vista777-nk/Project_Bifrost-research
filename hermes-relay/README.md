# Hermes Relay — Bifrost Hermes 集成

> 本目录是 Bifrost 的 Hermes 开源模型适配层。**当前为架构预留阶段，代码为骨架。**

---

## 设计原则

- **复用 Core**：不重写任何业务逻辑，直接从根目录 `core/` 和 `adapters/` 导入
- **薄包装**：仅负责将 Core 能力包装为 Hermes function calling 格式
- **GOAP 原生**：内建 Goal Oriented Action Planning 推理模板

---

## 目录结构

```
hermes-relay/
├── __init__.py                    # 包入口
├── hermes_tools/                  # 核心模块
│   ├── __init__.py                #   公开 API
│   ├── tools.py                   #   Hermes/OpenAI 工具定义 + 执行调度
│   ├── prompts.py                 #   系统提示生成（ChatML + GOAP）
│   └── goap_templates.py          #   GOAP 推理模板（每工业软件一个）
├── tests/                         # 测试（待实现）
├── requirements.txt               # Hermes 特有依赖
└── README.md                      # 本文件
```

---

## 快速开始（未来）

```bash
# 安装依赖
pip install -r requirements.txt

# 测试工具定义导出
python -c "from hermes_tools import get_hermes_tool_definitions; print(len(get_hermes_tool_definitions()))"
# 输出: 6

# 生成 Hermes 系统提示
python -c "from hermes_tools import build_system_prompt; print(build_system_prompt('kicad-pcb'))"

# 生成 ChatML 格式消息
python -c "from hermes_tools import build_chatml_prompt; print(build_chatml_prompt('导出 KiCad 工程 Gerber', 'kicad-pcb'))"
```

---

## 与 Codex 路径的对比

| 维度 | Codex 路径 | Hermes 路径 |
|------|-----------|------------|
| **入口** | Skill (SKILL.md) | 系统提示 (system prompt) |
| **工具注册** | MCP Server (stdio) | 系统提示中 `<tools>` JSON |
| **工具调用** | MCP tools/call | `<tool_call>` XML 标签 |
| **推理框架** | Skill 文档引导 | GOAP scratch_pad |
| **Core 复用** | ✅ 同一套 | ✅ 同一套（跨目录导入） |
| **Adapter 复用** | ✅ 同一套 | ✅ 同一套 |

---

## 依赖关系

```
hermes-relay/hermes_tools/
  →  import core/          (domain, actions, validators, errors)  ← 根目录
  →  import adapters/      (base, kicad, keil, stm32cubeide, …)   ← 根目录
```

`core/` 和 `adapters/` 位于仓库根目录，与 `hermes-relay/` 同级。

---

## 当前状态

| 模块 | 状态 |
|------|:---:|
| 工具定义（tools.py） | ✅ 骨架完成 |
| 系统提示生成（prompts.py） | ✅ 骨架完成 |
| GOAP 模板（goap_templates.py） | ✅ 骨架完成 |
| 工具执行调度 | ⏳ 待 codex-relay Core 实现后对接 |
| 测试 | ⏳ 待 Phase H1 |

---

## 参考

- [Hermes-Function-Calling](https://github.com/NousResearch/Hermes-Function-Calling) — Hermes 官方 function calling 示例
- [docs/09-hermes-integration.md](../docs/09-hermes-integration.md) — Bifrost Hermes 集成方案
- [agentskills.io](https://agentskills.io/) — Agent Skills 开放标准
