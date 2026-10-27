"""退出码判定（唯一实现，见 data/README §7.9）。

基准表（§7.9）：0 = 无 blocker/major；2 = 有 minor 无 blocker/major；3 = 有 major/blocker。

``--fail-on`` 语义（本模块的**唯一定义**，plan/03 §八 只说"可提升门槛"）：
它只会让判定**更严**，永远不会让 major/blocker 反向变成通过——
即 ``exit 3`` 的条件是「基准表命中」**或**「最高严重度 ≥ fail_on」。
因此 ``--fail-on=note`` 会把任一 note 也判成失败，``--fail-on=blocker`` 仍不会放过 major
（基准表优先，§7.9 是唯一真相源，选项不得推翻它）。
"""

from __future__ import annotations

from collections.abc import Iterable

from . import constants as C
from .model import Defect


def worst_severity(defects: Iterable[Defect]) -> str:
    """返回缺陷集中最高的严重度；空集返回 ``note``（等价于"无事"）。"""
    worst = C.SEV_NOTE
    for defect in defects:
        if C.SEVERITY_RANK[defect.severity] > C.SEVERITY_RANK[worst]:
            worst = defect.severity
    return worst


def decide_exit_code(defects: Iterable[Defect], *, fail_on: str = C.FAIL_ON_DEFAULT) -> int:
    """按 §7.9 决定审计类退出码（0 / 2 / 3）。

    参数校验：``fail_on`` 不在四档内 → ``ValueError``（不静默回落默认值）。
    """
    if fail_on not in C.SEVERITIES:
        raise ValueError(f"--fail-on 必须是 {C.SEVERITIES}: {fail_on!r}")

    defects = tuple(defects)
    if not defects:
        return C.EXIT_OK

    worst = worst_severity(defects)
    worst_rank = C.SEVERITY_RANK[worst]

    # 基准表：major / blocker 一律 3（--fail-on 不得推翻）
    baseline_fail = worst_rank >= C.SEVERITY_RANK[C.SEV_MAJOR]
    # 提升门槛：最高严重度达到用户指定档
    stricter_fail = worst_rank >= C.SEVERITY_RANK[fail_on]

    if baseline_fail or stricter_fail:
        return C.EXIT_MAJOR
    if worst == C.SEV_MINOR:
        return C.EXIT_MINOR
    return C.EXIT_OK
