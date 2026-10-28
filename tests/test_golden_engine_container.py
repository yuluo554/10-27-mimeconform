"""c 簇（容器层）的**引擎侧**回归：真跑 `split_container` / `audit_maildir`，与 `expect.json` 逐条比对。

判据与其它簇同口径（`plan/04` §四 / `HANDOFF-M5` §三.6）：

* 比对键 = ``rule_id`` / ``path`` / ``offset`` / ``class``（另加 ``offset_kind``：容器层是
  ``message-relative``，Maildir 文件名是 ``absolute`` 占位）；
* 顺序无关：两边都按 ``(rule_id, path, offset)`` 排序后比；
* 负例必须零缺陷，正例的 **rule_id 集合不得被扩大**。

M5 的专属断言（题面点名 / `plan/03` §五 / §7.7 验收）：

1. **三种读法的切分表都要输出**（`split_variants`），`auto` 只决定主表；
2. 复现 cpython #93376（`c-from-bad`）：MC-C01，落点 = 该消息 `msg#2` 的 ``offset=0``；
3. `>From` 未转义（`c-from-unescaped`）：MC-C02 只在"变体读法不一致"时触发；
   裸 `From ` 行被三种读法一致误切（`c-body-from`）：MC-C04。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mimeconform import constants as C
from mimeconform.container import (
    MBOX_VARIANTS,
    MessageSpan,
    audit_maildir,
    detect_variant,
    split_container,
)
from mimeconform.exit_codes import decide_exit_code
from mimeconform.scan import split_lines

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "golden"

#: c 簇全部 case（6 个：5 正例 + 1 负例）。
C_CASES = tuple(sorted(path.name for path in GOLDEN.glob("c-*")))


def _expect(case: str) -> dict[str, object]:
    return json.loads((GOLDEN / case / "expect.json").read_text(encoding="utf-8"))


def _input_file(case: str) -> str:
    info = _expect(case)["input"]
    assert isinstance(info, dict)
    return str(info["file"])


def _result(case: str):
    infile = _input_file(case)
    if infile.endswith(".mbox"):
        return split_container((GOLDEN / case / infile).read_bytes(), variant="auto")
    return audit_maildir(GOLDEN / case / "maildir")


def _defects(case: str):
    return _result(case).defects


def _keyed(defects: object) -> list[tuple[str, str, int, str, str]]:
    rows: list[tuple[str, str, int, str, str]] = []
    assert isinstance(defects, (list, tuple))
    for defect in defects:
        if isinstance(defect, dict):
            rows.append(
                (
                    str(defect["rule_id"]),
                    str(defect["path"]),
                    int(defect["offset"]),
                    str(defect["class"]),
                    str(defect["offset_kind"]),
                )
            )
        else:
            rows.append(
                (defect.rule_id, defect.path, defect.offset, defect.klass, defect.offset_kind)  # type: ignore[union-attr]
            )
    return sorted(rows)


# ── 分母与逐 case 命中 ─────────────────────────────────────────────────────


def test_c_cluster_denominator_is_nonempty() -> None:
    """非空跑自证：下面 6 条参数化判据若在空集上跑是空转的。"""
    assert len(C_CASES) == 6, f"只扫到 {len(C_CASES)} 个 c-* case"
    assert sum(1 for case in C_CASES if _expect(case)["expectation"] == "negative") == 1


@pytest.mark.parametrize("case", C_CASES)
def test_c_cluster_matches_expectation(case: str) -> None:
    """引擎侧命中：``rule_id`` / ``path`` / ``offset`` / ``class`` / ``offset_kind`` 逐条一致。"""
    expect = _expect(case)
    actual = _defects(case)
    assert _keyed(list(actual)) == _keyed(expect["defects"]), (
        f"{case}: 引擎侧与 expect.json 不一致\n"
        f"  期望 {_keyed(expect['defects'])}\n  实际 {_keyed(list(actual))}"
    )
    assert len(actual) == expect["defect_count"]


@pytest.mark.parametrize("case", C_CASES)
def test_c_cluster_matches_declared_exit_code(case: str) -> None:
    """退出码由缺陷集复算（全部 `diff/note` → 恒为 0）。"""
    expect = _expect(case)
    assert decide_exit_code(_defects(case), fail_on=C.FAIL_ON_DEFAULT) == expect["exit_code"] == C.EXIT_OK


@pytest.mark.parametrize("case", C_CASES)
def test_c_cluster_has_no_stray_notes(case: str) -> None:
    """负例零缺陷；正例里除 `expect` 声明的规则外不得出现别的 rule_id。"""
    expect = _expect(case)
    actual = _defects(case)
    expected_rules = {str(row["rule_id"]) for row in expect["defects"]}  # type: ignore[index]
    actual_rules = {defect.rule_id for defect in actual}
    assert actual_rules == expected_rules, f"{case}: 规则集合不符（实际 {sorted(actual_rules)}）"
    if expect["expectation"] == "negative":
        assert not actual, f"{case}: 负例出现缺陷（误报）"


# ── 三种读法的切分表 + auto + file_offset（§7.7）───────────────────────────


@pytest.mark.parametrize("case", C_CASES)
def test_variant_tables_match_expect_extra(case: str) -> None:
    """`split_variants` 的条数与 `auto` 的主表必须与 `expect_extra` 一致（全变体并出）。"""
    extra = _expect(case).get("expect_extra")
    assert isinstance(extra, dict)
    result = _result(case)
    if "variant_split_counts" in extra:
        counts = {name: len(spans) for name, spans in result.split_variants.items()}
        assert counts == extra["variant_split_counts"], f"{case}: 切分表条数不符 {counts}"
        assert result.primary_variant == extra["auto"], f"{case}: auto 主表不符"
    if "file_offset" in extra:
        primary = result.split_variants[result.primary_variant]
        assert any(
            span.file_offset == extra["file_offset"] for span in primary
        ), f"{case}: 主表里没有 file_offset 为 {extra['file_offset']} 的消息"


def test_three_variants_disagree_on_unescaped_from() -> None:
    """`c-from-unescaped`：mboxo/mboxrd 误切 3 条、mboxcl 按 Content-Length 只切 2 条。

    这是 C02 的证据形态：**变体差异是证据，不是某一种读法错了**。
    """
    result = _result("c-from-unescaped")
    assert [len(result.split_variants[name]) for name in MBOX_VARIANTS] == [3, 3, 2]
    assert result.primary_variant == "mboxcl"


def test_auto_rule_is_pure_byte_not_heuristic() -> None:
    """§7.7：`auto` 只看字节（Content-Length → mboxcl；`>From ` 且无 `>>From ` → mboxo）。"""
    assert detect_variant(b"From a@example.invalid Thu Jan  1 00:00:00 2026\nContent-Length: 3\n\nabc\n") == "mboxcl"
    assert detect_variant(b"From a@example.invalid Thu Jan  1 00:00:00 2026\n\n>From x\n") == "mboxo"
    assert detect_variant(b"From a@example.invalid Thu Jan  1 00:00:00 2026\n\nplain\n") == "mboxo"


def test_switching_the_primary_variant_changes_which_rule_fires() -> None:
    """主表可切换，且**缺陷随主表变** —— 这是"变体差异是证据"的可执行证明。

    `c-from-unescaped` 按 mboxcl（auto 的主表）读：正文 `From ` 行被 Content-Length 兜住，
    只出 C02（读法分歧）；按 mboxo 读：那行真的把消息切成两半，片段不成消息 → 出 C04。
    **两套结论都必须可复现**，报告不会替用户选一种"正确"。
    """
    data = (GOLDEN / "c-from-unescaped" / "mail.mbox").read_bytes()
    as_mboxcl = split_container(data, variant="mboxcl")
    as_mboxo = split_container(data, variant="mboxo")
    assert [d.rule_id for d in as_mboxcl.defects] == ["MC-C02"]
    assert [d.rule_id for d in as_mboxo.defects] == ["MC-C04"]
    # 三张切分表在两次调用里完全相同（切分表总是全出，只有"主表"变）。
    assert {name: len(spans) for name, spans in as_mboxcl.split_variants.items()} == {
        name: len(spans) for name, spans in as_mboxo.split_variants.items()
    }


def test_split_container_rejects_unknown_variant() -> None:
    with pytest.raises(ValueError, match="变体"):
        split_container(b"", variant="mboxz")


def test_single_message_input_yields_no_container_messages() -> None:
    """单封 `.eml` 不以 `From ` 分隔行开头 → 容器表为空（不把 .eml 误判成空 mbox）。"""
    data = (GOLDEN / "a-clean-mixed" / "msg.eml").read_bytes()
    result = split_container(data)
    assert result.split_variants == {name: () for name in MBOX_VARIANTS}
    assert result.defects == ()


# ── 复现项：cpython #93376 + C02/C04 的分工 ────────────────────────────────


def test_reproduces_cpython_93376_malformed_from_line() -> None:
    """#93376：`From alice@example.invalid`（缺日期）→ MC-C01，落点 = msg#2 offset 0。"""
    data = (GOLDEN / "c-from-bad" / "mail.mbox").read_bytes()
    (defect,) = _defects("c-from-bad")
    assert defect.rule_id == "MC-C01"
    assert defect.path == "msg#2"
    assert defect.offset == 0
    assert defect.offset_kind == C.OFFSET_MESSAGE_RELATIVE
    assert "缺日期" in defect.detail


