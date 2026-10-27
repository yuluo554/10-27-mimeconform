"""命令行界面：参数面 / 退出码映射 / IO（唯一允许写 stdout 与文件的地方）。

**退出码映射是本模块的核心职责**（plan/03 §八）：

* ``argparse`` 对未知子命令 / 缺必填参数 / ``--version`` 都抛 ``SystemExit``；
* 本项目的 ``2`` 语义是"审计完成、存在 minor"（data/README §7.9），
  因此**必须**把 argparse 的 ``SystemExit`` 统一捕获：``0``（--help / --version）保留，
  其余一律映射为 ``1``（用法错误）。否则"打错参数"会被读成"有轻微缺陷"。
* 引擎未就绪（骨架期）→ ``EngineNotReady`` → ``1`` + 明确文案，**绝不返回 0**。

**失败路径零副作用**：所有审计在拿到完整结果之前不写任何文件；
``--out`` 只在渲染成功之后才落盘。
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from . import __version__
from . import constants as C
from .errors import EngineNotReady, InputError, MimeconformError, UsageError
from .exit_codes import decide_exit_code

_DESCRIPTION = (
    "MIME 结构体检器：把邮件的原始字节转成带 RFC 条款引用的结构缺陷账本。"
    "每缺陷 = 位置 + 严重度 + RFC 出处 + 硬规则/实现差异标记。"
)
_EPILOG = (
    "退出码: 0 无 blocker/major | 1 用法错误或输入不可读 | 2 有 minor | 3 有 major/blocker"
)


def _ensure_utf8_stdio() -> None:
    """保证任意控制台 / CI 管道下都能输出 UTF-8 文案。

    按 ``stream.encoding`` 探针决定是否 reconfigure：UTF-8 与中文控制台（cp936）
    保持不动，其余（如 CI 的 cp1252）重配成 UTF-8 + ``backslashreplace``。
    """
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", "") or "").lower()
        if encoding in {"utf-8", "utf8", "cp936", "gbk", "gb2312", "gb18030"}:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="backslashreplace")
        except (ValueError, OSError):  # pragma: no cover - 极少数不可重配的流
            continue


class _Parser(argparse.ArgumentParser):
    """把 argparse 的用法错误转成 exit 1（不走 argparse 自带的 2）。"""

    def error(self, message: str):  # type: ignore[override]
        raise UsageError(message)


def _positive_int(text: str) -> int:
    try:
        value = int(text, 10)
    except ValueError:
        raise argparse.ArgumentTypeError(f"需要整数: {text!r}") from None
    if value < 1:
        # 显式拒绝 0 / 负数，不静默改回默认值（skill 阶段 6「or DEFAULT」条）
        raise argparse.ArgumentTypeError(f"必须 >= 1: {value}")
    return value


def build_parser() -> argparse.ArgumentParser:
    """构造参数解析器。**测试直接调用它做参数面反射对账**（README ↔ parser）。"""
    parser = _Parser(
        prog="mimeconform",
        description=_DESCRIPTION,
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"mimeconform {__version__}")

    sub = parser.add_subparsers(dest="command", metavar="{audit,selftest}")

    audit = sub.add_parser(
        "audit",
        help="审计一个 .eml / .mbox 文件，输出缺陷账本",
        description="审计输入文件的 MIME 结构，把缺陷写入 --out 或 stdout。",
    )
    audit.add_argument("path", metavar="INPUT", help="输入文件（.eml / .mbox / Maildir 目录）")
    audit.add_argument(
        "--out",
        metavar="PATH",
        default=None,
        help="输出路径；以 .json 结尾写 JSON，以 .md 结尾写 Markdown，其余按目录处理（写两种）",
    )
    audit.add_argument(
        "--format",
        choices=("json", "md", "both"),
        default="both",
        help="输出格式（默认 both）；与 --out 目录形态配合",
    )
    audit.add_argument(
        "--fail-on",
        choices=C.SEVERITIES,
        default=C.FAIL_ON_DEFAULT,
        help=f"提升失败门槛（默认 {C.FAIL_ON_DEFAULT}）；只会更严，不会放过 major/blocker",
    )
    audit.add_argument(
        "--max-depth",
        type=_positive_int,
        default=C.MAX_DEPTH_DEFAULT,
        metavar="N",
        help=f"最大嵌套深度（策略项，默认 {C.MAX_DEPTH_DEFAULT}；超限只出 gray/note）",
    )
    audit.add_argument(
        "--strict-depth",
        action="store_true",
        help="把超深度计入退出码（仍为 gray，severity 提为 minor）",
    )
    audit.add_argument(
        "--mbox-variant",
        choices=C.MBOX_VARIANTS,
        default=C.MBOX_VARIANT_DEFAULT,
        help=f"mbox 读法（默认 {C.MBOX_VARIANT_DEFAULT}）；所有变体的切分表都会输出",
    )
    audit.add_argument(
        "--container",
        action="store_true",
        help="把输入当作容器（.mbox / Maildir）而不是单封邮件",
    )

    selftest = sub.add_parser(
        "selftest",
        help="校验 golden 语料的自洽性（数据级，不跑引擎）",
        description=(
            "逐 case 校验 data/golden：expect.json 可解析、缺陷六元组齐全、"
            "defect_count 与 defects 一致、exit_code 可由缺陷集复算。"
        ),
    )
    selftest.add_argument(
        "--data-dir",
        metavar="DIR",
        default=None,
        help="golden 语料根目录（默认仓库内 data/golden；发布包/测试可显式指定）",
    )
    return parser


# ── selftest：数据级校验（不依赖规则引擎）─────────────────────────────────


def _repo_root() -> Path:
    """仓库根（源码态 / editable 安装）。

    **非 editable 安装时这里指向 site-packages**，`data/golden` 不在包内 ——
    这是**设计如此**（语料是开发期资产，不进 wheel），故安装态必须显式传 `--data-dir`。
    """
    return Path(__file__).resolve().parents[1]


def _default_golden_dir() -> Path:
    return _repo_root() / "data" / "golden"


def _validate_expect(case_dir: Path) -> list[str]:
    """校验单个 case 的 ``expect.json``；返回问题列表（空 = 通过）。"""
    import json

    problems: list[str] = []
    expect_path = case_dir / "expect.json"
    if not expect_path.is_file():
        return [f"{case_dir.name}: 缺 expect.json"]
    try:
        payload = json.loads(expect_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"{case_dir.name}: expect.json 无法解析（{exc}）"]

    if not isinstance(payload, dict):
        return [f"{case_dir.name}: expect.json 顶层必须是对象"]

    if payload.get("case") != case_dir.name:
        problems.append(f"{case_dir.name}: case 字段与目录名不一致（{payload.get('case')!r}）")

    input_info = payload.get("input")
    if not isinstance(input_info, dict) or not isinstance(input_info.get("file"), str):
        problems.append(f"{case_dir.name}: 缺 input.file")
    else:
        target = case_dir / str(input_info["file"])
        if not target.is_file():
            problems.append(f"{case_dir.name}: 输入文件缺失（{input_info['file']}）")
        else:
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if input_info.get("sha256") != digest:
                problems.append(f"{case_dir.name}: input.sha256 与实际字节不符")
            if input_info.get("bytes") != target.stat().st_size:
                problems.append(f"{case_dir.name}: input.bytes 与实际字节数不符")

    defects = payload.get("defects")
    if not isinstance(defects, list):
        return problems + [f"{case_dir.name}: defects 必须是数组"]

    if payload.get("defect_count") != len(defects):
        problems.append(
            f"{case_dir.name}: defect_count={payload.get('defect_count')} 与 defects 长度 {len(defects)} 不一致"
        )

    from .model import Defect

    parsed: list[Defect] = []
    for idx, raw in enumerate(defects):
        if not isinstance(raw, dict):
            problems.append(f"{case_dir.name}: defects[{idx}] 不是对象")
            continue
        klass = raw.get("class")
        try:
            defect = Defect(
                rule_id=str(raw["rule_id"]),
                klass=str(klass),
                severity=str(raw["severity"]),
                path=str(raw["path"]),
                offset=int(raw["offset"]),
                offset_kind=str(raw["offset_kind"]),
                rfc=str(raw["rfc"]),
                detail=str(raw["detail"]),
            )
            defect.validate()
        except (KeyError, TypeError, ValueError) as exc:
            problems.append(f"{case_dir.name}: defects[{idx}] 不合法（{exc}）")
            continue
        parsed.append(defect)

    expected_exit = payload.get("exit_code")
    actual_exit = decide_exit_code(parsed, fail_on=C.FAIL_ON_DEFAULT)
    if expected_exit != actual_exit:
        problems.append(
            f"{case_dir.name}: exit_code={expected_exit} 与缺陷集复算值 {actual_exit} 不一致"
        )

    for key in ("fingerprint", "tree_digest"):
        value = payload.get(key)
        if value is not None and (not isinstance(value, str) or len(value) != 64):
            problems.append(f"{case_dir.name}: {key} 必须是 64 位十六进制串")
    return problems


def _run_selftest(data_dir: Path, *, explicit: bool) -> int:
    if not data_dir.is_dir():
        sys.stderr.write(f"selftest: 数据目录不存在: {data_dir}\n")
        if explicit:
            sys.stderr.write("  你显式传了 --data-dir，但它不是一个目录。\n")
        else:
            sys.stderr.write(
                "  这是默认路径（仓库内 data/golden）。如果你是从**已安装的包**运行，"
                "语料不在包内 —— 请显式传 --data-dir <仓库>/data/golden。\n"
            )
        sys.stderr.write(
            "  另外：golden 语料自里程碑 M1 起落地；此处显式失败而不返回 0"
            "（读不了/没数据 ≠ 没问题，data/README §7.9）。\n"
        )
        return C.EXIT_USAGE

    cases = sorted(p for p in data_dir.iterdir() if p.is_dir() and (p / "expect.json").is_file())
    if not cases:
        sys.stderr.write(
            f"selftest: {data_dir} 下没有任何 case（0 个）——数据未就绪，不是「全部通过」。\n"
        )
        return C.EXIT_USAGE

    problems: list[str] = []
    for case_dir in cases:
        problems.extend(_validate_expect(case_dir))

    if problems:
        sys.stdout.write(f"selftest: {len(cases)} cases, {len(problems)} 项问题\n")
        for item in problems:
            sys.stdout.write(f"FAIL  {item}\n")
        return C.EXIT_USAGE

    sys.stdout.write(f"selftest: {len(cases)} cases, 0 问题\n")
    return C.EXIT_OK


# ── audit ────────────────────────────────────────────────────────────────


def _read_input(path: Path) -> bytes:
    if not path.exists():
        raise UsageError(f"输入不存在: {path}")
    if path.is_dir():
        raise UsageError(f"输入是目录（容器层自里程碑 M5 起支持）: {path}")
    try:
        with path.open("rb") as handle:
            return handle.read()
    except OSError as exc:
        raise InputError(f"无法按字节读取 {path}: {exc}") from exc


def _engine_available() -> bool:
    """引擎是否已落地（`scan_message` 不再抛 `EngineNotReady` 即为真）。

    M2 起 `scan.py` 已实现，本函数恒为真；保留它是因为**报告路径只在这一处汇总**
    —— 将来再加模块（M3–M5）时，接线点仍然只有 `_run_audit` 一个。
    """
    return True


#: 本轮 `audit` 真正跑过的引擎层（顺序 = 报告里的展示顺序）。
#: **加模块必须同改这里**，否则报告会把"没查"说成"查过"（`tests/test_cli_contract.py` 断言）。
_AUDITED_ENGINES: tuple[str, ...] = ("scan", "headers")

#: 仍未接入 `audit` 的引擎层（M4 / M5）。它们仍是 `EngineNotReady`。
_NOT_YET_AUDITED: tuple[str, ...] = ("transfer", "attribution", "container")


def _audited_engines() -> tuple[str, ...]:
    return _AUDITED_ENGINES


def _tree_info(result: object) -> dict[str, object]:
    """把 `ScanResult` 的**结构事实**整理成报告字段（不判定，只搬运）。"""
    from .scan import AMBIGUITY_NOTE

    tree_alternatives = getattr(result, "tree_alternatives", ())
    divergence = getattr(result, "divergence", None)
    facts = getattr(result, "facts", {}) or {}
    info: dict[str, object] = {
        "mode": facts.get("mode", "inner-first"),
        "node_count": facts.get("node_count", 1),
        "max_depth": facts.get("max_depth"),
        "tree_alternatives": len(tree_alternatives),
        "truncated_paths": list(facts.get("truncated_paths", ())),
        # 覆盖面声明（M3）：报告必须自己说清"这轮审计了哪几层"——
        # 否则一份干净的账本会被读成"全模块都查过了"。加模块时同改 `_audited_engines`。
        "audited_engines": list(_audited_engines()),
        "not_yet_audited": list(_NOT_YET_AUDITED),
    }
    if divergence is not None:
        info["divergence"] = {
            "path": divergence.path,
            "offset": divergence.offset,
            "note": divergence.note,
        }
        # plan/00 D9：默认展示不构成判定 —— 报告必须自己说出来，不能只在文档里写。
        info["declaration"] = "默认展示的树不构成判定；" + AMBIGUITY_NOTE
    return info


def _render(result: object, defects: tuple, *, input_name: str, data: bytes, exit_code: int) -> tuple[str, str]:
    """同一份台账 → (JSON, Markdown)。两条产物同源（plan/02 §七）。"""
    from .ledger import build
    from .report import render_json, render_markdown

    root = getattr(result, "root", None)
    ledger = build(defects, root)
    kwargs = dict(
        input_name=input_name,
        input_bytes=len(data),
        input_sha256=hashlib.sha256(data).hexdigest(),
        exit_code=exit_code,
        tree_info=_tree_info(result),
    )
    return render_json(ledger, **kwargs), render_markdown(ledger, **kwargs)


def _write_outputs(args: argparse.Namespace, json_text: str, md_text: str) -> None:
    """把产物写到 `--out` 或 stdout。

    `--out` 的三种形态（`plan/03` §八）：
    * 以 ``.json`` 结尾 → 只写 JSON；
    * 以 ``.md`` 结尾 → 只写 Markdown；
    * 其余按**目录**处理 → 按 ``--format`` 写 ``report.json`` / ``report.md``。

    **只写指定路径**：绝不写输入所在目录（只读红线，`plan/00` §六.5）。
    """
    out = args.out
    if out is None:
        if args.format in {"json", "both"}:
            sys.stdout.write(json_text)
        if args.format in {"md", "both"}:
            sys.stdout.write(md_text)
        return

    target = Path(out)
    suffix = target.suffix.lower()
    try:
        if suffix == ".json":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json_text, encoding="utf-8")
            return
        if suffix in {".md", ".markdown"}:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(md_text, encoding="utf-8")
            return
        target.mkdir(parents=True, exist_ok=True)
        if args.format in {"json", "both"}:
            (target / "report.json").write_text(json_text, encoding="utf-8")
        if args.format in {"md", "both"}:
            (target / "report.md").write_text(md_text, encoding="utf-8")
    except OSError as exc:
        raise InputError(f"无法写入 {target}: {exc}") from exc


def _audit(data: bytes, args: argparse.Namespace):
    """跑本轮已落地的全部引擎面，返回 ``(ScanResult-like, 合并后的缺陷元组)``。

    **接线点只有这一处**（`plan/03` §八）：每棒把新落地的模块加进这里，别处不改。
    M2 = `scan`（树与边界）；M3 = `headers`（头编码）；M4 = `transfer`；M5 = `attribution`/`container`。
    """
    from .headers import audit_headers
    from .scan import scan_message

    result = scan_message(data, max_depth=args.max_depth, strict_depth=args.strict_depth)
    header_defects = audit_headers(result.root, data)
    combined = tuple(sorted(result.defects + header_defects, key=lambda item: item.sort_key))
    return result, combined


def _run_audit(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = _read_input(path)

    if not _engine_available():  # pragma: no cover - M2 起恒真
        from ._pending import _not_ready

        raise _not_ready("scan_message")

    result, defects = _audit(data, args)
    exit_code = decide_exit_code(defects, fail_on=args.fail_on)
    json_text, md_text = _render(result, defects, input_name=path.name, data=data, exit_code=exit_code)
    _write_outputs(args, json_text, md_text)
    return exit_code


# ── main ─────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """进程入口。返回退出码（不在此处 ``sys.exit``，便于测试直接断言数值）。"""
    _ensure_utf8_stdio()
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --help / --version = 0；argparse 的用法错误 = 1
        code = exc.code if isinstance(exc.code, int) else C.EXIT_USAGE
        return C.EXIT_OK if code == 0 else C.EXIT_USAGE
    except UsageError as exc:
        sys.stderr.write(f"mimeconform: 用法错误: {exc}\n")
        sys.stderr.write(parser.format_usage())
        return C.EXIT_USAGE

    if args.command is None:
        sys.stderr.write(parser.format_help())
        return C.EXIT_USAGE

    try:
        if args.command == "selftest":
            data_dir = Path(args.data_dir) if args.data_dir else _default_golden_dir()
            return _run_selftest(data_dir, explicit=args.data_dir is not None)
        if args.command == "audit":
            return _run_audit(args)
    except EngineNotReady as exc:
        sys.stderr.write(f"mimeconform: {exc}\n")
        return C.EXIT_USAGE
    except (UsageError, InputError) as exc:
        sys.stderr.write(f"mimeconform: {exc}\n")
        return C.EXIT_USAGE
    except MimeconformError as exc:  # 兜底：任何自家异常都不许变成 traceback / exit 0
        sys.stderr.write(f"mimeconform: {exc}\n")
        return C.EXIT_USAGE

    sys.stderr.write(f"mimeconform: 未知子命令: {args.command}\n")
    return C.EXIT_USAGE
