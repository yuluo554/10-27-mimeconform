"""退出码与 CLI 契约（plan/03 §八）。

四条退出码的 CLI 级证据在 M2 齐备：**0**（`--version` / 干净审计）、**1**（用法错误 /
输入不可读）、**2**（审计完成且只有 `minor`）、**3**（`major`/`blocker`）。

**骨架期语义已被替换而非删除**（plan/00 D16）：那时 `audit` 对任何输入都 exit 1，
用来证明"未实现 ≠ 干净"。M2 起 `scan` 已落地、M3 起 `headers`、M4 起 `transfer`，于是 D16 的活口改成
`test_unimplemented_engines_still_fail_loudly` —— 仍未实现的两个模块必须继续显式失败。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from mimeconform import constants as C
from mimeconform.cli import build_parser, main
from mimeconform.errors import EngineNotReady, UsageError

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "golden"


# ── 0 ────────────────────────────────────────────────────────────────────


def test_version_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    captured = capsys.readouterr()
    assert "mimeconform" in captured.out


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"]) == 0
    captured = capsys.readouterr()
    assert "audit" in captured.out and "selftest" in captured.out


# ── 1：用法错误 ───────────────────────────────────────────────────────────


def test_unknown_subcommand_is_one(capsys: pytest.CaptureFixture[str]) -> None:
    """未知子命令必须是 1，不能是 2（2 = 有 minor，见 data/README §7.9）。"""
    assert main(["frobnicate"]) == C.EXIT_USAGE
    captured = capsys.readouterr()
    assert captured.err


def test_missing_required_argument_is_one() -> None:
    """缺必填参数：argparse 默认 SystemExit(2)，本项目必须映射为 1。"""
    assert main(["audit"]) == C.EXIT_USAGE


def test_unknown_flag_is_one() -> None:
    assert main(["audit", "x.eml", "--nope"]) == C.EXIT_USAGE


def test_bad_fail_on_value_is_one() -> None:
    assert main(["audit", "x.eml", "--fail-on=catastrophic"]) == C.EXIT_USAGE


def test_bad_format_value_is_one() -> None:
    assert main(["audit", "x.eml", "--format=yaml"]) == C.EXIT_USAGE


def test_zero_max_depth_rejected() -> None:
    """`--max-depth 0` 是非法输入 → 显式拒绝（不静默回落默认 32）。"""
    assert main(["audit", "x.eml", "--max-depth", "0"]) == C.EXIT_USAGE


def test_missing_input_file_is_one(tmp_path: Path) -> None:
    missing = tmp_path / "nope.eml"
    assert main(["audit", str(missing)]) == C.EXIT_USAGE


# ── 0 / 2 / 3：审计的真实退出码（M2 接线）─────────────────────────────────


def test_audit_clean_message_exits_zero() -> None:
    """0：审计完成、无 blocker/major（§7.9）。"""
    clean = GOLDEN / "b-clean-nested" / "msg.eml"
    assert main(["audit", str(clean), "--format", "json"]) == C.EXIT_OK


def test_audit_minor_only_exits_two() -> None:
    """2：只有 `minor`（boundary 超 70）—— 与 argparse 的 2 必须区分（那份映射在 main 里）。"""
    case = GOLDEN / "b-boundary-long" / "msg.eml"
    assert main(["audit", str(case), "--format", "json"]) == C.EXIT_MINOR


def test_audit_major_exits_three() -> None:
    """3：存在 `major`（内层 boundary 重复）。"""
    case = GOLDEN / "b-inner-dup" / "msg.eml"
    assert main(["audit", str(case), "--format", "json"]) == C.EXIT_MAJOR


def test_audit_note_only_stays_zero() -> None:
    """`note` / `gray` 登记不影响退出码：证明确实没有把 diff/gray 硬判成错误。"""
    case = GOLDEN / "b-no-final" / "msg.eml"
    assert main(["audit", str(case), "--format", "json"]) == C.EXIT_OK


def test_audit_strict_depth_promotes_the_policy_note_to_minor() -> None:
    """`--strict-depth` 是用户显式选择：把超深度计入退出码（severity 提为 minor，§7.6）。"""
    case = GOLDEN / "b-deep-nest" / "msg.eml"
    assert main(["audit", str(case), "--format", "json"]) == C.EXIT_OK
    assert main(["audit", str(case), "--format", "json", "--strict-depth"]) == C.EXIT_MINOR


def test_audit_fail_on_can_be_stricter_but_never_softer() -> None:
    """`--fail-on` 只更严（§7.9）：note 门槛能把干净审计判成失败，blocker 门槛放不过 major。"""
    clean = GOLDEN / "b-clean-nested" / "msg.eml"
    assert main(["audit", str(clean), "--format", "json", "--fail-on=note"]) == C.EXIT_OK
    noted = GOLDEN / "b-no-final" / "msg.eml"
    assert main(["audit", str(noted), "--format", "json", "--fail-on=note"]) == C.EXIT_MAJOR
    major = GOLDEN / "b-inner-dup" / "msg.eml"
    assert main(["audit", str(major), "--format", "json", "--fail-on=blocker"]) == C.EXIT_MAJOR


def test_audit_writes_json_and_markdown(tmp_path: Path) -> None:
    """`--out` 目录形态：两种格式都写；且**只写该目录**（只读红线）。"""
    case = GOLDEN / "b-clean-nested" / "msg.eml"
    out_dir = tmp_path / "reports"
    assert main(["audit", str(case), "--out", str(out_dir)]) == C.EXIT_OK
    assert (out_dir / "report.json").is_file()
    assert (out_dir / "report.md").is_file()
    # 输入所在目录不得多出任何文件（只读红线）
    assert sorted(p.name for p in (GOLDEN / "b-clean-nested").iterdir()) == [
        "README.md",
        "expect.json",
        "msg.eml",
    ]


def test_audit_out_by_extension_picks_one_format(tmp_path: Path) -> None:
    case = GOLDEN / "b-clean-nested" / "msg.eml"
    json_path = tmp_path / "one.json"
    md_path = tmp_path / "one.md"
    assert main(["audit", str(case), "--out", str(json_path)]) == C.EXIT_OK
    assert main(["audit", str(case), "--out", str(md_path)]) == C.EXIT_OK
    assert json_path.read_text(encoding="utf-8").lstrip().startswith("{")
    assert md_path.read_text(encoding="utf-8").startswith("#")


def test_audit_report_declares_the_ambiguity(tmp_path: Path) -> None:
    """D9：默认树的展示**不构成判定** —— 报告自己必须说出来。"""
    case = GOLDEN / "b-inner-dup" / "msg.eml"
    out = tmp_path / "amb.json"
    assert main(["audit", str(case), "--out", str(out)]) == C.EXIT_MAJOR
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["tree"]["tree_alternatives"] == 2
    assert payload["tree"]["divergence"]["path"] == "0.1"
    assert "不构成判定" in payload["tree"]["declaration"]


# ── 1：仍未实现的模块必须继续显式失败（plan/00 D16 的活口）────────────────


def _empty_node():
    from mimeconform.model import Node

    return Node(
        path="0",
        content_type="text/plain",
        boundary=None,
        headers=(),
        body_range=(0, 0),
        body_sha256="0" * 64,
    )


def test_unimplemented_engines_still_fail_loudly() -> None:
    """M5 的两个模块仍未实现 → 调用即抛 `EngineNotReady`，绝不静默返回。

    D16 的语义没有随里程碑消失，只是从 `audit` 搬到了这些模块上：**未实现 ≠ 干净**。
    M3 起 `headers` 已落地、M4 起 `transfer` 已落地，因此它们从这里移出，
    改由正向断言（`test_headers_engine_is_wired_into_audit` /
    `test_transfer_engine_is_wired_into_audit`）覆盖 —— 接线与"仍未实现"是两份证据。
    """
    from mimeconform import attribution, container

    calls = (
        lambda: attribution.audit_attribution(_empty_node()),
        lambda: container.split_container(b"From a@example.invalid x\n"),
    )
    for call in calls:
        with pytest.raises(EngineNotReady, match="尚未实现"):
            call()


def test_headers_engine_is_wired_into_audit(tmp_path: Path) -> None:
    """M3 的接线证据：`audit` 必须真的跑 `headers`，且报告声明"查了哪几层"。

    为什么单列一条：`headers.parse_headers` 单独可跑，并**不**证明 `audit` 会调用它。
    这里用 h 簇语料走完整 CLI 路径，再检查报告里的覆盖面字段。
    """
    case = GOLDEN / "h-ew-space" / "msg.eml"
    out = tmp_path / "h.json"
    assert main(["audit", str(case), "--out", str(out)]) == C.EXIT_MINOR
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert [d["rule_id"] for d in payload["defects"]] == ["MC-H03"], "头编码缺陷必须出现在 report 里"
    assert payload["tree"]["audited_engines"] == ["scan", "headers", "transfer"]
    assert payload["tree"]["not_yet_audited"] == ["attribution", "container"]


def test_transfer_engine_is_wired_into_audit(tmp_path: Path) -> None:
    """M4 的接线证据：`audit` 必须真的跑 `transfer`（`transfer.audit_body` 单独可跑不算数）。

    `t-qp-artifact` 只出 MC-T07，报告里的缺陷正是引擎判定；覆盖面字段同时把 `transfer`
    从"尚未接入"移到"本轮已审计"。
    """
    case = GOLDEN / "t-qp-artifact" / "msg.eml"
    out = tmp_path / "t.json"
    assert main(["audit", str(case), "--out", str(out)]) == C.EXIT_MAJOR
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert sorted({d["rule_id"] for d in payload["defects"]}) == ["MC-T07"], payload["defects"]
    assert payload["tree"]["audited_engines"] == ["scan", "headers", "transfer"]
    assert payload["tree"]["not_yet_audited"] == ["attribution", "container"]


def test_headers_and_tree_defects_share_one_ledger() -> None:
    """同一封邮件同时有 B 与 H 缺陷时，两者进**同一份**台账（不是各出一份报告）。"""
    from mimeconform.cli import _audit, build_parser
    from mimeconform.ledger import build

    data = (
        b"Subject: =?UTF-8?Q?foo bar?=\r\n"
        b'Content-Type: multipart/mixed; boundary="b"\r\n'
        b"\r\n--b\r\n\r\nbody\r\n"
    )
    args = build_parser().parse_args(["audit", "x.eml"])
    _result, defects = _audit(data, args)
    rules = {defect.rule_id for defect in defects}
    assert "MC-H03" in rules, f"H 簇缺陷没进台账：{sorted(rules)}"
    assert "MC-B05" in rules, f"B 簇缺陷也在同一批里：{sorted(rules)}"
    ledger = build(defects)  # 六元组校验 + 排序 + 指纹一次过
    assert ledger["count"] == len(defects)


# ── selftest 的数据态语义 ─────────────────────────────────────────────────


def test_selftest_missing_data_dir_is_one(tmp_path: Path) -> None:
    assert main(["selftest", "--data-dir", str(tmp_path / "nope")]) == C.EXIT_USAGE


def test_selftest_empty_data_dir_is_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """0 个 case 不能被读成"全部通过"（空分母 ≠ 通过）。"""
    assert main(["selftest", "--data-dir", str(tmp_path)]) == C.EXIT_USAGE
    captured = capsys.readouterr()
    assert "0 个" in captured.err or "没有任何 case" in captured.err


# ── 参数面反射（README ↔ parser 的双向对账靠它）──────────────────────────


def test_parser_exposes_documented_flags() -> None:
    """`plan/03` §八 列出的旗标必须真的被 parser 接受（文档与实现不能各写一套）。"""
    parser = build_parser()
    expected = {
        "--out",
        "--format",
        "--fail-on",
        "--max-depth",
        "--strict-depth",
        "--mbox-variant",
        "--container",
        "--data-dir",
        "--version",
    }
    accepted: set[str] = set()
    for action in parser._actions:  # noqa: SLF001 - 反射对账必须看真实参数面
        accepted.update(action.option_strings)
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            for sub in action.choices.values():
                for sub_action in sub._actions:  # noqa: SLF001
                    accepted.update(sub_action.option_strings)
    missing = expected - accepted
    assert not missing, f"plan/03 §八 写了但 parser 不认: {sorted(missing)}"


def test_parser_rejects_unknown_format() -> None:
    """多值/枚举参数：未知值必须显式拒绝，不静默回落。"""
    with pytest.raises(UsageError):
        build_parser().parse_args(["audit", "x.eml", "--format=sarif"])


def test_parser_accepts_defaults() -> None:
    args = build_parser().parse_args(["audit", "x.eml"])
    assert args.format == "both"
    assert args.fail_on == C.FAIL_ON_DEFAULT
    assert args.max_depth == C.MAX_DEPTH_DEFAULT
    assert args.mbox_variant == C.MBOX_VARIANT_DEFAULT
    assert args.container is False
    assert args.strict_depth is False


def test_engine_not_ready_is_a_mimeconform_error() -> None:
    """EngineNotReady 必须走自家异常体系（否则 CLI 的映射会漏）。"""
    from mimeconform.errors import MimeconformError

    assert issubclass(EngineNotReady, MimeconformError)
