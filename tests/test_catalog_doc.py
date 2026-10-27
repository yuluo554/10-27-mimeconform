"""`docs/defect-catalog.md` ↔ `rules/catalog.json` 的**机器对账**。

判据（`plan/05` §二 M3 DoD / `plan/06` §二）：

1. **规则数一致**：人读表里出现的 `MC-*` 行 == catalog 的规则数（`plan/05` 点名的 DoD）；
2. **逐值一致**：每行的 `class` / `severity` 与 catalog 相同（文档不能各写一套）；
3. **双向覆盖**：catalog 有而文档没有、文档有而 catalog 没有，都要红。

**为什么不按"整篇包含 rule_id"判**：那种判据在文档把某条规则只写进正文注释时也会绿，
但读者查表时找不到它 —— 判据的作用域比它想判的那件事宽（`check_sprint_layout.py` 的
`LAYOUT.SECTIONS` 踩过同一个坑，见那里的注释）。这里只认**表格行**。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from mimeconform.rules import load_catalog

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "defect-catalog.md"

CATALOG = {rule.rule_id: rule for rule in load_catalog()}

#: 表头形态：``| rule_id | 判定 | class | severity | … |``（允许 §三 多加几列）。
_ROW = re.compile(r"^\|\s*(MC-[BHTAC]\d{2})\s*\|")


#: `severity` 单元格允许带括号补充（如 ``note（--strict-depth → minor）``）——
#: 取**开头那个词**，并要求它恰是四档之一（不做 `in` 判定：`"notex"` 也含 `note`）。
_SEVERITY = re.compile(r"^(blocker|major|minor|note)(?![\w-])")


def _doc_rows() -> dict[str, tuple[str, str]]:
    """从人读表抽 ``{rule_id: (class, severity)}``；只认**表格行**。"""
    rows: dict[str, tuple[str, str]] = {}
    duplicates: list[str] = []
    for line in DOC.read_text(encoding="utf-8").split("\n"):
        match = _ROW.match(line)
        if not match:
            continue
        cells = [cell.strip() for cell in line.split("|")]
        rule_id = cells[1]
        if rule_id in rows:
            duplicates.append(rule_id)
        # cells: ['', rule_id, 判定, class, severity, ...]
        severity = _SEVERITY.match(cells[4])
        assert severity, f"{rule_id}: severity 单元格形态异常: {cells[4]!r}"
        rows[rule_id] = (cells[3], severity.group(1))
    assert not duplicates, f"人读表里同一规则出现多行（读者不知道该信哪一行）: {duplicates}"
    return rows


def test_doc_exists_and_is_nonempty() -> None:
    assert DOC.is_file(), f"缺人读缺陷分类表: {DOC}"
    assert CATALOG, "catalog 为空 —— 下面的对账是空转"


def test_doc_rule_count_matches_catalog() -> None:
    """M3 DoD 的原文判据：两边规则数一致。"""
    rows = _doc_rows()
    assert len(rows) == len(CATALOG), (
        f"规则数不一致：文档 {len(rows)} 条 / catalog {len(CATALOG)} 条；"
        f"只在文档 {sorted(set(rows) - set(CATALOG))}；只在 catalog {sorted(set(CATALOG) - set(rows))}"
    )


def test_doc_covers_every_catalog_rule() -> None:
    """双向覆盖：catalog 的每条规则都必须在人读表里有行。"""
    missing = sorted(set(CATALOG) - set(_doc_rows()))
    assert not missing, f"catalog 有而人读表没有的规则: {missing}"


def test_doc_has_no_rules_outside_the_catalog() -> None:
    """反方向：人读表不得写 catalog 里不存在的规则号（那是"文档先行"的假账）。"""
    extra = sorted(set(_doc_rows()) - set(CATALOG))
    assert not extra, f"人读表里有 catalog 不存在的规则号: {extra}"


@pytest.mark.parametrize("rule_id", sorted(CATALOG))
def test_doc_class_and_severity_match_catalog(rule_id: str) -> None:
    """逐值的 `class` / `severity` 一致 —— 门禁降级必须同时反映在两处。"""
    rows = _doc_rows()
    if rule_id not in rows:
        pytest.skip("上一条测试已报覆盖缺口")
    klass, severity = rows[rule_id]
    rule = CATALOG[rule_id]
    assert klass == rule.klass, f"{rule_id}: 文档 class={klass!r} catalog={rule.klass!r}"
    assert severity == rule.severity, f"{rule_id}: 文档 severity={severity!r} catalog={rule.severity!r}"


def test_doc_names_the_uncovered_clusters_honestly() -> None:
    """未落地的簇必须在文档里显式标注（不能让人读成"全查过了"）。"""
    text = DOC.read_text(encoding="utf-8")
    for token in ("T 传输编码", "A 归属与引用", "C 容器"):
        assert token in text, f"文档没有如实标注未覆盖的簇: {token}"
    assert "⬜" in text, "未覆盖的簇必须用 ⬜ 标记"


def test_doc_states_the_2231_judgement_order() -> None:
    """§7.5 第 3 条（2231 三阶段）必须写进人读文档 —— 否则读者无法复核判定顺序。"""
    text = DOC.read_text(encoding="utf-8")
    for token in ("MC-H09", "MC-H10", "MC-H11", "只记第一处"):
        assert token in text, f"文档缺 2231 判定顺序的说明: {token}"
