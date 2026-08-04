# 调研报告：实际软件栈自动化路径

> **日期**：2026-08-04
> **目的**：确认用户实际安装的 7 款工业软件的 CLI/API 能力边界
> **策略**：每款软件标注主路径（🥇）、备选路径（🥈）、兜底方案（🥉）

---

## 软件清单

| # | 软件 | 版本 | 领域 | 优先级 |
|---|------|------|------|:---:|
| 1 | KiCad | 8.0.9 (x86_64) | PCB 设计 | Phase 1 |
| 2 | Keil MDK | 5.39 (64bit) | ARM 嵌入式开发 | Phase 3 |
| 3 | STM32CubeIDE | 1.17.0 (推荐) | STM32 集成开发 | Phase 2 |
| 4 | Code Composer Studio | 12.8.1 (推荐) | TI 芯片开发 | Phase 2 |
| 5 | AutoCAD | 2022 | CAD 绘图 | Phase 5 |
| 6 | Multisim | 14.3 | 电路仿真 | Phase 1 |
| 7 | SolidWorks | 2024 SP5 (64bit) | 3D CAD/机械设计 | Phase 4 |

---

## 1. KiCad 8.0.9

| 路径 | 类型 | 稳定性 | 推荐 |
|------|------|--------|:---:|
| pcbnew Python API | API | ⭐⭐⭐⭐⭐ | 🥇 |
| kicad-cli | CLI | ⭐⭐⭐⭐ | 🥈 |

**关键能力**：
- `pcbnew.LoadBoard()` — 加载 PCB 文件
- Gerber 导出（plot）、DRC 运行、BOM 遍历
- 详见 `docs/research-kicad-cli.md`

**环境检测**：`import pcbnew` + `shutil.which("kicad-cli")`

---

## 2. Keil MDK 5.39

| 路径 | 类型 | 稳定性 | 推荐 |
|------|------|--------|:---:|
| UV4 CLI | CLI | ⭐⭐⭐⭐ | 🥇 |
| CMSIS-DAP / J-Link | 调试器协议 | ⭐⭐⭐ | 🥈 |

**关键能力**：
```bash
# 编译工程
UV4.exe -b project.uvprojx -t "Target 1" -o build.log

# 烧录（通过 J-Link / ST-Link）
UV4.exe -f project.uvprojx -t "Target 1"
```

**环境检测**：`shutil.which("UV4.exe")` 或注册表查找 Keil 安装路径

---

## 3. STM32CubeIDE

| 路径 | 类型 | 稳定性 | 推荐 |
|------|------|--------|:---:|
| Eclipse headless CLI | CLI | ⭐⭐⭐⭐ | 🥇 |
| STM32CubeMX CLI（内嵌） | CLI | ⭐⭐⭐ | 🥈 |
| pyocd（调试器） | Python API | ⭐⭐⭐ | 辅助 |

**关键能力**：
```bash
# 导入工程
stm32cubeide.exe --launcher.suppressErrors -nosplash -application org.eclipse.cdt.managedbuilder.core.headlessbuild -import /path/to/project

# 编译
stm32cubeide.exe -nosplash -application org.eclipse.cdt.managedbuilder.core.headlessbuild -build "Project/Release"

# 烧录（内嵌 STM32CubeProgrammer）
STM32_Programmer_CLI -c port=SWD -w firmware.elf
```

**环境检测**：`shutil.which("stm32cubeide.exe")` 或 `shutil.which("STM32_Programmer_CLI.exe")`

---

## 4. Code Composer Studio (CCS) 12.8.1

| 路径 | 类型 | 稳定性 | 推荐 |
|------|------|--------|:---:|
| Theia headless CLI | CLI | ⭐⭐⭐⭐ | 🥇 |
| DSS (Debug Server Scripting) | JS API | ⭐⭐⭐⭐ | 🥇 |
| UniFlash CLI | CLI | ⭐⭐⭐ | 🥈 |

**关键能力**：
```bash
# 编译
ccstudio.exe -nosplash -application org.eclipse.cdt.managedbuilder.core.headlessbuild -build "Project/Release"

# 烧录/调试（DSS JavaScript）
dslite.bat --mode flash -c targetConfig.ccxml -f firmware.out
```

**DSS 脚本示例**（JavaScript）：
```javascript
var ds = new DebugServer();
ds.setConfig("targetConfig.ccxml");
ds.connect();
ds.memory.loadRaw(0x00000000, "firmware.bin", 32, false);
ds.disconnect();
```

**环境检测**：`shutil.which("ccstudio.exe")` 或 `shutil.which("dslite.bat")`

---

## 5. AutoCAD 2022

