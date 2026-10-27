"""h 簇（头编码）的**引擎侧**回归：真跑 `scan_message` + `audit_headers`，与 `expect.json` 逐条比对。

判据与 b 簇同口径（`plan/04` §四 / `HANDOFF-M3` §三.6）：

* 比对键 = ``rule_id`` / ``path`` / ``offset`` / ``class`` —— **不比 ``severity``**
  （受原句门禁影响，补齐原句后可能提级）；
* 顺序无关：两边都按 ``(rule_id, path, offset)`` 排序后比；
* 负例必须零缺陷，正例的 **rule_id 集合不得被扩大**（误报是本题最贵的失败）。

另有三条是 M3 的专属断言（题面点名 / `plan/03` §二 验收）：

1. `h-ew-newline`：MC-H12 命中时**不得**同时报 MC-H03，被压掉的规则号在 ``related`` 里（§7.5 第 2 条）；
2. `h-2231-seq` / `h-2231-quote` / `h-2231-pct`：复现 SO 44154520 的形状，**只看 rule_id 与 offset**；
3. `decode_filename`：先 2231 后 2047 的顺序骨架（D10）与"编号不连续即显式失败"。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mimeconform import constants as C
from mimeconform.exit_codes import decide_exit_code
from mimeconform.headers import audit_headers, decode_filename, parse_headers
from mimeconform.scan import scan_message

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "golden"

#: h 簇全部 case（12 个：11 正例 + 1 负例；`data/README` §五 的矩阵下界远高于此）。
H_CASES = tuple(sorted(path.name for path in GOLDEN.glob("h-*")))


def _expect(case: str) -> dict[str, object]:
    return json.loads((GOLDEN / case / "expect.json").read_text(encoding="utf-8"))


def _input_bytes(case: str) -> bytes:
    info = _expect(case)["input"]
    assert isinstance(info, dict)
    return (GOLDEN / case / str(info["file"])).read_bytes()


def _defects(case: str):
    data = _input_bytes(case)
    return audit_headers(scan_message(data).root, data)


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


def test_h_cluster_denominator_is_nonempty() -> None:
    """非空跑自证：下面 12 条参数化判据若在空集上跑是空转的。"""
    assert len(H_CASES) == 12, f"只扫到 {len(H_CASES)} 个 h-* case"
    assert sum(1 for case in H_CASES if _expect(case)["expectation"] == "negative") >= 1


@pytest.mark.parametrize("case", H_CASES)
def test_h_cluster_matches_expectation(case: str) -> None:
    """引擎侧命中：``rule_id`` / ``path`` / ``offset`` / ``class`` 逐条一致。"""
    expect = _expect(case)
    actual = _defects(case)
    assert _keyed(list(actual)) == _keyed(expect["defects"]), (
        f"{case}: 引擎侧与 expect.json 不一致\n"
        f"  期望 {_keyed(expect['defects'])}\n  实际 {_keyed(list(actual))}"
    )
    assert len(actual) == expect["defect_count"]


@pytest.mark.parametrize("case", H_CASES)
def test_h_cluster_matches_declared_exit_code(case: str) -> None:
    """退出码由缺陷集复算（不含 `--fail-on` 提升），与 `expect.exit_code` 一致。"""
    expect = _expect(case)
    assert decide_exit_code(_defects(case), fail_on=C.FAIL_ON_DEFAULT) == expect["exit_code"]


@pytest.mark.parametrize("case", H_CASES)
def test_h_cluster_has_no_stray_notes(case: str) -> None:
    """负例零缺陷；正例里除 `expect` 声明的规则外不得出现别的 rule_id。"""
    expect = _expect(case)
    actual = _defects(case)
    expected_rules = {str(row["rule_id"]) for row in expect["defects"]}  # type: ignore[index]
    actual_rules = {defect.rule_id for defect in actual}
    assert actual_rules == expected_rules, f"{case}: 规则集合不符（实际 {sorted(actual_rules)}）"
    if expect["expectation"] == "negative":
        assert not actual, f"{case}: 负例出现缺陷（误报）"


@pytest.mark.parametrize("case", H_CASES)
def test_h_offsets_are_absolute_or_declared_line(case: str) -> None:
    """`offset_kind=absolute` 的偏移必须落在输入内；`line` 必须是头块内的合法行号。"""
    data = _input_bytes(case)
    for defect in _defects(case):
        assert defect.offset_kind in {C.OFFSET_ABSOLUTE, C.OFFSET_LINE}
        if defect.offset_kind == C.OFFSET_ABSOLUTE:
            assert 0 <= defect.offset < len(data), f"{case}: {defect.rule_id} 偏移越界"
        else:
            assert 1 <= defect.offset <= data.count(b"\n") + 1, f"{case}: {defect.rule_id} 行号越界"


# ── §7.5 第 2 条：H12 与 H03 互斥（同一字节不得双记）─────────────────────


def test_ew_newline_suppresses_h03_and_records_it_as_related() -> None:
    """`h-ew-newline`：只报 MC-H12，且 ``related`` 里记着被压掉的 MC-H03。"""
    defects = _defects("h-ew-newline")
    assert [defect.rule_id for defect in defects] == ["MC-H12"], "命中 H12 时不得同时报 H03（§7.5 第 2 条）"
    (defect,) = defects
    assert defect.klass == C.CLASS_DIFF, "折行/解码顺序 RFC 未定 → 只能 diff（§四.5）"
    assert "MC-H03" in defect.related, "被压掉的规则号必须进 related，否则报告看不出这是互斥的结果"

    expect = _expect("h-ew-newline")
    extra = expect["expect_extra"]
    assert isinstance(extra, dict)
    assert extra["no_double_record"] is True
    assert list(defect.related) == list(extra["related"])


def test_ew_space_without_fold_still_reports_h03() -> None:
    """阴性对照：没有折行时 H03 必须照报 —— 互斥不是"永远不报 H03"。"""
    defects = _defects("h-ew-space")
    (defect,) = defects
    assert defect.rule_id == "MC-H03"
    assert defect.klass == C.CLASS_HARD
    assert not defect.related


# ── 复现项：SO 44154520 / SO 52442469（只看 rule_id 与 offset）────────────


def test_reproduces_so_44154520_missing_star_zero() -> None:
    """SO 44154520：`filename*="UTF-8''%D7%A2.pdf"` 缺 `*0` → MC-H09，偏移落在参数名上。"""
    data = _input_bytes("h-2231-seq")
    defects = _defects("h-2231-seq")
    (defect,) = defects
    assert defect.rule_id == "MC-H09"
    assert defect.path == "0.2", "附件参数在第二个子部件上"
    assert defect.offset_kind == C.OFFSET_ABSOLUTE
    assert data[defect.offset : defect.offset + 9] == b"filename*", "偏移必须指向参数名本身"
    assert defect.klass == C.CLASS_DIFF, "R10 整行未录原句 → 只能是 diff/note"
    assert "*0" in defect.detail, "修正提示（文本，不自动改文件）必须写在 detail 里"


def test_reproduces_so_52442469_encoded_word_newline() -> None:
    """SO 52442469：`=?UTF-8?Q?=C3=A5` + 折行 + `=C3=A4?=` → MC-H12，偏移指向 encoded-word 起点。"""
    data = _input_bytes("h-ew-newline")
    (defect,) = _defects("h-ew-newline")
    assert defect.rule_id == "MC-H12"
    assert data[defect.offset : defect.offset + 10] == b"=?UTF-8?Q?"
    assert b"\r\n" in data[defect.offset : defect.offset + 30], "样本里确实带着折行"

    # 取值层：折行被当作内部 FWS，两个半截拼起来才解得出 `åä`
    block = parse_headers(data)
    subject = next(head for head in block.headers if head.name == "Subject")
    assert len(subject.encoded_words) == 1, "折行内的两部分属于**同一个** encoded-word"
    assert subject.encoded_words[0]["length"] > 15


# ── 判定顺序（§7.5 第 1 条）：头行 > 998 先于 encoded-word 检查 ────────────


def test_h07_line_998_is_hard_major_and_line_kinded() -> None:
    """`h-line-998`：MC-H07 `hard/major`，`offset_kind="line"`（行宽类规则的行号口径）。"""
    defects = _defects("h-line-998")
    (defect,) = defects
    assert defect.rule_id == "MC-H07"
    assert defect.klass == C.CLASS_HARD
    assert defect.severity == C.SEV_MAJOR
    assert defect.offset_kind == C.OFFSET_LINE
    assert decide_exit_code(defects) == C.EXIT_MAJOR


def test_h07_runs_before_encoded_word_checks() -> None:
    """同一条超长行里既超 998 又含 encoded-word 时，两条账都要出（不同字节、不同规则）。

    构造：行长 > 998 且行内带 encoded-word —— MC-H07 记行号，MC-H02 记行号（同一行、不同 rule_id）。
    `_entry_defects` 与 §7.5 第 1 条都不把它们当"双记"，因为它们判的是不同条款。
    """
    encoded = b"=?UTF-8?B?QUJD?="
    long_line = encoded + b" " + b"x" * 1030
    data = b"Subject: " + long_line + b"\r\n\r\nbody\r\n"
    defects = parse_headers(data).defects
    rules = {(defect.rule_id, defect.offset_kind) for defect in defects}
    assert ("MC-H07", C.OFFSET_LINE) in rules
    assert ("MC-H02", C.OFFSET_LINE) in rules


# ── 判定顺序（§7.5 第 3 条）：2231 三阶段只记第一处 ──────────────────────


def test_2231_stages_stop_at_the_first_failure() -> None:
    """编号坏了就只报 MC-H09 —— 不再往下判单引号 / %HH（一个坏参数不出三条账）。"""
    data = (
        b"Content-Type: application/pdf\r\n"
        b"Content-Disposition: attachment; filename*=UTF-8'zh'%ZZ.pdf\r\n"
        b"\r\nbody\r\n"
    )
    rules = [defect.rule_id for defect in parse_headers(data).defects]
    assert rules == ["MC-H09"], f"缺 *0 时不该再判单引号/百分号转义，实际 {rules}"


def test_2231_quote_stage_precedes_percent_stage() -> None:
    """单引号不全时只报 MC-H10（%HH 阶段不再跑）。"""
    data = (
        b"Content-Type: application/pdf\r\n"
        b"Content-Disposition: attachment; filename*0*=UTF-8'%ZZ.pdf\r\n"
        b"\r\nbody\r\n"
    )
    rules = [defect.rule_id for defect in parse_headers(data).defects]
    assert rules == ["MC-H10"], f"实际 {rules}"


def test_2231_continuation_numbers_must_be_contiguous() -> None:
    """跳号（`*0` 之后是 `*2`）→ MC-H09，且指向第二个不对的参数名。"""
    data = (
        b"Content-Type: application/pdf\r\n"
        b"Content-Disposition: attachment; filename*0*=UTF-8''a; filename*2*=b\r\n"
        b"\r\nbody\r\n"
    )
    defects = parse_headers(data).defects
    (defect,) = defects
    assert defect.rule_id == "MC-H09"
    assert data[defect.offset : defect.offset + 9] == b"filename*"


def test_leading_zero_continuation_is_reported() -> None:
    """前导零（`*00`）→ MC-H09（R10 §3 的另一个子项）。"""
    data = (
        b"Content-Type: application/pdf\r\n"
        b"Content-Disposition: attachment; filename*00*=UTF-8''a.pdf\r\n"
        b"\r\nbody\r\n"
    )
    (defect,) = parse_headers(data).defects
    assert defect.rule_id == "MC-H09"
    assert "前导零" in defect.detail


# ── 保守判定的阴性面（误报是本题最贵的失败）───────────────────────────────


def test_plain_long_header_without_encoded_word_is_not_h02() -> None:
    """没有 encoded-word 的长头行不属于 MC-H02（那是 H07 / 其它簇的事）。"""
    data = b"Subject: " + b"y" * 200 + b"\r\n\r\nbody\r\n"
    assert not [defect for defect in parse_headers(data).defects if defect.rule_id == "MC-H02"]


def test_two_complete_encoded_words_are_not_a_continuation() -> None:
    """两个各自完整的 encoded-word + FWS 是合法折叠（`h-clean-folded` 的判据单元）。"""
    data = (
        b"Subject: =?UTF-8?Q?=E4=BD=A0=E5=A5=BD?=\r\n"
        b" =?UTF-8?B?5LiA5Liq56S65L6L?=\r\n"
        b"\r\nbody\r\n"
    )
    assert parse_headers(data).defects == ()


def test_encoded_word_in_body_text_is_not_judged() -> None:
    """正文里的 `=?` 不是 encoded-word 位置：头块之外一字节都不判。"""
    data = b"Subject: ok\r\n\r\n=?UTF-8?Q?this is body text with spaces?=\r\n"
    assert parse_headers(data).defects == ()


def test_params_are_only_judged_on_parameter_headers() -> None:
    """`; a=b` 形态出现在 Subject 里不是参数 —— 对它判 2231 就是把普通文本误报成缺陷。"""
    data = b"Subject: notes; filename*=UTF-8''x.pdf\r\n\r\nbody\r\n"
    assert parse_headers(data).defects == ()


# ── 入口契约（显式失败，不静默）───────────────────────────────────────────


def test_parse_headers_rejects_non_bytes() -> None:
    with pytest.raises(TypeError, match="bytes"):
        parse_headers("Subject: x\r\n")  # type: ignore[arg-type]


def test_parse_headers_rejects_negative_base_offset() -> None:
    with pytest.raises(ValueError, match="base_offset"):
        parse_headers(b"Subject: x\r\n", -1)


def test_audit_headers_rejects_out_of_range_spans() -> None:
    """节点头块跨度越界 → 显式报错（不猜、不截断）。"""
    from mimeconform.model import Header, Node

    node = Node(
        path="0",
        content_type="text/plain",
        boundary=None,
        headers=(Header(name="Subject", raw_value_sha256="0" * 64, octets=1, line_spans=((0, 99),)),),
        body_range=(0, 0),
        body_sha256="0" * 64,
    )
    with pytest.raises(ValueError, match="越界"):
        audit_headers(node, b"Subject: x\r\n\r\n")


# ── `decode_filename`：D10 的顺序骨架（取值调用点在 M5）────────────────────


def test_decode_filename_prefers_rfc2231_over_2047() -> None:
    """2231 有效时用 2231；参数里的 2047 形态只是普通文本，不再二次解码。"""
    params = [
        {"name": "filename*0*", "value": "UTF-8''%E6%8A%A5%E5%91%8A.pdf", "extended": True},
    ]
    assert decode_filename(params, "=?UTF-8?B?Zm9yZ2V0?=") == "报告.pdf"


def test_decode_filename_falls_back_to_2047_for_a_plain_value() -> None:
    """普通 `filename="=?…?="` 形态：2231 缺席时，值里的 encoded-word 由 2047 解码。"""
    params = [{"name": "filename", "value": "=?UTF-8?Q?=E6=8A=A5=E5=91=8A.pdf?="}]
    assert decode_filename(params, "") == "报告.pdf"


def test_decode_filename_uses_raw_value_when_no_filename_param() -> None:
    """一个 `filename` 参数都没有时，才退回 `raw_value` 本身。"""
    assert decode_filename([], "=?UTF-8?B?5oql5ZGKLnBkZg==?=") == "报告.pdf"


def test_decode_filename_merges_continuations_in_order() -> None:
    """多个续行按编号拼接（不是按出现顺序），且只在 *0* 上取 charset。"""
    params = [
        {"name": "filename*1*", "value": "%E5%91%8A.pdf"},
        {"name": "filename*0*", "value": "UTF-8''%E6%8A%A5"},
    ]
    assert decode_filename(params, "") == "报告.pdf"


def test_decode_filename_joins_adjacent_encoded_words_without_lwsp() -> None:
    """§6.2：相邻 encoded-word 之间的 LWSP 显示时忽略（拼成 `ab`，不是 `a b`）。"""
    raw = "=?UTF-8?Q?a?= =?UTF-8?Q?b?="
    assert decode_filename([], raw) == "ab"


def test_decode_filename_refuses_non_contiguous_numbers() -> None:
    """编号跳号 → 显式失败（不静默拼接出一段"看起来对"的文件名）。"""
    params = [
        {"name": "filename*0*", "value": "UTF-8''a"},
        {"name": "filename*2*", "value": "b"},
    ]
    with pytest.raises(ValueError, match="不连续"):
        decode_filename(params, "")


def test_decode_filename_does_not_swallow_illegal_percent_escapes() -> None:
    """非法 `%ZZ` 按字面保留（MC-H11 记账；取值层不吞字节）。"""
    params = [{"name": "filename*0*", "value": "UTF-8''%ZZ.pdf"}]
    assert decode_filename(params, "") == "%ZZ.pdf"


# ── 与 `scan` 的行切分契约一致（K7，两个模块各有一份实现）──────────────────


def test_line_splitter_matches_scan() -> None:
    """`headers` 不得 import `scan`（分层），故各有一份切行实现 —— 语义必须一致。

    差异样本刻意包含裸 CR、`\\x0b`、`\\x0c` 与末行无行尾：`bytes.splitlines()` 会多切，
    两边都必须只按 `\\n` 切。
    """
    from mimeconform.headers import _iter_lines
    from mimeconform.scan import split_lines

    for sample in (b"a\r\nb\nc\rd\x0be\x0cf\n", b"no-eol", b"", b"\n\n\n", b"tail\n"):
        mine = [(line.start, line.content + b"\n") for line in _iter_lines(sample)]
        theirs = split_lines(sample)
        assert [start for start, _raw in mine] == [start for start, _raw in theirs], sample
        # 内容与"行界只认 \n"的判据：把 scan 的原始行去掉行尾后必须逐字节相等
        for (_start, raw), line in zip(theirs, _iter_lines(sample)):
            content = raw[:-1] if raw.endswith(b"\n") else raw
            if content.endswith(b"\r"):
                content = content[:-1]
            assert line.content == content, sample
