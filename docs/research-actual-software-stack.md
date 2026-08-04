# 调研报告：实际软件栈自动化路径

> **日期**：2026-08-04
> **状态**：基于用户实际安装的 6 款软件重新评估

---

## 0. 软件清单与自动化路径总览

| # | 软件 | 版本 | 主路径 | 自动化潜力 | 推荐优先级 |
|---|------|------|--------|:---:|:---:|
| 1 | **KiCad** | 8.0.9 | pcbnew Python API | ⭐⭐⭐⭐⭐ | 🥇 第一 |
| 2 | **Keil MDK** | 5.39 | UV4.exe CLI | ⭐⭐⭐⭐ | 🥈 第二 |
| 3 | **STM32CubeMX** | 6.15.0 | CLI 脚本模式 | ⭐⭐⭐⭐ | 🥈 第二 |
| 4 | **SolidWorks** | 2024 SP5 | COM (pywin32) | ⭐⭐⭐⭐ | 🥉 第三 |
| 5 | **AutoCAD** | 2022 | COM + accoreconsole | ⭐⭐⭐ | 🥉 第三 |
| 6 | **Multisim** | 14.3 | 受限（文件解析） | ⭐⭐ | 第四 |

---

## 1. KiCad 8.0.9

> **结论**：无变化，仍是首发首选。pcbnew Python API 是最强自动化路径。

| 动作 | 路径 | 稳定性 |
|------|------|:---:|
| `open_project` | `pcbnew.LoadBoard()` | ⭐⭐⭐⭐⭐ |
| `export_gerber` | `pcbnew.PLOT_CONTROLLER` 或 `kicad-cli pcb export gerber` | ⭐⭐⭐⭐⭐ |
| `export_bom` | `kicad-cli sche export bom` | ⭐⭐⭐⭐ |
| `run_drc` | `pcbnew.DRC` | ⭐⭐⭐⭐ |
| `collect_artifacts` | 文件系统遍历 | ⭐⭐⭐⭐⭐ |

**版本注意**：8.0.9 属于 KiCad 8 系列，API 稳定，与 8.0.x 通用。

---

## 2. Keil MDK 5.39（⭐ 新发现的关键工具）

> **结论**：Keil 的 UV4.exe 拥有成熟的 CLI，可做编译 + 烧录 + 调试的全流程自动化。
> 这比我们原来计划的 pyocd/CubeProgrammer 路径更直接——用户的 STM32 工程本身就建在 Keil 里。

### 2.1 CLI 命令

```bash
# 编译工程
UV4.exe -b project.uvprojx -o build.log -j0

# 烧录固件（通过 ST-Link/ULINK）
UV4.exe -f project.uvprojx -t "TargetName"

# 清理
UV4.exe -c project.uvprojx

# 批处理模式（静默运行）
UV4.exe -b project.uvprojx -o build.log -j0 -z
```

### 2.2 关键发现

- `-b` 构建、`-f` 烧录、`-c` 清理，参数非常清晰
- 返回标准退出码（0=成功，非零=失败）
- `-o` 输出日志到文件，方便我们结构化解析
- **支持多 Target**：`-t` 指定烧录目标

### 2.3 Bifrost 适配器建议动作

| 动作 | 实现方式 | 风险 |
|------|---------|:---:|
| `build_project` | `UV4.exe -b -o build.log` | 🟢 低 |
| `flash_firmware` | `UV4.exe -f -t "Target"` | 🔴 高（需确认） |
| `clean_project` | `UV4.exe -c` | 🟢 低 |
| `read_build_log` | 解析 build.log | 🟢 低 |
| `identify_target` | 解析 .uvprojx XML | 🟢 低 |

---

## 3. STM32CubeMX 6.15.0（⭐ 新发现）

> **结论**：CubeMX 有 CLI 脚本模式，可以从 `.ioc` 文件自动生成代码。
> 典型场景：用 CubeMX 配好引脚 → 生成 Keil 工程 → Keil 编译烧录。

### 3.1 CLI 命令

