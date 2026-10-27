"""`python -m mimeconform` 入口（与 console script 等价的第二条通路）。

两条通路的 ``sys.path`` 来源不同（CWD vs 安装记录），CI 必须各冒烟一次
（见 plan/03 §八 与 skill 阶段 6「安装面第四面」）。
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":  # pragma: no cover - 进程入口
    sys.exit(main())