| 路径 | 类型 | 稳定性 | 推荐 |
|------|------|--------|:---:|
| accoreconsole | CLI | ⭐⭐⭐⭐ | 🥇 |
| COM (AutoCAD.Application) | API | ⭐⭐⭐⭐ | 🥈 |
| Script (.scr) | 脚本 | ⭐⭐⭐ | 🥉 |

**关键能力**：
```bash
# 无头模式执行脚本
accoreconsole.exe /i "drawing.dwg" /s "script.scr" /p "AutoCAD"

# COM 接口（Python pywin32）
import win32com.client
acad = win32com.client.Dispatch("AutoCAD.Application")
doc = acad.Documents.Open("drawing.dwg")
```

**环境检测**：`shutil.which("accoreconsole.exe")`

---

## 6. Multisim 14.3

> **2026-08-05 联网验证更新**：此前"主路径 = .ms14 XML 解析"的假设**已被推翻**。
> `.ms14` 是 NI 专有格式，无证据表明可直接按 XML 解析。经验证的可行路径如下。

| 路径 | 类型 | 稳定性 | 推荐 |
|------|------|--------|:---:|
| COM Automation API（pywin32） | API | ⭐⭐⭐⭐ | 🥇 |
| 命令行 netlist 仿真 | CLI | ⭐⭐⭐ | 🥈 |
| LVM 导出（LabVIEW） | 互操作 | ⭐⭐ | 辅助 |
| .ms14 直接解析 | 脚本 | ⭐ | ❌ 放弃（专有格式，非 XML） |

**已验证的关键能力**（COM Automation API，经 NI 官方 KB 与开源项目 [Multisim-MCP](https://github.com/Last-emo-boy/Multisim-MCP) 双重验证）：
- 打开/保存设计文件（.ms14 及 .ms8+ 旧格式）
- 枚举元件/探针/输入/输出、修改元件参数、替换元件
- 运行仿真（瞬态 / AC 扫描 / DC 工作点）、采集仿真输出数据
- 导出电路图像
- SPICE netlist 直通：不打开 .ms14，直接对内联 netlist 做仿真，适合程序化生成电路

**命令行模式**：NI 官方文档确认存在（ni.com/docs → Multisim → Command Line），可基于 netlist 做批处理仿真，但能力远少于 COM API。

**重要限制**：
- 仅 Windows；若 Multisim COM 组件为 32-bit，必须用 32-bit Python 运行
- COM 接口无官方完整文档，最佳参考是 Multisim-MCP 的 `com_adapter.py` 实现
- 修改元件前需停止仿真；建议所有修改走 snapshot + save_as，不覆盖原设计文件

**环境检测**：`win32com.client.Dispatch("Multisim.Application")` + `shutil.which("multisim.exe")`

**借鉴资源**：
- [Last-emo-boy/Multisim-MCP](https://github.com/Last-emo-boy/Multisim-MCP) — Multisim COM Automation 的 MCP Server（61 工具，pywin32，分层架构与本项目一致，含 snapshot/audit log 安全模式）
- [hodini007/Elecsyn](https://github.com/hodini007/Elecsyn) — AI 生成 SPICE netlist 并导入 Multisim 的自动化代理

---

## 7. SolidWorks 2024 SP5

| 路径 | 类型 | 稳定性 | 推荐 |
|------|------|--------|:---:|
| COM (SldWorks.Application) | API | ⭐⭐⭐⭐ | 🥇 |
| Macro (.swp) | 宏 | ⭐⭐⭐ | 🥈 |
| Document Manager API | API | ⭐⭐⭐ | 辅助 |

**关键能力**：
```python
import win32com.client
sw = win32com.client.Dispatch("SldWorks.Application")
doc = sw.OpenDoc("part.sldprt", 1)  # 1=part, 2=assembly, 3=drawing
# 导出 STEP
doc.SaveAs3("part.step", 0, 0)  # swSaveAsCurrentVersion
```

**环境检测**：尝试 `win32com.client.Dispatch("SldWorks.Application")`

---

## 集成优先级总结

| 批次 | 软件 | 主导路径 | 关键依赖 |
|:---:|------|---------|---------|
| Phase 1 | KiCad | pcbnew Python API | KiCad Python 环境 |
| Phase 1 | Multisim | COM Automation API | pywin32（仅 Windows） |
| Phase 2 | STM32CubeIDE | Eclipse headless CLI | CubeIDE 安装路径 |
| Phase 2 | CCS | DSS + Theia CLI | CCS 安装路径 |
| Phase 3 | Keil MDK | UV4 CLI | Keil 安装路径 |
| Phase 4 | SolidWorks | COM | pywin32（仅 Windows） |
| Phase 5 | AutoCAD | accoreconsole + COM | pywin32 |
