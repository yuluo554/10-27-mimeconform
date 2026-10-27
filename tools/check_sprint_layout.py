#!/usr/bin/env python3
"""布局门（方法论装订第②件）—— 把"项目还长在方法论上"变成可跑红的断言。

判据一律落**仓库内文件**（不读 git 元数据：浅克隆下 `git tag` / 历史深度会翻转）。
退出码：0 全绿 / 1 有 FAIL / 2 用法错误。

**形态纪律**（照 `ai-tool-project-sprint` references/methodology-binding.md）：
* 非空跑自证：每个判据都打印"这轮扫到了几个"；
* 枚举式而非抽查式：状态副本用命中集合驱动，并断言下界；
* 超集宽容：只断言"必需节都存在"，不断言"节数恰好等于 N"；
* 永不崩：被检查对象不存在时报一条 FAIL 并继续；
* 真值不取自任何一个副本（逐副本采集，任一里程碑出现两种状态即 FAIL）。

**变异验证**（改完判据必重跑，见 tools/verify_layout_gate.py）：18 组，全组符合预期。
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ── 配置（换项目改这一段）──────────────────────────────────────────────────

REQUIRED_FILES = (
    "AGENTS.md",
    "README.md",
    "LICENSE",
    "pyproject.toml",
    "data/README.md",
    "plan/00-README总览.md",
    "plan/01-题目文档.md",
    "plan/02-架构与技术选型.md",
    "plan/03-模块详设.md",
    "plan/04-数据计划.md",
    "plan/05-里程碑与验收.md",
    "plan/06-交付对标与决策.md",
    "tools/check_sprint_layout.py",
    "tools/check_desensitized.py",
)

REQUIRED_SECTIONS = {
    "plan/00-README总览.md": ("文档索引", "决策记录", "承诺-证据台账", "里程碑"),
    "plan/01-题目文档.md": ("任务要求", "评分标准", "边界与非目标"),
    "plan/02-架构与技术选型.md": ("分层", "字节扫描状态机", "退出码", "确定性"),
    "plan/03-模块详设.md": ("公共数据模型", "CLI", "规则目录"),
    "plan/04-数据计划.md": ("数据清单", "生成器", "重建判据", "数值口径"),
    "plan/05-里程碑与验收.md": ("DoD", "已知未验证项"),
    "plan/06-交付对标与决策.md": ("评分维度对标", "风险登记", "缺口"),
    "data/README.md": ("依据查证", "条款原句台账", "数值口径"),
}
#: 关键词必须出现在**标题行**里（见 `check_sections` 的注释）。

#: HANDOFF 七节（硬约束①）。项目自定更细的格式是合法超集 —— 只断言"必需节都存在"。
HANDOFF_SECTIONS = ("当前进度", "当前事实", "待办", "既定口径", "环境坑", "DoD", "命令速查")

#: 项目**已声明**的豁免：M0 的收尾记录就是计划套件本身，不写 HANDOFF-M0。
EXEMPT_MILESTONES = frozenset({0})
#: 交接单格式冻结起点（更早的里程碑只查存在性，不查节）。
HANDOFF_FORMAT_FROM = 1
#: 末棒要不要交接单：False = 要（写"收官交接单"）。
HANDOFF_EXEMPT_LAST = False

#: 状态副本：同一里程碑在这几处的状态必须互相一致。
STATUS_COPIES = (
    ("plan/00-README总览.md", "里程碑表"),
    ("plan/05-里程碑与验收.md", "状态表"),
    ("README.md", "状态表"),
)

#: 只认"状态行"：表格行且首格就是里程碑号（不扫自由文本 —— 防张冠李戴的假红）。
STATUS_LINE = re.compile(r"^\|\s*\*{0,2}M(\d+)\b")
PENDING_MARKERS = ("⬜", "🟡", "未开始", "未执行", "待执行", "待确认")

#: 收尾记录只挂在**发布里程碑**；它未 ✅ 时本项报 PASS 并写明"尚不适用"。
RELEASE_MILESTONE = 6

#: 文档点名的 `tools/*` 脚本必须有实物。
#: 前置边界 `(?<![\w/])` 防止把 ``mimeconform/devtools/gen_golden.py`` 误判成 ``tools/gen_golden.py``
#: （假阳性会让门要求一个本项目根本不该在 `tools/` 下存在的文件）。
DOC_TOOL_PATTERN = re.compile(r"(?<![\w/])tools/[\w.-]+\.(?:py|mjs|js|cjs|sh|ps1)")
#: 已点名但**尚未到**该里程碑的脚本：{path: milestone}。里程碑翻 ✅ 后必须删除。
PENDING_TOOLS: dict[str, int] = {}
#: 确实不打算实现的脚本（理由写在这里）。
EXEMPT_TOOLS: frozenset[str] = frozenset()

#: 装订行：三个锚点必须同现于一行（前瞻，顺序无关）。
BINDING_LINE = re.compile(
    r"^>(?=.*ai-tool-project-sprint)(?=.*check_sprint_layout)(?=.*20\d{2}-\d{2}-\d{2}).*$",
    re.MULTILINE,
)


# ── 检查框架 ──────────────────────────────────────────────────────────────


@dataclass
class Gate:
    checks: list[tuple[str, bool, str]] = field(default_factory=list)
    scanned: dict[str, int] = field(default_factory=dict)

    def add(self, check_id: str, ok: bool, detail: str) -> None:
        self.checks.append((check_id, ok, detail))

    def read(self, rel: str) -> str | None:
        path = ROOT / rel
        if not path.is_file():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None


def check_required_files(gate: Gate) -> None:
    missing = [rel for rel in REQUIRED_FILES if not (ROOT / rel).is_file()]
    gate.scanned["files"] = len(REQUIRED_FILES) - len(missing)
    gate.add(
        "LAYOUT.FILES",
        not missing,
        f"缺: {','.join(missing)}" if missing else f"{gate.scanned['files']} 份齐备",
    )


def check_binding_head(gate: Gate) -> None:
    text = gate.read("plan/00-README总览.md") or ""
    ok = bool(BINDING_LINE.search(text))
    gate.add(
        "LAYOUT.BINDING_HEAD",
        ok,
        "plan/00 顶部有装订行（三锚点齐）"
        if ok
        else "plan/00 顶部缺装订行（需同现：方法论名 + 布局门命令 + 装订日期）",
    )


def _headings(text: str) -> list[str]:
    """抽出全部标题行（`#` 开头）。**小节判据只认标题**，不扫自由文本。"""
    return [line for line in text.split("\n") if line.lstrip().startswith("#")]


def check_sections(gate: Gate) -> None:
    """必需小节判据：关键词必须出现在**标题行**里。

    **为什么只认标题**：首版写成 ``needle in text``（整篇包含），于是"CLI"这类词在正文里
    出现过就判绿——把标题删掉、正文里仍提到它时**门不变红**（变异 M04/M09 实测）。
    这是"扫自由文本"的假门形态：判据的作用域比它想判的那件事宽。
    """
    bad: list[str] = []
    scanned = 0
    for rel, needles in REQUIRED_SECTIONS.items():
        text = gate.read(rel)
        if text is None:
            continue
        scanned += 1
        headings = "\n".join(_headings(text))
        missing = [needle for needle in needles if needle not in headings]
        if missing:
            bad.append(f"{rel}: {'/'.join(missing)}")
    gate.scanned["sections"] = scanned
    gate.add(
        "LAYOUT.SECTIONS",
        not bad,
        "；".join(bad) if bad else f"{scanned} 份文档小节齐备（只认标题行）",
    )


def collect_states(gate: Gate) -> tuple[dict[int, set[str]], dict[str, int]]:
    """逐副本采集状态 → ``({里程碑: {done,pending}}, {副本: 命中行数})``。

    **真值不取自任何一个副本**：任一里程碑出现两种状态即 FAIL。
    每份副本的命中行数必须可见（0 行 = 该副本不参与判定，是合法配置但不能冒充已核对）。
    """
    states: dict[int, set[str]] = {}
    rows_by_copy: dict[str, int] = {}
    for rel, _kind in STATUS_COPIES:
        text = gate.read(rel)
        if text is None:
            rows_by_copy[rel] = 0
            continue
        rows = 0
        for line in text.split("\n"):
            match = STATUS_LINE.match(line)
            if not match:
                continue
            rows += 1
            state = "pending" if any(mark in line for mark in PENDING_MARKERS) else "done"
            states.setdefault(int(match.group(1)), set()).add(state)
        rows_by_copy[rel] = rows
    return states, rows_by_copy


def check_status_agreement(gate: Gate, states: dict[int, set[str]], rows_by_copy: dict[str, int]) -> None:
    conflicts = [
        f"M{index} 在副本间状态不一致（{' vs '.join(sorted(values))}）"
        for index, values in sorted(states.items())
        if len(values) > 1
    ]
    per_copy = " ".join(
        f"{rel.split('/')[-1]}:{rows}" for rel, rows in sorted(rows_by_copy.items())
    )
    total_rows = sum(rows_by_copy.values())
    if not conflicts and total_rows == 0:
        gate.add("LAYOUT.STATUS", False, f"所有副本合计 0 行状态行（判据空跑）：{per_copy}")
        return
    gate.add(
        "LAYOUT.STATUS",
        not conflicts,
        "；".join(conflicts)
        if conflicts
        else f"{len(rows_by_copy)} 处副本 × {len(states)} 个里程碑 状态全一致（行数 {per_copy}）",
    )


def check_handoffs(gate: Gate, done: list[int], all_milestones: list[int]) -> None:
    last = max(all_milestones) if all_milestones else 0
    problems: list[str] = []
    found = 0
    for index in sorted(done):
        if index in EXEMPT_MILESTONES:
            continue
        if HANDOFF_EXEMPT_LAST and index == last:
            continue
        rel = f"plan/HANDOFF-M{index}.md"
        text = gate.read(rel)
        if text is None:
            hint = "：末棒要么写收官交接单，要么置 HANDOFF_EXEMPT_LAST 并在 AGENTS.md 说明" if index == last else ""
            problems.append(f"{rel}(缺{hint})")
            continue
        found += 1
        if index < HANDOFF_FORMAT_FROM:
            continue
        lack = [name for name in HANDOFF_SECTIONS if name not in text]
        if lack:
            problems.append(f"{rel}(缺节: {'/'.join(lack)})")
    gate.scanned["handoffs"] = found
    exempt_note = f"；已声明豁免 {sorted(EXEMPT_MILESTONES)}" if EXEMPT_MILESTONES else ""
    gate.add(
        "LAYOUT.HANDOFFS",
        not problems,
        "；".join(problems) if problems else f"{found} 份交接单齐{exempt_note}",
    )


def check_stale_gaps(gate: Gate, done: list[int]) -> None:
    """`plan/06` 的「缺口」列是状态的隐蔽副本。

    **按表头定位列号再取单元格**（不是"最后一列"，也不是"行里含『缺口』二字"）：
    本项目 `plan/06` 的缺口表是 ``| # | 缺口 | 状态 | 关闭条件 |``——缺口不是最后一列。
    首版按"最后一列"取，实际取到「状态」列，于是把 M 号写进缺口格**永远抓不到**（假门族 ②）。
    扫描面 = 表头 → 首条非表格行即止；匹配前剥掉行内代码与文件名（假门族 ⑥）。
    """
    text = gate.read("plan/06-交付对标与决策.md") or ""
    lines = text.split("\n")
    header_index = next(
        (i for i, line in enumerate(lines) if line.startswith("|") and "缺口" in line),
        -1,
    )
    if header_index < 0:
        gate.add("LAYOUT.GAPS", False, "plan/06 找不到含『缺口』表头的表（判据表搬走了？）")
        return
    header_cells = [cell.strip() for cell in lines[header_index].split("|")]
    try:
        column = header_cells.index("缺口")
    except ValueError:  # 表头可能写成「缺口 / 开放项」
        column = next(
            (idx for idx, cell in enumerate(header_cells) if "缺口" in cell),
            -1,
        )
    if column < 0:
        gate.add("LAYOUT.GAPS", False, f"plan/06 缺口表头里找不到『缺口』单元格: {header_cells}")
        return
    stale: list[str] = []
    scanned_rows = 0
    for line in lines[header_index + 2 :]:
        if not line.startswith("|"):
            break
        scanned_rows += 1
        cells = line.split("|")
        cell = cells[column] if column < len(cells) else ""
        cleaned = re.sub(r"`[^`]*`", " ", cell)
        cleaned = re.sub(r"[\w./-]+\.(?:md|py|mjs|js|json|toml|txt|whl|gz|zip)", " ", cleaned)
        for index in done:
            if re.search(rf"(^|[^0-9A-Za-z])M{index}([^0-9]|$)", cleaned):
                stale.append(f"plan/06 缺口列仍提 M{index}: {cell.strip()}")
    gate.scanned["gap_rows"] = scanned_rows
    gate.add(
        "LAYOUT.GAPS",
        not stale,
        "；".join(stale) if stale else f"plan/06 缺口列（第 {column} 列）扫了 {scanned_rows} 行，无已 ✅ 里程碑",
    )


def check_ledger(gate: Gate, done: list[int]) -> None:
    """承诺-证据台账是状态的**第四份副本**，按它自己的表头定位（它不是状态表）。"""
    text = gate.read("plan/00-README总览.md") or ""
    lines = text.split("\n")
    header_index = next(
        (
            i
            for i, line in enumerate(lines)
            if line.startswith("|") and "承诺" in line and "状态" in line
        ),
        -1,
    )
    if header_index < 0:
        gate.add("LAYOUT.LEDGER", False, "plan/00 找不到『承诺-证据台账』表头（承诺项与状态列）")
        return
    gate.scanned["ledger"] = 1
    bad: list[str] = []
    rows = 0
    for line in lines[header_index + 2 :]:
        if not line.startswith("|"):
            break
        rows += 1
        cells = [cell.strip() for cell in line.split("|")]
        status = cells[-2] if len(cells) >= 2 else ""
        if not re.search(r"[⬜🟡]|未开始|待 M\d|待开工", status):
            continue
        for index in done:
            if re.search(rf"(^|[^0-9A-Za-z])M{index}([^0-9]|$)", status, re.IGNORECASE):
                bad.append(f"台账行仍挂未完成: {status[:60]}")
    if rows == 0:
        gate.add("LAYOUT.LEDGER", False, "台账表 0 行——判据空跑")
        return
    gate.add(
        "LAYOUT.LEDGER",
        not bad,
        "；".join(bad) if bad else f"台账 {rows} 行，已成 ✅ 的里程碑无未完成标记",
    )


def check_release_doc(gate: Gate, done: list[int], all_milestones: list[int]) -> None:
    release_milestone = RELEASE_MILESTONE or (max(all_milestones) if all_milestones else 0)
    if release_milestone == 0 or release_milestone not in done:
        gate.add(
            "LAYOUT.RELEASE",
            True,
            f"发布里程碑 M{release_milestone} 未完成，收尾记录尚不适用（已扫 {len(done)} 个 ✅ 里程碑）",
        )
        return
    release = gate.read(f"plan/RELEASE-M{release_milestone}.md")
    wrapup = gate.read(f"plan/WRAPUP-M{release_milestone}.md")
    if release is None and wrapup is None:
        gate.add(
            "LAYOUT.RELEASE",
            False,
            f"缺 plan/RELEASE-M{release_milestone}.md 或 plan/WRAPUP-M{release_milestone}.md",
        )
        return
    if release is None:
        gate.add("LAYOUT.RELEASE", True, "WRAPUP 形态")
        return
    columns = bool(
        re.search(r"^##\s*一、tag 前事实", release, re.MULTILINE)
        and re.search(r"^##\s*二、tag 后追加", release, re.MULTILINE)
    )
    heading = bool(re.search(r"^#{2,3}.*覆盖对账", release, re.MULTILINE))
    rows = len(re.findall(r"^\|.*(实现|不适用|待首推).*\|$", release, re.MULTILINE))
    gate.add(
        "LAYOUT.RELEASE",
        columns and heading and rows >= 3,
        f"两栏:{columns} 覆盖对账小节:{heading} 三态行数:{rows}",
    )


def check_documented_tools(gate: Gate, done: list[int]) -> None:
    """文档点名的 `tools/*` 脚本必须有实物；未到里程碑的登记在 PENDING_TOOLS。"""
    docs = ["AGENTS.md"]
    plan_dir = ROOT / "plan"
    if plan_dir.is_dir():
        docs.extend(f"plan/{path.name}" for path in sorted(plan_dir.glob("*.md")))
    referenced: set[str] = set()
    for rel in docs:
        text = gate.read(rel)
        if text is None:
            continue
        referenced.update(DOC_TOOL_PATTERN.findall(text))
    if not referenced:
        gate.add(
            "LAYOUT.DOC_TOOLS",
            False,
            f"扫了 {len(docs)} 份文档，0 处 tools/ 引用——判据是空的（阳性对照失败）",
        )
        return
    gate.scanned["doc_tools"] = len(referenced)
    missing: list[str] = []
    deferred: list[str] = []
    stale: list[str] = []
    for rel in sorted(referenced):
        if (ROOT / rel).is_file() or rel in EXEMPT_TOOLS:
            continue
        milestone = PENDING_TOOLS.get(rel)
        if milestone is None:
            missing.append(rel)
        elif milestone in done:
            stale.append(f"{rel}（M{milestone} 已 ✅，登记项必须清理）")
        else:
            deferred.append(f"{rel}(M{milestone})")
    problems = missing + stale
    detail = f"{len(referenced)} 个文档点名的 tools/ 脚本"
    if problems:
        detail += f"；问题: {','.join(problems)}"
    elif deferred:
        detail += f"；{len(deferred)} 个待里程碑落位: {','.join(deferred)}"
    else:
        detail += " 全部在位"
    gate.add("LAYOUT.DOC_TOOLS", not problems, detail)


# ── 主流程 ────────────────────────────────────────────────────────────────


def run_gate() -> tuple[list[tuple[str, bool, str]], dict[str, int]]:
    gate = Gate()
    for runner in (check_required_files, check_binding_head, check_sections):
        try:
            runner(gate)
        except Exception as exc:  # noqa: BLE001 - 门永不崩：报一条 FAIL 并继续
            gate.add(runner.__name__, False, f"异常: {exc}")

    try:
        states, rows_by_copy = collect_states(gate)
    except Exception as exc:  # noqa: BLE001
        gate.add("LAYOUT.STATUS", False, f"采集状态异常: {exc}")
        states, rows_by_copy = {}, {}

    done = sorted(index for index, values in states.items() if "done" in values)
    all_milestones = sorted(states)

    for runner in (
        lambda: check_status_agreement(gate, states, rows_by_copy),
        lambda: check_handoffs(gate, done, all_milestones),
        lambda: check_stale_gaps(gate, done),
        lambda: check_ledger(gate, done),
        lambda: check_release_doc(gate, done, all_milestones),
        lambda: check_documented_tools(gate, done),
    ):
        try:
            runner()
        except Exception as exc:  # noqa: BLE001
            gate.add(f"LAYOUT.UNEXPECTED.{len(gate.checks)}", False, f"异常: {exc}")

    return gate.checks, gate.scanned


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="布局门：方法论装订的结构断言")
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 输出（供变异验证脚本消费）",
    )
    args = parser.parse_args(argv)

    checks, scanned = run_gate()
    failed = [item for item in checks if not item[1]]

    if args.json:
        import json

        payload = {
            "checks": [{"id": cid, "ok": ok, "detail": detail} for cid, ok, detail in checks],
            "scanned": scanned,
            "failed": len(failed),
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0 if not failed else 1

    sys.stdout.write("布局门（方法论装订） · 判据只落仓库内文件\n")
    sys.stdout.write("=" * 56 + "\n")
    for check_id, ok, detail in checks:
        sys.stdout.write(f"{'PASS' if ok else 'FAIL'}  {check_id}  {detail}\n")
    sys.stdout.write("=" * 56 + "\n")
    counts = " / ".join(f"{key} {value}" for key, value in scanned.items())
    sys.stdout.write(f"这轮扫到：{counts}\n")
    sys.stdout.write(f"结论: {'全绿' if not failed else f'{len(failed)} 项 FAIL'}\n")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
