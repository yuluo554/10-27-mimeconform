"""异常与退出码分类。

**为什么单独一个模块**：``argparse`` 对未知子命令 / 缺必填参数抛 ``SystemExit(2)``，
而本项目的 ``2`` 语义是"审计完成、存在 minor"（data/README §7.9）——两者必须显式区分，
否则"用法错误"会被读成"有轻微缺陷"。分类集中在这里，CLI 只做一次映射。
"""

from __future__ import annotations


class MimeconformError(Exception):
    """本项目的基类异常。"""


class UsageError(MimeconformError):
    """用法错误：参数非法 / 文件不存在 / 不可读 / 输入不是预期形态。→ exit 1"""


class InputError(MimeconformError):
    """输入不可读或读取过程中失败。→ exit 1"""


class EngineNotReady(MimeconformError):
    """引擎阶段尚未实现（骨架期专用）。

    骨架期**必须**显式抛它，由 CLI 映射为 exit 1 + 明确文案 —— 绝不静默返回 0
    （plan/00 D16：读不了 / 没实现都不得被读成"干净"）。
    """
