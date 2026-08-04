# Codex Relay — Bifrost Codex 插件

> 本目录是 Bifrost 的 Codex 插件实现。**当前为 Phase 0（设计完成），代码尚未开始。**

---

## 目录

```
codex-relay/
├── plugin.json                    # Agent Plugin 清单（待创建）
├── .mcp.json                      # MCP Server 配置（待创建）
├── skills/                        # Skill 集合（每工业软件一个 skill 文件夹）
│   ├── kicad-pcb/SKILL.md         #   KiCad PCB 工作流
│   ├── stm32-flash/SKILL.md       #   STM32 烧录工作流
│   ├── ti-flash/SKILL.md          #   TI 烧录工作流
│   ├── solidworks-cad/SKILL.md    #   SolidWorks CAD 工作流
│   └── relay-core/SKILL.md        #   通用中继工具
├── codex_plugin/                  # Python 包（MCP Server 实现）
│   ├── mcp/server.py              #   MCP Server 入口（待实现）
│   ├── mcp/tools.py               #   工具实现（待实现）
│   └── mcp/schemas.py             #   JSON Schema 生成（待实现）
├── core/                          # 核心引擎（框架无关）
│   ├── domain.py                  #   数据模型（待实现）
│   ├── actions.py                 #   动作引擎（待实现）
│   ├── validators.py              #   校验框架（待实现）
│   └── errors.py                  #   错误体系（待实现）
├── adapters/                      # 工业软件适配器
│   ├── base.py                    #   BaseAdapter 抽象类（待实现）
│   ├── kicad/                     #   KiCad（pcbnew Python API）
│   ├── stm32/                     #   STM32（pyocd / CubeProgrammer）
│   ├── ti/                        #   TI（UniFlash / DSLite）
│   └── solidworks/                #   SolidWorks（COM 接口）
├── examples/                      # 使用示例
└── tests/                         # 测试
```

## 开发状态

| 阶段 | 状态 |
|------|:---:|
| Phase 0 — 设计 | ✅ 完成 |
| Phase 1 — 最小可用插件 | ⏳ 待开始 |
| Phase 2 — KiCad 适配器 | ⏳ 待开始 |

详见 [docs/05-implementation-plan.md](../docs/05-implementation-plan.md)
