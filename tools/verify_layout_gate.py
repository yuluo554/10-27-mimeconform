#!/usr/bin/env python3
"""布局门的变异验证：判据有几条，变异就覆盖几条。

**为什么是脚本而不是一句"我验过了"**：假门族里最常见的形态是"门跑了且绿，但某条判据
从未被证伪过"。本脚本**逐组**改坏一个真实文件、跑门、断言它变红、再逐字节还原。

形态纪律（skill「变异脚本三连」）：
* 替换前 ``assert marker 存在``；
* 替换后 ``assert 文件已变``（防 marker 撞了 docstring 之类的静默 no-op）；
* 还原后 ``assert 字节一致``；
* 全包 ``try/finally``。

用法::

    py -3.12 tools/verify_layout_gate.py          # 跑全组
    py -3.12 tools/verify_layout_gate.py -k M02   # 只跑某组

退出码：0 全部符合预期 / 1 有组未如期变红 / 2 用法错误。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "tools" / "check_sprint_layout.py"


# ── 基础设施 ──────────────────────────────────────────────────────────────


def _load_gate_module():
    name = "_verify_layout_gate_target"
    spec = importlib.util.spec_from_file_location(name, GATE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run_gate_json() -> dict:
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(GATE), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    if not result.stdout.strip():
        raise RuntimeError(f"门没有输出：rc={result.returncode} stderr={result.stderr}")
    return json.loads(result.stdout)


def failed_ids(payload: dict) -> set[str]:
    return {item["id"] for item in payload["checks"] if not item["ok"]}


@dataclass
class Mutation:
    name: str
    target: str          # 仓库内相对路径
    marker: str          # 必须存在的原文
    replacement: str     # 替换成
    expect: str          # 期望变红的判据 id
    expect_green: bool = False   # True = 期望"门仍绿"（阴性对照）
    kind: str = "replace"        # replace | delete
    #: 附加编辑：``(target, marker, replacement)``，在主编辑之后施加、还原时一并复原。
    #: 用于"同时改门自己的配置"这类变异（如把 HANDOFF_EXEMPT_LAST 置 true）。
    extras: tuple[tuple[str, str, str], ...] = ()

    def _edit(self, root: Path, target: str, marker: str, replacement: str) -> tuple[Path, bytes]:
        path = root / target
        original = path.read_bytes()
        text = original.decode("utf-8")
        assert marker in text, f"{self.name}: marker 不在 {target} 中（变异会静默 no-op）"
        mutated_text = text.replace(marker, replacement, 1)
        assert mutated_text != text, f"{self.name}: 替换后文本未变"
        path.write_bytes(mutated_text.encode("utf-8"))
        assert path.read_bytes() != original, f"{self.name}: 写入后字节未变"
        return path, original

    def apply(self, root: Path) -> list[tuple[Path, bytes]]:
        """执行变异（含附加编辑）。返回 ``[(路径, 原始字节)]`` 供还原。

        **删除形态**走"改名"而不是"删内容"——门判的是文件存在性。
        """
        target_path = root / self.target
        text = target_path.read_bytes().decode("utf-8")
        assert self.marker in text, f"{self.name}: marker 不在 {self.target} 中（变异会静默 no-op）"

        if self.kind == "delete":
            shadow = target_path.with_name(target_path.name + ".mutant")
            assert not shadow.exists(), f"{self.name}: 残留 {shadow.name}，上一轮未清理"
            original_bytes = target_path.read_bytes()
            target_path.rename(shadow)
            assert not target_path.exists(), f"{self.name}: 改名后原路径仍存在"
            restores = [(target_path, original_bytes)]
        else:
            restores = [self._edit(root, self.target, self.marker, self.replacement)]

        for extra_target, extra_marker, extra_replacement in self.extras:
            restores.append(self._edit(root, extra_target, extra_marker, extra_replacement))
        return restores


# ── 变异组 ────────────────────────────────────────────────────────────────

MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        "M01 删 AGENTS.md",
        "AGENTS.md",
        "# AGENTS.md",
        "",
        "LAYOUT.FILES",
        kind="delete",
    ),
    Mutation(
        "M02 删 plan/02（计划套件缺一份）",
        "plan/02-架构与技术选型.md",
        "# 02 · 架构与技术选型",
        "",
        "LAYOUT.FILES",
        kind="delete",
    ),
    Mutation(
        "M03 删掉 plan/00 顶部装订行",
        "plan/00-README总览.md",
        "> 方法论：`ai-tool-project-sprint`（装订 2026-10-27）｜布局门：`py -3.12 tools/check_sprint_layout.py`｜脱敏门：`py -3.12 tools/check_desensitized.py`｜续接对话第一件事 = 跑布局门",
        "> 方法论装订行已被移除（变异）",
        "LAYOUT.BINDING_HEAD",
    ),
    Mutation(
        "M04 删 plan/03 的 CLI 小节（整行标题关键词）",
        "plan/03-模块详设.md",
        "## 八、`cli.py` — CLI 契约总表",
        "## 八、`cli.py` — 命令接口契约总表",
        "LAYOUT.SECTIONS",
    ),
    Mutation(
        "M05 单副本翻状态（M0 ✅ → ⬜，只改 plan/05）",
        "plan/05-里程碑与验收.md",
        "| **M0 计划先行 + 骨架** | `plan/00`–`06`、`data/README.md`、`AGENTS.md`、`tools/` 两道门、可运行骨架（`--version` / `selftest` / 退出码 0·1）、`tests/` 守门、`.gitignore`/`.gitattributes`/`LICENSE` | ✅ 完成（2026-10-27） |",
        "| **M0 计划先行 + 骨架** | 同上 | ⬜ 未开始 |",
        "LAYOUT.STATUS",
    ),
    Mutation(
        "M06 台账行挂未完成标记（已 ✅ 的 M0）",
        "plan/00-README总览.md",
        "| 计划套件齐全（00–06 + data 台账） | `plan/00`–`06` + `data/README.md` | ✅ | 布局门 `LAYOUT.FILES` / `LAYOUT.SECTIONS` | ✅ 完成（M0） |",
        "| 计划套件齐全（00–06 + data 台账） | `plan/00`–`06` + `data/README.md` | ✅ | 布局门 `LAYOUT.FILES` / `LAYOUT.SECTIONS` | ⬜ 待 M0 复核 |",
        "LAYOUT.LEDGER",
    ),
    Mutation(
        "M07 缺口格里提已 ✅ 的 M0",
        "plan/06-交付对标与决策.md",
        "| G1 | 规则判定实现 |",
        "| G1 | 规则判定实现（M0） |",
        "LAYOUT.GAPS",
    ),
    Mutation(
        "M08 文档点名一个不存在的 tools 脚本",
        "AGENTS.md",
        "## 环境事实与禁忌（实测日期 2026-10-27）",
        "## 环境事实与禁忌（实测日期 2026-10-27）\n\n另见 `tools/does_not_exist.py`。",
        "LAYOUT.DOC_TOOLS",
    ),
    Mutation(
        "M09 删 plan/00 的必需小节标题关键词（决策记录）",
        "plan/00-README总览.md",
        "## 二、决策记录表",
        "## 二、决议表",
        "LAYOUT.SECTIONS",
    ),
    Mutation(
        "M10 单副本翻状态（README 的 M0 ✅ → ⬜）",
        "README.md",
        "| M0 | 计划套件 + 方法论装订 + 可运行骨架 | ✅ 完成 |",
        "| M0 | 计划套件 + 方法论装订 + 可运行骨架 | ⬜ 未开始 |",
        "LAYOUT.STATUS",
    ),
    Mutation(
        "M11 发布里程碑 M6 翻 ✅ 但删留档（构造'缺档 + 已 ✅'）",
        "plan/00-README总览.md",
        "| **M6 发布** | 干净环境验证 + 发布 | ⬜ 未开始 |",
        "| **M6 发布** | 干净环境验证 + 发布 | ✅ 完成 |",
        "LAYOUT.HANDOFFS",
    ),
    Mutation(
        "M12 门自己的用法错误必须 rc=2（不用文件变异，见 verify_one）",
        "AGENTS.md",
        "# AGENTS.md",
        "# AGENTS.md",
        "USAGE",
        expect_green=True,
    ),
    Mutation(
        "M13 豁免分支的正向证明：置 HANDOFF_EXEMPT_LAST=true 后末棒无交接单也放行",
        "plan/00-README总览.md",
        "| **M6 发布** | 干净环境验证 + 发布 | ⬜ 未开始 |",
        "| **M6 发布** | 干净环境验证 + 发布 | ✅ 完成 |",
        "LAYOUT.HANDOFFS",
        expect_green=True,
        extras=((
            "tools/check_sprint_layout.py",
            "HANDOFF_EXEMPT_LAST = False",
            "HANDOFF_EXEMPT_LAST = True",
        ),),
    ),
)

#: 阴性对照（期望门**仍绿**）：证明"该由人补的那一块，门确实管不到"。
NEGATIVE_CONTROLS: tuple[Mutation, ...] = (
    Mutation(
        "N01 散文状态行改回过期措辞（门仍绿：它不参与判定）",
        "plan/00-README总览.md",
        "> **版本**：v1（2026-10-27，出题阶段 4 = 骨架 + 首提交）",
        "> **版本**：v1（2026-10-27，出题阶段 4 = 骨架 + 首提交）｜当前状态：M0 未开工（阴性对照）",
        "LAYOUT.STATUS",
        expect_green=True,
    ),
    Mutation(
        "N02 缺口格里写带文件名的完成说明（剥离后必须放行）",
        "plan/06-交付对标与决策.md",
        "| G2 | golden 语料 | ✅ 关闭（51 case，`--check` 0 diff） | `--check` 0 diff |",
        "| G2 | golden 语料（说明见 `plan/RELEASE-M6.md`） | ✅ 关闭（51 case，`--check` 0 diff） | `--check` 0 diff |",
        "LAYOUT.GAPS",
        expect_green=True,
    ),
)


# ── 主流程 ────────────────────────────────────────────────────────────────


def verify_one(mutation: Mutation, root: Path) -> tuple[bool, str]:
    """返回 ``(符合预期, 说明)``。"""
    if mutation.name.startswith("M12"):
        # 用法错误：未知参数必须 rc=2（这是门的契约，不是文档变异）
        result = subprocess.run(
            [sys.executable, str(GATE), "--bogus-flag"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=root,
        )
        ok = result.returncode == 2
        return ok, f"未知参数 rc={result.returncode}（期望 2）"

    restores = mutation.apply(root)
    try:
        payload = run_gate_json()
        failed = failed_ids(payload)
        if mutation.expect_green:
            ok = mutation.expect not in failed
            return ok, f"{mutation.expect} {'仍绿（符合预期）' if ok else '变红了（阴性对照失败）'}"
        ok = mutation.expect in failed
        return ok, (
            f"{mutation.expect} 如期变红"
            if ok
            else f"{mutation.expect} 未变红（实际 FAIL: {sorted(failed) or '无'}）"
        )
    finally:
        for path, original in restores:
            if mutation.kind == "delete" and path == root / mutation.target:
                shadow = path.with_name(path.name + ".mutant")
                if shadow.exists():
                    shadow.replace(path)
            else:
                path.write_bytes(original)
            assert path.read_bytes() == original, f"{mutation.name}: 还原后字节不一致！"
            assert not path.with_name(path.name + ".mutant").exists(), (
                f"{mutation.name}: 还原后残留 .mutant"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="布局门变异验证")
    parser.add_argument("-k", default=None, help="只跑名字含该子串的组")
    parser.add_argument("--root", default=str(ROOT), help="仓库根（默认本项目）")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    gate_module = _load_gate_module()
    baseline, _scanned = gate_module.run_gate()
    baseline_failed = [cid for cid, ok, _detail in baseline if not ok]
    if baseline_failed:
        sys.stdout.write(f"基线不是全绿（{baseline_failed}）——先修布局再跑变异\n")
        return 1

    groups = [*MUTATIONS, *NEGATIVE_CONTROLS]
    if args.k:
        groups = [m for m in groups if args.k in m.name]
    if not groups:
        sys.stdout.write(f"没有匹配 {args.k!r} 的变异组\n")
        return 2

    unexpected: list[str] = []
    for mutation in groups:
        ok, note = verify_one(mutation, root)
        sys.stdout.write(f"{'OK  ' if ok else 'BAD '} {mutation.name} → {note}\n")
        if not ok:
            unexpected.append(mutation.name)

    sys.stdout.write("=" * 56 + "\n")
    sys.stdout.write(
        f"{len(groups)} 组：{len(groups) - len(unexpected)} 符合预期 / {len(unexpected)} 不符\n"
    )
    if unexpected:
        sys.stdout.write("不符: " + "; ".join(unexpected) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
