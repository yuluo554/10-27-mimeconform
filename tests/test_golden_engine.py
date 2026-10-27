"""b 簇（树与边界）的**引擎侧**回归：真跑 `scan_message`，与 `expect.json` 逐条比对。

判据（`plan/04` §四 / `plan/01` §四）：

* 比对键 = ``rule_id`` / ``path`` / ``offset`` / ``class`` —— **不比 ``severity``**
  （它受原句门禁影响，补齐原句后可能提级；拿它做断言会把"正确的降级"判成失败）；
* ``defects`` 顺序无关：比对前两边都按 ``(rule_id, path, offset)`` 排序；
* 每个 case 的 ``tree_digest`` 必须与引擎复算一致（M2 的必做项，`HANDOFF-M2` §三.4）；
* 负例必须**零缺陷**（误报是本题最贵的失败）。

另外三条是"复现项"的专属断言（题面点名，`plan/01` §二 模块 M1 验收）：

1. `b-inner-dup`：#69914 —— MC-B06 `hard/major` + **两棵候选树** + ``divergence.path == "0.1"``，
   且 ``stdlib_compare`` 的实测值（1 条 ``StartBoundaryNotFoundDefect``）被重跑验证；
2. `b-wrapped-header`：#56141 —— 折叠头必须被正确读成 multipart：**零缺陷 + 2 个子部件**；
3. `b-no-final` / `b-delim-not-bol` / `b-close-malformed` —— 三条 `note` 级规则**不改退出码**。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mimeconform import constants as C
from mimeconform.devtools.stdlib_compare import collect_stdlib_defects
from mimeconform.exit_codes import decide_exit_code
from mimeconform.ledger import tree_digest
from mimeconform.scan import scan_message

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "golden"

#: b 簇全部 case（11 个：10 正例 + 1 负例；`plan/04` §二 的矩阵下界远高于此）。
B_CASES = tuple(sorted(path.name for path in GOLDEN.glob("b-*")))


def _expect(case: str) -> dict[str, object]:
    return json.loads((GOLDEN / case / "expect.json").read_text(encoding="utf-8"))


def _input_bytes(case: str) -> bytes:
    info = _expect(case)["input"]
    assert isinstance(info, dict)
    return (GOLDEN / case / str(info["file"])).read_bytes()


def _scan(case: str):
    return scan_message(_input_bytes(case))


def _keyed(defects: object) -> list[tuple[str, str, int, str]]:
    """比对键四元组，排序后可比（顺序无关，`plan/04` §四）。"""
    rows: list[tuple[str, str, int, str]] = []
    assert isinstance(defects, list)
    for defect in defects:
        if isinstance(defect, dict):
            rows.append(
                (str(defect["rule_id"]), str(defect["path"]), int(defect["offset"]), str(defect["class"]))
            )
        else:
            rows.append((defect.rule_id, defect.path, defect.offset, defect.klass))  # type: ignore[union-attr]
    return sorted(rows)


@pytest.mark.parametrize("case", B_CASES)
def test_b_cluster_matches_expectation(case: str) -> None:
    """引擎侧命中：``rule_id`` / ``path`` / ``offset`` / ``class`` 逐条一致。"""
    expect = _expect(case)
    result = _scan(case)
    assert _keyed(list(result.defects)) == _keyed(expect["defects"]), (
        f"{case}: 引擎侧与 expect.json 不一致\n"
        f"  期望 {_keyed(expect['defects'])}\n  实际 {_keyed(list(result.defects))}"
    )
    assert len(result.defects) == expect["defect_count"]


@pytest.mark.parametrize("case", B_CASES)
def test_b_cluster_matches_declared_exit_code(case: str) -> None:
    """退出码由缺陷集复算（不含 `--fail-on` 提升），与 `expect.exit_code` 一致。"""
    expect = _expect(case)
    result = _scan(case)
    assert decide_exit_code(result.defects, fail_on=C.FAIL_ON_DEFAULT) == expect["exit_code"]


@pytest.mark.parametrize("case", B_CASES)
def test_b_cluster_tree_digest_is_reproducible(case: str) -> None:
    """树指纹必须由引擎复算得出（M2 的必做项：M1 时它恒为 null）。"""
    expect = _expect(case)
    assert expect["tree_digest"] is not None, f"{case}: tree_digest 未回填（M2 必做项）"
    assert tree_digest(_scan(case).root) == expect["tree_digest"]


@pytest.mark.parametrize("case", B_CASES)
def test_b_cluster_has_no_stray_notes(case: str) -> None:
    """负例零缺陷；正例里除 `expect` 声明的规则外不得出现别的 rule_id。

    **为什么单列一条**：只比"等价"会漏掉"多报了但恰好也少报"的情形 ——
    这里显式断言 rule_id 集合不被扩大（误报是本题最贵的失败）。
    """
    expect = _expect(case)
    result = _scan(case)
    expected_rules = {str(row["rule_id"]) for row in expect["defects"]}  # type: ignore[index]
    actual_rules = {defect.rule_id for defect in result.defects}
    assert actual_rules == expected_rules, f"{case}: 规则集合不符（实际 {sorted(actual_rules)}）"
    if expect["expectation"] == "negative":
        assert not result.defects, f"{case}: 负例出现缺陷（误报）"


# ── 复现项 1：cpython #69914（内层 boundary 重复）──────────────────────────


def test_inner_dup_reports_hard_major_and_two_candidate_trees() -> None:
    """D9：必须报 MC-B06 `hard/major`，并给**两棵**候选树 + 分歧位置。"""
    result = _scan("b-inner-dup")
    (defect,) = result.defects
    assert defect.rule_id == "MC-B06"
    assert defect.klass == C.CLASS_HARD, "#69914 的复用是 R7 已录原句的硬规则"
    assert defect.severity == C.SEV_MAJOR
    assert defect.path == "0.1"

    assert len(result.tree_alternatives) == 2, "必须给两棵候选树，不替用户选一个"
    assert result.divergence is not None, "缺 divergence：报告无法指出歧义在哪一层"
    assert result.divergence.path == "0.1"
    assert result.divergence.offset > 0
    # 两棵树的节点数不同（内层先闭合 = 3 节点 / 外层先闭合 = 3 节点但结构不同）
    first, second = result.tree_alternatives
    assert tree_digest(first) != tree_digest(second), "两棵候选树不该有相同的树指纹"


def test_inner_dup_default_tree_is_declared_not_judged() -> None:
    """默认树是"展示顺序"，报告必须声明它不构成判定（plan/00 D9）。"""
    from mimeconform.scan import DEFAULT_TREE_MODE, scan_message as scan

    result = scan(_input_bytes("b-inner-dup"))
    assert result.facts["mode"] == DEFAULT_TREE_MODE == "inner-first"
    assert result.tree_alternatives[0] is result.root, "第一棵必须是默认（展示用）树"


def test_inner_dup_stdlib_compare_matches_the_recorded_measurement() -> None:
    """`stdlib_compare` 断言按 §二.5 的实测值写：1 条 `StartBoundaryNotFoundDefect`。

    这条测试是"我们说的标准库行为"与"标准库此刻的行为"之间的活口 —— 若某天上游修好了
    #69914，这里会红，届时按新实测更新 golden 与说明，**不要**放宽断言。
    """
    expect = _expect("b-inner-dup")
    recorded = expect["stdlib_compare"]
    assert isinstance(recorded, dict)
    measured = collect_stdlib_defects(_input_bytes("b-inner-dup"))
    types = [entry["type"] for entry in measured["defects"]]  # type: ignore[index]
    assert measured["count"] == recorded["defects"] == 1, (
        f"标准库实测 defect 数 {measured['count']} 与 golden 记录的 {recorded['defects']} 不符"
    )
    assert types == recorded["types"] == ["StartBoundaryNotFoundDefect"]


# ── 复现项 2：cpython #56141（折行头破坏边界检测）──────────────────────────


def test_wrapped_header_parses_as_multipart_with_two_children() -> None:
    """折叠头必须被正确读成 multipart（#56141 是历史 bug，现在钉住回归面）。"""
    expect = _expect("b-wrapped-header")
    assert expect["expectation"] == "negative"
    result = _scan("b-wrapped-header")
    assert not result.defects, "折叠头是合法形态（RFC 5322 §2.2.3 的 FWS）"
    assert result.root.content_type == "multipart/mixed"
    assert result.root.boundary == "wrapped"
    assert len(result.root.children) == 2
    assert [child.content_type for child in result.root.children] == ["text/plain", "text/html"]


