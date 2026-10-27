"""缺陷台账：校验、排序、指纹、唯一序列化入口（data/README §7.8）。

**为什么指纹要两套**（plan/00 决策记录）：
``fingerprint`` 变了 = 判定/规则变了；``tree_digest`` 变了 = 解析结果或输入变了。
混用一个摘要就无法归因。

**自检必须挂在 :func:`build` 里**（不是 ``__main__``）——``--check`` 等路径都要经过它
（skill「自检只写在 ``__main__`` 里」形态）。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence

from . import constants as C
from .model import Defect, Node, path_key


def validate_all(defects: Iterable[Defect]) -> None:
    """逐条校验；任何一条不合法即抛错（不跳过、不修正）。"""
    for defect in defects:
        defect.validate()


def sorted_defects(defects: Iterable[Defect]) -> tuple[Defect, ...]:
    """§7.8：按 ``(rule_id, path, offset)`` 升序，path 按分段整数比。"""
    return tuple(sorted(defects, key=lambda d: d.sort_key))


def _canonical_line(payload: dict[str, object]) -> str:
    """规范 JSON 行：固定键序由调用方保证，``ensure_ascii=true``，无空格分隔。"""
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def fingerprint(defects: Sequence[Defect]) -> str:
    """§7.8 缺陷集指纹：``sha256(按 (rule_id, path, offset) 排序后的规范 JSON 行)``。

    参与指纹的字段固定为 ``rule_id/class/severity/path/offset/offset_kind/rfc``
    （与 :meth:`Defect.as_json` 的键序一致，但**去掉 detail** —— detail 是叙述文本，
    允许措辞改进而不改变"判定变了没有"这一判断）。
    """
    lines: list[str] = []
    for defect in sorted(defects, key=lambda d: d.sort_key):
        payload = {
            "rule_id": defect.rule_id,
            "class": defect.klass,
            "severity": defect.severity,
            "path": defect.path,
            "offset": defect.offset,
            "offset_kind": defect.offset_kind,
            "rfc": defect.rfc,
        }
        lines.append(_canonical_line(payload))
    joined = "\n".join(lines)  # 末尾无换行（§7.8）
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _iter_nodes(root: Node) -> Iterable[Node]:
    yield root
    for child in root.children:
        yield from _iter_nodes(child)


def tree_digest(root: Node) -> str:
    """§7.8 树形指纹：``[path, content_type(小写), boundary|None, body_sha256]`` 按 path 排序。"""
    rows = [
        [node.path, node.content_type.lower(), node.boundary, node.body_sha256]
        for node in _iter_nodes(root)
    ]
    rows.sort(key=lambda row: path_key(str(row[0])))
    joined = _canonical_line(rows)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def build(defects: Iterable[Defect], root: Node | None = None) -> dict[str, object]:
    """构造台账。

    返回结构（机读形态的唯一形状）::

        {"defects": [...], "count": N, "by_class": {...}, "by_severity": {...},
         "none_by_design": N, "fingerprint": "...", "tree_digest": "..." | None}

    **自检在本函数内**：校验、排序、计数一致性、指纹复算全部在这里做。
    """
    ordered = sorted_defects(defects)
    validate_all(ordered)

    by_class = {name: 0 for name in C.CLASSES}
    by_severity = {name: 0 for name in C.SEVERITIES}
    for defect in ordered:
        by_class[defect.klass] += 1
        by_severity[defect.severity] += 1

    if sum(by_class.values()) != len(ordered):  # 三值封闭的自检
        raise AssertionError("class 计数与缺陷数不一致：出现了三值之外的值")

    ledger: dict[str, object] = {
        "defects": [d.as_json() for d in ordered],
        "count": len(ordered),
        "by_class": by_class,
        "by_severity": by_severity,
        "none_by_design": sum(1 for d in ordered if d.rfc == C.RFC_NONE_BY_DESIGN),
        "fingerprint": fingerprint(ordered),
        "tree_digest": tree_digest(root) if root is not None else None,
    }

    # 自检：指纹必须可复算（同一批缺陷两次调用得到同一值）
    if ledger["fingerprint"] != fingerprint(ordered):
        raise AssertionError("fingerprint 不可复算")
    return ledger


def dumps(payload: object) -> str:
    """**唯一** JSON 序列化入口：缩进 2、``ensure_ascii=True``、结尾恰好一个换行。

    缩进是为了人读 diff；字节确定性由"同一对象两次 ``dumps`` 相同"保证，
    双跑逐字节一致由 ``tests/test_determinism.py`` 锁住。
    """
    text = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=False)
    return text + "\n"
