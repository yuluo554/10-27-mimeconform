"""用标准库 ``email`` 做对照取证（**仅测试与证据**，不进报告路径）。

存在的理由（`plan/01` §1.3）：标准库把 defect 挂到对象上但不报告、也不计数。
本模块把这些 defect **读出来**，用来证明"标准库记为可解析、本工具记为缺陷"。

用法（只在测试/证据脚本里）::

    from mimeconform.devtools.stdlib_compare import collect_stdlib_defects
    collect_stdlib_defects(raw_bytes)  # -> {"defects": [...], "count": N}

**审阅注意**：本文件是 `import email` 的唯一合法出现点。
"""

from __future__ import annotations

import email
from email import policy


def collect_stdlib_defects(raw: bytes) -> dict[str, object]:
    """把标准库挂在对象树上的 defect 全部收集出来（含子部件）。"""
    message = email.message_from_bytes(raw, policy=policy.compat32)
    found: list[dict[str, object]] = []

    def walk(part: object, path: str) -> None:
        for defect in getattr(part, "defects", ()) or ():
            found.append(
                {
                    "path": path,
                    "type": type(defect).__name__,
                    "args": [str(arg) for arg in getattr(defect, "args", ())],
                }
            )
        if getattr(part, "is_multipart", lambda: False)():
            for idx, child in enumerate(part.get_payload(), start=1):  # type: ignore[attr-defined]
                walk(child, f"{path}.{idx}")

    walk(message, "0")
    return {"defects": found, "count": len(found)}
