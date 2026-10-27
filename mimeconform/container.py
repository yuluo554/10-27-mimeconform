"""容器层审计：mbox / Maildir（可选模块 M5 / 里程碑 M5）。

**变体纪律（data/README §7.7，plan/00 D3）**：``>From`` 转义是 **mboxo 约定，不是 RFC**；
mboxrd / mboxcl 的转义与长度前缀规则**互不相同**。因此：

* 全部规则只出 ``diff``；
* **所有变体的切分表都写入报告的 ``split_variants``**，``auto`` 只决定"主表"是哪一份；
* 报告必须写明"按 mboxo 读"还是"按 mboxrd 读"，不得只判一种"正确"。

骨架期 :func:`split_container` 抛 :class:`~mimeconform.errors.EngineNotReady`。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import constants as C
from ._pending import _not_ready
from .model import Defect


@dataclass(frozen=True, slots=True)
class MessageSpan:
    """一条消息在容器内的位置。``offset_kind = message-relative``（§7.10）。"""

    index: int                    # msg#<n>，从 1 开始
    start: int                    # 相对消息起点（From 行首）
    end: int
    file_offset: int              # 容器文件内的绝对偏移
    from_line: bytes = b""


@dataclass(frozen=True, slots=True)
class ContainerResult:
    primary_variant: str = C.MBOX_VARIANT_DEFAULT
    split_variants: dict[str, tuple[MessageSpan, ...]] = field(default_factory=dict)
    defects: tuple[Defect, ...] = field(default=())


def detect_variant(data: bytes) -> str:
    """按 §7.7 的**纯字节规则**判定主变体（不打分、不启发式）。

    * 出现 ``Content-Length:`` 头 → ``mboxcl``；
    * 否则出现 ``>From `` 且无 ``>>From `` → ``mboxo``；
    * 否则 ``mboxo``。
    """
    if b"\nContent-Length:" in b"\n" + data or data.startswith(b"Content-Length:"):
        return "mboxcl"
    if b"\n>From " in b"\n" + data and b"\n>>From " not in b"\n" + data:
        return "mboxo"
    return "mboxo"


def split_container(data: bytes, *, variant: str = C.MBOX_VARIANT_DEFAULT) -> ContainerResult:
    """按指定变体切分容器，并同时给出全部变体的切分表。"""
    raise _not_ready("split_container")
