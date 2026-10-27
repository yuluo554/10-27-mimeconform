"""golden 语料生成器（`mimeconform/devtools/gen_golden.py`）的守门测试。

判据（`plan/04` §三 / §五）：

1. **可重建**：`build()` 到临时目录 → 与 `data/golden/` 逐字节一致；CLI `--check` 返回 0。
2. **三件齐**：每个 case 目录都有 `expect.json` + `README.md` + 一个输入（`msg.eml` /
   `mail.mbox` / `maildir` 子路径）。
3. **正负例语义**：正例 `defects` 非空、负例为空；`defect_count` / `exit_code` 由构造复算。
4. **六元组完整**：每条缺陷 `rfc` 非空、`detail` 非空、`class` 三值、`severity` 四档。
5. **题面点名的复现项齐备**（11 项）。
6. **自检真能证伪**：把 expect.json 改坏后 `_self_check` 必须抛错（否则门是摆设）。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from mimeconform import constants as C
from mimeconform.cli import main as cli_main
from mimeconform.devtools import gen_golden as g
from mimeconform.exit_codes import decide_exit_code
from mimeconform.model import Defect

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "golden"

#: 题面点名的 11 个复现项（`plan/01` §1.4 / §二 验收）。
REPRODUCTION_CASES = (
    "b-inner-dup",  # cpython #69914
    "b-wrapped-header",  # cpython #56141
    "c-from-bad",  # cpython #93376
    "h-2231-seq",  # SO 44154520
    "h-ew-newline",  # SO 52442469
    "t-qp-artifact",  # SO 79133579
    "t-b64-len",  # SO 6029218
    "a-body-attach",  # SO 6255202
    "a-noname",  # SO 12816042
    "a-cid-open",  # SO 10107788
    "a-related-start",  # SO 39328935
)


def _case_dirs() -> list[Path]:
    return sorted(path for path in GOLDEN.iterdir() if path.is_dir())


def _expect(case_dir: Path) -> dict[str, object]:
    return json.loads((case_dir / "expect.json").read_text(encoding="utf-8"))


def _as_defects(payload: dict[str, object]) -> list[Defect]:
    rows = payload["defects"]
    assert isinstance(rows, list)
    return [
        Defect(
            rule_id=str(row["rule_id"]),
            klass=str(row["class"]),
            severity=str(row["severity"]),
            path=str(row["path"]),
            offset=int(row["offset"]),
            offset_kind=str(row["offset_kind"]),
            rfc=str(row["rfc"]),
            detail=str(row["detail"]),
        )
        for row in rows
        if isinstance(row, dict)
    ]


# ── 1. 可重建（位级一致）──────────────────────────────────────────────────


def test_build_into_temp_dir_matches_repo_corpus() -> None:
    """生成器重跑必须与入库语料逐字节一致（`--check` 的库内等价）。"""
    with tempfile.TemporaryDirectory() as tmp:
        g.build(Path(tmp) / "golden")
        diffs = g._tree_diff(GOLDEN, Path(tmp) / "golden")
    assert diffs == [], "语料与生成器不一致（改动后须重跑生成器）：\n" + "\n".join(diffs)


def test_cli_check_reports_zero_diff() -> None:
    """真命令：`python -m mimeconform.devtools.gen_golden --check` → 0 且打印 N cases, 0 diff。"""
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "mimeconform.devtools.gen_golden", "--check"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "cases, 0 diff" in result.stdout


def test_check_detects_a_single_byte_change() -> None:
    """非空跑自证：语料被改一个字节时 `--check` 必须变红（否则比对是假的）。"""
    with tempfile.TemporaryDirectory() as tmp:
        golden_copy = Path(tmp) / "golden"
        g.build(golden_copy)
        target = golden_copy / "b-no-boundary" / "msg.eml"
        target.write_bytes(target.read_bytes() + b"X")
        assert g._tree_diff(golden_copy, golden_copy) == []  # 同一棵树当然一致
        rc = g.check(golden_copy)
    assert rc == 1, "语料被篡改后 --check 仍然返回 0"


# ── 2. 三件齐 + 3. 正负例语义 ────────────────────────────────────────────


def test_every_case_has_exactly_three_files() -> None:
    cases = _case_dirs()
    assert len(cases) == len(g.CASES) == 51, f"case 数不对: 目录 {len(cases)} / 注册表 {len(g.CASES)}"
    for case_dir in cases:
        files = sorted(p for p in case_dir.rglob("*") if p.is_file())
        assert len(files) == 3, f"{case_dir.name}: 期望 3 个文件，实际 {len(files)}：{files}"
        names = {p.name for p in files}
        assert names == {"expect.json", "README.md", files_input_name(case_dir)}, (
            f"{case_dir.name}: 三件齐判据不满足：{names}"
        )


def files_input_name(case_dir: Path) -> str:
    payload = _expect(case_dir)
    info = payload["input"]
    assert isinstance(info, dict)
    return Path(str(info["file"])).name


def test_expectation_matches_defect_emptiness() -> None:
    for case_dir in _case_dirs():
        payload = _expect(case_dir)
        defects = _as_defects(payload)
        if payload["expectation"] == "positive":
            assert defects, f"{case_dir.name}: 正例缺陷集为空"
        else:
            assert payload["expectation"] == "negative"
            assert defects == [], f"{case_dir.name}: 负例出现缺陷 {defects}"
        assert payload["defect_count"] == len(defects)
        assert payload["exit_code"] == decide_exit_code(defects, fail_on=C.FAIL_ON_DEFAULT)


def test_fingerprint_is_reproducible() -> None:
    from mimeconform.ledger import fingerprint

    for case_dir in _case_dirs():
        payload = _expect(case_dir)
        assert payload["fingerprint"] == fingerprint(_as_defects(payload)), (
            f"{case_dir.name}: fingerprint 与缺陷集不一致"
        )


# ── 4. 六元组完整 ────────────────────────────────────────────────────────


def test_every_defect_is_a_complete_six_tuple() -> None:
    for case_dir in _case_dirs():
        for defect in _as_defects(_expect(case_dir)):
            defect.validate()  # 六元组 + path 语法 + offset 非负 + rfc/detail 非空
            assert defect.klass in C.CLASSES
            assert defect.severity in C.SEVERITIES


def test_semantic_rules_never_claim_hard() -> None:
    """`data/README` §7.1 的升级禁令在语料层同样成立（golden 不能先撒谎）。"""
    from mimeconform.rules import SEMANTIC_RULES

    offenders = [
        f"{case_dir.name}: {defect.rule_id}"
        for case_dir in _case_dirs()
        for defect in _as_defects(_expect(case_dir))
        if defect.rule_id in SEMANTIC_RULES and defect.klass == C.CLASS_HARD
    ]
    assert not offenders, "语义层规则在 golden 里被标成 hard：" + ", ".join(offenders)


def test_offsets_point_inside_the_input_file() -> None:
    for case_dir in _case_dirs():
        payload = _expect(case_dir)
        info = payload["input"]
        assert isinstance(info, dict)
        size = int(info["bytes"])
        for defect in _as_defects(payload):
            if defect.offset_kind == C.OFFSET_LINE:
                assert 1 <= defect.offset <= 200, f"{case_dir.name}: 行号越界 {defect.rule_id}"
            else:
                assert 0 <= defect.offset <= size, f"{case_dir.name}: 偏移越界 {defect.rule_id}"


# ── 5. 复现项齐备 ────────────────────────────────────────────────────────


@pytest.mark.parametrize("case", REPRODUCTION_CASES)
def test_named_reproductions_exist_and_cite_a_source(case: str) -> None:
    case_dir = GOLDEN / case
    assert case_dir.is_dir(), f"缺题面点名的复现 case: {case}"
    payload = _expect(case_dir)
    assert str(payload["source"]).strip(), f"{case}: source 为空"
    assert "自造" not in str(payload["source"]) or "SO" in str(payload["source"]) or "#" in str(
        payload["source"]
    ), f"{case}: 复现项必须引 issue / SO 编号"


# ── 6. 自检真能证伪 + selftest 真命令回归 ────────────────────────────────


@pytest.mark.parametrize(
    "field, value",
    [
        ("defect_count", 999),
        ("exit_code", 0),
        ("fingerprint", "0" * 64),
    ],
)
def test_self_check_catches_tampered_expect(field: str, value: object) -> None:
    """把 expect 的派生字段改坏 → `_self_check` 必须抛错（门不是摆设）。"""
    files, expect = g.b_no_boundary()
    name = "b-no-boundary"
    tampered = dict(expect)
    tampered[field] = value
    if field == "exit_code" and expect["exit_code"] == value:
        pytest.skip("该 case 的退出码恰好等于篡改值")
    with pytest.raises(AssertionError):
        g._self_check(name, files, tampered)


def test_self_check_catches_negative_with_defect() -> None:
    files, expect = g.b_clean_nested()
    tampered = dict(expect)
    tampered["defects"] = list(g.b_no_boundary()[1]["defects"])
    tampered["defect_count"] = len(tampered["defects"])
    with pytest.raises(AssertionError):
        g._self_check("b-clean-nested", files, tampered)


def test_self_check_catches_missing_needle() -> None:
    """正例声称的字节不在文件里 → 必须失败（防"证据锚点"变成空话）。"""
    files, expect = g.t_qp_artifact()
    with pytest.raises(AssertionError):
        g._self_check("t-qp-artifact", {"msg.eml": b"clean body, no artifacts\r\n"}, expect)


def test_selftest_command_is_green_on_real_corpus() -> None:
    """真命令回归：`mimeconform selftest` 必须对真实语料返回 0。"""
    assert cli_main(["selftest"]) == C.EXIT_OK
