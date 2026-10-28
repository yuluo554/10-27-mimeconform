"""t 簇（传输编码）的**引擎侧**回归：真跑 `scan_message` + `audit_transfer`，与 `expect.json` 逐条比对。

判据与 b / h 簇同口径（`plan/04` §四 / `HANDOFF-M4` §三.6）：

* 比对键 = ``rule_id`` / ``path`` / ``offset`` / ``class`` —— **不比 ``severity``**
  （受原句门禁影响，补齐原句后可能提级）；
* 顺序无关：两边都按 ``(rule_id, path, offset)`` 排序后比；
* 负例必须零缺陷，正例的 **rule_id 集合不得被扩大**（误报是本题最贵的失败）。

另有三条是 M4 的专属断言（题面点名 / `plan/03` §三 验收）：

1. 复现 SO 79133579（`=ustomers` / `=o:p>` / `=ure`）：**每处非法转义各记一条**，精确到字节偏移；
2. 复现 SO 6029218（`QUJDRQ`）：MC-T03 命中且偏移落在正文首字节；
3. 判定顺序 / 压账：MC-T08 先于 MC-T01；MC-T01 命中时 **不**登记 MC-T02/T03/T04。
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from mimeconform import constants as C
from mimeconform.exit_codes import decide_exit_code
from mimeconform.scan import scan_message, split_lines
from mimeconform.transfer import (
    KNOWN_CTE,
    audit_body,
    audit_transfer,
    decode_base64,
    decode_qp,
    observe_body_shape,
    qp_lines,
)

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "golden"

#: t 簇全部 case（13 个：11 正例 + 2 负例）。
T_CASES = tuple(sorted(path.name for path in GOLDEN.glob("t-*")))

#: 非 t 簇的 `.eml`（误报面：transfer 不得在这些 case 上出任何 T 缺陷）。
OTHER_CASES = tuple(
    sorted(
        path.parent.name
        for path in GOLDEN.glob("*/msg.eml")
        if not path.parent.name.startswith("t-")
    )
)


def _expect(case: str) -> dict[str, object]:
    return json.loads((GOLDEN / case / "expect.json").read_text(encoding="utf-8"))


def _input_bytes(case: str) -> bytes:
    info = _expect(case)["input"]
    assert isinstance(info, dict)
    return (GOLDEN / case / str(info["file"])).read_bytes()


def _defects(case: str):
    data = _input_bytes(case)
    return audit_transfer(scan_message(data).root, data)


def _keyed(defects: object) -> list[tuple[str, str, int, str]]:
    rows: list[tuple[str, str, int, str]] = []
    assert isinstance(defects, (list, tuple))
    for defect in defects:
        if isinstance(defect, dict):
            rows.append(
                (str(defect["rule_id"]), str(defect["path"]), int(defect["offset"]), str(defect["class"]))
            )
        else:
            rows.append((defect.rule_id, defect.path, defect.offset, defect.klass))  # type: ignore[union-attr]
    return sorted(rows)


# ── 分母与逐 case 命中 ─────────────────────────────────────────────────────


def test_t_cluster_denominator_is_nonempty() -> None:
    """非空跑自证：下面 13 条参数化判据若在空集上跑是空转的。"""
    assert len(T_CASES) == 13, f"只扫到 {len(T_CASES)} 个 t-* case"
    assert sum(1 for case in T_CASES if _expect(case)["expectation"] == "negative") == 2


@pytest.mark.parametrize("case", T_CASES)
def test_t_cluster_matches_expectation(case: str) -> None:
    """引擎侧命中：``rule_id`` / ``path`` / ``offset`` / ``class`` 逐条一致。"""
    expect = _expect(case)
    actual = _defects(case)
    assert _keyed(list(actual)) == _keyed(expect["defects"]), (
        f"{case}: 引擎侧与 expect.json 不一致\n"
        f"  期望 {_keyed(expect['defects'])}\n  实际 {_keyed(list(actual))}"
    )
    assert len(actual) == expect["defect_count"]


@pytest.mark.parametrize("case", T_CASES)
def test_t_cluster_matches_declared_exit_code(case: str) -> None:
    """退出码由缺陷集复算（不含 `--fail-on` 提升），与 `expect.exit_code` 一致。"""
    expect = _expect(case)
    assert decide_exit_code(_defects(case), fail_on=C.FAIL_ON_DEFAULT) == expect["exit_code"]


@pytest.mark.parametrize("case", T_CASES)
def test_t_cluster_has_no_stray_notes(case: str) -> None:
    """负例零缺陷；正例里除 `expect` 声明的规则外不得出现别的 rule_id。"""
    expect = _expect(case)
    actual = _defects(case)
    expected_rules = {str(row["rule_id"]) for row in expect["defects"]}  # type: ignore[index]
    actual_rules = {defect.rule_id for defect in actual}
    assert actual_rules == expected_rules, f"{case}: 规则集合不符（实际 {sorted(actual_rules)}）"
    if expect["expectation"] == "negative":
        assert not actual, f"{case}: 负例出现缺陷（误报）"


@pytest.mark.parametrize("case", T_CASES)
def test_t_cluster_offsets_are_absolute_and_in_range(case: str) -> None:
    """T 簇一律 `offset_kind="absolute"`，且偏移落在输入内。"""
    data = _input_bytes(case)
    for defect in _defects(case):
        assert defect.offset_kind == C.OFFSET_ABSOLUTE
        assert 0 <= defect.offset < len(data), f"{case}: {defect.rule_id} 偏移越界"


# ── 误报面：非 t 簇不得出任何 T 缺陷 ────────────────────────────────────────


def test_other_clusters_have_no_transfer_defects() -> None:
    """误报是本题最贵的失败：`a/b/c/h` 簇（38 个 case）上 `audit_transfer` 必须零缺陷。

    这条与逐 case 的引擎断言是两份证据：前者钉"该报的报了"，后者钉"不该报的没报"。
    """
    assert len(OTHER_CASES) >= 30, f"只扫到 {len(OTHER_CASES)} 个非 t 簇 case"
    offenders: list[str] = []
    for case in OTHER_CASES:
        data = _input_bytes(case)
        for defect in audit_transfer(scan_message(data).root, data):
            offenders.append(f"{case}: {defect.rule_id} @ {defect.offset}")
    assert not offenders, "transfer 在非 t 簇上误报：\n  " + "\n  ".join(offenders)


# ── 复现项 1：SO 79133579（QP 伪影 `=ustomers` / `=o:p>` / `=ure`）──────────


def test_reproduces_so_79133579_each_illegal_escape_is_recorded() -> None:
    """每处非法转义**各记一条**（精确到字节偏移），不是合并成一条。"""
    data = _input_bytes("t-qp-artifact")
    defects = _defects("t-qp-artifact")
    assert len(defects) == 3, f"应有三处非法转义各一条，实际 {len(defects)}"
    assert {defect.rule_id for defect in defects} == {"MC-T07"}
    assert all(defect.klass == C.CLASS_HARD and defect.severity == C.SEV_MAJOR for defect in defects)
    centers = [defect.offset for defect in defects]
    for needle in (b"=ustomers", b"=o:p>", b"=ure"):
        at = data.find(needle)
        assert at in centers, f"缺少 `{needle.decode('latin-1')}` 的落点 @ {at}"
        # 偏移必须正好指向 `=`
        assert data[at : at + 1] == b"="
    # 非法转义不得被吞：解码结果里仍能看到原样保留的 `=us` / `=o:` / `=ur`
    decoded, _facts = decode_qp(data[data.find(b"\r\n\r\n") + 4 :])
    assert b"=us" in decoded and b"=o:" in decoded and b"=ur" in decoded


# ── 复现项 2：SO 6029218（base64 长度非 4 的倍数）─────────────────────────


def test_reproduces_so_6029218_truncated_group() -> None:
    """`QUJDRQ`（6 个 base64 字符）→ MC-T03，落点 = 正文首字节。"""
    data = _input_bytes("t-b64-len")
    (defect,) = _defects("t-b64-len")
    assert defect.rule_id == "MC-T03"
    assert defect.klass == C.CLASS_DIFF
    body_start = data.find(b"QUJDRQ")
    assert defect.offset == body_start
    assert defect.rfc == "RFC 2045 §6.8"


# ── 判定顺序 / 压账（§7.5 第 5 条）─────────────────────────────────────────


def test_unknown_cte_precedes_cross_check_and_suppresses_everything() -> None:
    """MC-T08 先于一切：声明值未知 → 只出 MC-T08，不做 declared vs observed。

    构造：声明 `x-mystery-enc`，正文写 base64（形态与声明都"像"，但未知声明下无从交叉校验）。
    """
    facts = audit_body(b"QUJDQUJD", "x-mystery-enc", path="0", body_offset=0, cte_offset=7)
    rules = [defect.rule_id for defect in facts.defects]
    assert rules == ["MC-T08"], f"未知 CTE 之下只应出 T08，实际 {rules}"
    assert facts.defects[0].offset == 7, "MC-T08 落在 CTE 头行行首（由调用方给出）"


def test_declared_base64_but_observed_text_emits_t01_only() -> None:
    """MC-T01 命中时**不**登记 MC-T02/T03/T04（`data/golden/t-cte-mismatch` 的口径）。"""
    facts = audit_body(
        b"this body is plainly readable text, not base64\r\n",
        "base64",
        path="0",
        body_offset=100,
    )
    rules = [defect.rule_id for defect in facts.defects]
    assert rules == ["MC-T01"], f"实测非 base64 时只应出 T01，实际 {rules}"
    assert facts.defects[0].offset == 100, "MC-T01 落点 = 正文首字节"
    assert facts.defects[0].rfc == C.RFC_NONE_BY_DESIGN
    for suppressed in ("MC-T02", "MC-T03", "MC-T04"):
        assert suppressed not in rules, f"{suppressed} 应被压掉"


def test_qp_line_width_is_not_recorded_on_a_line_with_an_illegal_escape() -> None:
    """非法转义使该行不再是 encoded line → 该行不记行宽（同一行不双记）。

    构造：一行既超 76 octets 又含 `=us`；只应出 MC-T07，不出 MC-T05。
    """
    body = b"=" + b"a" * 90 + b" =us\r\n"  # 首行 > 76、含非法转义 `=us`
    facts = audit_body(body, "quoted-printable", path="0", body_offset=0)
    rules = [defect.rule_id for defect in facts.defects]
    assert "MC-T05" not in rules, "含非法转义的行不得再记行宽"
    assert rules == ["MC-T07"], f"实际 {rules}"


def test_qp_line_width_is_recorded_on_a_clean_long_line() -> None:
    """阴性对照：干净的超宽 encoded line 必须照记 MC-T05。"""
    facts = audit_body(b"a" * 80 + b"\r\n", "quoted-printable", path="0", body_offset=5)
    rules = [defect.rule_id for defect in facts.defects]
    assert rules == ["MC-T05"]
    assert facts.defects[0].offset == 5


def test_qp_soft_break_at_line_end_still_continues_is_not_a_defect() -> None:
    """合法软换行（`=` 后有下一行）不判 MC-T06（`t-clean-qp` 的判据单元）。"""
    body = b"first line ends with a soft break =\r\nsecond line continues here\r\n"
    rules = [defect.rule_id for defect in audit_body(body, "quoted-printable").defects]
    assert rules == [], f"合法软换行不该出账，实际 {rules}"


def test_base64_foreign_char_is_counted_not_swallowed() -> None:
    """字母表外字符按 §6.8 忽略并计数：`foreign_chars` 递增，且解码结果与 stdlib 一致。"""
    shape = observe_body_shape(b"QUJD*QUJD\r\n")
    assert shape.kind == "base64"
    assert shape.foreign_chars == 1
    decoded, facts = decode_base64(b"QUJD*QUJD\r\n")
    assert facts["foreign_count"] == 1
    assert decoded == base64.b64decode(b"QUJDQUJD")


def test_base64_decoder_matches_the_stdlib_on_clean_input() -> None:
    """自写解码器与标准库交叉校验（`base64` 只允许出现在测试端）。"""
    for payload in (b"QUJD", b"QUJDQUJD", b"", b"AA==", b"QUJDQUJDQUJDQUJD"):
        mine, _facts = decode_base64(payload)
        assert mine == base64.b64decode(payload), payload


def test_base64_offsets_are_exact() -> None:
    """T02/T03/T04 的落点精确到字节（比对键含 offset，必须稳定）。"""
    body = b"QQ==QQ==\r\n"
    facts = audit_body(body, "base64", path="0", body_offset=10)
    (defect,) = facts.defects
    assert defect.rule_id == "MC-T02"
    assert defect.offset == 12  # 第一处非法 `=` 位于正文第 2 字节

    facts = audit_body(b"QUJDRQ\r\n", "base64", path="0", body_offset=20)
    (defect,) = facts.defects
    assert defect.rule_id == "MC-T03"
    assert defect.offset == 20

    facts = audit_body(b"QUJD*QUJD\r\n", "base64", path="0", body_offset=30)
    (defect,) = facts.defects
    assert defect.rule_id == "MC-T04"
    assert defect.offset == 34  # `*` 位于正文第 4 字节


def test_declared_base64_with_a_74_plus_2_padded_body_has_no_defect() -> None:
    """阴性对照：合法 base64（76 列折行 + 正确填充）零缺陷。"""
    facts = audit_body(b"QUJD" * 19 + b"\r\nAA==\r\n", "base64", path="0", body_offset=0)
    assert facts.defects == ()


# ── 声明面（CTE 头）────────────────────────────────────────────────────────


def test_unknown_cte_recognizes_only_the_five_known_values() -> None:
    """已知 CTE 只有 5 个；`x-*` 扩展一律按未知处理（`t-cte-unknown` 的判据单元）。"""
    assert KNOWN_CTE == frozenset({"7bit", "8bit", "binary", "quoted-printable", "base64"})
    for value in ("x-mystery-enc", "x-uuencode", "BASE-64", "quoted_printable"):
        assert value.strip().lower() not in KNOWN_CTE, f"{value} 不该被当作已知 CTE"


def test_declared_cte_is_read_case_insensitively() -> None:
    """声明值取大小写无关的第一个 token（`Base64` == `base64`）。"""
    facts = audit_body(b"QUJDRQ\r\n", "Base64", path="0", body_offset=0)
    assert [defect.rule_id for defect in facts.defects] == ["MC-T03"]


# ── 形态观察（observe_body_shape / qp_lines）────────────────────────────────


def test_observe_body_shape_classifies_the_documented_kinds() -> None:
    assert observe_body_shape(b"").kind == "empty"
    assert observe_body_shape(b"   \r\n\r\n").kind == "empty"
    assert observe_body_shape(b"QUJDQUJD").kind == "base64"
    assert observe_body_shape(b"this body is plainly readable text").kind == "text"
    assert observe_body_shape(b"caf\xc3\xa9 latte").kind == "binary"
    assert observe_body_shape(b"plain =3D text =").kind == "qp"


def test_qp_lines_reports_width_soft_break_and_offsets() -> None:
    lines = qp_lines(b"abc=\r\ndef\r\n")
    assert [line.content for line in lines] == [b"abc=", b"def"]
    assert lines[0].start == 0 and lines[1].start == 6
    assert lines[0].content.endswith(b"=")


# ── 与 `scan` 的行切分契约一致（K7，两个模块各有一份实现）──────────────────


def test_line_splitter_matches_scan() -> None:
    """`transfer` 不得 import `scan`（分层），故各有一份切行实现 —— 语义必须一致。

    差异样本刻意包含裸 CR、`\\x0b`、`\\x0c` 与末行无行尾：`bytes.splitlines()` 会多切，
    两边都必须只按 `\\n` 切。
    """
    from mimeconform.transfer import _iter_body_lines

    for sample in (b"a\r\nb\nc\rd\x0be\x0cf\n", b"no-eol", b"", b"\n\n\n", b"tail\n"):
        mine = [(line.start, line.content + b"\n") for line in _iter_body_lines(sample)]
        theirs = split_lines(sample)
        assert [start for start, _raw in mine] == [start for start, _raw in theirs], sample
        for (_start, raw), line in zip(theirs, _iter_body_lines(sample)):
            content = raw[:-1] if raw.endswith(b"\n") else raw
            if content.endswith(b"\r"):
                content = content[:-1]
            assert line.content == content, sample


# ── 入口契约（显式失败，不静默）───────────────────────────────────────────


def test_audit_body_returns_a_valid_six_tuple() -> None:
    """产出的每条缺陷都过 `Defect.validate()`（六元组 + path 语法 + rfc/detail 非空）。"""
    facts = audit_body(b"QUJDRQ\r\n", "base64", path="0.2", body_offset=0)
    for defect in facts.defects:
        defect.validate()