# Codex Relay — Bifrost Codex 插件

> 本目录是 Bifrost 的 Codex 插件实现。**当前为 Phase 0（设计完成），代码尚未开始。**

---

## 目录

```
codex-relay/
├── plugin.json                    # Agent Plugin 清单（待创建）
├── .mcp.json                      # MCP Server 配置（待创建）
├── skills/                        # Skill 集合（每工业软件一个 skill 文件夹）
│   ├── kicad-pcb/SKILL.md         #   KiCad 8.0.9 — PCB 工作流
│   ├── keil-build/SKILL.md        #   Keil MDK 5.39 — 编译/烧录
│   ├── cubeide-build/SKILL.md      #   STM32CubeIDE — 配置/编译/烧录
│   ├── ccs-flash/SKILL.md         #   CCS 12.8 — TI 芯片烧录/调试
│   ├── autocad-dwg/SKILL.md       #   AutoCAD 2022 — 脚本/导出
│   ├── multisim-reader/SKILL.md   #   Multisim 14.3 — 电路读取
│   ├── solidworks-cad/SKILL.md    #   SolidWorks 2024 SP5 — CAD 操作
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
├── adapters/                      # 工业软件适配器（8 个）
│   ├── base.py                    #   BaseAdapter 抽象类（待实现）
│   ├── kicad/                     #   KiCad 8.0.9（pcbnew Python API）
│   ├── keil/                      #   Keil MDK 5.39（UV4 CLI）
│   ├── stm32cubeide/              #   STM32CubeIDE 1.17（Eclipse CLI）
│   ├── ccs/                       #   CCS 12.8（Theia CLI + DSS）
│   ├── autocad/                   #   AutoCAD 2022（accoreconsole + COM）
│   ├── multisim/                  #   Multisim 14.3（XML 解析 + COM）
│   └── solidworks/                #   SolidWorks 2024 SP5（COM / Macro）
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
