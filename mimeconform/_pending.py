"""骨架期的模块占位（M2–M5 逐棒替换为真实实现）。

**为什么单独放一个模块**：plan/02 的依赖规则把六个业务模块列为独立文件；
骨架期它们必须**存在且可 import**（否则 AST 守门与"文档点名的工具/模块"判据无从落地），
但**不得静默通过**——任何调用都抛 :class:`EngineNotReady`，由 CLI 映射成 exit 1。
"""

from __future__ import annotations

from .errors import EngineNotReady

_NOT_READY = (
    "{name} 尚未实现：本项目的规则引擎自里程碑 M2 起逐棒落地"
    "（M2 树与边界 / M3 头编码 / M4 传输编码 / M5 归属与容器）。"
    "骨架期任何审计请求都会显式失败，不返回 0 —— 读不了/没实现绝不能被读成「干净」"
    "（plan/00 D16）。"
)


def _not_ready(name: str) -> EngineNotReady:
    return EngineNotReady(_NOT_READY.format(name=name))
