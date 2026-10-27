"""字节扫描状态机：头块定位 → multipart 切分 → 递归子部件（模块 M1 / 里程碑 M2）。

**状态机契约（plan/02 §二，实现时不得改变语义）**::

    HEADER_BLOCK ──空行──▶ BODY
                        ├─ Content-Type: multipart/*; boundary=B ──▶ PART_BODY(B)
                        └─ message/rfc822 ──▶ 递归

    PART_BODY(B) 逐行扫描（\\r\\n 与裸 \\n 都接受，行界保留原始偏移）：
      "--"+B       → part 开始
      "--"+B+"--"  → multipart 关闭
      其余          → 归入当前 part 的字节区间

**纪律**：行界按 ``\\n`` 切分而非 ``str.splitlines()``（后者还会切 ``\\r`` / ``\\x0b`` / ``\\u2028``）；
boundary 比较按字节、不做大小写折叠；preamble/epilogue 不计入 ``body_sha256``。

骨架期 :func:`scan_message` 抛 :class:`~mimeconform.errors.EngineNotReady`。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import constants as C
from ._pending import _not_ready
from .model import Defect, Divergence, Node


@dataclass(frozen=True, slots=True)
class ScanResult:
    root: Node
    defects: tuple[Defect, ...] = field(default=())
    tree_alternatives: tuple[Node, ...] = field(default=())
    divergence: Divergence | None = None
    facts: dict[str, object] = field(default_factory=dict)


def split_lines(data: bytes, start: int = 0) -> list[tuple[int, bytes]]:
    """按 ``\\n`` 切行，返回 ``(行首偏移, 行字节含行尾)`` 列表。

    这是引擎的**唯一**切行实现：不做解码、不吞 ``\\r``、不把 ``\\x0b`` 当行界。
    Unicode 的 ``splitlines()`` 语义与 MIME 的行定义不同，用它会改变字节偏移。
    """
    if start < 0 or start > len(data):
        raise ValueError(f"start 越界: {start}")
    out: list[tuple[int, bytes]] = []
    pos = start
    while pos < len(data):
        nl = data.find(b"\n", pos)
        if nl < 0:
            out.append((pos, data[pos:]))
            break
        out.append((pos, data[pos : nl + 1]))
        pos = nl + 1
    if not data[start:]:  # 空输入 → 空列表（不是 [""]）
        return []
    return out


def scan_message(data: bytes, *, max_depth: int = C.MAX_DEPTH_DEFAULT) -> ScanResult:
    """把一封邮件的原始字节切成 multipart 树并产出 MC-B 系列缺陷。"""
    raise _not_ready("scan_message")
