"""退出码判定（`data/README` §7.9 的唯一实现）。

M0 只能测到**函数级** 0/2/3（`audit` 的接线在 M2）；CLI 级 0/1 在
`tests/test_cli_contract.py`。这不算"跳过了 2/3"——判据本体在此已逐档锁住，
M2 只需把 `scan` 的结果喂进来（接线测试届时补在此文件末尾）。
"""

from __future__ import annotations

import pytest

from mimeconform import constants as C
from mimeconform.exit_codes import decide_exit_code, worst_severity
from mimeconform.model import Defect


def defect(severity: str, *, klass: str | None = None, rule_id: str = "MC-B01", offset: int = 0) -> Defect:
    klass = klass or ("hard" if severity in {"blocker", "major", "minor"} else "diff")
    return Defect(
        rule_id=rule_id,
        klass=klass,
        severity=severity,
        path="0",
        offset=offset,
        offset_kind="absolute",
        rfc="RFC 2046 §5.1.1" if klass == "hard" else C.RFC_NONE_BY_DESIGN,
        detail="x",
    )


def test_no_defects_is_zero() -> None:
    assert decide_exit_code([]) == C.EXIT_OK


def test_only_notes_is_zero() -> None:
    """`note` 不影响退出码（§7.9：0 = 无 blocker/major；note 只是登记）。"""
    assert decide_exit_code([defect("note")]) == C.EXIT_OK


def test_minor_only_is_two() -> None:
    assert decide_exit_code([defect("minor")]) == C.EXIT_MINOR


def test_major_is_three() -> None:
    assert decide_exit_code([defect("major")]) == C.EXIT_MAJOR


def test_blocker_is_three() -> None:
    assert decide_exit_code([defect("blocker")]) == C.EXIT_MAJOR


@pytest.mark.parametrize("fail_on", C.SEVERITIES)
def test_fail_on_never_softens_baseline(fail_on: str) -> None:
    """`--fail-on` 只会更严：major/blocker 在任何门槛下都是 3（§7.9 是唯一真相源）。"""
    assert decide_exit_code([defect("major")], fail_on=fail_on) == C.EXIT_MAJOR
    assert decide_exit_code([defect("blocker")], fail_on=fail_on) == C.EXIT_MAJOR


def test_fail_on_note_escalates_notes() -> None:
    assert decide_exit_code([defect("note")], fail_on="note") == C.EXIT_MAJOR


def test_fail_on_minor_escalates_minor() -> None:
    assert decide_exit_code([defect("minor")], fail_on="minor") == C.EXIT_MAJOR


def test_fail_on_blocker_keeps_blocker_as_three() -> None:
    assert decide_exit_code([defect("blocker")], fail_on="blocker") == C.EXIT_MAJOR


def test_fail_on_invalid_raises() -> None:
    """非法门槛必须抛错，不静默回落默认值（skill 阶段 6「or DEFAULT」条）。"""
    with pytest.raises(ValueError, match="fail-on"):
        decide_exit_code([], fail_on="fatal")


def test_worst_severity() -> None:
    assert worst_severity([]) == C.SEV_NOTE
    assert worst_severity([defect("note"), defect("minor")]) == C.SEV_MINOR
    assert worst_severity([defect("major"), defect("minor")]) == C.SEV_MAJOR
    assert worst_severity([defect("blocker"), defect("major")]) == C.SEV_BLOCKER
