"""传输编码审计：自写 base64 / QP 观察与解码（模块 M3 / 里程碑 M4）。

**为什么自写**（plan/03 §三）：需要 ``foreign_chars`` 计数与"非法填充/非法 ``=HH`` 的字节偏移"；
标准库解码器把这些信息丢掉或直接抛异常。``base64`` 只在测试端做交叉校验。

**纪律**：
* 行宽按 **octets**（不含 CRLF/LF）；
* base64 字母表外字符**按 RFC 2045 §6.8 忽略**并计数（"出现"本身不是违规，MC-T04 只出 note）；
* QP 非法 ``=HH`` **原样保留该字节**（不吞字符）—— SO 79133579 的 ``=ustomers`` 正是被吞的结果。

骨架期 :func:`observe_body_shape` / :func:`decode_base64` / :func:`decode_qp`
抛 :class:`~mimeconform.errors.EngineNotReady`。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ._pending import _not_ready
from .model import Defect


@dataclass(frozen=True, slots=True)
class Shape:
    """不依赖声明、按字节给出的实际形态。"""

    kind: str                       # text | base64 | qp | binary | empty
    line_max_octets: int = 0
    soft_breaks: int = 0
    foreign_chars: int = 0


@dataclass(frozen=True, slots=True)
class BodyFacts:
    declared_cte: str | None = None
    shape: Shape | None = None
    decoded_sha256: str | None = None
    defects: tuple[Defect, ...] = field(default=())


def observe_body_shape(body: bytes) -> Shape:
    """按字节判定实际形态（不做解码）。"""
    raise _not_ready("observe_body_shape")


def decode_base64(body: bytes) -> tuple[bytes, dict[str, object]]:
    """按 RFC 2045 §6.8 解码：字母表外字符忽略并计数，填充/长度问题记入 facts。"""
    raise _not_ready("decode_base64")


def decode_qp(body: bytes) -> tuple[bytes, dict[str, object]]:
    """解码 quoted-printable：非法 ``=HH`` 原样保留并登记偏移。"""
    raise _not_ready("decode_qp")


def audit_body(body: bytes, declared_cte: str | None) -> BodyFacts:
    """产出一个叶节点的正文级缺陷（MC-T 系列）。"""
    raise _not_ready("audit_body")
