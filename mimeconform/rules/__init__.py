"""规则目录（`catalog.json`）的装载与门禁。

**`catalog.json` 自里程碑 M3 起落地**（`plan/03` §九）。本模块现在就把**校验逻辑**写死，
这样 M3 只需补数据、不用改判据——判据不变形，门才不会在实现时被"顺手放宽"。

门禁三条（`plan/00` D12、锚点 #10）：

1. 每条规则的 ``ledger_key`` 必须存在于 ``data/rfc-ledger.json``；
2. ``klass == "hard"`` 时该键的 ``verbatim`` 必须非空；
3. ``verbatim`` 为空时，该条 ``klass`` 只能是 ``diff``/``gray`` **且** ``severity == "note"``。

另加一条语义层禁令（D7 / D11）：登记在 ``SEMANTIC_RULES`` 里的规则**永不 hard**。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .. import constants as C
from ..errors import EngineNotReady

CATALOG_PATH = Path(__file__).with_name("catalog.json")
LEDGER_PATH = Path(__file__).resolve().parents[2] / "data" / "rfc-ledger.json"

#: `class` 三值 / `severity` 四档的**代码侧来源**只有 `constants`（§7.1 / §7.4）。
CLASSES: tuple[str, ...] = C.CLASSES
SEVERITIES: tuple[str, ...] = C.SEVERITIES

#: 语义层规则集：拿不到 `hard`（`data/README` §7.1 升级禁令的代码侧镜像）。
SEMANTIC_RULES: frozenset[str] = frozenset(
    {
        "MC-T01",
        "MC-T08",
        "MC-T11",
        "MC-H08",
        "MC-H12",
        "MC-B05",
        "MC-B09",
        *{f"MC-A{i:02d}" for i in range(1, 9)},
        *{f"MC-C{i:02d}" for i in range(1, 6)},
    }
)

_REQUIRED_FIELDS = ("rule_id", "module", "klass", "severity", "rfc", "ledger_key", "detector", "summary")


class CatalogError(EngineNotReady):
    """规则目录或其台账镜像不满足门禁。"""


@dataclass(frozen=True, slots=True)
class Rule:
    rule_id: str
    module: str
    klass: str
    severity: str
    rfc: str
    ledger_key: str
    detector: str
    summary: str


def _load_json(path: Path, label: str) -> object:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CatalogError(f"{label} 不存在: {path}（自里程碑 M3 起落地）") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise CatalogError(f"{label} 不是合法 JSON: {path}: {exc}") from exc


def resolve_verbatim(ledger: dict[str, object], ledger_key: str) -> tuple[bool, str | None]:
    """把 `ledger_key` 解析成 ``(键存在, 逐字原句或 None)``。

    键形态两种（`data/rfc-ledger.json`）：

    * ``"RFC2046-5.1.1"`` —— 整节；取该节的 ``verbatim``；
    * ``"RFC2046-5.1.1#close-delimiter-form"`` —— **子项**；取该子项的 ``verbatim``。

    为什么需要子项粒度：一个节里常常只有一部分有逐字原句（如 §5.1.1 的
    "boundary 必填/≤70 字符"有、而 "delimiter 形态"没有）。按整节判会把后者放行成 `hard`。
    """
    clauses = ledger.get("clauses")
    if not isinstance(clauses, dict):
        raise CatalogError("rfc-ledger.json 必须是 {clauses: {...}} 形态")
    key, _, subname = ledger_key.partition("#")
    clause = clauses.get(key)
    if not isinstance(clause, dict):
        return False, None
    if not subname:
        verbatim = clause.get("verbatim")
        return True, verbatim if isinstance(verbatim, str) and verbatim.strip() else None
    subclauses = clause.get("subclauses")
    if not isinstance(subclauses, dict) or subname not in subclauses:
        return False, None
    sub = subclauses[subname]
    if not isinstance(sub, dict):
        return False, None
    if sub.get("recorded") is not True:
        return True, None
    verbatim = sub.get("verbatim")
    return True, verbatim if isinstance(verbatim, str) and verbatim.strip() else None


def validate_catalog(catalog: object, ledger: object) -> list[Rule]:
    """纯函数：校验并返回规则列表。不读磁盘，便于测试注入坏数据。"""
    if not isinstance(catalog, dict):
        raise CatalogError("catalog 顶层必须是对象")
    raw_rules = catalog.get("rules")
    if not isinstance(raw_rules, list):
        raise CatalogError("catalog.rules 必须是数组")
    if not isinstance(ledger, dict) or not isinstance(ledger.get("clauses"), dict):
        raise CatalogError("rfc-ledger.json 必须是 {clauses: {...}} 形态")

    rules: list[Rule] = []
    seen: set[str] = set()
    problems: list[str] = []

    for idx, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            problems.append(f"rules[{idx}] 不是对象")
            continue
        missing = [key for key in _REQUIRED_FIELDS if not raw.get(key)]
        if missing:
            problems.append(f"rules[{idx}] 缺字段: {','.join(missing)}")
            continue
        rule = Rule(**{key: str(raw[key]) for key in _REQUIRED_FIELDS})
        if rule.rule_id in seen:
            problems.append(f"{rule.rule_id}: rule_id 重复（编号一经分配不得复用，§7.2）")
            continue
        seen.add(rule.rule_id)

        # 三值封闭 / 四档封闭（§7.1 / §7.4）：catalog 是机读真相源，不得出现第四值
        if rule.klass not in CLASSES:
            problems.append(f"{rule.rule_id}: class 必须是 {CLASSES} 之一（当前 {rule.klass!r}）")
            continue
        if rule.severity not in SEVERITIES:
            problems.append(f"{rule.rule_id}: severity 必须是 {SEVERITIES} 之一（当前 {rule.severity!r}）")
            continue

        if rule.rule_id in SEMANTIC_RULES and rule.klass == "hard":
            problems.append(f"{rule.rule_id}: 语义层规则不得为 hard（§7.1 升级禁令）")
            rules.append(rule)
            continue

        exists, verbatim = resolve_verbatim(ledger, rule.ledger_key)
        if not exists:
            problems.append(f"{rule.rule_id}: ledger_key {rule.ledger_key!r} 不在 rfc-ledger.json 中")
            rules.append(rule)
            continue
        has_verbatim = verbatim is not None
        if rule.klass == "hard" and not has_verbatim:
            problems.append(
                f"{rule.rule_id}: class=hard 但 {rule.ledger_key} 没有逐字原句（D12：宁降级不补条款）"
            )
        if not has_verbatim and rule.klass == "hard":
            pass  # 上面已报
        elif not has_verbatim and rule.klass not in {"diff", "gray"}:
            problems.append(
                f"{rule.rule_id}: {rule.ledger_key} 无原句，class 只能是 diff/gray（当前 {rule.klass}）"
            )
        if not has_verbatim and rule.severity != "note":
            problems.append(
                f"{rule.rule_id}: {rule.ledger_key} 无原句，severity 只能是 note（当前 {rule.severity}）"
            )
        rules.append(rule)

    if problems:
        raise CatalogError("规则目录门禁未通过：\n  - " + "\n  - ".join(problems))
    return rules


def load_catalog() -> list[Rule]:
    """装载并校验规则目录。缺失或不合规一律抛 :class:`CatalogError`。"""
    catalog = _load_json(CATALOG_PATH, "catalog.json")
    ledger = _load_json(LEDGER_PATH, "data/rfc-ledger.json")
    return validate_catalog(catalog, ledger)


def rule_ids() -> tuple[str, ...]:
    return tuple(rule.rule_id for rule in load_catalog())
