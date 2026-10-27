"""规则目录门禁的**逻辑**测试（用注入数据，不依赖 `data/rfc-ledger.json` 是否已落地）。

这三条是题面"技术创新"分值的机械落点：

* **D12 原句门禁**：`hard` 必须有逐字原句；无原句只能 `diff`/`gray` 且 `severity=note`；
* **D7 三值封闭**：`class` 不得出现第四值；
* **D11 语义层禁令**：`MC-A*` / `MC-C*` / `MC-T01` 等永远拿不到 `hard`。

M3 落地真实 `catalog.json` 后，本文件的注入用例继续跑（它们是判据的**证伪证据**，
不是"数据还没来时的占位"）。
"""

from __future__ import annotations

import pytest

from mimeconform.rules import SEMANTIC_RULES, CatalogError, validate_catalog


def clause(verbatim: str | None) -> dict[str, object]:
    return {"rfc": "RFC 2046", "section": "5.1.1", "verbatim": verbatim, "row": "R6"}


def rule(**overrides: object) -> dict[str, object]:
    base = {
        "rule_id": "MC-B06",
        "module": "scan",
        "klass": "hard",
        "severity": "major",
        "rfc": "RFC 2046 §5.1.1",
        "ledger_key": "RFC2046-5.1.1",
        "detector": "scan.nested_boundary_reuse",
        "summary": "nested multipart reuses outer boundary",
    }
    base.update(overrides)
    return base


def catalog(*rules: dict[str, object]) -> dict[str, object]:
    return {"schema_version": 1, "rules": list(rules)}


def ledger(verbatim: str | None = "each nested 'multipart' entity uses a different boundary delimiter.") -> dict[str, object]:
    return {"clauses": {"RFC2046-5.1.1": clause(verbatim)}}


# ── 正例 ──────────────────────────────────────────────────────────────────


def test_hard_rule_with_verbatim_passes() -> None:
    rules = validate_catalog(catalog(rule()), ledger())
    assert len(rules) == 1
    assert rules[0].klass == "hard"


def test_diff_rule_without_verbatim_passes_when_note() -> None:
    data = catalog(
        rule(
            rule_id="MC-T01",
            module="transfer",
            klass="diff",
            severity="note",
            rfc="none-by-design",
            ledger_key="RFC2045-6.1",
        )
    )
    rules = validate_catalog(data, {"clauses": {"RFC2045-6.1": clause(None)}})
    assert rules[0].klass == "diff"


def test_gray_rule_without_verbatim_passes_when_note() -> None:
    data = catalog(
        rule(
            rule_id="MC-B09",
            module="scan",
            klass="gray",
            severity="note",
            rfc="none-by-design",
            ledger_key="none",
        )
    )
    rules = validate_catalog(data, {"clauses": {"none": clause(None)}})
    assert rules[0].klass == "gray"


# ── D12：原句门禁 ─────────────────────────────────────────────────────────


def test_hard_rule_without_verbatim_is_rejected() -> None:
    """这是 D12 的机械落点：台账没原句 → 代码里报不了 hard。"""
    with pytest.raises(CatalogError, match="没有逐字原句"):
        validate_catalog(catalog(rule()), ledger(verbatim=None))


def test_hard_rule_with_blank_verbatim_is_rejected() -> None:
    with pytest.raises(CatalogError, match="没有逐字原句"):
        validate_catalog(catalog(rule()), ledger(verbatim="   "))


def test_missing_ledger_key_is_rejected() -> None:
    data = catalog(rule(ledger_key="RFC9999-9.9"))
    with pytest.raises(CatalogError, match="不在 rfc-ledger.json"):
        validate_catalog(data, ledger())


def test_verbatimless_rule_cannot_claim_major_severity() -> None:
    """无原句时 severity 只能是 note（否则会出现"没条款但判得很重"）。"""
    data = catalog(
        rule(rule_id="MC-T01", module="transfer", klass="diff", severity="major", ledger_key="RFC2045-6.1")
    )
    with pytest.raises(CatalogError, match="severity 只能是 note"):
        validate_catalog(data, {"clauses": {"RFC2045-6.1": clause(None)}})


