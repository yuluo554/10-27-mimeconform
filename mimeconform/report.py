"""报告渲染（JSON + Markdown，单一数据源）。

**零判定**（plan/02 §七 / plan/03 §七）：本模块只做格式化，不做规则判定、不重算摘要、
不 import 任何业务判定模块。AST 守门 ``tests/test_engine_guards.py::test_report_is_pure`` 断言。

同一个台账对象同时渲染两种格式 —— "JSON/MD 同源"是结构性质，不是人工比对。
"""

from __future__ import annotations

from . import __version__
from . import constants as C
from .ledger import dumps

_DISCLAIMERS = (
    "缺陷账本不是解码器：本工具不承诺比别人解得更全，只承诺解出来的树 + 缺陷账本可复核。",
    "审计引擎不 import email：标准库的宽松行为正是被审计对象。",
    "未检索到 ≠ 首创：开源空白检索按软论据处理。",
    "节号不等于原句：台账里未留逐字原句的子项只能出 note。",
)


def _header_lines(input_name: str, input_bytes: int, input_sha256: str, exit_code: int) -> list[str]:
    return [
        f"工具版本: mimeconform {__version__}",
        f"输入: {input_name} ({input_bytes} bytes)",
        f"输入 sha256: {input_sha256}",
        f"退出码: {exit_code}",
    ]


def _tree_section(tree_info: dict[str, object]) -> list[str]:
    """结构事实小节的排版（**只搬运**：所有值都来自 ``tree_info``）。"""
    lines = ["## 结构事实", ""]
    lines.append(f"- 展示树语义: `{tree_info.get('mode')}`")
    lines.append(f"- 节点数: {tree_info.get('node_count')}")
    lines.append(f"- 候选树数量: {tree_info.get('tree_alternatives')}")
    divergence = tree_info.get("divergence")
    if isinstance(divergence, dict):
        lines.append(
            f"- 分歧位置: path `{divergence.get('path')}` @ offset {divergence.get('offset')}"
        )
        lines.append(f"- 分歧说明: {divergence.get('note')}")
    declaration = tree_info.get("declaration")
    if declaration:
        lines.append(f"- 声明: {declaration}")
    truncated = tree_info.get("truncated_paths")
    if isinstance(truncated, list) and truncated:
        lines.append(f"- 超深度停止下钻的路径: {', '.join(f'`{p}`' for p in truncated)}")
    lines.append("")
    return lines


def render_json(
    ledger: dict[str, object],
    *,
    input_name: str,
    input_bytes: int,
    input_sha256: str,
    exit_code: int,
    tree_info: dict[str, object] | None = None,
) -> str:
    """机读产物：与 MD 共用同一个 ``ledger``，没有任何额外判定。

    ``tree_info`` 是**引擎已经算好**的结构事实（候选树数量 / 分歧位置 / 截断路径），
    本函数只做搬运与排版 —— 不重算、不判定（AST 守门 ``test_report_is_pure``）。
    """
    payload: dict[str, object] = {
        "tool": {"name": "mimeconform", "version": __version__},
        "input": {
            "name": input_name,
            "bytes": input_bytes,
            "sha256": input_sha256,
        },
        "exit_code": exit_code,
        "summary": {
            "count": ledger["count"],
            "by_class": ledger["by_class"],
            "by_severity": ledger["by_severity"],
            "none_by_design": ledger["none_by_design"],
        },
        "fingerprint": ledger["fingerprint"],
        "tree_digest": ledger["tree_digest"],
        "defects": ledger["defects"],
        "disclaimers": list(_DISCLAIMERS),
    }
    if tree_info is not None:
        payload["tree"] = tree_info
    return dumps(payload)


def render_markdown(
    ledger: dict[str, object],
    *,
    input_name: str,
    input_bytes: int,
    input_sha256: str,
    exit_code: int,
    tree_info: dict[str, object] | None = None,
) -> str:
    """人读产物：同一 ``ledger``，只换排版。"""
    lines: list[str] = []
    lines.append("# mimeconform 结构缺陷账本")
    lines.append("")
    for line in _header_lines(input_name, input_bytes, input_sha256, exit_code):
        lines.append(f"- {line}")
    lines.append("")

    count = ledger["count"]
    by_class = ledger["by_class"]
    by_severity = ledger["by_severity"]
    assert isinstance(by_class, dict) and isinstance(by_severity, dict)
    class_text = " · ".join(f"{k} {by_class[k]}" for k in C.CLASSES)
    sev_text = " · ".join(f"{k} {by_severity[k]}" for k in C.SEVERITIES)
    lines.append(f"## 概要")
    lines.append("")
    lines.append(f"- 缺陷总数: {count}")
    lines.append(f"- 按 class: {class_text}")
    lines.append(f"- 按 severity: {sev_text}")
    lines.append(f"- 无条款支撑（{C.RFC_NONE_BY_DESIGN}）: {ledger['none_by_design']}")
    lines.append(f"- 缺陷集指纹: `{ledger['fingerprint']}`")
    lines.append(f"- 树指纹: `{ledger['tree_digest']}`")
    lines.append("")

    if tree_info is not None:
        lines.extend(_tree_section(tree_info))

    lines.append("## 缺陷明细")
    lines.append("")
    defects = ledger["defects"]
    assert isinstance(defects, list)
    if not defects:
        lines.append("无缺陷。")
        lines.append("")
    else:
        lines.append("| # | rule_id | class | severity | path | offset | kind | rfc | detail |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for idx, defect in enumerate(defects, start=1):
            assert isinstance(defect, dict)
            lines.append(
                "| {i} | {rule_id} | {class} | {severity} | {path} | {offset} | {offset_kind} | {rfc} | {detail} |".format(
                    i=idx, **defect
                )
            )
        lines.append("")

    lines.append("## 诚实口径")
    lines.append("")
    for text in _DISCLAIMERS:
        lines.append(f"- {text}")
    lines.append("")
    return "\n".join(lines)
