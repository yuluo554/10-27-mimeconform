"""退出码与 CLI 契约（plan/03 §八）。

M0 阶段可确证的两条：**0**（`--version`）与 **1**（用法错误 / 输入不可读 / 引擎未就绪）。
`2` / `3` 属 M2 起的审计结果，届时在此文件补两条（此处显式 skip 并写明原因，不假装通过）。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from mimeconform import constants as C
from mimeconform.cli import build_parser, main
from mimeconform.errors import EngineNotReady, UsageError


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


# ── 1：引擎未就绪（骨架期显式失败，绝不返回 0）─────────────────────────────


def test_audit_is_not_ready_and_says_so(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "sample.eml"
    target.write_bytes(b"From: a@example.invalid\r\n\r\nhello\r\n")
    code = main(["audit", str(target)])
    captured = capsys.readouterr()
    assert code == C.EXIT_USAGE, "骨架期 audit 必须 exit 1，绝不返回 0（plan/00 D16）"
    assert "尚未实现" in captured.err
    assert "M2" in captured.err


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