def test_verbatimless_rule_cannot_be_hard_by_class() -> None:
    data = catalog(rule(klass="hard", ledger_key="RFC2045-6.1"))
    with pytest.raises(CatalogError):
        validate_catalog(data, {"clauses": {"RFC2045-6.1": clause(None)}})


# ── D7 / D11：语义层禁令 ──────────────────────────────────────────────────


def test_semantic_rules_set_covers_the_documented_families() -> None:
    """登记表必须覆盖 `data/README` §7.1 升级禁令点名的全部规则族。"""
    expected = {
        "MC-T01",
        "MC-T08",
        "MC-T11",
        "MC-H08",
        "MC-H12",
        "MC-B05",
        "MC-B09",
        *(f"MC-A{i:02d}" for i in range(1, 9)),
        *(f"MC-C{i:02d}" for i in range(1, 6)),
    }
    assert SEMANTIC_RULES == expected


@pytest.mark.parametrize("rule_id", sorted(SEMANTIC_RULES))
def test_semantic_rule_cannot_be_hard(rule_id: str) -> None:
    """语义层规则拿不到 `hard`——**即使台账里有原句**（D11 高于原句门禁）。"""
    data = catalog(rule(rule_id=rule_id))
    with pytest.raises(CatalogError, match="语义层规则不得为 hard"):
        validate_catalog(data, ledger())


def test_duplicate_rule_id_is_rejected() -> None:
    """编号一经分配不得复用（§7.2）。"""
    with pytest.raises(CatalogError, match="rule_id 重复"):
        validate_catalog(catalog(rule(), rule()), ledger())


def test_missing_required_field_is_rejected() -> None:
    bad = rule()
    del bad["detector"]
    with pytest.raises(CatalogError, match="缺字段"):
        validate_catalog(catalog(bad), ledger())


def test_unknown_class_value_is_rejected() -> None:
    """`class` 三值封闭：第四值不得通过（连 `hard` 之外的拼写都不行）。"""
    with pytest.raises(CatalogError):
        validate_catalog(catalog(rule(klass="fatal")), ledger())


def test_catalog_must_have_rules_array() -> None:
    with pytest.raises(CatalogError, match="rules"):
        validate_catalog({"rules": "nope"}, ledger())


def test_ledger_shape_is_checked() -> None:
    with pytest.raises(CatalogError, match="clauses"):
        validate_catalog(catalog(rule()), {"rows": []})


# ── 子项粒度（`<节>#<子项>`）───────────────────────────────────────────────

SUBCLAUSE_LEDGER = {
    "clauses": {
        "RFC2046-5.1.1": {
            "rfc": "RFC 2046",
            "section": "5.1.1",
            "row": "R6",
            "recorded": "partial",
            "verbatim": "The Content-Type field for multipart entities requires one parameter, 'boundary'.",
            "subclauses": {
                "boundary-required": {
                    "row": "R6",
                    "recorded": True,
                    "verbatim": "The Content-Type field for multipart entities requires one parameter, 'boundary'.",
                },
                "close-delimiter-form": {"row": "R7", "recorded": False, "verbatim": None},
            },
        }
    }
}


def test_subclause_with_verbatim_allows_hard() -> None:
    data = catalog(rule(ledger_key="RFC2046-5.1.1#boundary-required"))
    rules = validate_catalog(data, SUBCLAUSE_LEDGER)
    assert rules[0].klass == "hard"


def test_subclause_without_verbatim_forbids_hard() -> None:
    """同一节里"有原句的子项"可 hard，"没原句的子项"必须降级 —— 按整节判会放行后者。"""
    data = catalog(rule(ledger_key="RFC2046-5.1.1#close-delimiter-form"))
    with pytest.raises(CatalogError, match="没有逐字原句"):
        validate_catalog(data, SUBCLAUSE_LEDGER)


