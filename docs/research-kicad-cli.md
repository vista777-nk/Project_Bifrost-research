# 调研报告：KiCad 自动化路径

> **日期**：2026-08-04
> **目的**：确认 KiCad 的 CLI/API 能力边界，为 adapter 设计提供依据
> **优先级原则**：pcbnew Python API > kicad-cli > 文件解析 > GUI

---

## 1. KiCad 自动化路径总览

| 路径 | 类型 | 稳定性 | 覆盖范围 | 推荐度 |
|------|------|--------|---------|--------|
| **pcbnew Python API** | API | ⭐⭐⭐⭐⭐ | PCB 全部操作 | 🥇 主路径 |
| **kicad-cli** | CLI | ⭐⭐⭐⭐ | 导出/DRC/BOM | 🥈 辅助路径 |
| **文件直接解析** | 脚本 | ⭐⭐⭐ | 读取工程信息 | 🥉 兜底 |
| GUI 自动化 | GUI | ⭐⭐ | 全部 | ❌ 不用 |

---

## 2. pcbnew Python API（主路径）

### 2.1 可用性

KiCad 自带 Python 解释器和 `pcbnew` 模块。安装在系统 Python 中也可通过 `import pcbnew` 使用（需配置路径）。

```python
import pcbnew

# 加载 PCB 文件
board = pcbnew.LoadBoard("project.kicad_pcb")

# 获取板子信息
print(f"板子尺寸: {board.GetBoardEdgesBoundingBox()}")
print(f"元件数量: {len(board.GetFootprints())}")
print(f"网络数量: {len(board.GetNets())}")
```

### 2.2 导出 Gerber

```python
import pcbnew

board = pcbnew.LoadBoard("project.kicad_pcb")

# 设置绘图选项
plot_options = pcbnew.PLOT_CONTROLLER()
plot_options.SetLayer(pcbnew.F_Cu)
plot_options.SetPlotFrameRef(False)

# 创建 Gerber 输出
# ...（详细 API 略，有官方文档）
```

### 2.3 运行 DRC

> ⚠️ **2026-08-05 验证修正**：KiCad 8 的 pcbnew **没有公开稳定的 DRC Python 接口**
>（此前示例中的 `pcbnew.DRC()` 并不存在）。DRC 请走 kicad-cli（见 §3.1），
> 其 `--format json` 输出即为结构化违规列表，效果等价且更稳定。

### 2.4 导出 BOM

```python
# pcbnew 本身不直接导出 BOM
# 但可以遍历元件列表生成结构化数据
for footprint in board.GetFootprints():
    ref = footprint.GetReference()
    value = footprint.GetValue()
    # 可以输出为 CSV/JSON
```

### 2.5 限制

- 需要在 KiCad 的 Python 环境中运行，或正确配置 `PYTHONPATH`
- 部分新版本 API 可能有变化（KiCad 7 → 8）
- 不能操作原理图（eeschema 有单独的 Python API）

---

## 3. kicad-cli（辅助路径）

### 3.1 可用命令

> ✅ 以下语法已对照 KiCad 8.0 官方 CLI 文档逐条验证（2026-08-05）。

```bash
# 导出 Gerber（每层一个文件，用于打样；注意是 gerbers 复数；
# 单数 gerber 是把多层合并到单个文件，用途不同，勿混淆）
kicad-cli pcb export gerbers -o output/gerber/ project.kicad_pcb

# 导出 BOM（注意是 sch 不是 sche）
kicad-cli sch export bom -o output/bom.csv project.kicad_sch

# 运行 DRC（JSON 结构化输出；--exit-code-violations 使有违规时退出码为 5，CI 友好）
kicad-cli pcb drc --format json --severity-all --exit-code-violations -o drc_report.json project.kicad_pcb

# 导出 3D 模型
kicad-cli pcb export step -o project.step project.kicad_pcb
```

### 3.2 优势

- 不需要配置 Python 环境
- 命令行参数稳定
- 适合简单的一步操作
- 返回标准退出码

### 3.3 劣势

- 无法做复杂操作（如遍历元件、修改 PCB）
- 每次调用启动新进程，开销较大
- 错误信息不如 Python API 详细

---

## 4. 推荐集成策略

对 codex-relay 项目：

| 动作 | 首选路径 | 原因 |
|------|---------|------|
| `open_project` | pcbnew API | 需要把 board 对象保留在内存 |
| `export_gerber` | 二者皆可 | CLI 更简单，API 更灵活 |
| `export_bom` | CLI (`kicad-cli sche export bom`) | 最直接 |
| `run_drc` | CLI（`kicad-cli pcb drc --format json`） | KiCad 8 pcbnew 无公开 DRC 接口；JSON 输出即可结构化解析 |
| `collect_artifacts` | 文件系统遍历 | 不依赖 KiCad |
| `get_project_info` | API + 文件解析 | API 拿 board 数据，文件解析拿工程配置 |

---

## 5. 环境检测

Adapter 初始化时需检测：

```python
def check_kicad_availability() -> dict:
    """
    返回:
    {
        "available": True/False,
        "pcbnew_available": True/False,
        "cli_available": True/False,
        "version": "8.0.4" or None,
        "python_path": "/usr/lib/kicad/...",
        "issues": ["未找到 pcbnew 模块", ...]
    }
    """
```

检测顺序：
1. `import pcbnew` → 主路径可用
2. `shutil.which("kicad-cli")` → CLI 可用
3. 二者都不可用 → 报告 `available=False`

---

## 6. 参考资料

- [KiCad pcbnew Python API 文档](https://docs.kicad.org/master/en/pcbnew/pcbnew.html)
- [kicad-cli 命令行参考](https://docs.kicad.org/master/en/cli/cli.html)
- KiCad 源码 `pcbnew/python/` 目录（实测 API）
