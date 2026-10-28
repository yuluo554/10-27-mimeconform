"""容器层审计：mbox / Maildir（可选模块 M5 / 里程碑 M5）。

**变体纪律（`data/README` §7.7，`plan/00` D3）**：``>From`` 转义是 **mboxo 约定，不是 RFC**；
mboxrd / mboxcl 的转义与长度前缀规则**互不相同**。因此：

* 全部规则只出 ``diff``；
* **所有变体的切分表都写入报告的 ``split_variants``**，``auto`` 只决定"主表"是哪一份；
* 报告必须写明"按 mboxo 读"还是"按 mboxrd 读"，不得只判一种"正确"。

**判定口径（M5 落地，与 `data/golden/c-*/expect.json` 对齐）**：

* ``MC-C01`` 分隔行无法解析（`From <地址> <日期>` 缺日期字段）→ 落点为该消息 ``msg#N`` 的
  ``offset=0``（`message-relative`）；真实文件位置见切分表的 ``file_offset``；
* ``MC-C03`` 零长度消息（分隔行之后到下一分隔行之间 0 字节）→ 同样 ``offset=0``；
* ``MC-C04`` 分隔行信封完整，但切出的片段**不具备消息头块**（三种读法一致误切）→ ``offset=0``；
* ``MC-C02`` 正文里**未转义**的 ``From `` 行：其它变体在此切分、主表不切 → 变体切分表不一致；
  落点 = 该 ``From `` 行相对消息起点的偏移（`message-relative`）；
* ``MC-C05`` Maildir ``cur/`` 条目名缺 ``:2,<flags>`` 信息段 → 作用于文件名，无字节偏移
  （``offset=0`` 是占位），`offset_kind="absolute"`。

**C02 与 C04 的分工**（golden 的 ``c-from-unescaped`` / ``c-body-from``）：C02 = 变体读法
**不一致**（有 ``Content-Length`` 兜住的那类）；C04 = 三种读法**一致**误切（片段不成消息）。

**分层**：本模块位于最底层（只看容器字节，不看 multipart 树），不得 import
``scan`` / ``headers`` / ``transfer`` / ``attribution``；行切分有一份本地实现（K7）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import constants as C
from .errors import InputError
from .model import Defect

#: MC-C 系列的静态形态（``class`` / ``severity`` / ``rfc``）—— 引擎侧的唯一定义点。
#: 与 ``mimeconform/rules/catalog.json`` **逐值一致**（``tests/test_catalog_consistency.py``）。
#: C 簇全部 ``diff/note`` + ``none-by-design``：mbox / Maildir 都不是 RFC（D3）。
_RULE_META: dict[str, tuple[str, str, str]] = {
    "MC-C01": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-C02": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-C03": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-C04": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
    "MC-C05": (C.CLASS_DIFF, C.SEV_NOTE, C.RFC_NONE_BY_DESIGN),
}

#: 三种 mbox 读法（§7.7）。
MBOX_VARIANTS: tuple[str, ...] = ("mboxo", "mboxrd", "mboxcl")
#: ``auto`` 之外的全部合法取值。
VARIANT_CHOICES: tuple[str, ...] = MBOX_VARIANTS + ("auto",)

#: mbox 分隔行前缀（按字节，不做大小写折叠）。
_SEPARATOR = b"From "
#: Maildir 的三种子目录（`cur/` 条目必须带 ``:2,<flags>``）。
_MAILDIR_SUBDIRS = ("cur", "new", "tmp")


@dataclass(frozen=True, slots=True)
class MessageSpan:
    """一条消息在容器内的位置。``offset_kind = message-relative``（§7.10）。"""

    index: int                    # msg#<n>，从 1 开始
    start: int                    # 相对文件起点的消息起点（From 行首）
    end: int                      # 消息终点（下一分隔行行首或文件末尾）
    file_offset: int              # 容器文件内的绝对偏移（== start；单列以对齐 §7.10 报告口径）
    from_line: bytes = b""        # 分隔行内容（不含行尾）


@dataclass(frozen=True, slots=True)
class ContainerResult:
    primary_variant: str = C.MBOX_VARIANT_DEFAULT
    split_variants: dict[str, tuple[MessageSpan, ...]] = field(default_factory=dict)
    defects: tuple[Defect, ...] = field(default=())
    container_kind: str = "mbox"          # "mbox" | "maildir"
    entries: tuple[str, ...] = ()         # Maildir 条目相对路径（mbox 为空）


# ── 行切分（K7：与 `scan.split_lines` 同语义，但不得反向 import）──────────


def _iter_lines(data: bytes, start: int = 0, end: int | None = None) -> list[tuple[int, bytes, int]]:
    """按 ``\\n`` 切行 → ``(行首, 内容不含行尾, 行尾之后的偏移)``。

    与 ``scan.split_lines`` 的语义一致（只认 ``\\n`` 为行界）；容器模块不能 import `scan`，
    故各有一份实现，由 ``tests/test_golden_engine_container.py::test_line_splitter_matches_scan``
    交叉断言。
    """
    stop = len(data) if end is None else end
    out: list[tuple[int, bytes, int]] = []
    pos = start
    while pos < stop:
        newline = data.find(b"\n", pos, stop)
        line_end = stop if newline < 0 else newline + 1
        content = data[pos:line_end]
        if content.endswith(b"\n"):
            content = content[:-1]
        if content.endswith(b"\r"):
            content = content[:-1]
        out.append((pos, content, line_end))
        pos = line_end
    return out


def _defect(rule_id: str, path: str, offset: int, offset_kind: str, detail: str) -> Defect:
    klass, severity, rfc = _RULE_META[rule_id]
    defect = Defect(
        rule_id=rule_id,
        path=path,
        offset=offset,
        offset_kind=offset_kind,
        klass=klass,
        severity=severity,
        rfc=rfc,
        detail=detail,
    )
    defect.validate()
    return defect


# ── 变体判定（§7.7 纯字节规则，不打分）────────────────────────────────────


def detect_variant(data: bytes) -> str:
    """按 §7.7 的**纯字节规则**判定主变体（不打分、不启发式）。

    * 出现 ``Content-Length:`` 头 → ``mboxcl``；
    * 否则出现 ``>From `` 且无 ``>>From `` → ``mboxo``；
    * 否则 ``mboxo``。
    """
    if b"\nContent-Length:" in b"\n" + data or data.startswith(b"Content-Length:"):
        return "mboxcl"
    if b"\n>From " in b"\n" + data and b"\n>>From " not in b"\n" + data:
        return "mboxo"
    return "mboxo"


# ── 切分 ──────────────────────────────────────────────────────────────────


def _mboxcl_end(data: bytes, header_start: int) -> int | None:
    """``mboxcl``：按 ``Content-Length`` 求消息终点；无该头或形态不对 → ``None``（回落 mboxo）。"""
    pos = header_start
    content_length: int | None = None
    blank_found = False
    while pos < len(data):
        newline = data.find(b"\n", pos)
        line_end = len(data) if newline < 0 else newline + 1
        content = data[pos:line_end]
        if content.endswith(b"\n"):
            content = content[:-1]
        if content.endswith(b"\r"):
            content = content[:-1]
        if content == b"":
            blank_found = True
            pos = line_end
            break
        if content[:1] in (b" ", b"\t"):
            pos = line_end
            continue
        colon = content.find(b":")
        if colon <= 0:
            return None
        name = content[:colon].decode("ascii", "replace").lower()
        if name == "content-length":
            try:
                content_length = int(content[colon + 1 :].strip())
            except ValueError:
                content_length = None
        pos = line_end
    if not blank_found or content_length is None or content_length < 0:
        return None
    end = pos + content_length
    return end if end <= len(data) else None


def _split_variant(data: bytes, variant: str) -> tuple[MessageSpan, ...]:
    """按指定读法切分 mbox，返回消息切分表（``msg#1`` 起，按分隔行出现顺序）。"""
    separators = [
        (start, content, line_end)
        for start, content, line_end in _iter_lines(data)
        if content.startswith(_SEPARATOR)
    ]
    spans: list[MessageSpan] = []
    index = 0
    while index < len(separators):
        start, content, line_end = separators[index]
        end: int | None = None
        if variant == "mboxcl":
            end = _mboxcl_end(data, line_end)
        if end is None or end <= start:
            end = separators[index + 1][0] if index + 1 < len(separators) else len(data)
        next_index = index + 1
        while next_index < len(separators) and separators[next_index][0] < end:
            next_index += 1
        spans.append(
            MessageSpan(
                index=len(spans) + 1,
                start=start,
                end=end,
                file_offset=start,
                from_line=content,
            )
        )
        index = next_index
    return tuple(spans)


