"""数据模型与台账不变量（六元组 / 三值封闭 / rfc 非空 / 排序 / 指纹）。"""

from __future__ import annotations

import hashlib

import pytest

from mimeconform import constants as C
from mimeconform.ledger import build, dumps, fingerprint, tree_digest
from mimeconform.model import Defect, Node, path_key


def make_defect(
    rule_id: str = "MC-B01",
    klass: str = "hard",
    severity: str = "blocker",
    path: str = "0",
    offset: int = 0,
    offset_kind: str = "absolute",
    rfc: str = "RFC 2046 §5.1.1",
    detail: str = "multipart missing boundary",
) -> Defect:
    return Defect(
        rule_id=rule_id,
        klass=klass,
        severity=severity,
        path=path,
        offset=offset,
        offset_kind=offset_kind,
        rfc=rfc,
        detail=detail,
    )


# ── 六元组不变量 ──────────────────────────────────────────────────────────


def test_valid_defect_passes() -> None:
    make_defect().validate()


@pytest.mark.parametrize("klass", ["fatal", "", "HARD", "note"])
def test_class_is_closed_three_values(klass: str) -> None:
    with pytest.raises(ValueError, match="三值"):
        make_defect(klass=klass).validate()


@pytest.mark.parametrize("severity", ["critical", "", "info"])
def test_severity_is_four_levels(severity: str) -> None:
    with pytest.raises(ValueError, match="四档"):
        make_defect(severity=severity).validate()


@pytest.mark.parametrize("rfc", ["", "   ", "\t"])
def test_rfc_must_not_be_blank(rfc: str) -> None:
    """D8：无条款时写 none-by-design，不许留空。"""
    with pytest.raises(ValueError, match="rfc 不得为空"):
        make_defect(rfc=rfc).validate()


def test_none_by_design_is_accepted() -> None:
    make_defect(klass="diff", severity="note", rfc=C.RFC_NONE_BY_DESIGN).validate()


@pytest.mark.parametrize("path", ["", "0.", ".1", "msg#0/0", "a.b", "0..1"])
def test_path_shape(path: str) -> None:
    with pytest.raises(ValueError, match="path"):
        make_defect(path=path).validate()


@pytest.mark.parametrize("path", ["0", "0.1", "0.2.10", "msg#3", "msg#3/0.1", "msg#12/0.3.2"])
def test_path_accepts_documented_forms(path: str) -> None:
    make_defect(path=path).validate()


def test_negative_offset_rejected() -> None:
    with pytest.raises(ValueError, match="offset"):
        make_defect(offset=-1).validate()


def test_offset_kind_closed() -> None:
    with pytest.raises(ValueError, match="offset_kind"):
        make_defect(offset_kind="roughly").validate()


def test_rule_id_shape() -> None:
    for bad in ("B01", "MC-B1", "MC-BXXX", "MC-001"):
        with pytest.raises(ValueError, match="rule_id"):
            make_defect(rule_id=bad).validate()


# ── 路径排序按分段整数比（0.10 在 0.9 之后）───────────────────────────────


def test_path_key_is_numeric_per_segment() -> None:
    assert path_key("0.10") > path_key("0.9")
    assert path_key("0.2.1") > path_key("0.2")
    # 容器层路径以消息序号打头，保证 msg#2 排在 msg#10 之前（不是字符串比）
    assert path_key("msg#3/0.1") == (3, 0, 1)
    assert path_key("msg#10") > path_key("msg#9")


def test_defects_sorted_numerically_not_lexically() -> None:
    a = make_defect(path="0.10", offset=10)
    b = make_defect(path="0.9", offset=9)
    ordered = build([a, b])["defects"]
    assert [d["path"] for d in ordered] == ["0.9", "0.10"]


# ── 台账 ──────────────────────────────────────────────────────────────────


def test_ledger_counts_and_classes() -> None:
    ledger = build(
        [
            make_defect(rule_id="MC-B01", klass="hard", severity="blocker"),
            make_defect(rule_id="MC-T01", klass="diff", severity="note", rfc=C.RFC_NONE_BY_DESIGN),
            make_defect(rule_id="MC-B09", klass="gray", severity="note", rfc=C.RFC_NONE_BY_DESIGN),
        ]
    )
    assert ledger["count"] == 3
    assert ledger["by_class"] == {"hard": 1, "diff": 1, "gray": 1}
    assert ledger["none_by_design"] == 2


def test_empty_ledger_has_defined_fingerprint() -> None:
    ledger = build([])
    assert ledger["count"] == 0
    assert ledger["fingerprint"] == hashlib.sha256(b"").hexdigest()


def test_fingerprint_is_stable_and_order_independent() -> None:
    a = make_defect(rule_id="MC-B01", offset=5)
    b = make_defect(rule_id="MC-B02", offset=9)
    assert fingerprint([a, b]) == fingerprint([b, a])


def test_fingerprint_changes_when_judgement_changes() -> None:
    base = make_defect(severity="major")
    changed = make_defect(severity="minor")
    assert fingerprint([base]) != fingerprint([changed])


def test_fingerprint_ignores_detail_wording() -> None:
    """detail 是叙述文本：改措辞不应改变"判定变了没有"这一判断。"""
    a = make_defect(detail="boundary missing")
    b = make_defect(detail="no boundary parameter present at all")
    assert fingerprint([a]) == fingerprint([b])


def test_tree_digest_order_independent_but_content_sensitive() -> None:
    leaf_a = Node(path="0.1", content_type="text/plain", boundary=None, headers=(), body_range=(0, 5), body_sha256="a" * 64)
    leaf_b = Node(path="0.2", content_type="text/plain", boundary=None, headers=(), body_range=(6, 10), body_sha256="b" * 64)
    root1 = Node(path="0", content_type="multipart/mixed", boundary="X", headers=(), body_range=(0, 10), body_sha256="r" * 64, children=(leaf_a, leaf_b))
    root2 = Node(path="0", content_type="multipart/mixed", boundary="X", headers=(), body_range=(0, 10), body_sha256="r" * 64, children=(leaf_b, leaf_a))
    assert tree_digest(root1) == tree_digest(root2), "树指纹按 path 排序，与 children 元组顺序无关"

    leaf_c = Node(path="0.2", content_type="text/plain", boundary=None, headers=(), body_range=(6, 10), body_sha256="c" * 64)
    root3 = Node(path="0", content_type="multipart/mixed", boundary="X", headers=(), body_range=(0, 10), body_sha256="r" * 64, children=(leaf_a, leaf_c))
    assert tree_digest(root3) != tree_digest(root1)


def test_tree_digest_content_type_is_lowercased() -> None:
    leaf = Node(path="0.1", content_type="text/plain", boundary=None, headers=(), body_range=(0, 1), body_sha256="a" * 64)
    upper = Node(path="0.1", content_type="text/plain", boundary=None, headers=(), body_range=(0, 1), body_sha256="a" * 64)
    assert tree_digest(leaf) == tree_digest(upper)


def test_dumps_is_deterministic() -> None:
    ledger = build([make_defect()])
    assert dumps(ledger) == dumps(ledger)
    assert dumps(ledger).endswith("\n")
    assert not dumps(ledger).endswith("\n\n")


def test_ledger_rejects_invalid_defect() -> None:
    with pytest.raises(ValueError):
        build([make_defect(klass="fatal")])


def test_ledger_without_tree_has_null_tree_digest() -> None:
    assert build([])["tree_digest"] is None
