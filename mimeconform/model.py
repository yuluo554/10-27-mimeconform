"""数据模型与不变量。

``Defect`` 是题面要求的**六元组**（plan/01 §二）：``rule_id`` / ``class`` / ``severity`` /
``path`` / ``offset``(+``offset_kind``) / ``rfc``，另加 ``detail`` 与 ``related``。
``class`` 字段名在 Python 里会与内置名冲突，故属性名为 ``klass``，序列化键仍是 ``"class"``。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import constants as C

#: 树路径（data/README §7.3）：`0`、`0.2`、`0.2.1`；容器层为 `msg#3`（n 从 1 起）
#: 或 `msg#3/0.1`。路径不做任何重排、去重、大小写折叠。
_PATH_RE = re.compile(r"^(?:msg#[1-9]\d*(?:/\d+(?:\.\d+)*)?|\d+(?:\.\d+)*)$")
#: 规则编号（§7.2）：`MC-<域字母><两位数字>`；域字母固定为 B/H/T/A/C。
_RULE_RE = re.compile(r"^MC-[BHTAC]\d{2}$")


@dataclass(frozen=True, slots=True)
class Defect:
    """一条结构缺陷。构造即校验（见 :meth:`validate`）。"""

    rule_id: str
    klass: str
    severity: str
    path: str
    offset: int
    offset_kind: str
    rfc: str
    detail: str
    related: tuple[str, ...] = field(default=())

    def validate(self) -> None:
        """不变量校验。任何一条不成立即 ``ValueError``（不静默修正）。"""
        if not _RULE_RE.match(self.rule_id):
            raise ValueError(f"rule_id 形态非法（应为 MC-<B|H|T|A|C><两位>）: {self.rule_id!r}")
        if self.klass not in C.CLASSES:
            raise ValueError(f"class 必须是三值之一 {C.CLASSES}: {self.klass!r}")
        if self.severity not in C.SEVERITIES:
            raise ValueError(f"severity 必须是四档之一 {C.SEVERITIES}: {self.severity!r}")
        if not _PATH_RE.match(self.path):
            raise ValueError(f"path 形态非法（应为 0 / 0.1 / msg#3/0.1）: {self.path!r}")
        if self.offset < 0:
            raise ValueError(f"offset 不得为负: {self.offset}")
        if self.offset_kind not in C.OFFSET_KINDS:
            raise ValueError(f"offset_kind 非法 {C.OFFSET_KINDS}: {self.offset_kind!r}")
        # D8：rfc 不得为空；"没有条款"必须显式写成 none-by-design 或"仅定义 X、未定义 Y"
        if not self.rfc.strip():
            raise ValueError("rfc 不得为空：无条款时写 none-by-design（plan/00 D8）")
        if not self.detail.strip():
            raise ValueError("detail 不得为空：每条缺陷要说清发生了什么")

    def as_json(self) -> dict[str, object]:
        """规范化的机读形态（键序固定，供指纹与报告共用）。"""
        return {
            "rule_id": self.rule_id,
            "class": self.klass,
            "severity": self.severity,
            "path": self.path,
            "offset": self.offset,
            "offset_kind": self.offset_kind,
            "rfc": self.rfc,
            "detail": self.detail,
        }

    @property
    def sort_key(self) -> tuple[str, tuple[int, ...], int]:
        """§7.8 的排序键：``(rule_id, path, offset)``，path 按分段整数比。"""
        return (self.rule_id, path_key(self.path), self.offset)


def path_key(path: str) -> tuple[int, ...]:
    """把 ``msg#3/0.2.1`` / ``msg#3`` / ``0.10`` 变成可整数比较的键。

    ``0.10`` 排在 ``0.9`` 之后（按分段整数比，不按字符串比，§7.8）。
    容器层路径以消息序号作首段，保证 ``msg#2`` 排在 ``msg#10`` 之前。
    """
    if "/" in path:
        head, body = path.split("/", 1)
        return (int(head.split("#")[1]), *(int(seg) for seg in body.split(".")))
    if path.startswith("msg#"):
        return (int(path.split("#")[1]),)
    return tuple(int(seg) for seg in path.split("."))


@dataclass(frozen=True, slots=True)
class Header:
    name: str
    raw_value_sha256: str
    octets: int
    line_spans: tuple[tuple[int, int], ...] = field(default=())
    encoded_words: tuple[dict[str, object], ...] = field(default=())
    params: tuple[dict[str, object], ...] = field(default=())


@dataclass(frozen=True, slots=True)
class Node:
    """multipart 树的一个节点。"""

    path: str
    content_type: str
    boundary: str | None
    headers: tuple[Header, ...]
    body_range: tuple[int, int]
    body_sha256: str
    children: tuple["Node", ...] = field(default=())
    truncated: bool = False

    def validate(self) -> None:
        if not _PATH_RE.match(self.path):
            raise ValueError(f"节点 path 非法: {self.path!r}")
        if "/" in self.content_type and self.content_type != self.content_type.lower():
            raise ValueError(f"content_type 必须小写: {self.content_type!r}")
        if self.boundary is not None and not isinstance(self.boundary, str):
            raise ValueError("boundary 必须是 str 或 None")


@dataclass(frozen=True, slots=True)
class Divergence:
    """内层 boundary 重复时，两棵候选树的首个分歧位置（plan/00 D9）。"""

    path: str
    offset: int
    note: str


@dataclass(frozen=True, slots=True)
class AuditResult:
    """一次审计的完整产出（渲染层只消费它，不做判定）。"""

    input_name: str
    input_bytes: int
    input_sha256: str
    root: Node
    defects: tuple[Defect, ...]
    tree_alternatives: tuple[Node, ...] = field(default=())
    divergence: Divergence | None = None
    facts: dict[str, object] = field(default_factory=dict)