def test_c02_is_recorded_where_variants_disagree() -> None:
    """C02 落在被误切的 `From ` 行（消息内相对偏移），而不是消息起点。"""
    result = _result("c-from-unescaped")
    (defect,) = result.defects
    assert defect.rule_id == "MC-C02"
    assert defect.path == "msg#1"
    assert defect.offset > 0, "C02 必须指到正文里那处 From 行"
    data = (GOLDEN / "c-from-unescaped" / "mail.mbox").read_bytes()
    span = next(s for s in result.split_variants[result.primary_variant] if s.index == 1)
    assert data[span.start + defect.offset : span.start + defect.offset + 5] == b"From "


def test_c04_is_recorded_when_all_variants_agree_to_mis_split() -> None:
    """C04：三种读法一致误切，片段不具备消息头块 → 落在 msg#2（片段的）起点。"""
    result = _result("c-body-from")
    (defect,) = result.defects
    assert defect.rule_id == "MC-C04"
    assert defect.path == "msg#2"
    assert defect.offset == 0
    counts = {name: len(spans) for name, spans in result.split_variants.items()}
    assert counts["mboxo"] == counts["mboxrd"] == counts["mboxcl"] == 2


def test_c03_zero_length_message_keeps_its_sequence_number() -> None:
    """零长度消息仍占一个 `msg#N`（序号按分隔行顺序，不按内容长度）。"""
    result = _result("c-empty-msg")
    (defect,) = result.defects
    assert defect.rule_id == "MC-C03"
    assert defect.path == "msg#2"
    assert len(result.split_variants[result.primary_variant]) == 3


