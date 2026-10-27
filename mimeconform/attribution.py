"""归属与引用审计（模块 M4 / 里程碑 M5）。

**全部规则 ``diff`` / ``gray``，无 ``hard``**（plan/00 D11）：
``Content-Disposition`` 与 ``multipart/related`` 的规范定义不在本题核对的五部 RFC
（2045/2046/2047/2231/5322）之内。按"不得编造条款"红线，宁可全降级。

``filename`` 取值顺序：先 RFC 2231（含续行）→ 再 RFC 2047（plan/00 D10）。

骨架期 :func:`audit_attribution` 抛 :class:`~mimeconform.errors.EngineNotReady`。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ._pending import _not_ready
from .model import Defect, Node


@dataclass(frozen=True, slots=True)
class Attachment:
    path: str
    disposition: str | None
    filename: str | None
    name: str | None
    content_id: str | None
    referenced_by: tuple[str, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class AttributionResult:
    attachments: tuple[Attachment, ...] = field(default=())
    defects: tuple[Defect, ...] = field(default=())


def audit_attribution(root: Node, body_text_by_path: dict[str, str] | None = None) -> AttributionResult:
    """从树结构判定正文/附件归属与 ``cid:`` 引用闭合（MC-A 系列）。"""
    raise _not_ready("audit_attribution")
