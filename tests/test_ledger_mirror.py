"""台账镜像：`data/rfc-ledger.json`（机读）↔ `data/README.md` §三（人读）。

**判据**：两处的 `(RFC 号, 节号)` 集合必须相等；且每行的「原句留档」状态
（全录 / 部分 / 未录）必须一致。

这是"数值口径只有一个真相源"在条款台账上的落法：机读镜像可以细化到 `subclauses`，
但**不得新增人读台账里没有的节号**，也不得把"未录"悄悄标成"已录"。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEDGER_JSON = ROOT / "data" / "rfc-ledger.json"
README = ROOT / "data" / "README.md"


@pytest.fixture(scope="module")
def mirror() -> dict:
    return json.loads(LEDGER_JSON.read_text(encoding="utf-8"))


def _human_rows() -> dict[str, str]:
    """从 `data/README.md` §三 抽出 ``{规则号: 原句留档状态}``。

    「原句留档」列的形态是 **`**全录**` / `**部分**（…子项未录…）` / `**未录** → …`**：
    状态是**开头那个加粗词**，括号里的补充说明本身就含"全录/未录"字样。
    按"整格包含某个词"判会把「部分」读成「全录」（首版实测 R4/R7/R9 三条假绿）。
    """
    text = README.read_text(encoding="utf-8")
    section = text.split("## 三、RFC 条款原句台账")
    assert len(section) == 2, "data/README 里找不到 §三 条款台账"
    body = section[1].split("## 四、")[0]
    mapping = {"全录": "full", "部分": "partial", "未录": "none"}
    rows: dict[str, str] = {}
    for line in body.split("\n"):
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 8:
            continue
        rule = cells[1]
        if not re.fullmatch(r"R\d+", rule):
            continue
        status_cell = cells[-2]
        leading = re.match(r"^\*{0,2}(全录|部分|未录)\*{0,2}", status_cell)
        assert leading, f"{rule} 的原句留档列形态异常: {status_cell!r}"
        rows[rule] = mapping[leading.group(1)]
    return rows


def _json_rows(mirror: dict) -> dict[str, str]:
    """从机读镜像汇总到**规则号**粒度。

    一个 R 号可能横跨多个节（如 R7 = §5.1.1 的 delimiter 子项 + §5.1.2 的嵌套子项），
    所以状态必须按**子项**汇总，而不是按 clause 的顶层 `row`：
    clause 的 `row` 只是该节的"代表行"，子项可以挂到别的行（如 `header-line-76` → R2）。
    汇总规则与 `data/README` §三 的定义一致：
    全录 = 该行判定的每一条都有逐字原句；部分 = 有子项无原句；未录 = 整行只有节号。
    """
    clauses = mirror["clauses"]
    assert clauses, "机读台账为空"
    per_row: dict[str, list[bool]] = {}

    for _key, clause in clauses.items():
        recorded = clause.get("recorded")
        subclauses = clause.get("subclauses") or {}
        if recorded == "none" and not subclauses:
            per_row.setdefault(clause["row"], []).append(False)
            continue
        for sub in subclauses.values():
            per_row.setdefault(sub.get("row", clause["row"]), []).append(bool(sub.get("recorded")))

    result: dict[str, str] = {}
    for row, flags in per_row.items():
        if not flags:
            result[row] = "none"
        elif all(flags):
            result[row] = "full"
        elif any(flags):
            result[row] = "partial"
        else:
            result[row] = "none"
    return result


def test_mirror_has_eleven_rows_worth_of_clauses(mirror: dict) -> None:
    """`data/README` §三 是 11 行台账；机读镜像必须覆盖 R1–R11 全部。"""
    rows = set(_json_rows(mirror))
    expected = {f"R{index}" for index in range(1, 12)}
    assert rows == expected, f"机读台账缺行: {sorted(expected - rows)}；多行: {sorted(rows - expected)}"


def test_mirror_matches_human_ledger_rows(mirror: dict) -> None:
    """人读台账的 R 号集合 == 机读镜像的 R 号集合。"""
    human = set(_human_rows())
    mirrored = set(_json_rows(mirror))
    assert human == mirrored, f"人读/机读不一致：只在人读 {sorted(human - mirrored)}；只在机读 {sorted(mirrored - human)}"


def test_recorded_status_matches(mirror: dict) -> None:
    """「原句留档」状态逐行一致（全录 / 部分 / 未录）。这是 D12 的证据面。"""
    human = _human_rows()
    mirrored = _json_rows(mirror)
    mismatches = [
        f"{row}: 人读={human[row]} 机读={mirrored[row]}"
        for row in sorted(human)
        if row in mirrored and human[row] != mirrored[row]
    ]
    assert not mismatches, "原句留档状态不一致：\n" + "\n".join(mismatches)


def test_clause_sections_are_present_in_human_ledger(mirror: dict) -> None:
    """机读镜像里的每个 `(RFC 号, 节号)` 必须能在人读台账的出处列里找到。"""
    text = README.read_text(encoding="utf-8")
    section = text.split("## 三、RFC 条款原句台账")[1].split("## 四、")[0]
    missing: list[str] = []
    for key, clause in mirror["clauses"].items():
        needle = f"§{clause['section']}"
        if needle not in section:
            missing.append(f"{key}（{needle}）")
    assert not missing, f"机读镜像里的节号在人读台账里找不到: {missing}"


def test_no_verbatim_outside_human_ledger(mirror: dict) -> None:
    """机读镜像**不得**给"未录"的行补原句（那是凭空造条款）。"""
    text = README.read_text(encoding="utf-8")
    section = text.split("## 三、RFC 条款原句台账")[1].split("## 四、")[0]
    offenders: list[str] = []
    for key, clause in mirror["clauses"].items():
        if clause.get("recorded") == "none":
            continue
        verbatim = clause.get("verbatim")
        if not verbatim:
            continue
        # 原句必须能在人读台账里逐字找到（允许换行/空白差异）
        normalized_section = re.sub(r"\s+", " ", section)
        normalized_verbatim = re.sub(r"\s+", " ", verbatim).strip()
        if normalized_verbatim not in normalized_section:
            offenders.append(f"{key}: {normalized_verbatim[:60]}…")
    assert not offenders, "机读镜像的原句在人读台账里找不到（疑似凭空补条款）：\n" + "\n".join(offenders)


def test_unrecorded_clauses_have_no_verbatim(mirror: dict) -> None:
    """未录子项的 `verbatim` 必须是 null —— 这是原句门禁的判据输入。"""
    offenders: list[str] = []
    for key, clause in mirror["clauses"].items():
        for name, sub in (clause.get("subclauses") or {}).items():
            if not sub.get("recorded") and sub.get("verbatim"):
                offenders.append(f"{key}#{name}")
    assert not offenders, f"未录子项带了原句（状态与数据矛盾）: {offenders}"
