"""口径常量集中处 —— 每一条都指回 ``data/README.md`` §七。

**纪律**：数值口径只有一处定义（``data/README.md`` §七）。本模块是代码侧的**唯一**落点；
其他模块一律 import 这里，禁止在别处写字面量（``tests/test_constants_single_source.py`` 断言）。
"""

from __future__ import annotations

# ── §7.1 class 三值（封闭）──────────────────────────────────────────────────
CLASS_HARD = "hard"
CLASS_DIFF = "diff"
CLASS_GRAY = "gray"
CLASSES: tuple[str, ...] = (CLASS_HARD, CLASS_DIFF, CLASS_GRAY)

# ── §7.4 严重度四档 ────────────────────────────────────────────────────────
SEV_BLOCKER = "blocker"
SEV_MAJOR = "major"
SEV_MINOR = "minor"
SEV_NOTE = "note"
SEVERITIES: tuple[str, ...] = (SEV_BLOCKER, SEV_MAJOR, SEV_MINOR, SEV_NOTE)
SEVERITY_RANK: dict[str, int] = {
    SEV_NOTE: 0,
    SEV_MINOR: 1,
    SEV_MAJOR: 2,
    SEV_BLOCKER: 3,
}

# ── §7.10 位置口径 ─────────────────────────────────────────────────────────
OFFSET_ABSOLUTE = "absolute"
OFFSET_MESSAGE_RELATIVE = "message-relative"
OFFSET_LINE = "line"
OFFSET_KINDS: tuple[str, ...] = (OFFSET_ABSOLUTE, OFFSET_MESSAGE_RELATIVE, OFFSET_LINE)

# ── §7.9 退出码 ────────────────────────────────────────────────────────────
EXIT_OK = 0          # 审计完成，无 blocker/major
EXIT_USAGE = 1       # 用法错误或输入不可读（防腐层：读不了 ≠ 没问题）
EXIT_MINOR = 2       # 审计完成，存在 minor（无 blocker/major）
EXIT_MAJOR = 3       # 审计完成，存在 major/blocker

# ── §7.9 --fail-on 门槛（默认 major）──────────────────────────────────────
FAIL_ON_DEFAULT = SEV_MAJOR

# ── §7.6 --max-depth 策略项（默认 32；gray，默认不影响退出码）──────────────
MAX_DEPTH_DEFAULT = 32

# ── §7.7 mbox 变体 ─────────────────────────────────────────────────────────
MBOX_VARIANTS: tuple[str, ...] = ("mboxo", "mboxrd", "mboxcl", "auto")
MBOX_VARIANT_DEFAULT = "auto"

# ── 无条款时的 rfc 占位（§7.1：不得为空，用"没有条款"本身作证据）──────────
RFC_NONE_BY_DESIGN = "none-by-design"
