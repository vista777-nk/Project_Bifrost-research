# 调研报告：STM32 烧录自动化路径

> **日期**：2026-08-04
> **目的**：确认 STM32 固件烧录的 CLI/API 能力边界，为 adapter 设计提供依据
> **优先级原则**：pyocd > STM32CubeProgrammer CLI > stm32loader > OpenOCD > GUI

---

## 1. STM32 烧录路径总览

| 路径 | 类型 | 稳定性 | 覆盖范围 | 推荐度 |
|------|------|--------|---------|--------|
| **pyocd** | Python API | ⭐⭐⭐⭐⭐ | ARM Cortex-M 全系列 | 🥇 主路径 |
| **STM32CubeProgrammer CLI** | CLI | ⭐⭐⭐⭐ | STM32 全系列 | 🥈 主路径（官方） |
| **stm32loader** | Python 库 | ⭐⭐⭐ | UART bootloader | 🥉 辅助 |
| **OpenOCD** | CLI | ⭐⭐⭐ | 宽泛但配置复杂 | 备用 |
| GUI 自动化 | GUI | ⭐⭐ | 全部 | ❌ 不用 |

---

## 2. pyocd（Python API — 首选）

### 2.1 优势

- **纯 Python**，不需要额外安装 ST 工具
- 支持几乎所有 STM32 系列（通过 CMSIS-Pack）
- 结构化 Python API，便于错误处理
- 支持编程、校验、擦除、读取、调试

### 2.2 安装

```bash
pip install pyocd
```

### 2.3 核心操作示例

```python
from pyocd.core.helpers import ConnectHelper
from pyocd.flash.loader import FlashLoader
from pyocd.flash.flash import Flash

# 1. 识别设备
session = ConnectHelper.session_with_chosen_probe()
board = session.board
target = board.target
print(f"设备: {target.part_number}")
print(f"Flash: {target.memory_map.get_boot_memory()}")

# 2. 烧录固件
with open("firmware.bin", "rb") as f:
    firmware_data = f.read()

loader = FlashLoader(session)
loader.add_data(target.memory_map.get_boot_memory().start, firmware_data)
loader.commit()

# 3. 校验写入
flash = target.memory_map.get_boot_memory()
data = target.read_memory_block8(flash.start, len(firmware_data))
if data == firmware_data:
    print("校验通过")
else:
    print("校验失败")

# 4. 擦除
target.mass_erase()
```

### 2.4 限制

- 需要调试器（ST-Link、J-Link、CMSIS-DAP）
- 不是 ST 官方工具，极端情况下可能不支持最新芯片
- 需要正确的 CMSIS-Pack

---

## 3. STM32CubeProgrammer CLI（官方 CLI — 主路径备选）

### 3.1 命令示例

```bash
# 识别设备
STM32_Programmer_CLI -c port=SWD

# 烧录固件
STM32_Programmer_CLI -c port=SWD -w firmware.bin 0x08000000

# 校验写入
STM32_Programmer_CLI -c port=SWD -v firmware.bin 0x08000000

# 擦除
STM32_Programmer_CLI -c port=SWD -e all

# 读取 Flash 到文件
STM32_Programmer_CLI -c port=SWD -r output.bin 0x08000000 0x10000
```

### 3.2 优势

- ST 官方工具，支持最全
- 稳定的命令行接口
- 支持所有 STM32 系列
- 可通过子进程调用

### 3.3 劣势

- 需要单独安装（不是 pip 可装）
- 子进程调用，错误解析需正则匹配
- 没有结构化输出

---

## 4. stm32loader（UART Bootloader）

适用于通过串口（USART1）使用内建 bootloader 烧录的场景。

```python
import stm32loader

loader = stm32loader.Stm32Loader(port="COM3", baud=115200)
loader.connect()
loader.write(0x08000000, firmware_data)
loader.verify(0x08000000, firmware_data)
```

### 限制
- 仅适用于 UART bootloader 模式（需手动设置 BOOT0 引脚）
- 速度较慢（115200bps 典型）
- 不支持 SWD 调试

---

## 5. 推荐集成策略

对 codex-relay 项目的 STM32 adapter：

### 5.1 检测顺序

```python
def check_stm32_availability() -> dict:
    """
    按优先级检测:
    1. pyocd 是否可 import
    2. STM32_Programmer_CLI 是否在 PATH
    3. stm32loader 是否可 import
    """
```

### 5.2 动作映射

| 动作 | pyocd 实现 | CLI 备选 |
|------|-----------|---------|
| `identify_device` | `session_with_chosen_probe()` | `STM32_Programmer_CLI -c port=SWD` |
| `flash_firmware` | `FlashLoader.commit()` | `-w firmware.bin 0x08000000` |
| `verify_flash` | `read_memory_block8()` 对比 | `-v firmware.bin 0x08000000` |
| `erase_flash` | `mass_erase()` | `-e all` |
| `read_device_log` | `read_memory_block8()` | `-r output.bin` |
| `lock_device` | `call_function()` | `-ob RDP=0xBB` |
| `unlock_device` | `call_function()` | `-ob RDP=0xAA` |

### 5.3 安全规则（特别重要）

以下操作**必须** `confirmation_required`：
- `flash_firmware`（烧录）
- `erase_flash`（擦除）
- `lock_device`（锁定芯片）
- `unlock_device`（解锁芯片，会触发 Mass Erase）

以下操作可以自动执行：
- `identify_device`（识别设备）
- `verify_flash`（校验）
- `read_device_log`（读取）

---

## 6. 硬件测试环境需求

### 最低配置
- 1 块 STM32F4 或 STM32F1 开发板
- 1 个 ST-Link/V2 调试器
- USB 线缆

### 推荐配置
- STM32F407G-DISC1 开发板（板载 ST-Link）
- 一个已知可用的 firmware.bin 测试固件

---

## 7. 风险与注意事项

| 风险 | 应对 |
|------|------|
| 烧录中断导致芯片变砖 | 使用 STM32CubeProgrammer 的 Recovery 模式 |
| 错误固件烧入 | 烧录前校验固件文件格式和大小 |
| 调试器连接不稳定 | 重试机制（最多 3 次），降低 SWD 频率 |
| 写保护/读保护 | 检测并报告给用户，不自动绕过 |
| 供电不足 | 提示用户使用外部供电 |

---

## 8. 参考资料

- [pyocd 文档](https://pyocd.io/)
- [STM32CubeProgrammer 用户手册](https://www.st.com/en/development-tools/stm32cubeprog.html)
- [stm32loader PyPI](https://pypi.org/project/stm32loader/)
