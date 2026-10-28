"""自指守门：文档里写的测试数必须是**真实 passed**，不许拿 collected 冒充（D1 / D4）。

**为什么要有这个文件**：全仓 46 条规则、51 例 golden、三值分布都有门守着，唯独
"本项目自己有几种测试"没有任何判据 —— 于是 `plan/` 里六处写着 `682 passed`，
而 682 恒等于 `--collect-only` 的 collected 数，真实 passed 是 681。

**两个数每次现取，不写常量白名单**（这是本文件的设计底线）：

* `collected` = 整树 `--collect-only` 的条数；
* `passed`    = 整树执行后的 `N passed`；
* `own`       = 本文件自己的测试条数（只 collect 本文件取得）。

**允许出现在文档里的 `N passed` 只可能是这四个值**，它们都由上面三个量现算：

| 场景 | 公式 |
| --- | --- |
| 当前树 · 开发树（有 `.git`） | `passed` |
| 当前树 · 解包树（无 `.git`，多 1 个 skip） | `passed - 1` |
| v1.0.0 时刻 · 开发树（本文件尚未存在） | `passed - own` |
| v1.0.0 时刻 · 解包树 | `passed - own - 1` |

历史两值必须允许，因为 `plan/RELEASE-M6.md` 是**已发布产物**的记录，改了就是伪造；
而"文档写了本文件加入之前的数"与"文档抄了 collected"是两回事 —— 后者（collected）
恰好落在四个允许值之外（collected = passed + skip，被这一条挡住）。

**本文件的判据边界（诚实声明）**：它拦得住"collected 冒充 passed""文档没跟上当前
真实值""数字离谱"。它拦不住"684 被改成同样合法的 683"这类同集合内互串，也不
试图判断某个数落在**哪一段**文字里 —— 那需要把每行期望值写成常量表，反而更脆。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWN_FILE = Path(__file__).resolve()

#: 被守门的三份文档（`plan/HANDOFF-M6.md` 是 M6 收官交接单，另两份是发布留档与决策表）。
TARGETS = (
    "plan/HANDOFF-M6.md",
    "plan/RELEASE-M6.md",
    "plan/06-交付对标与决策.md",
)

#: 文档里声明的两种写法：``684 passed`` 与 ``（684 条）``。
COUNT_PATTERN = re.compile(r"(\d+)\s*passed|（(\d+)\s*条）")

_SUMMARY_PASSED = re.compile(r"(\d+)\s+passed")
_SUMMARY_SKIPPED = re.compile(r"(\d+)\s+skipped")
_COLLECTED = re.compile(r"(\d+)\s+tests?\s+collected")


def _pytest(*args: str) -> subprocess.CompletedProcess[str]:
    """子进程跑 pytest（必须落在仓库根；`-p no:cacheprovider` 避免污染工作树）。"""
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-o", "addopts=", "-p", "no:cacheprovider", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


_LIVE: dict[str, int] | None = None


def live_counts() -> dict[str, int]:
    """现取 `collected` / `passed` / `skipped` / `own`。

    **递归防护**：执行态的子进程必须 `--ignore` 掉本文件，否则本文件会在子进程里
    再起一个子进程，无限套娃。本文件自己的条数由"只 collect 本文件"单独取得，
    因此 `passed` 仍能还原成整树的真实值（本文件的 3 条在整树里恒为 passed）。
    """
    global _LIVE
    if _LIVE is not None:
        return _LIVE

    collected_run = _pytest("--collect-only", "-q")
    collected_match = _COLLECTED.search(collected_run.stdout)
    assert collected_match, f"取不到 collected：{collected_run.stdout[-400:]!r}"

    own_run = _pytest(str(OWN_FILE), "--collect-only", "-q")
    own_match = _COLLECTED.search(own_run.stdout)
    assert own_match, f"取不到本文件自身条数：{own_run.stdout[-400:]!r}"

    run = _pytest("-q", "--tb=no", "--ignore", str(OWN_FILE))
    passed_match = _SUMMARY_PASSED.search(run.stdout)
    skipped_match = _SUMMARY_SKIPPED.search(run.stdout)
    assert run.returncode == 0, f"子树不绿，判据无从谈起：\n{run.stdout[-2000:]}"
    assert passed_match, f"取不到 passed 汇总行：{run.stdout[-400:]!r}"

    own = int(own_match.group(1))
    _LIVE = {
        "collected": int(collected_match.group(1)),
        "passed": int(passed_match.group(1)) + own,
        "skipped": int(skipped_match.group(1)) if skipped_match else 0,
        "own": own,
    }
    return _LIVE


def allowed_values(live: dict[str, int]) -> set[int]:
    """四个合法场景值（见模块 docstring 的表）。"""
    passed, own = live["passed"], live["own"]
    return {passed, passed - 1, passed - own, passed - own - 1}


def scan_counts(texts: dict[str, str]) -> list[tuple[str, int, int]]:
    """返回 ``(相对路径, 行号, 数字)``；行号从 1 起，供报错指位。"""
    found: list[tuple[str, int, int]] = []
    for rel, text in texts.items():
        for lineno, line in enumerate(text.split("\n"), start=1):
            for match in COUNT_PATTERN.finditer(line):
                value = match.group(1) or match.group(2)
                found.append((rel, lineno, int(value)))
    return found


def gate_violations(texts: dict[str, str], live: dict[str, int]) -> list[str]:
    """判据本体：非空跑 + 每个数必须落在四个合法场景值里 + collected 绝不出现。"""
    found = scan_counts(texts)
    problems: list[str] = []
    if len(found) < 4:
        # 非空跑自证：文件被读空、或判据面被削掉时，这里必须红。
        problems.append(f"扫到的测试数声明只有 {len(found)} 处（<4）——判据是空的")
    allowed = allowed_values(live)
    for rel, lineno, value in found:
        if value == live["collected"]:
            problems.append(
                f"{rel}:{lineno} 写的是 {value} —— 这恰好是 collected，"
                f"真实 passed 是 {live['passed']}"
            )
        elif value not in allowed:
            problems.append(
                f"{rel}:{lineno} 写 {value}，不在允许集合 {sorted(allowed)} 内"
            )
    return problems


def read_targets() -> dict[str, str]:
    return {rel: (ROOT / rel).read_text(encoding="utf-8") for rel in TARGETS}


def test_documented_test_count_matches_reality() -> None:
    """文档里的每个测试数都必须是真实 passed（或合法的历史/解包形态），不能是 collected。"""
    live = live_counts()
    problems = gate_violations(read_targets(), live)
    assert not problems, "文档测试数与实测不符：\n" + "\n".join(problems)


def test_no_stale_682() -> None:
    """collected 冒充 passed 这一形态（v1.0.0 时代的具体值是 682）——按现取 collected 判。

    不写死 682：collected 会随测试增减而变，写死等于给下一轮留一个恒空的门。
    """
    live = live_counts()
    texts = read_targets()
    offenders = [
        f"{rel}:{lineno} → {value}"
        for rel, lineno, value in scan_counts(texts)
        if value == live["collected"]
    ]
    assert not offenders, (
        f"collected（{live['collected']}）被写成了 passed：\n" + "\n".join(offenders)
    )


def test_count_gate_finds_the_docs() -> None:
    """阴性对照：目标文件读成空时，判据必须红 —— 否则上面两条是空转的。"""
    live = live_counts()
    empty = {rel: "" for rel in TARGETS}
    assert gate_violations(empty, live), "文档读空时判据竟然全绿 —— 假门"
    # 阳性对照同时成立：真实文档必须过。
    assert not gate_violations(read_targets(), live), "真实文档未过判据（与上面两条不一致）"