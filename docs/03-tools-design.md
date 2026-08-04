# 03 — 工具接口设计（AI 可读版）

> **前置阅读**：`02-data-models.md`
> **后续阅读**：`04-plugin-design.md`
> **用途**：精确定义每个 MCP 工具的输入参数、输出格式、错误场景、调用示例

---

## 工具总览

| # | 工具名 | 用途 | 风险 | 优先级 |
|---|--------|------|------|--------|
| 1 | `list_adapters` | 列出可用适配器 | 低 | P0（一期必做） |
| 2 | `run_action` | 执行结构化动作 | 中-高 | P0（一期必做） |
| 3 | `validate_result` | 校验执行结果 | 低 | P1（一期建议做） |
| 4 | `collect_logs` | 收集日志和产物 | 低 | P1（一期建议做） |
| 5 | `confirm_action` | 确认高风险动作 | 低 | P0（一期必做） |
| 6 | `preview_action` | 预览动作效果 | 低 | P2（二期） |

---

## 1. `list_adapters`

### 用途
列出当前系统中所有已安装且可用的软件适配器及其状态。

### 输入
```json
{
  "filter": "string (optional) - 按名称过滤: 'kicad' | 'stm32' | 'ti' | 'solidworks' | 空=全部"
}
```

### 输出
```json
{
  "success": true,
  "adapters": [
    {
      "name": "kicad",
      "display_name": "KiCad EDA",
      "version": "0.1.0",
      "software_version": "8.0.4",
      "available": true,
      "available_actions": ["open_project", "export_gerber", "export_bom", "run_drc", "collect_artifacts"],
      "priority_path": "pcbnew_api",
      "status_message": "",
      "capabilities": ["export", "validate", "pcb"]
    }
  ],
  "count": 1,
  "summary": "找到 1 个可用适配器"
}
```

### 错误场景
- 无：此工具不应失败（即使没有适配器也返回空列表）

---

## 2. `run_action`

### 用途
执行一个结构化动作。这是系统最核心的通用工具。

### 输入
```json
{
  "app": "string (必填) - 目标软件: kicad | stm32 | ti | solidworks",
  "action_name": "string (必填) - 动作名称",
  "parameters": {
    "key": "value (任意 JSON，由 adapter 解释)"
  },
  "mode": "string (optional, default='normal') - dry_run | normal | force",
  "task_id": "string (optional) - 关联的 Task ID，不提供则自动生成",
  "timeout_seconds": "integer (optional, default=300)",
  "retry_on_failure": "boolean (optional, default=true)"
}
```

### 输出（成功）
```json
{
  "success": true,
  "action_id": "act-a1b2c3d4",
  "task_id": "task-e5f6g7h8",
  "action_name": "export_gerber",
  "status": "success",
  "start_time": "2026-08-04T10:30:00Z",
  "end_time": "2026-08-04T10:30:15Z",
  "duration_ms": 15000,
  "summary": "成功导出 Gerber 文件到 output/gerber/ 目录，共 8 个文件",
  "artifacts": [
    {
      "path": "output/gerber/project-F_Cu.gbr",
      "size_bytes": 245760,
      "checksum": "sha256:abc123...",
      "mime_type": "application/x-gerber",
      "description": "顶层铜箔 Gerber"
    }
  ],
  "warnings": [],
  "errors": [],
  "logs": ["[10:30:00] 加载工程...", "[10:30:05] 开始导出...", "[10:30:15] 导出完成"],
  "validation": null,
  "next_suggestion": "建议使用 validate_result 检查导出结果",
  "raw_output": null,
  "metadata": {}
}
```

### 输出（需要确认）
```json
{
  "success": false,
  "action_id": "act-x1y2z3",
  "task_id": "task-e5f6g7h8",
  "action_name": "flash_firmware",
  "status": "confirmation_required",
  "start_time": "2026-08-04T10:30:00Z",
  "end_time": "2026-08-04T10:30:01Z",
  "duration_ms": 1000,
  "summary": "烧录操作需要用户确认",
  "artifacts": [],
  "warnings": ["即将擦除 Flash 并写入新固件，此操作不可撤销"],
  "errors": [
    {
      "error_code": "ERR_CONFIRMATION_REQUIRED",
      "severity": "needs_human",
      "message": "烧录固件到 STM32F407 需要显式确认",
      "suggested_action": "调用 confirm_action 工具确认或取消此操作",
      "context": {"device": "STM32F407", "firmware": "build/firmware.bin", "erase_first": true},
      "recoverable": true
    }
  ],
  "logs": [],
  "validation": null,
  "next_suggestion": "请调用 confirm_action(action_id='act-x1y2z3') 确认",
  "raw_output": null,
  "metadata": {}
}
```

### 输出（失败）
```json
{
  "success": false,
  "action_id": "act-err001",
  "task_id": "task-e5f6g7h8",
  "action_name": "open_project",
  "status": "failed",
  "start_time": "2026-08-04T10:30:00Z",
  "end_time": "2026-08-04T10:30:02Z",
  "duration_ms": 2000,
  "summary": "无法打开工程：文件不存在",
  "artifacts": [],
  "warnings": [],
  "errors": [
    {
      "error_code": "ERR_FILE_NOT_FOUND",
      "severity": "fatal",
      "message": "工程文件 'project.kicad_pro' 不存在",
      "suggested_action": "检查文件路径是否正确，确认工程文件存在",
      "context": {"path": "/home/user/project.kicad_pro"},
      "recoverable": false
    }
  ],
  "logs": ["[10:30:00] 尝试打开工程 /home/user/project.kicad_pro", "[10:30:02] 文件不存在"],
  "validation": null,
  "next_suggestion": "检查路径后重试",
  "raw_output": null,
  "metadata": {}
}
```

