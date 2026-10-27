"""源码包与安装面：sdist 自足、`MANIFEST.in` 白名单反查实物。

**为什么现在测**：这两条是 M6 才"真正"用到的，但判据落在这里成本极低，
且 `MANIFEST.in` 写成"有这一行"（而不是"覆盖了仓库里的真实文件"）是最常见的假门形态。

M0 的可验部分：
* `MANIFEST.in` 声明的每个条目**都能在仓库里找到匹配的真实文件**（反查实物）；
* `mimeconform/rules/*.json` 被 package-data 覆盖（M3 落地后文件必须在白名单内）。
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.in"


def _manifest_patterns() -> list[tuple[str, str]]:
    """解析 `MANIFEST.in` → ``[(kind, pattern)]``。"""
    entries: list[tuple[str, str]] = []
    for raw in MANIFEST.read_text(encoding="utf-8").split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        kind, _, rest = line.partition(" ")
        entries.append((kind, rest.strip()))
    return entries


def test_manifest_exists_and_parses() -> None:
    assert MANIFEST.is_file(), "缺 MANIFEST.in —— 源码包里不会有规则目录与台账"
    entries = _manifest_patterns()
    assert entries, "MANIFEST.in 解析出 0 条规则（探针失效）"


def test_manifest_include_entries_match_real_files() -> None:
    """`include <path>` 必须指向**真实存在**的文件（不是"写了就算"）。"""
    missing = [
        pattern
        for kind, pattern in _manifest_patterns()
        if kind == "include" and not (ROOT / pattern).is_file()
    ]
    assert not missing, f"MANIFEST.in 的 include 指向不存在的文件: {missing}"


#: 已声明但**尚未到**其落地里程碑的 MANIFEST 条目：``{目录: 里程碑}``。
#: 该里程碑翻 ✅ 后必须删除登记，否则 `test_manifest_pending_entries_are_not_stale` 会红。
#: 当前为空 —— `data/*.json`（rfc-ledger.json）已随 M0 一并落地。
PENDING_MANIFEST: dict[str, int] = {}


def test_manifest_recursive_entries_match_at_least_one_file() -> None:
    """`recursive-include <dir> <glob>...` 必须真的匹配到文件（空匹配 = 白名单失效）。

    `MANIFEST.in` 允许**一条规则带多个 glob**（`recursive-include mimeconform *.py *.json`），
    首版按单 glob 解析 → 把 `*.py *.json` 当成一个模式 → 0 匹配 → 假红。
    """
    empties: list[str] = []
    for kind, pattern in _manifest_patterns():
        if kind != "recursive-include":
            continue
        parts = pattern.split()
        if not parts:
            continue
        directory, globs = parts[0], parts[1:] or ["*"]
        base = ROOT / directory
        if not base.is_dir():
            empties.append(f"{directory}（目录不存在）")
            continue
        matched = [
            path
            for path in base.rglob("*")
            if path.is_file() and any(fnmatch.fnmatch(path.name, glob) for glob in globs)
        ]
        if not matched and directory not in PENDING_MANIFEST:
            empties.append(f"{directory} {' '.join(globs)}（0 个匹配）")
    assert not empties, f"MANIFEST.in 的 recursive-include 有项匹配为空: {empties}"


def test_manifest_pending_entries_are_not_stale() -> None:
    """登记项在里程碑落地后必须清理（否则"待落地"会变成永久豁免）。"""
    if not PENDING_MANIFEST:
        return
    status_text = (ROOT / "plan" / "05-里程碑与验收.md").read_text(encoding="utf-8")
    for directory, milestone in PENDING_MANIFEST.items():
        pattern = re.compile(rf"^\|\s*\**M{milestone}\b.*$", re.MULTILINE)
        line = pattern.search(status_text)
        if line is None:
            continue
        assert "⬜" in line.group(0) or "未开始" in line.group(0), (
            f"PENDING_MANIFEST 里 data 目录登记为 M{milestone}，而 M{milestone} 已 ✅ —— 必须清理登记"
            f"（或该目录已有实物）"
        )


def test_rules_json_would_be_packaged() -> None:
    """`rules/*.json` 必须同时被 `MANIFEST.in`（sdist）与 package-data（wheel）覆盖。"""
    import tomllib

    patterns = _manifest_patterns()
    covered = any(
        kind == "recursive-include" and pattern.startswith("mimeconform") and "json" in pattern
        for kind, pattern in patterns
    )
    assert covered, "MANIFEST.in 未覆盖 mimeconform 的 json（sdist 里会缺规则目录）"

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]["mimeconform"]
    assert any("rules" in pattern for pattern in package_data), "package-data 未覆盖 rules/*.json"


def test_license_and_readme_are_shipped() -> None:
    """读 Release 页的人会期待包里带这两个（题面交付面要求）。"""
    patterns = _manifest_patterns()
    included = {pattern for kind, pattern in patterns if kind == "include"}
    assert "LICENSE" in included
    assert "README.md" in included


def test_no_host_paths_in_manifest() -> None:
    """`MANIFEST.in` 不得含本机绝对路径（发布件会把它带出去）。"""
    text = MANIFEST.read_text(encoding="utf-8")
    assert not re.search(r"\b[A-Za-z]:[\\/]", text), "MANIFEST.in 里有盘符绝对路径"
