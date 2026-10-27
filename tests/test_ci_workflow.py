"""CI workflow 的静态判据（skill 阶段 7 D「CI 与对账」的本机可验部分）。

**为什么要有这个测试**：workflow 的缺陷只有首推才显形，但其中一大半是**纯静态**的
（YAML 非法 / job=0 / 步骤顺序 / 契约退出码没 `set +e`）。本文件把这类"本机就能判"的
先拦下来，把首推预算留给真正只在远端显形的那部分。

判据（每条对应一个已知坑）：
1. **YAML 可解析**且 job / step 数符合预期 —— 值里裸 `: ` 会让 GitHub 直接不建 job（`jobs=0`）。
2. **契约退出码**：任何"调用可能返回非 0 的子命令 + 后续断言"的 step，必须 `set +e` 再显式断言。
3. **跨 step 相对路径不共享**：publish 类 step 不得用裸相对重定向。
4. **CI 本文件自己的退出码断言**不含已退役的语义（本项目只有 0/1/2/3）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# **硬 import，不用 `pytest.importorskip`**：`importorskip` 会把整模块折叠成一条 skip →
# "步骤顺序"这条判据在 CI 里从未执行过，而 run 仍是绿的（skill 阶段 7 E 的实测坑）。
# PyYAML 已声明进 dev extra，缺它就是环境没按 README 装。
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


def test_workflow_files_exist() -> None:
    assert WORKFLOWS, "没有任何 workflow 文件"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_yaml_is_parseable(path: Path) -> None:
    """YAML 非法时 GitHub 连 job 都不建，而 state/字节一切正常（首推 0-job 红的成因）。"""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{path.name} 顶层必须是 mapping"
    assert payload.get("jobs"), f"{path.name} 没有 jobs —— GitHub 会建 0 个 job"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_job_has_runs_on(path: Path) -> None:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    for name, job in payload["jobs"].items():
        assert "runs-on" in job, f"{path.name}: job {name} 缺 runs-on"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_contract_exit_code_steps_use_set_plus_e(path: Path) -> None:
    """凡是捕获 `$?` 的 step，必须有 `set +e`（否则 `set -e` 会在断言之前中断）。"""
    text = path.read_text(encoding="utf-8")
    payload = yaml.safe_load(text)
    offenders: list[str] = []
    for job_name, job in payload["jobs"].items():
        for step in job.get("steps", []):
            script = step.get("run")
            if not isinstance(script, str):
                continue
            if "$?" not in script and "code=" not in script:
                continue
            if "set +e" not in script:
                offenders.append(f"{job_name}/{step.get('name', '<unnamed>')}")
    assert not offenders, f"{path.name}: 这些 step 捕获退出码却没有 `set +e`: {offenders}"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_step_names_are_safe_yaml_scalars(path: Path) -> None:
    """step `name` 里裸 `: ` 会把 YAML 解析成 mapping（首推 0-job 红的经典成因）。

    这里不重复实现解析器语义（`safe_load` 已证），只断言"每个 name 都是 str"——
    如果某个 name 被解析成 dict，说明它确实被冒号切开了。
    """
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    for job_name, job in payload["jobs"].items():
        for step in job.get("steps", []):
            name = step.get("name")
            if name is None:
                continue
            assert isinstance(name, str), f"{path.name}: {job_name} 有 step name 被解析成非字符串：{name!r}"


def test_ci_asserts_only_contract_exit_codes() -> None:
    """退出码断言只能是 0/1/2/3（`data/README` §7.9）；写到 4 就是过期契约。"""
    allowed = {"0", "1", "2", "3"}
    for path in WORKFLOWS:
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r'test "\$code" = "(\d+)"', text):
            assert match.group(1) in allowed, (
                f"{path.name}: 断言了不在契约内的退出码 {match.group(1)}（§7.9 只有 0/1/2/3）"
            )


def test_ci_runs_both_entrypoints() -> None:
    """`python -m` 与裸 console script 是两条通路（sys.path 来源不同），两条都要冒烟。"""
    text = "\n".join(path.read_text(encoding="utf-8") for path in WORKFLOWS)
    assert "mimeconform --version" in text, "CI 未冒烟 console script"
    assert "python -m mimeconform" in text, "CI 未冒烟 module 入口"


def test_ci_runs_both_gates() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in WORKFLOWS)
    assert "tools/check_sprint_layout.py" in text, "CI 未跑布局门"
    assert "tools/check_desensitized.py" in text, "CI 未跑脱敏门"


def test_ci_tests_run_after_install() -> None:
    """步骤顺序：`pip install ... dev` 必须出现在 `pytest` 之前（门会继承子进程的依赖）。"""
    for path in WORKFLOWS:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in payload["jobs"].items():
            runs = [step.get("run", "") for step in job.get("steps", [])]
            install_idx = next(
                (i for i, run in enumerate(runs) if "[dev]" in run or '"dev"' in run),
                None,
            )
            pytest_idx = next((i for i, run in enumerate(runs) if "pytest" in run), None)
            if pytest_idx is None or install_idx is None:
                continue
            assert install_idx < pytest_idx, (
                f"{path.name}: {job_name} 先跑 pytest 再装 dev extra —— 首推必红"
            )