### 错误场景

| error_code | 说明 | 处理建议 |
|-----------|------|---------|
| `ERR_ADAPTER_NOT_FOUND` | 指定 app 没有可用适配器 | 先调用 `list_adapters` |
| `ERR_ACTION_NOT_SUPPORTED` | 该适配器不支持此动作 | 检查 `available_actions` |
| `ERR_CONFIRMATION_REQUIRED` | 需要用户确认 | 调用 `confirm_action` |
| `ERR_TIMEOUT` | 执行超时 | 可重试，增大 timeout |
| `ERR_FILE_NOT_FOUND` | 输入文件不存在 | 检查路径 |
| `ERR_PERMISSION_DENIED` | 权限不足 | 检查文件/设备权限 |
| `ERR_SOFTWARE_NOT_FOUND` | 工业软件未安装 | 安装软件后重试 |
| `ERR_UNKNOWN` | 未知错误 | 查看 `raw_output` 和 `logs` |

---

## 3. `validate_result`

### 用途
对指定的 `ActionResult` 做校验，确认输出是否满足预期。

### 输入
```json
{
  "action_id": "string (必填) - 要校验的 action_id",
  "checks": "array (optional) - 指定校验项，空=全部默认校验"
}
```

### 输出
```json
{
  "success": true,
  "validation": {
    "action_id": "act-a1b2c3d4",
    "passed": true,
    "checks": [
      {
        "check_name": "file_exists",
        "status": "passed",
        "message": "所有 8 个 Gerber 文件均存在",
        "evidence": "output/gerber/ 目录含 8 个 .gbr 文件"
      },
      {
        "check_name": "file_size",
        "status": "passed",
        "message": "所有文件大小在正常范围内",
        "evidence": "最小 1.2KB, 最大 245KB, 平均值 45KB"
      },
      {
        "check_name": "drc_errors",
        "status": "warning",
        "message": "DRC 发现 2 个警告，0 个错误",
        "evidence": "drc_report.txt"
      }
    ],
    "failed_checks": [],
    "evidence": ["output/gerber/", "drc_report.txt"],
    "recommendation": "导出结果正常，DRC 有 2 个警告建议人工查看",
    "validated_at": "2026-08-04T10:31:00Z"
  }
}
```

### 错误场景
- `ERR_ACTION_NOT_FOUND`：指定的 action_id 不存在
- `ERR_VALIDATION_NOT_APPLICABLE`：该动作类型不支持校验

---

## 4. `collect_logs`

### 用途
收集指定动作或任务的日志、错误信息和产物列表。

### 输入
```json
{
  "action_id": "string (optional) - 指定动作 ID",
  "task_id": "string (optional) - 指定任务 ID（收集该任务下所有动作的日志）",
  "include_raw_output": "boolean (optional, default=false)",
  "format": "string (optional, default='json') - json | text"
}
```

### 输出
```json
{
  "success": true,
  "action_id": "act-a1b2c3d4",
  "task_id": "task-e5f6g7h8",
  "logs": ["[10:30:00] ...", "[10:30:05] ...", "[10:30:15] ..."],
  "errors": [],
  "artifacts": [...],
  "raw_output": null,
  "summary": "共收集 3 条日志，0 个错误，8 个产物"
}
```

---

## 5. `confirm_action`

### 用途
对之前被标记为 `confirmation_required` 的动作进行显式确认或取消。

### 输入
```json
{
  "action_id": "string (必填) - 要确认的动作 ID",
  "confirm": "boolean (必填) - true=确认执行, false=取消",
  "reason": "string (optional) - 确认或取消的原因"
}
```

### 输出（确认）
```json
{
  "success": true,
  "action_id": "act-x1y2z3",
  "confirmed": true,
  "message": "已确认执行 flash_firmware",
  "next_step": "系统将自动执行该动作，请等待结果"
}
```

### 输出（取消）
```json
{
  "success": true,
  "action_id": "act-x1y2z3",
  "confirmed": false,
  "message": "已取消 flash_firmware",
  "next_step": "动作已取消，可以修改参数后重试"
}
```

### 错误场景
- `ERR_ACTION_NOT_FOUND`
- `ERR_NOT_IN_CONFIRMABLE_STATE`：动作不处于"等待确认"状态

---

## 6. `preview_action`（二期）

### 用途
预览一个动作会发生什么，不实际执行（dry-run）。

### 输入
```json
{
  "app": "string (必填)",
  "action_name": "string (必填)",
  "parameters": {}
}
```

### 输出
```json
{
  "success": true,
  "preview": {
    "will_modify_files": ["output/gerber/"],
    "will_create_files": ["output/gerber/project-F_Cu.gbr", "..."],
    "will_delete_files": [],
    "estimated_duration_seconds": 15,
    "requires_confirmation": false,
    "risks": ["会覆盖 output/gerber/ 下的同名文件"],
    "warnings": []
  }
}
```

---

## 7. 工具调用流程示例

### 场景：用户说"把 KiCad 工程导出 Gerber 并检查"

```
Step 1: list_adapters (filter="kicad")
  → 确认 KiCad 可用，获得 available_actions

Step 2: run_action (app="kicad", action_name="open_project", parameters={"project_path": "..."})
  → ActionResult (success=true)

Step 3: run_action (app="kicad", action_name="export_gerber", parameters={"output_dir": "..."})
  → ActionResult (success=true, artifacts=[...])

Step 4: validate_result (action_id="act-...")
  → ValidationReport (passed=true)

Step 5: collect_logs (action_id="act-...")
  → 汇总日志和产物
```

---

## 8. 下一步

继续阅读 `04-plugin-design.md` — Codex 插件层如何组织 Skill 和 MCP Server。