def test_unknown_subclause_is_rejected() -> None:
    data = catalog(rule(ledger_key="RFC2046-5.1.1#does-not-exist"))
    with pytest.raises(CatalogError, match="不在 rfc-ledger.json"):
        validate_catalog(data, SUBCLAUSE_LEDGER)


def test_resolve_verbatim_directly() -> None:
    from mimeconform.rules import resolve_verbatim

    exists, verbatim = resolve_verbatim(SUBCLAUSE_LEDGER, "RFC2046-5.1.1#boundary-required")
    assert exists and verbatim and "requires one parameter" in verbatim
    exists, verbatim = resolve_verbatim(SUBCLAUSE_LEDGER, "RFC2046-5.1.1#close-delimiter-form")
    assert exists and verbatim is None
    exists, _ = resolve_verbatim(SUBCLAUSE_LEDGER, "RFC9999-1.1")
    assert not exists


# ── `none-by-design` 哨兵键（M3 落地，`data/README` §7.1 / D8）───────────────


def test_none_by_design_sentinel_is_recognized() -> None:
    """`rfc = none-by-design` 的规则写哨兵键 → 走同一条降级判据（`diff` + `note` 通过）。

    它**不是豁免**：台账里没有这一键，但"没有条款"本身就是登记过的证据。
    """
    from mimeconform.rules import NO_CLAUSE_KEY

    assert NO_CLAUSE_KEY == "none-by-design"
    data = catalog(
        rule(rule_id="MC-B05", klass="diff", severity="note", rfc="none-by-design", ledger_key=NO_CLAUSE_KEY)
    )
    rules = validate_catalog(data, {"clauses": {}})
    assert rules[0].klass == "diff"
    assert rules[0].severity == "note"


def test_none_by_design_sentinel_cannot_be_hard() -> None:
    """哨兵键解析成"原句为空"，因此拿不到 `hard` —— 这是它与"豁免"的区别。"""
    from mimeconform.rules import NO_CLAUSE_KEY

    data = catalog(
        rule(rule_id="MC-B03", klass="hard", severity="major", rfc="none-by-design", ledger_key=NO_CLAUSE_KEY)
    )
    with pytest.raises(CatalogError, match="没有逐字原句"):
        validate_catalog(data, {"clauses": {}})


def test_none_by_design_sentinel_cannot_claim_major() -> None:
    from mimeconform.rules import NO_CLAUSE_KEY

    data = catalog(
        rule(rule_id="MC-B03", klass="diff", severity="major", rfc="none-by-design", ledger_key=NO_CLAUSE_KEY)
    )
    with pytest.raises(CatalogError, match="severity 只能是 note"):
        validate_catalog(data, {"clauses": {}})


# ── 真实文件的当前状态（M0：尚未落地，必须报"不存在"而不是崩）────────────


def test_real_catalog_is_absent_and_reports_cleanly() -> None:
    """M3 之前 `catalog.json` 不存在 → 抛 `CatalogError`（具名异常，不是 FileNotFoundError）。

    `data/rfc-ledger.json` 已落地（M0 顺带产出），但规则目录要等 M2–M5 的规则实装，
    因此这条判据现在仍然成立；M3 之后 `CATALOG_PATH` 存在，本测试转为 skip 并由
    `tests/test_catalog_gate.py` 的注入用例 + 真实目录加载共同覆盖。
    """
    from mimeconform.rules import CATALOG_PATH, load_catalog

    if CATALOG_PATH.is_file():
        pytest.skip("catalog.json 已落地（M3 之后）——本判据转为真实门禁测试")
    with pytest.raises(CatalogError, match="不存在"):
        load_catalog()


def test_real_ledger_mirror_is_loadable() -> None:
    """机读台账必须存在、可解析、且 `clauses` 非空（它是门禁的判据输入）。"""
    import json

    from mimeconform.rules import LEDGER_PATH

    assert LEDGER_PATH.is_file(), f"缺机读台账: {LEDGER_PATH}"
    payload = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    assert payload["clauses"], "机读台账 clauses 为空"
