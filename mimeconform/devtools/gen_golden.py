"""golden 语料生成器（里程碑 M1 落地）。

**设计要点（`plan/04` §三）**：

* 每个 case 是**纯函数**，返回 ``(files, expect)``；生成器只做拼装，**不解析、不判定**。
  期望缺陷是手写常量 + 构造时的结构性断言，不是"跑一遍工具看输出"（避免真值 = 被测实现）。
* 写盘一律 ``write_bytes()``（不用文本模式：Windows 会把 ``\\n`` 翻成 ``\\r\\n``，
  而 golden 的字节本身就是被测对象）。
* ``_self_check()`` 必须挂在 :func:`build` 末尾（不是 ``__main__``）——``--check`` 走
  ``build()``，写错位置等于自检在门下从没跑过。
* ``--check`` 在**系统临时目录**里重建再逐字节比对，不在仓库内留产物。

骨架期 :func:`build` 抛 :class:`~mimeconform.errors.EngineNotReady`。
"""

from __future__ import annotations

import argparse
import sys

from ..errors import EngineNotReady

_NOT_READY = (
    "golden 语料生成器尚未实现（里程碑 M1）：语料矩阵见 plan/04 §二，"
    "合成纪律见 data/README.md §六。骨架期不产出任何语料，也不假装通过 --check。"
)


def build(out_dir: object) -> None:
    """把全部 case 写到 ``out_dir``（每个 case 一个子目录）。"""
    raise EngineNotReady(_NOT_READY)


def check(expected_dir: object) -> int:
    """在临时目录重建并与 ``expected_dir`` 逐字节比对；返回进程退出码。"""
    raise EngineNotReady(_NOT_READY)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m mimeconform.devtools.gen_golden",
        description="golden 语料生成器（里程碑 M1）",
    )
    parser.add_argument("--out", metavar="DIR", default="data/golden", help="输出目录")
    parser.add_argument("--check", action="store_true", help="重生成并逐字节比对，不写仓库")
    args = parser.parse_args(argv)

    try:
        if args.check:
            return check(args.out)
        build(args.out)
    except EngineNotReady as exc:
        sys.stderr.write(f"gen_golden: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