def test_wrapped_header_stdlib_compare_matches_the_recorded_measurement() -> None:
    expect = _expect("b-wrapped-header")
    recorded = expect["stdlib_compare"]
    assert isinstance(recorded, dict)
    measured = collect_stdlib_defects(_input_bytes("b-wrapped-header"))
    assert measured["count"] == recorded["defects"] == 0


# ── 复现项 3：note 级规则不改退出码 ───────────────────────────────────────


@pytest.mark.parametrize("case", ["b-no-final", "b-delim-not-bol", "b-close-malformed", "b-preamble-epilogue", "b-empty-multipart", "b-deep-nest"])
def test_note_level_rules_do_not_change_exit_code(case: str) -> None:
    """`diff` / `gray` 的登记不影响退出码（§7.9）：证明确实没把它们硬判成错误。"""
    expect = _expect(case)
    result = _scan(case)
    assert result.defects, f"{case}: 期望至少一条登记"
    assert all(defect.severity == C.SEV_NOTE for defect in result.defects)
    assert decide_exit_code(result.defects) == C.EXIT_OK == expect["exit_code"]


def test_no_final_boundary_reports_the_forced_close_offset() -> None:
    """MC-B05 必须给出"树在第 N 字节被迫闭合"的位置，且 **N = 文件末尾**。"""
    data = _input_bytes("b-no-final")
    result = scan_message(data)
    (defect,) = result.defects
    assert defect.rule_id == "MC-B05"
    assert defect.offset == len(data), "缺 final boundary 的落点是片段被迫结束处"
    assert defect.rfc == C.RFC_NONE_BY_DESIGN


