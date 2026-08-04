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

| 路径 | 类型 | 稳定性 | 推荐 |
|------|------|--------|:---:|
| XML 文件解析 | 脚本 | ⭐⭐⭐ | 🥇 |
| COM (Multisim.Application) | API | ⭐⭐⭐ | 🥈 |
| LVM 导出（LabVIEW） | 互操作 | ⭐⭐ | 辅助 |

**关键能力**：
- Multisim 工程文件 (.ms14) 本质是 XML，可直接解析电路结构
- COM 接口可读取仿真数据、导出网表
- 网表可导出为 SPICE 格式

**环境检测**：`shutil.which("multisim.exe")`

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
| Phase 1 | Multisim | XML 解析 | —（零依赖） |
| Phase 2 | STM32CubeIDE | Eclipse headless CLI | CubeIDE 安装路径 |
| Phase 2 | CCS | DSS + Theia CLI | CCS 安装路径 |
| Phase 3 | Keil MDK | UV4 CLI | Keil 安装路径 |
| Phase 4 | SolidWorks | COM | pywin32（仅 Windows） |
| Phase 5 | AutoCAD | accoreconsole + COM | pywin32 |
| Phase 4 | SolidWorks | COM | pywin32（仅 Windows） |