```bash
# 从 .ioc 文件生成代码
STM32CubeMX.exe -q script_file -s

# script_file 示例内容：
# config load project.ioc
# generate code project_output_dir
# exit
```

或直接：
```bash
java -jar STM32CubeMX.exe -q script.txt
```

### 3.2 关键限制

- 脚本语法文档不够完善，需实测验证
- 生成的代码目录结构固定
- **与 Keil 配合**形成完整工具链

### 3.3 Bifrost 适配器建议动作

| 动作 | 说明 | 风险 |
|------|------|:---:|
| `load_ioc` | 加载 .ioc 配置文件 | 🟢 低 |
| `generate_code` | 从 .ioc 生成 HAL 代码 | 🟡 中（覆盖文件） |
| `export_config_report` | 导出引脚配置报告 | 🟢 低 |

### 3.4 与 Keil 的工作流组合

```
STM32CubeMX 生成代码 → Keil UV4 编译 → Keil UV4 烧录
     (adapter)           (adapter)        (adapter)
```

这是 STM32 开发的标准流程。Bifrost 应该将二者编排为工作流。

---

## 4. SolidWorks 2024 SP5

> **结论**：COM 接口是 SolidWorks 自动化的黄金标准。2024 版本 API 非常成熟。

### 4.1 COM 连接

```python
import win32com.client

sw = win32com.client.Dispatch("SldWorks.Application")
sw.Visible = True  # 或 False 做后台处理

doc = sw.OpenDoc("path/to/part.sldprt", 1)  # 1=part, 2=assembly, 3=drawing
```

### 4.2 关键动作

| 动作 | COM API | 说明 |
|------|---------|------|
| `open_document` | `sw.OpenDoc(path, type)` | 打开零件/装配体/工程图 |
| `export_step` | `doc.SaveAs(path)` 或 `sw.ExportToSTEP()` | 导出 STEP |
| `export_drawing_pdf` | `doc.SaveAs(path)` | 工程图导出 PDF |
| `export_drawing_dwg` | `doc.SaveAs(path)` | 工程图导出 DWG |
| `get_mass_properties` | `doc.GetMassProperties()` | 质量属性 |
| `collect_custom_properties` | `doc.CustomInfo()` | 自定义属性 |

### 4.3 限制

- **仅 Windows**（COM 依赖）
- 需要 SolidWorks 已安装且许可有效
- 首次启动较慢（10-30 秒）

---

## 5. AutoCAD 2022（⭐ 新发现）

> **结论**：AutoCAD 有多种自动化路径。`accoreconsole.exe` 可做无头脚本执行。

### 5.1 自动化路径

| 路径 | 类型 | 能力 | 推荐度 |
|------|------|------|:---:|
| `accoreconsole.exe` | CLI | 运行脚本、处理 DWG | 🥇 |
| COM (pywin32) | API | 完整对象模型 | 🥇 |
| .NET API | API | 高级操作 | 🥈 |
| AutoLISP 脚本 | 脚本 | 传统自动化 | 🥉 |

### 5.2 CLI 命令

```bash
# Core Console 无头运行
accoreconsole.exe /i "input.dwg" /s "script.scr" /l "en-US"

# 通过 COM
python -c "import win32com.client; acad = win32com.client.Dispatch('AutoCAD.Application'); ..."
```

### 5.3 Bifrost 适配器建议动作

| 动作 | 说明 |
|------|------|
| `open_drawing` | 打开 DWG 文件 |
| `export_pdf` | 导出 PDF 图纸 |
| `export_dxf` | 导出 DXF 交换格式 |
| `run_lisp_script` | 执行 AutoLISP 脚本 |
| `get_layer_list` | 读取图层信息 |
| `purge_drawing` | 清理未使用对象 |

### 5.4 与 SolidWorks 的协同

AutoCAD ↔ SolidWorks 之间有很强的数据交换需求：
- SolidWorks 工程图 → AutoCAD DWG
- AutoCAD 布局 → SolidWorks 草图参考

---

## 6. Multisim 14.3（⚠️ 自动化最受限）

> **结论**：Multisim 是 NI 的电路仿真工具，自动化路径非常有限。