# ── 深度策略项（§7.6）────────────────────────────────────────────────────


def test_deep_nest_default_is_gray_note_and_stops_descent() -> None:
    """超深度默认只出 `gray/note`，并登记"停止下钻"的路径（不是崩溃）。"""
    result = _scan("b-deep-nest")
    (defect,) = result.defects
    assert defect.rule_id == "MC-B09"
    assert defect.klass == C.CLASS_GRAY
    assert defect.severity == C.SEV_NOTE
    truncated = result.facts["truncated_paths"]
    assert isinstance(truncated, list) and truncated == [defect.path]
    # 停止下钻的可观测后果：节点数受限，而不是把 35 层全建出来
    assert result.facts["node_count"] == C.MAX_DEPTH_DEFAULT + 1


def test_deep_nest_strict_depth_escalates_severity_only() -> None:
    """`--strict-depth` 只把 severity 提为 minor —— `class` 仍是 `gray`（§7.6）。"""
    data = _input_bytes("b-deep-nest")
    strict = scan_message(data, strict_depth=True)
    (defect,) = strict.defects
    assert defect.klass == C.CLASS_GRAY, "策略项不能因为用户加了开关就变成条款判定"
    assert defect.severity == C.SEV_MINOR
    assert decide_exit_code(strict.defects) == C.EXIT_MINOR


