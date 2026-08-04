# CODE_OF_CONDUCT.md — 社区行为准则

> **本文档定义 Bifrost 社区的四项基础规范。**
>
> 如果你是第一次参与本项目，这是应该读的第一份社区文档。
> 如果你不确定某个行为是否合适，先查这份文档。
> 如果这份文档没有覆盖你的情况，请以"善意推定"为原则行事。

---

## 目录

- [一、参与者公约](#一参与者公约)
- [二、协作规范](#二协作规范)
- [三、Issue 规范](#三issue-规范)
- [四、命名与引用的尊重](#四命名与引用的尊重)

---

## 一、参与者公约

### 1.1 我们对所有参与者的承诺

Bifrost 致力于为每个人提供**无骚扰、包容、友善**的参与体验，无论其年龄、体型、残障状况、种族、性别认同与表达、经验水平、教育背景、社会经济地位、国籍、个人外貌、宗教信仰或性取向。

### 1.2 期望的行为

以下行为是社区鼓励和期望的：

| 行为 | 说明 |
|------|------|
| **善意推定** | 在解释他人的言论和行动时，优先假定善意意图 |
| **建设性反馈** | 批评针对想法而非个人；提供具体可操作的改进建议 |
| **承认错误** | 犯错时不推诿，公开承认并修正 |
| **尊重时间** | Issue 描述清楚、PR 小而聚焦、不期望即时回复 |
| **分享知识** | 帮助新人理解项目架构和设计决策 |
| **使用包容性语言** | 避免性别化代词（用"他们"替代"他/她"）、避免不必要的俚语 |

### 1.3 不可接受的行为

以下行为**绝不**被容忍：

- 任何形式的骚扰、恐吓或歧视
- 侮辱性/贬损性言论、人身攻击或政治攻击
- 未经允许公开发布他人私人信息（如物理地址、电子邮箱）
- 持续的无效或离题评论（trolling）
- 鼓吹或鼓励以上任何行为
- 使用含有性暗示的图像、文字或链接
- 发布暴力威胁或针对他人的攻击性言论
- 故意使用项目社区宣扬暴力和仇恨的歧视性语言

### 1.4 执行

社区维护者有权利和责任删除、编辑或拒绝与本行为准则不符的评论、提交、代码、wiki 编辑、issue 和其他贡献，并有权暂时或永久禁止任何他们认为有不当、威胁、冒犯或有害行为的贡献者参与。

**执行流程**：

1. **首次轻度违规** → 私下书面警告
2. **重复或中度违规** → 临时禁言（7-30 天）
3. **严重或屡次违规** → 永久移除

所有执行决定将记录在内部日志中，并向受影响者说明理由。

---

## 二、协作规范

### 2.1 Commit Message 规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 1.0.0，使用简体中文描述：

```
<type>(<scope>): <简短描述>

<详细说明（可选）>

<脚注（可选）>
```

**type 类型**：

| Type | 用途 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(kicad): 实现 export_gerber 动作` |
| `fix` | Bug 修复 | `fix(core): 修复 ActionResult 序列化丢失 metadata 字段` |
| `docs` | 文档变更 | `docs(security): 新增 SECURITY.md` |
| `refactor` | 重构（不改变功能） | `refactor(adapters): 提取 BaseAdapter 公共逻辑` |
| `test` | 测试 | `test(kicad): 添加 Gerber 导出集成测试` |
| `chore` | 杂项（构建、依赖、工具） | `chore: 添加 .gitignore` |
| `style` | 格式调整 | `style: ruff 格式化所有 Python 文件` |
| `perf` | 性能优化 | `perf(core): 减少 pydantic 模型序列化开销` |
| `security` | 安全修复 | `security: 修复 CLI 参数注入漏洞` |

**scope 范围**：模块名 (`core`, `kicad`, `stm32`, `ti`, `solidworks`, `mcp`, `docs`)。

### 2.2 分支策略

```bash
main ─────────────────────────── ● (稳定主线)
     \
      feat/kicad-export-gerber ──●──● (开发 → 合并 → 删除)
```

| 分支类型 | 命名格式 | 用途 |
|----------|----------|------|
| `main` | — | 稳定主线 |
| `feat/<desc>` | `feat/kicad-export-gerber` | 新功能 |
| `fix/<desc>` | `fix/confirmation-timeout` | Bug 修复 |
| `docs/<desc>` | `docs/adr-0001` | 纯文档变更 |
| `exp/<desc>` | `exp/solidworks-com-test` | 实验性分支 |

### 2.3 Pull Request 规范

每个 PR 必须：

- [ ] 关联至少一个 Issue（如无，先创建 Issue 讨论）
- [ ] 代码通过 `ruff` 和 `mypy` 检查
- [ ] 包含相关测试（新功能必有测试）
- [ ] 更新受影响的文档
- [ ] 如果是破坏性变更（如修改数据模型字段名），在 PR 描述中明确标注 `BREAKING CHANGE`

### 2.4 代码审查

- 至少一位维护者审查后合并
- 审查者聚焦于：逻辑正确性、安全影响、测试覆盖、文档充分性
- 如果是 AI 辅助生成的代码，必须在 PR 描述中标注使用的工具

---

## 三、Issue 规范

### 3.1 Bug 报告

```markdown
## 环境
- OS: [Windows 11 / Ubuntu 24.04 / macOS 15]
- Python: [3.11.x]
- Bifrost 版本: [commit hash]

## 复现步骤
1. ...
2. ...
3. ...

## 预期行为
...

## 实际行为
...

## 日志/截图
（请附上 `collect_logs` 输出或终端输出）
```

### 3.2 功能请求

```markdown
## 动机
（为什么需要这个功能？解决什么问题？）

## 提议方案
（你期望的行为是什么？）

## 影响范围
（会影响哪些模块？）
```

---

## 四、命名与引用的尊重

### 4.1 项目命名

本项目代号 **"Bifrost"**（彩虹桥），取自北欧神话。项目正式名称为 **"Bifrost Relay"**，仓库名为 `bifrost`。

在社区讨论中，**不要**用贬损性变体或谐音梗称呼本项目或其他项目。

### 4.2 商标与第三方

- **KiCad** 是 KiCad EDA 的商标
- **STM32** 是 STMicroelectronics 的注册商标
- **SolidWorks** 是 Dassault Systèmes 的注册商标
- **Codex** 是 OpenAI 的商标
- **Hermes** 模型系列由 Nous Research 开发

本项目是一个独立的开源社区项目，与上述公司/组织**无关联、无背书关系**。

### 4.3 AI 辅助内容的透明度

本项目鼓励使用 AI 工具辅助开发，但要求：

- AI 生成的代码必须在 commit message 或 PR 描述中标注
- AI 生成的文档需要在文件头部标注辅助工具
- 不鼓励将包含敏感信息的日志/代码粘贴到公开 AI 服务中

---

## 五、发布与打包策略

### 5.1 项目结构原则

```
bifrost/                          ← 仓库根
├── core/          ← 共享：数据模型 + 动作引擎 + 校验框架
├── adapters/      ← 共享：8 个工业软件适配器
├── codex-relay/   ← Codex 专属：plugin.json / .mcp.json / skills / MCP Server
├── hermes-relay/  ← Hermes 专属：hermes_tools / GOAP 模板
└── docs/          ← 共享：技术文档
```

**原则**：`core/` 和 `adapters/` 不依赖任何 AI 框架。`codex-relay/` 和 `hermes-relay/` 各自引用它们。

### 5.2 发布打包

各平台发布时，从仓库中提取对应文件组成独立分发包：

#### Codex 发布包 (`bifrost-codex`)

```
bifrost-codex/
├── core/              ← cp -r 仓库根/core/
├── adapters/          ← cp -r 仓库根/adapters/
├── codex_plugin/      ← cp -r 仓库根/codex-relay/codex_plugin/
├── skills/            ← cp -r 仓库根/codex-relay/skills/
├── plugin.json        ← cp    仓库根/codex-relay/plugin.json
├── .mcp.json          ← cp    仓库根/codex-relay/.mcp.json
└── pyproject.toml     ← 含 mcp/typer 依赖
```

安装：`codex plugin install --local ./bifrost-codex`

#### Hermes 发布包 (`bifrost-hermes`)

```
bifrost-hermes/
├── core/              ← cp -r 仓库根/core/
├── adapters/          ← cp -r 仓库根/adapters/
├── hermes_tools/      ← cp -r 仓库根/hermes-relay/hermes_tools/
└── pyproject.toml     ← 仅 pydantic/structlog 依赖
```

使用：`from hermes_tools import build_system_prompt, get_hermes_tool_definitions`

#### pip 安装（开发模式）

```bash
# 完整安装（Codex + Hermes + 所有适配器）
pip install -e .

# 仅 Codex
pip install -e ".[codex]"

# 仅 Hermes
pip install -e ".[hermes]"

# 含特定适配器
pip install -e ".[codex,stm32,solidworks]"
```

### 5.3 版本号规则

遵循 [Semantic Versioning](https://semver.org/) 2.0.0：

| 版本类型 | 含义 | 示例 |
|---------|------|------|
| `0.x.y` | 开发阶段，API 不稳定 | `0.1.0` → `0.2.0` |
| `1.0.0` | 首个稳定版，Core API 冻结 | Phase 5 完成后 |
| `major.minor.patch` | 破坏性变更 / 新功能 / 修复 | `1.1.0` / `1.1.1` |

---

## 适用范围

本行为准则适用于所有 Bifrost 社区空间（GitHub Issues、PR、Discussions、相关社交平台），以及个人代表项目参与公共活动时的行为。

## 联系方式

如遇违规行为或需要帮助，请联系项目维护者：

📧 **Email**：[待填写]

所有投诉将被保密审查和及时处理。

---

## 致谢

本行为准则参考了以下来源：

- [Contributor Covenant](https://www.contributor-covenant.org/) 2.1
- [Conventional Commits](https://www.conventionalcommits.org/) 1.0.0
- [Project Prometheus CONVENTIONS.md](https://github.com/)（结构参考）

---

<p align="center">
  <em>🌈 Bifrost — 桥接 AI 与工业，也桥接人与人。</em>
</p>