def _valid_separator(from_line: bytes) -> bool:
    """``From <地址> <日期>`` 形态：地址之后必须还有带数字的日期字段（cpython #93376 的判据）。"""
    if not from_line.startswith(_SEPARATOR):
        return False
    remainder = from_line[len(_SEPARATOR) :]
    if b" " not in remainder:
        return False
    _sender, date_part = remainder.split(b" ", 1)
    return any(48 <= byte <= 57 for byte in date_part)


def _has_header_block(rest: bytes) -> bool:
    """片段是否具备消息头块：首行是合法头（或空行）即算有。

    空行开头 = "空头块 + 正文" 的合法形态，不算误切；首行既非空行也不含冒号 → 不具备头块。
    """
    if rest == b"":
        return False
    first = rest.split(b"\n", 1)[0]
    if first.endswith(b"\r"):
        first = first[:-1]
    if first == b"":
        return True
    colon = first.find(b":")
    if colon <= 0:
        return False
    return all(33 <= byte <= 126 and byte != 58 for byte in first[:colon])


def _container_defects(
    data: bytes,
    primary_variant: str,
    tables: dict[str, tuple[MessageSpan, ...]],
) -> tuple[Defect, ...]:
    """以主表为准产出 MC-C01/C02/C03/C04（C05 见 :func:`audit_maildir`）。"""
    primary = tables[primary_variant]
    other_separators = {
        span.start for variant, spans in tables.items() if variant != primary_variant for span in spans
    }
    out: list[Defect] = []
    for span in primary:
        line_end = span.start + len(span.from_line)
        if line_end < len(data) and data[line_end : line_end + 1] == b"\r":
            line_end += 1
        if line_end < len(data) and data[line_end : line_end + 1] == b"\n":
            line_end += 1
        rest = data[line_end : span.end]

        if not _valid_separator(span.from_line):
            out.append(
                _defect(
                    "MC-C01",
                    f"msg#{span.index}",
                    0,
                    C.OFFSET_MESSAGE_RELATIVE,
                    f"分隔行 `{span.from_line.decode('latin-1')}` 缺日期字段（envelope 无法解析）："
                    "mbox 约定是 `From <地址> <日期>`，它不是 RFC（D3）→ 只登记"
                    f"（文件内位置见切分表 file_offset={span.file_offset}）",
                )
            )
            continue
        if rest == b"":
            out.append(
                _defect(
                    "MC-C03",
                    f"msg#{span.index}",
                    0,
                    C.OFFSET_MESSAGE_RELATIVE,
                    "零长度消息：`From ` 分隔行与下一条分隔行之间没有任何字节"
                    f"（文件内位置见切分表 file_offset={span.file_offset}）",
                )
            )
            continue
        if not _has_header_block(rest):
            out.append(
                _defect(
                    "MC-C04",
                    f"msg#{span.index}",
                    0,
                    C.OFFSET_MESSAGE_RELATIVE,
                    "该 `From ` 行信封完整，但它是被误当分隔行的正文内容 —— 切出的片段不具备消息头块："
                    "正文含裸 `From ` 行的直接证据",
                )
            )
            continue

        # MC-C02：正文里未转义的 `From ` 行（其它变体在此切分 → 变体切分表不一致）。
        for line_start, content, _line_end in _iter_lines(data, line_end, span.end):
            if not content.startswith(_SEPARATOR):
                continue
            if line_start not in other_separators:
                continue
            out.append(
                _defect(
                    "MC-C02",
                    f"msg#{span.index}",
                    line_start - span.start,
                    C.OFFSET_MESSAGE_RELATIVE,
                    "正文里的 `From ` 行未转义（mboxo 约定应写成 `>From `）："
                    "mboxo/mboxrd 读法在此误切一条消息，其它读法不受影响 → 各变体切分表不一致，"
                    "全部要输出",
                )
            )
    return tuple(sorted(out, key=lambda item: item.sort_key))