def test_c05_maildir_entry_name() -> None:
    """Maildir `cur/` 条目缺 `:2,` → MC-C05（作用于文件名，offset=0 是占位）。"""
    result = _result("c-maildir-name")
    (defect,) = result.defects
    assert result.container_kind == "maildir"
    assert defect.rule_id == "MC-C05"
    assert defect.offset_kind == C.OFFSET_ABSOLUTE
    assert result.entries == ("cur/1700000000-bad-name",)


def test_maildir_with_no_entries_fails_loudly(tmp_path: Path) -> None:
    """空分母 ≠ 通过：没有条目的 Maildir 必须显式失败。"""
    from mimeconform.errors import InputError

    (tmp_path / "cur").mkdir()
    with pytest.raises(InputError, match="没有任何条目"):
        audit_maildir(tmp_path)


# ── MessageSpan 的形态 + 与 `scan` 的行切分契约一致（K7）────────────────────


def test_message_span_is_message_relative_and_carries_file_offset() -> None:
    """`MessageSpan` 的 `offset_kind` 口径来自 `file_offset` + 相对 `start`（§7.10）。"""
    result = _result("c-body-from")
    spans = result.split_variants[result.primary_variant]
    assert spans[0].start == 0 and spans[0].file_offset == 0
    assert spans[1].start == spans[1].file_offset > 0
    assert all(span.end > span.start for span in spans)
    assert isinstance(spans[0], MessageSpan)


def test_line_splitter_matches_scan() -> None:
    """`container` 不得 import `scan`（分层），故各有一份切行实现 —— 语义必须一致。"""
    from mimeconform.container import _iter_lines

    for sample in (b"a\r\nb\nc\rd\x0be\x0cf\n", b"no-eol", b"", b"\n\n\n", b"tail\n"):
        mine = [(start, content + b"\n") for start, content, _end in _iter_lines(sample)]
        theirs = split_lines(sample)
        assert [start for start, _raw in mine] == [start for start, _raw in theirs], sample
        for (_start, raw), (_mstart, content, _end) in zip(theirs, _iter_lines(sample)):
            expected = raw[:-1] if raw.endswith(b"\n") else raw
            if expected.endswith(b"\r"):
                expected = expected[:-1]
            assert content == expected, sample
