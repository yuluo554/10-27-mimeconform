"""骨架期的模块占位（M5 收口后**已无引擎使用**；保留为 D16 的防腐层入口）。

**为什么还留着**：`plan/00` D16 的语义是"未实现的能力必须显式失败，绝不静默返回 0"。
M2–M5 逐棒把五个模块落地后，没有任何引擎还会抛 :class:`EngineNotReady`；但 CLI 里那条
防御性分支（`_run_audit` 的 `_engine_available()` 检查）仍然用本函数产出**具名异常**，
而不是 `raise NotImplementedError` —— 这样即使将来有人把某个引擎临时摘掉，退出码仍然走
`main()` 的统一映射（exit 1 + 明确文案），不会变成 traceback 或 0。

`tests/test_cli_contract.py::test_no_engine_remains_unwired` 断言"没有引擎再用它"；
本模块的存在**不是**"还没做完"的证据。
"""

from __future__ import annotations

from .errors import EngineNotReady

_NOT_READY = (
    "{name} 尚未实现：本项目的规则引擎自里程碑 M2 起逐棒落地"
    "（M2 树与边界 / M3 头编码 / M4 传输编码 / M5 归属与容器），M5 收口后五个模块全部落地。"
    "若看到本提示，说明当前树里的某个引擎被临时摘掉了 —— 审计请求会显式失败，不返回 0 "
    "（plan/00 D16：读不了/没实现绝不能被读成「干净」）。"
)


def _not_ready(name: str) -> EngineNotReady:
    return EngineNotReady(_NOT_READY.format(name=name))