# ── 入口：mbox ────────────────────────────────────────────────────────────


def split_container(data: bytes, *, variant: str = C.MBOX_VARIANT_DEFAULT) -> ContainerResult:
    """按指定变体切分 mbox，**同时给出三种读法的切分表**。

    ``variant="auto"`` 时按 §7.7 的纯字节规则决定"主表"是哪一份；缺陷只从主表产出。
    非容器输入（不以 ``From `` 分隔行开头）返回空表 —— **不**把 `.eml` 误判成空 mbox
    （CLI 在容器模式下对空表显式报错，见 `cli._run_audit`）。
    """
    if variant not in VARIANT_CHOICES:
        raise ValueError(f"未知 mbox 变体 {variant!r}（合法值 {VARIANT_CHOICES}）")
    if isinstance(data, bytearray):
        data = bytes(data)
    tables = {name: _split_variant(data, name) for name in MBOX_VARIANTS}
    primary_variant = detect_variant(data) if variant == "auto" else variant
    defects = _container_defects(data, primary_variant, tables)
    return ContainerResult(
        primary_variant=primary_variant,
        split_variants=tables,
        defects=defects,
        container_kind="mbox",
    )


# ── 入口：Maildir ─────────────────────────────────────────────────────────


def _maildir_entries(root: Path) -> list[tuple[str, Path]]:
    entries: list[tuple[str, Path]] = []
    for sub in _MAILDIR_SUBDIRS:
        directory = root / sub
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir(), key=lambda item: item.name):
            if path.is_file():
                entries.append((f"{sub}/{path.name}", path))
    return entries


