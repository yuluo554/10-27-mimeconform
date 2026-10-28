"""a 簇（归属与引用）的**引擎侧**回归：真跑 `scan_message` + `audit_attribution`，与 `expect.json` 逐条比对。

判据与 b / h / t 簇同口径（`plan/04` §四 / `HANDOFF-M5` §三.6）：

* 比对键 = ``rule_id`` / ``path`` / ``offset`` / ``class`` —— **不比 ``severity``**；
* 顺序无关：两边都按 ``(rule_id, path, offset)`` 排序后比；
* 负例必须零缺陷，正例的 **rule_id 集合不得被扩大**（误报是本题最贵的失败）。

M5 的专属断言（题面点名 / `plan/03` §四 验收）：

1. 复现 SO 6255202（`a-body-attach`）：MC-A01，落点 = 该叶节点 `Content-Type` 头行首；
2. 复现 SO 12816042（`a-noname`）：MC-A03，落点 = `Content-Disposition` 头行首；
3. 复现 SO 10107788（`a-cid-open`）：MC-A04，落点 = 正文里 `cid:` 引用本身；
4. 复现 SO 39328935（`a-related-start`）：MC-A05，落点 = `multipart/related` 的 `Content-Type` 行首；
5. `filename` 取值顺序（先 2231 后 2047，D10）—— 本模块是 `headers.decode_filename` 的调用点。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mimeconform import constants as C
from mimeconform.attribution import audit_attribution
from mimeconform.exit_codes import decide_exit_code
from mimeconform.scan import scan_message

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "golden"

#: a 簇全部 case（9 个：8 正例 + 1 负例）。
A_CASES = tuple(sorted(path.name for path in GOLDEN.glob("a-*")))


def _expect(case: str) -> dict[str, object]:
    return json.loads((GOLDEN / case / "expect.json").read_text(encoding="utf-8"))


def _input_bytes(case: str) -> bytes:
    info = _expect(case)["input"]
    assert isinstance(info, dict)
    return (GOLDEN / case / str(info["file"])).read_bytes()


def _run(case: str):
    data = _input_bytes(case)
    return audit_attribution(scan_message(data).root, data)


def _defects(case: str):
    return _run(case).defects


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


def test_a_cluster_denominator_is_nonempty() -> None:
    """非空跑自证：下面 9 条参数化判据若在空集上跑是空转的。"""
    assert len(A_CASES) == 9, f"只扫到 {len(A_CASES)} 个 a-* case"
    assert sum(1 for case in A_CASES if _expect(case)["expectation"] == "negative") == 1


@pytest.mark.parametrize("case", A_CASES)
def test_a_cluster_matches_expectation(case: str) -> None:
    """引擎侧命中：``rule_id`` / ``path`` / ``offset`` / ``class`` 逐条一致。"""
    expect = _expect(case)
    actual = _defects(case)
    assert _keyed(list(actual)) == _keyed(expect["defects"]), (
        f"{case}: 引擎侧与 expect.json 不一致\n"
        f"  期望 {_keyed(expect['defects'])}\n  实际 {_keyed(list(actual))}"
    )
    assert len(actual) == expect["defect_count"]


@pytest.mark.parametrize("case", A_CASES)
def test_a_cluster_matches_declared_exit_code(case: str) -> None:
    """退出码由缺陷集复算（不含 `--fail-on` 提升），与 `expect.exit_code` 一致。"""
    expect = _expect(case)
    assert decide_exit_code(_defects(case), fail_on=C.FAIL_ON_DEFAULT) == expect["exit_code"]


@pytest.mark.parametrize("case", A_CASES)
def test_a_cluster_has_no_stray_notes(case: str) -> None:
    """负例零缺陷；正例里除 `expect` 声明的规则外不得出现别的 rule_id。"""
    expect = _expect(case)
    actual = _defects(case)
    expected_rules = {str(row["rule_id"]) for row in expect["defects"]}  # type: ignore[index]
    actual_rules = {defect.rule_id for defect in actual}
    assert actual_rules == expected_rules, f"{case}: 规则集合不符（实际 {sorted(actual_rules)}）"
    if expect["expectation"] == "negative":
        assert not actual, f"{case}: 负例出现缺陷（误报）"


@pytest.mark.parametrize("case", A_CASES)
def test_a_cluster_offsets_are_absolute_and_in_range(case: str) -> None:
    """A 簇一律 `offset_kind="absolute"`，且偏移落在输入内。"""
    data = _input_bytes(case)
    for defect in _defects(case):
        assert defect.offset_kind == C.OFFSET_ABSOLUTE, f"{case}: {defect.rule_id} 不是 absolute"
        assert 0 <= defect.offset < len(data), f"{case}: {defect.rule_id} 偏移越界"


# ── 复现项：SO 6255202 / 12816042 / 10107788 / 39328935 ─────────────────────


def test_reproduces_so_6255202_text_attachment_as_body() -> None:
    """SO 6255202：`text/plain; name="notes.txt"` 缺 disposition → MC-A01，落点 = CT 行首。"""
    data = _input_bytes("a-body-attach")
    (defect,) = _defects("a-body-attach")
    assert defect.rule_id == "MC-A01"
    assert defect.path == "0.2"
    assert defect.klass == C.CLASS_DIFF and defect.severity == C.SEV_NOTE, "D11：A 簇永不 hard"
    assert data[defect.offset : defect.offset + 12] == b"Content-Type", "落点必须是 Content-Type 行首"


def test_reproduces_so_12816042_noname() -> None:
    """SO 12816042：`attachment` 无 filename / name → MC-A03，落点 = Content-Disposition 行首。"""
    data = _input_bytes("a-noname")
    (defect,) = _defects("a-noname")
    assert defect.rule_id == "MC-A03"
    assert data[defect.offset : defect.offset + 20] == b"Content-Disposition:", defect.offset
    assert "Noname" in defect.detail


def test_reproduces_so_10107788_cid_reference_is_open() -> None:
    """SO 10107788：正文 `cid:img002@...` 无对应 Content-ID → MC-A04，落点 = `cid:` 本身。"""
    data = _input_bytes("a-cid-open")
    (defect,) = _defects("a-cid-open")
    assert defect.rule_id == "MC-A04"
    assert defect.path == "0.1", "缺陷落在**引用方**的那条正文上"
    assert data[defect.offset : defect.offset + 4] == b"cid:"
    assert b"img001@example.invalid" in data, "被引用方的 Content-ID 存在但不匹配（字面比较）"


def test_reproduces_so_39328935_related_start_mismatch() -> None:
    """SO 39328935：`related` 的 start 不指向首部件 → MC-A05，落点 = 容器 CT 行首。"""
    data = _input_bytes("a-related-start")
    (defect,) = _defects("a-related-start")
    assert defect.rule_id == "MC-A05"
    assert defect.path == "0", "登记在 multipart/related 节点自身"
    assert data[defect.offset : defect.offset + 12] == b"Content-Type"


# ── 归属三态 + cid 双向闭合（构造单测，不依赖语料）────────────────────────


def test_attachment_facts_report_the_three_dispositions() -> None:
    """`attachments[]` 必须把 attachment / inline / 无 disposition 三态都如实给出。"""
    data = (
        b'Content-Type: multipart/mixed; boundary="b"\r\n'
        b"\r\n--b\r\n"
        b'Content-Type: text/plain; name="n.txt"\r\n\r\nbody\r\n'
        b"--b\r\n"
        b'Content-Type: image/png; name="i.png"\r\n'
        b"Content-Disposition: inline; filename=\"i.png\"\r\n"
        b"Content-ID: <i@example.invalid>\r\n\r\nQUJD\r\n"
        b"--b\r\n"
        b'Content-Type: application/pdf; name="a.pdf"\r\n'
        b'Content-Disposition: attachment; filename="a.pdf"\r\n\r\nJVBERi0=\r\n'
        b"--b--\r\n"
    )
    result = audit_attribution(scan_message(data).root, data)
    by_path = {item.path: item for item in result.attachments}
    assert by_path["0.1"].disposition is None
    assert by_path["0.2"].disposition == "inline"
    assert by_path["0.3"].disposition == "attachment"
    assert by_path["0.2"].content_id == "i@example.invalid"


def test_cid_closure_records_referenced_by_and_reports_the_open_one() -> None:
    """cid 双向闭合：被引用的部件 `referenced_by` 非空；未闭合的引用出 MC-A04。"""
    data = (
        b'Content-Type: multipart/related; boundary="r"\r\n'
        b"\r\n--r\r\n"
        b"Content-Type: text/html\r\n\r\n"
        b'<img src="cid:closed@example.invalid"><img src="cid:open@example.invalid">\r\n'
        b"--r\r\n"
        b"Content-Type: image/png\r\n"
        b"Content-ID: <closed@example.invalid>\r\n\r\nQUJD\r\n"
        b"--r--\r\n"
    )
    result = audit_attribution(scan_message(data).root, data)
    by_path = {item.path: item for item in result.attachments}
    assert by_path["0.2"].referenced_by == ("0.1",), "闭合的引用要记在 referenced_by 上"
    rules = [defect.rule_id for defect in result.defects]
    assert rules == ["MC-A04"], f"只有一个引用未闭合，实际 {rules}"
    assert "open@example.invalid" in result.defects[0].detail


def test_cid_comparison_is_literal_and_not_url_decoded() -> None:
    """`cid:` 比较按尖括号内字面值：`%40` 不解码成 `@`（否则会误判为闭合）。"""
    data = (
        b'Content-Type: multipart/related; boundary="r"\r\n'
        b"\r\n--r\r\n"
        b"Content-Type: text/html\r\n\r\n<img src=\"cid:a%40b\">\r\n"
        b"--r\r\n"
        b"Content-Type: image/png\r\nContent-ID: <a@b>\r\n\r\nQUJD\r\n"
        b"--r--\r\n"
    )
    rules = [defect.rule_id for defect in audit_attribution(scan_message(data).root, data).defects]
    assert rules == ["MC-A04"], "百分号编码不参与比较：a%40b 与 a@b 是两个不同的字面值"


def test_related_start_defaults_to_first_part_and_type_also_checked() -> None:
    """`start` 缺省 = 首部件；显式 `type` 与首部件不符也记 MC-A05。"""
    data = (
        b'Content-Type: multipart/related; boundary="r"; type="text/html"\r\n'
        b"\r\n--r\r\n"
        b"Content-Type: application/pdf\r\nContent-ID: <x@example.invalid>\r\n\r\nJVBERi0=\r\n"
        b"--r--\r\n"
    )
    (defect,) = audit_attribution(scan_message(data).root, data).defects
    assert defect.rule_id == "MC-A05"
    assert "type" in defect.detail


def test_a01_requires_a_name_parameter() -> None:
    """阴性对照：`text/plain` + `text/html` 并列（都没有 name）不是 A01（b-wrapped-header 的形态）。"""
    data = (
        b'Content-Type: multipart/mixed; boundary="b"\r\n'
        b"\r\n--b\r\nContent-Type: text/plain\r\n\r\nbody\r\n"
        b"--b\r\nContent-Type: text/html\r\n\r\n<p>x</p>\r\n"
        b"--b--\r\n"
    )
    assert audit_attribution(scan_message(data).root, data).defects == ()


def test_a08_requires_all_leaves_without_disposition_and_no_body_candidate() -> None:
    """A08 只在"整棵树的叶节点都无法判定"时触发；有正文候选则不报。"""
    no_candidate = (
        b'Content-Type: multipart/mixed; boundary="b"\r\n'
        b"\r\n--b\r\nContent-Type: application/octet-stream\r\n\r\nQUJD\r\n"
        b"--b\r\nContent-Type: application/octet-stream\r\n\r\nQUJD\r\n"
        b"--b--\r\n"
    )
    rules = [d.rule_id for d in audit_attribution(scan_message(no_candidate).root, no_candidate).defects]
    assert rules == ["MC-A08"]

    with_candidate = (
        b'Content-Type: multipart/mixed; boundary="b"\r\n'
        b"\r\n--b\r\nContent-Type: text/plain\r\n\r\nbody\r\n"
        b"--b\r\nContent-Type: application/octet-stream\r\n\r\nQUJD\r\n"
        b"--b--\r\n"
    )
    rules = [d.rule_id for d in audit_attribution(scan_message(with_candidate).root, with_candidate).defects]
    assert rules == [], f"有正文候选时归属可判定，不该出 A08：{rules}"


def test_filename_uses_2231_before_2047_at_the_call_site() -> None:
    """D10：本模块是 `decode_filename` 的调用点 —— 2231 与 2047 叠加时取 2231 的结果。"""
    from mimeconform.headers import decode_filename

    params = [{"name": "filename*0*", "value": "UTF-8''%E6%8A%A5%E5%91%8A.pdf", "extended": True}]
    assert decode_filename(params, "=?UTF-8?B?Zm9yZ2V0?=") == "报告.pdf"

    data = (
        b'Content-Type: multipart/mixed; boundary="b"\r\n'
        b"\r\n--b\r\nContent-Type: text/plain\r\n\r\nbody\r\n"
        b"--b\r\n"
        b'Content-Type: application/pdf; name="=?UTF-8?B?Zm9yZ2V0?="\r\n'
        b"Content-Disposition: attachment; filename*0*=UTF-8''%E6%8A%A5%E5%91%8A.pdf\r\n"
        b"\r\nJVBERi0=\r\n"
        b"--b--\r\n"
    )
    result = audit_attribution(scan_message(data).root, data)
    by_path = {item.path: item for item in result.attachments}
    assert by_path["0.2"].filename == "报告.pdf", "filename 必须走 2231（先），不是 2047"


# ── 跨簇：同一封邮件可以同时带多簇缺陷 ────────────────────────────────────


def test_h_2231_seq_also_bears_a02_and_that_is_a_true_positive() -> None:
    """`h-2231-seq`（SO 44154520）在 A 簇上**也**命中 MC-A02 —— 这是真阳性，不是误报。

    该样本的 `Content-Type` 写 `name="a.pdf"`，而 `Content-Disposition` 的
    `filename*="UTF-8''%D7%A2.pdf"` 解码后是 `ע.pdf`：两个字段给的名字**确实不同**。
    它的 `expect.json` 只登记 MC-H09（那是该 case 的立意），但**引擎在整封审计时会如实报两条** ——
    簇是规则的分类，不是"一封邮件只能属于一簇"。

    这条断言的作用：把这个跨簇事实钉成回归基线。若哪天 A02 的判据被改窄（例如跳过扩展形态参数），
    这里会红，改的人必须显式决定"要不要把这条真阳性丢掉"。
    """
    defects = _defects("h-2231-seq")
    assert [defect.rule_id for defect in defects] == ["MC-A02"], (
        f"h-2231-seq 的 name 与 filename 确实不同，应命中 A02：{[(d.rule_id, d.path) for d in defects]}"
    )
    assert "a.pdf" in defects[0].detail and "ע.pdf" in defects[0].detail


# ── 入口契约 ──────────────────────────────────────────────────────────────


def test_audit_attribution_rejects_non_bytes() -> None:
    node = scan_message(b"Subject: x\r\n\r\nbody\r\n").root
    with pytest.raises(TypeError, match="bytes"):
        audit_attribution(node, "not bytes")  # type: ignore[arg-type]


def test_audit_attribution_returns_valid_six_tuples() -> None:
    for case in A_CASES:
        for defect in _defects(case):
            defect.validate()
