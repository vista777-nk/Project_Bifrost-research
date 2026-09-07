# Codex Relay — Bifrost Codex 插件

Setup and verified readiness: [Local Codex Plugin Setup](../docs/CODEX_SETUP.md).
The installed plugin is `codex-relay@personal`; the MCP server is `bifrost-codex`.
Native circuit creation/editing, supported scope, and testing prompts:
[Native Circuit Authoring](../docs/10-circuit-authoring.md).

> 本目录仅包含 Codex 专属文件。共享的 `core/`、`adapters/`、`tests/`、`examples/` 位于项目根目录。

---

## 目录

```
codex-relay/                          ← Codex 专属
├── .codex-plugin/plugin.json         #   Codex Plugin 清单
├── .mcp.json                         #   MCP Server 配置
├── codex_plugin/                     #   Python 包（MCP Server 实现）
│   ├── __init__.py
│   └── mcp/
│       ├── __init__.py
│       ├── server.py                 #     MCP Server 入口
│       ├── tools.py                  #     工具实现与运行时状态
│       └── schemas.py                #     JSON Schema 生成
└── skills/                           #   Skill 集合（9 个 skill 文件夹）
    ├── kicad-pcb/SKILL.md
    ├── keil-build/SKILL.md
    ├── cubeide-build/SKILL.md
    ├── ccs-flash/SKILL.md
    ├── autocad-dwg/SKILL.md
    ├── multisim-reader/SKILL.md
    ├── solidworks-cad/SKILL.md
    ├── stm32-flash/SKILL.md          #   向后兼容
    └── relay-core/SKILL.md

项目根目录（共享）：
├── core/                             #   核心引擎
├── adapters/                         #   8 个工业软件适配器
├── tests/                            #   统一测试
├── examples/                         #   使用示例
└── docs/                             #   技术文档
```

## 与根目录的关系

- `codex_plugin/mcp/` → `from core.domain import ...` 同级导入
- `codex_plugin/mcp/` → `from adapters.base import ...` 同级导入
- Hermes 通过 `hermes-relay/hermes_tools/` → `from core.domain import ...` 同一套 Core

## 开发状态

| 阶段 | 状态 |
|------|:---:|
| Phase 0 — 设计 | ✅ 完成 |
| Phase 1 — 最小可用插件 | MCP Server 已完成，示例工程待补充 |

详见 [docs/05-implementation-plan.md](../docs/05-implementation-plan.md)