@pytest.mark.parametrize("bad", [0, -1])
def test_max_depth_must_be_positive(bad: int) -> None:
    """0 / 负数显式拒绝（不静默回落默认值，`plan/03` §八 纪律 1）。"""
    with pytest.raises(ValueError, match="max_depth"):
        scan_message(b"From: a@example.invalid\r\n\r\nbody\r\n", max_depth=bad)


# ── 建树的独立判据（不依赖 expect.json）──────────────────────────────────


def test_clean_nested_builds_the_documented_tree_shape() -> None:
    """负例的树形状：根 mixed（2 子）→ 第一个子是 alternative（2 子）。"""
    result = _scan("b-clean-nested")
    root = result.root
    assert root.path == "0"
    assert root.content_type == "multipart/mixed"
    assert [child.path for child in root.children] == ["0.1", "0.2"]
    alternative = root.children[0]
    assert alternative.content_type == "multipart/alternative"
    assert [child.path for child in alternative.children] == ["0.1.1", "0.1.2"]
    assert root.children[1].content_type == "application/pdf"


def test_body_sha256_excludes_preamble_and_epilogue() -> None:
    """preamble / epilogue 不计入 `body_sha256`（`plan/01` M1 确定性纪律）。"""
    data = _input_bytes("b-preamble-epilogue")
    result = scan_message(data)
    body_start, body_end = result.root.body_range
    body = data[body_start:body_end]
    assert b"preamble" not in body
    assert b"epilogue" not in body
    assert b"part one" in body


def test_boundary_comparison_is_byte_exact_not_case_folded() -> None:
    """boundary 按字节比较：大小写不同就是**不同**（`plan/01` M1 纪律）。

    构造：外层 `Mixed`、内层 `mixed` —— 不构成复用，故不得报 MC-B06，且两棵子树都要切出来。
    """
    data = (
        b"From: alice@example.invalid\r\n"
        b"Content-Type: multipart/mixed; boundary=\"Mixed\"\r\n"
        b"\r\n"
        b"--Mixed\r\n"
        b"Content-Type: multipart/alternative; boundary=\"mixed\"\r\n"
        b"\r\n"
        b"--mixed\r\n"
        b"Content-Type: text/plain; charset=us-ascii\r\n"
        b"\r\n"
        b"inner\r\n"
        b"--mixed--\r\n"
        b"--Mixed--\r\n"
    )
    result = scan_message(data)
    assert not [d for d in result.defects if d.rule_id == "MC-B06"], "大小写不同不是复用"
    assert not result.tree_alternatives, "没有复用就不该产出候选树"
    assert result.root.boundary == "Mixed"
    assert len(result.root.children) == 1
    assert result.root.children[0].boundary == "mixed"
    assert len(result.root.children[0].children) == 1


def test_split_lines_does_not_split_on_bare_cr_or_vt() -> None:
    """K7：切行只按 `\\n`。`\\r` / `\\x0b` / `\\u2028` 都不是行界（与 `bytes.splitlines()` 不同）。"""
    from mimeconform.scan import split_lines

    data = b"a\rb\x0bc\nd\x0ce\n"  # 只有第二个 \n 前的那一处是行界
    rows = split_lines(data)
    assert [raw for _start, raw in rows] == [b"a\rb\x0bc\n", b"d\x0ce\n"]
    # 与 splitlines() 的差异必须**真实存在**，否则这条判据是空转的
    assert len(data.splitlines()) != len(rows)


def test_split_lines_offsets_are_absolute() -> None:
    from mimeconform.scan import split_lines

    data = b"abc\ndef\n"
    assert [start for start, _raw in split_lines(data)] == [0, 4]
    assert [start for start, _raw in split_lines(data, 4)] == [4]
    with pytest.raises(ValueError, match="start 越界"):
        split_lines(data, -1)
    with pytest.raises(ValueError, match="end 越界"):
        split_lines(data, 0, len(data) + 1)
