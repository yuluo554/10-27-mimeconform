"""版本与 Python 下限的单一来源。

* `pyproject.toml` 的 `version` 是唯一真源；
* `mimeconform.__version__` 必须与它**逐字相等**（两处必须一起改）；
* `requires-python` 的下限必须落成**可执行的断言**（不是只写在文档里）。
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import mimeconform

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def _pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def test_package_version_matches_pyproject() -> None:
    declared = _pyproject()["project"]["version"]
    assert mimeconform.__version__ == declared, (
        f"版本两处不一致：pyproject={declared!r} __init__={mimeconform.__version__!r}"
        "（定版时必须一起改）"
    )


def test_version_has_no_surprises() -> None:
    version = mimeconform.__version__
    assert re.match(r"^\d+\.\d+\.\d+((a|b|rc)\d+)?(\.dev\d+)?$", version), f"版本形态异常: {version!r}"


def test_python_floor_is_declared_and_enforced() -> None:
    """下限写进 `requires-python`，且**当前解释器真的满足**（本机 3.8 通道必须被判不合格）。"""
    declared = _pyproject()["project"]["requires-python"]
    match = re.match(r"^>=(\d+)\.(\d+)$", declared)
    assert match, f"requires-python 形态异常: {declared!r}"
    floor = tuple(int(part) for part in match.groups())
    assert floor >= (3, 11), f"本项目要求下限 >= 3.11（plan/00 D13），实际声明 {declared!r}"
    assert sys.version_info[:2] >= floor, (
        f"当前解释器 {sys.version_info[:2]} 低于下限 {floor} —— 用它跑出来的绿不算证据"
    )


def test_scripts_entry_point_matches_package() -> None:
    scripts = _pyproject()["project"]["scripts"]
    assert scripts.get("mimeconform") == "mimeconform.cli:main"


def test_no_runtime_dependencies() -> None:
    """零第三方运行时依赖是硬承诺（README 与 plan/02 §十）。"""
    assert _pyproject()["project"]["dependencies"] == []


def test_packages_declared_are_real() -> None:
    """`packages` 声明的每个目录都必须真的存在且有 `__init__.py`。"""
    packages = _pyproject()["tool"]["setuptools"]["packages"]
    for package in packages:
        directory = ROOT / package.replace(".", "/")
        assert directory.is_dir(), f"声明的包目录不存在: {package} → {directory}"
        assert (directory / "__init__.py").is_file(), f"包缺 __init__.py: {package}"


def test_package_data_covers_rule_catalog() -> None:
    """运行时只读 `rules/*.json`：package-data 必须覆盖它（安装态才找得到）。"""
    package_data = _pyproject()["tool"]["setuptools"]["package-data"]
    assert "mimeconform" in package_data
    assert any("rules" in pattern for pattern in package_data["mimeconform"]), (
        "package-data 未覆盖 rules/*.json —— 装好的包里找不到规则目录"
    )