### 6.1 已知路径

| 路径 | 可行性 | 说明 |
|------|:---:|------|
| LabVIEW 集成 | ⚠️ 需 LabVIEW | 通过 VI 调用 |
| 文件解析 | ✅ | .ms14 文件是 XML 格式 |
| GUI 自动化 | ❌ 不推荐 | 最后手段 |

### 6.2 务实策略

Multisim 的适配器建议**退化为文件级操作**，不试图控制软件本身：

| 动作 | 实现方式 |
|------|---------|
| `read_circuit_info` | 解析 .ms14 XML 文件 |
| `export_netlist` | 从 XML 提取网表 |
| `collect_simulation_results` | 解析导出的 CSV 结果文件 |

### 6.3 风险评估

- 版本格式可能随 Multisim 版本变化
- 不是所有信息都在 XML 中可读
- 建议 Phase 4 或更后处理

---

## 7. 重新排定的适配器优先级

| 优先级 | 软件 | Phase | 理由 |
|:---:|------|:---:|------|
| 🥇 | **KiCad 8.0.9** | Phase 2 | API 最成熟、任务最标准化、无硬件依赖 |
| 🥈 | **Keil MDK 5.39** | Phase 3 | CLI 成熟、STM32 核心工具、与 CubeMX 协同 |
| 🥈 | **STM32CubeMX 6.15.0** | Phase 3 | CLI 可用、与 Keil 形成工具链 |
| 🥉 | **SolidWorks 2024 SP5** | Phase 4 | COM 接口强大但仅 Windows、启动慢 |
| 🥉 | **AutoCAD 2022** | Phase 4 | 与 SolidWorks 协同价值高、COM 可用 |
| 4 | **Multisim 14.3** | Phase 5+ | 自动化受限、退化为文件解析 |

---

## 8. 与原企划的差异对照

| 原计划软件 | 实际软件 | 变化 |
|-----------|---------|------|
| KiCad ✅ | KiCad 8.0.9 | 版本明确化 |
| STM32 烧录（pyocd/CubeProgrammer） | **Keil MDK + CubeMX** | 烧录路径变了！Keil CLI 是更直接的入口 |
| TI ❌ 删除 | — | 用户没有 TI 工具链 |
| SolidWorks ✅ | SolidWorks 2024 SP5 | 版本明确化 |
| — 🆕 | **AutoCAD 2022** | 新增 |
| — 🆕 | **Multisim 14.3** | 新增（自动化受限） |

---

## 9. 关键架构影响

### 9.1 Keil + CubeMX 组合改变了 STM32 适配器设计

原来我们假设用 pyocd 直接烧录裸固件。现在用户有 Keil 工程 + CubeMX 配置，工作流变成：

```
STM32CubeMX(.ioc) → 生成代码 → Keil UV4(编译) → Keil UV4(烧录) → 硬件
   ↑ Bifrost 驱动       ↑ Bifrost 驱动  ↑ Bifrost 驱动(需确认)
```

这意味着我们的 STM32 adapter 需要拆成两个子 adapter（`stm32cubemx` + `keil`），或作为一个组合 adapter。

### 9.2 AutoCAD + SolidWorks 协同

两个 CAD 工具互补：SolidWorks 擅长 3D，AutoCAD 擅长 2D 工程图。Bifrost 可以在二者之间做格式转换桥梁。

### 9.3 Multisim 的务实定位

不要试图做 GUI 自动化。定位为"电路信息读取器"——解析 .ms14 XML，提取网表和仿真结果。

---

## 10. 更新后的适配器目录建议

```
codex-relay/adapters/
├── base.py                        # BaseAdapter 抽象接口
├── kicad/                         # KiCad 8.0.9（Phase 2）
├── keil/                          # Keil MDK 5.39（Phase 3）
├── stm32cubemx/                   # STM32CubeMX 6.15.0（Phase 3）
├── solidworks/                    # SolidWorks 2024 SP5（Phase 4）
├── autocad/                       # AutoCAD 2022（Phase 4）
└── multisim/                      # Multisim 14.3（Phase 5+）
```
