"""头编码审计：RFC 2047（encoded-word）与 RFC 2231（参数续行）（模块 M2 / 里程碑 M3）。

**判定顺序写死（data/README §7.5 第 1–2 条）**：

1. 头块切分 → 头行 > 998（MC-H07）**先于** encoded-word 检查；
2. 先判 "encoded-word 跨行"（MC-H12，diff）；命中则**不再**报 MC-H03（内空白），
   被压掉的那条进 ``related`` —— 同一字节不得双记。

**编码长度按字节计**（plan/01 M2 纪律）：encoded-word 本身必须是 ASCII，
故拿编码后的字节数比 75 / 76 是保守且可复算的口径，不去猜 charset。

骨架期 :func:`parse_headers` 抛 :class:`~mimeconform.errors.EngineNotReady`。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ._pending import _not_ready
from .model import Defect, Header


@dataclass(frozen=True, slots=True)
class HeaderBlock:
    headers: tuple[Header, ...] = field(default=())
    defects: tuple[Defect, ...] = field(default=())
    end_offset: int = 0


def parse_headers(raw_header_block: bytes, base_offset: int = 0) -> HeaderBlock:
    """解析原始头块字节（未解码、未展开），产出头级缺陷。"""
    raise _not_ready("parse_headers")


def decode_filename(params: list[dict[str, object]], raw_value: str) -> str:
    """按 §7.5 第 3–4 条取 ``filename``：先 RFC 2231（含续行）→ 再 RFC 2047。

    顺序**不可交换**（plan/00 D10）：两层叠加时顺序不同会得出不同文件名，
    golden 就无法逐字节验收。
    """
    raise _not_ready("decode_filename")
