"""`catalog.json` 与引擎代码的**双源一致性**（`plan/03` §九；`HANDOFF-M3` §二.1）。

三条判据：

1. **`MC-B0x` 的五字段与 `scan._RULE_META` 逐值一致** —— 同一个 rule_id 不许在代码与 catalog
   里各说一套（`HANDOFF-M3` §二.1 点名要求加这条断言）；
2. **`MC-H0x/1x` 的五字段与 `headers._RULE_META` 逐值一致**（M3 新落的一簇，同口径）；
3. **`MC-T*` 的五字段与 `transfer._RULE_META` 逐值一致**（M4 新落的一簇，同口径）；
4. **`detector` 必须能在它声明的 `module` 里解析到** —— 否则"这条规则由谁发出"只是一句注释。

另有一条**反向覆盖**：三个 `_RULE_META` 里的每个 rule_id 都必须在 catalog 里有行。
只正向比会漏掉"代码里有、catalog 里没有"的规则 —— 那种规则的 `class` 完全不受门禁约束。
"""

from __future__ import annotations

import importlib

import pytest

from mimeconform import attribution, container, headers, scan, transfer
from mimeconform.rules import load_catalog

CATALOG = {rule.rule_id: rule for rule in load_catalog()}

#: `_RULE_META` 的形态是 `(class, severity, rfc)`，catalog 的字段名是 `klass`。
_META_MODULES = {
    "scan": scan,
    "headers": headers,
    "transfer": transfer,
    "attribution": attribution,
    "container": container,
}


def _meta_pairs(module_name: str) -> list[tuple[str, tuple[str, str, str]]]:
    module = _META_MODULES[module_name]
    meta = getattr(module, "_RULE_META")
    return sorted(meta.items())


def test_catalog_is_not_empty() -> None:
    """非空跑自证：下面的逐值比对若在空集上跑是空转。"""
    assert len(CATALOG) >= 46, f"catalog 只有 {len(CATALOG)} 条规则（M5 后应 ≥ B10 + H12 + T11 + A8 + C5）"


@pytest.mark.parametrize("module_name", sorted(_META_MODULES))
def test_every_engine_rule_is_in_the_catalog(module_name: str) -> None:
    """反向覆盖：引擎里定义的每个 rule_id 都必须在 catalog 里有行。"""
    missing = [rule_id for rule_id, _meta in _meta_pairs(module_name) if rule_id not in CATALOG]
    assert not missing, f"{module_name}._RULE_META 里的规则没有进 catalog: {missing}"


@pytest.mark.parametrize("module_name", sorted(_META_MODULES))
def test_meta_matches_catalog_verbatim(module_name: str) -> None:
    """`(class, severity, rfc)` 三个字段逐值一致（不许"各说一套"）。"""
    problems: list[str] = []
    for rule_id, (klass, severity, rfc) in _meta_pairs(module_name):
        rule = CATALOG.get(rule_id)
        if rule is None:
            continue  # 上一条测试已经报过
        if rule.klass != klass:
            problems.append(f"{rule_id}: class 代码={klass} catalog={rule.klass}")
        if rule.severity != severity:
            problems.append(f"{rule_id}: severity 代码={severity} catalog={rule.severity}")
        if rule.rfc != rfc:
            problems.append(f"{rule_id}: rfc 代码={rfc!r} catalog={rule.rfc!r}")
    assert not problems, "代码与 catalog 的规则形态不一致：\n  " + "\n  ".join(problems)


def test_every_catalog_rule_declares_a_known_module() -> None:
    """`module` 必须是真实存在的引擎模块（拼错的模块名会让 detector 断言变成空转）。"""
    unknown = sorted({rule.module for rule in CATALOG.values()} - set(_META_MODULES))
    assert not unknown, f"catalog 声明了未知 module: {unknown}"


def test_detector_resolves_in_its_module() -> None:
    """`detector` 写成 ``module.attr`` / ``module.Cls.attr``，必须真的解析得到。"""
    problems: list[str] = []
    for rule in CATALOG.values():
        head, _, rest = rule.detector.partition(".")
        if head != rule.module:
            problems.append(f"{rule.rule_id}: detector {rule.detector!r} 的模块前缀不是 {rule.module!r}")
            continue
        target: object = importlib.import_module(f"mimeconform.{rule.module}")
        for part in rest.split("."):
            if not hasattr(target, part):
                problems.append(f"{rule.rule_id}: mimeconform.{rule.module} 里找不到 {part!r}")
                target = None
                break
            target = getattr(target, part)
        if target is not None and rest and not callable(target):
            problems.append(f"{rule.rule_id}: {rule.detector!r} 不是可调用对象")
    assert not problems, "detector 无法解析：\n  " + "\n  ".join(problems)


def test_class_distribution_is_what_the_plan_says() -> None:
    """`hard` 的分布必须是**显式决定**，不能漂移。

    * `plan/03` §二 的 H 簇表点名 5 条 `hard`（H01/H02/H03/H06/H07），其余 7 条降级；
    * `plan/03` §一 的 B 簇表点名 3 条 `hard`（B01/B02/B06）；
    * `plan/03` §三 的 T 簇表点名 4 条 `hard`（T04 因 R9 子项全录、T05/T06/T07 因 R8 全录），其余 7 条降级。

    这是"原句门禁真的产生了后果"的证据：若哪天有人把 T02 提成 `hard`，
    上面的门禁会先红；若有人把 T05 降成 `diff`，这条会红（降级必须是显式决定）。
    """
    hard_h = sorted(rule_id for rule_id, rule in CATALOG.items() if rule.rule_id.startswith("MC-H") and rule.klass == "hard")
    assert hard_h == ["MC-H01", "MC-H02", "MC-H03", "MC-H06", "MC-H07"]
    hard_b = sorted(rule_id for rule_id, rule in CATALOG.items() if rule.rule_id.startswith("MC-B") and rule.klass == "hard")
    assert hard_b == ["MC-B01", "MC-B02", "MC-B06"]
    hard_t = sorted(rule_id for rule_id, rule in CATALOG.items() if rule.rule_id.startswith("MC-T") and rule.klass == "hard")
    assert hard_t == ["MC-T04", "MC-T05", "MC-T06", "MC-T07"]
    # A / C 两簇是语义层（`Content-Disposition` / `multipart/related` / mbox / Maildir 都不在
    # 五部 RFC 内，D11）→ `hard` 集合**必须为空**。这是"语义层真的拿不到 hard"的显式证据：
    # 若哪天有人把 A/C 提成 hard，这里会红（原句门禁也会先红）。
    hard_a = sorted(rule_id for rule_id, rule in CATALOG.items() if rule.rule_id.startswith("MC-A") and rule.klass == "hard")
    assert hard_a == []
    hard_c = sorted(rule_id for rule_id, rule in CATALOG.items() if rule.rule_id.startswith("MC-C") and rule.klass == "hard")
    assert hard_c == []