def _maildir_name_is_compliant(sub: str, name: str) -> bool:
    """``cur/`` 条目必须是 ``<unique>:2,<flags>``；``new/`` / ``tmp/`` 无该要求。"""
    if sub != "cur":
        return True
    return ":2," in name


def audit_maildir(root: Path) -> ContainerResult:
    """审计一个 Maildir 目录：切分表 + MC-C05（条目名不合规）。

    条目顺序固定为 ``cur/`` → ``new/`` → ``tmp/``，各自按文件名排序；``msg#N`` 从 1 起。
    目录里没有任何条目 → :class:`InputError`（空分母 ≠ 通过）。
    """
    root = Path(root)
    entries = _maildir_entries(root)
    if not entries:
        raise InputError(f"Maildir 目录里没有任何条目（{root}）：不是合法容器输入")

    spans: list[MessageSpan] = []
    defects: list[Defect] = []
    for index, (rel, path) in enumerate(entries, start=1):
        try:
            data = path.read_bytes()
        except OSError as exc:  # pragma: no cover - 权限/IO 异常
            raise InputError(f"无法按字节读取 Maildir 条目 {path}: {exc}") from exc
        spans.append(MessageSpan(index=index, start=0, end=len(data), file_offset=0, from_line=b""))
        sub, _, name = rel.partition("/")
        if not _maildir_name_is_compliant(sub, name):
            defects.append(
                _defect(
                    "MC-C05",
                    f"msg#{index}",
                    0,
                    C.OFFSET_ABSOLUTE,
                    f"{sub}/ 下的条目名 `{name}` 缺 `:2,<flags>` 信息段"
                    "（Maildir 约定：cur 条目应为 `<unique>:2,<flags>`）；Maildir 没有 RFC 依据 → 只登记",
                )
            )

    return ContainerResult(
        primary_variant="maildir",
        split_variants={},
        defects=tuple(sorted(defects, key=lambda item: item.sort_key)),
        container_kind="maildir",
        entries=tuple(rel for rel, _path in entries),
    )
