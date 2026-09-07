"""
Bifrost Adapters — 抽象基类

所有工业软件适配器必须实现此接口。
每个 adapter 负责将 Core 的标准 Action 翻译为具体软件的调用。

接口方法:
- name / version / available_actions: 适配器元信息
- check_availability(): 检查软件是否已安装且可调用
- execute(action): 执行一个结构化动作，返回 ActionResult
- validate(result): 对 ActionResult 做适配器级校验，返回 ValidationReport

参考: docs/01-architecture.md §2.4
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.domain import Action, ActionResult, ValidationReport


class BaseAdapter(ABC):
    """工业软件适配器抽象基类。

    每个具体软件（KiCad/Keil/STM32CubeIDE/CCS/AutoCAD/Multisim/SolidWorks）
    各自实现此接口。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """适配器名称: kicad | keil | stm32cubeide | ccs | autocad | multisim | solidworks"""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """适配器版本"""
        ...

    @property
    @abstractmethod
    def available_actions(self) -> list[str]:
        """该适配器支持的动作名称列表"""
        ...

    @abstractmethod
    def check_availability(self) -> bool:
        """检查目标软件是否已安装且可调用。

        Returns:
            True 表示软件可用，False 表示不可用（未安装/版本不兼容/许可过期等）
        """
        ...

    def can_execute(self, action: Action) -> bool:
        """Return whether this action can run in the current environment.

        Adapters with filesystem-only actions can override this without making
        the target application appear available in ``list_adapters``.
        """

        return self.check_availability()

    @abstractmethod
    def execute(self, action: Action) -> ActionResult:
        """执行一个结构化动作。

        Args:
            action: 待执行的动作（含参数、超时、重试策略等）

        Returns:
            ActionResult: 结构化执行结果
        """
        ...

    @abstractmethod
    def validate(self, result: ActionResult) -> ValidationReport:
        """对 ActionResult 做适配器级别的校验。

        每个 adapter 可根据自身软件特性定义额外的校验逻辑。
        通用校验（文件存在、产物非空等）由 core/validators.py 的 ResultValidator 处理。

        Args:
            result: 待校验的动作结果

        Returns:
            ValidationReport: 校验报告
        """
        ...
