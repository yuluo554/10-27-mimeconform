# HANDOFF-M4 — 进入 M4（传输编码）的收尾交接单

> 产出棒：M3（头编码：`headers.py` + MC-H 系列 + `rules/catalog.json` 与 `docs/defect-catalog.md`），2026-10-28。
> 用法：新对话第一件事 = 跑 `py -3.12 tools/check_sprint_layout.py`（见 `AGENTS.md`）。
> **库内一律相对路径**；绝对路径只出现在会话启动命令里。

---

## 一、当前进度 + 证据

**M3 已完成并验证**（状态以 `plan/00` 里程碑表为准；本节的数字是**当轮实测**）。

| 项 | 实测证据 |
| --- | --- |
| 布局门 | `py -3.12 tools/check_sprint_layout.py` → 9 条判据全 PASS，`这轮扫到：files 14 / sections 8 / handoffs 3 / gap_rows 8 / ledger 1 / doc_tools 3` |
| 脱敏门 | `py -3.12 tools/check_desensitized.py` → **167 个文本文件，0 命中**（豁免 2 份） |
| 布局门变异验证 | `py -3.12 -X utf8 tools/verify_layout_gate.py` → **15 组：15 符合预期 / 0 不符** |
| 全量测试 | `py -3.12 -X utf8 -m pytest` → **476 passed, 1 skipped**（M2 时 362 passed；新增 `test_golden_engine_headers.py` 74 条 + `test_catalog_doc.py` 28 条 + `test_catalog_consistency.py` 8 条 + `test_cli_contract.py` 2 条接线断言 + `test_catalog_gate.py` 3 条哨兵键用例） |
| 生成器可重建 | `py -3.12 -m mimeconform.devtools.gen_golden --check` → **`51 cases, 0 diff`**（exit 0；语料未改） |
| 语料数据级校验 | `py -3.12 -m mimeconform selftest` → **`51 cases, 0 问题`**（exit 0） |
| `h-*` 引擎侧 | 12/12 case 命中（比对键 `rule_id`/`path`/`offset`/`class`）；11 正例、1 负例零误报 |
| CLI 级退出码（h 簇） | `h-line-998` → 3；`h-ew-long` / `h-ew-line-long` / `h-ew-space` → 2；其余 → 0（与各自 `expect.json` 一致） |
| 复现 SO 44154520 | `h-2231-seq`：MC-H09 `diff/note` @ `filename*` 参数名（offset 381）；`*0` 修正提示写进 `detail` |
| 复现 SO 52442469 | `h-ew-newline`：MC-H12 `diff/note` @ encoded-word 起点（offset 63），`related == ("MC-H03",)`，**不**双记 |
| catalog 门禁 | `load_catalog()` 返回 **22 条**（B 10 + H 12）全部过原句门禁；`test_real_catalog_is_absent_and_reports_cleanly` **转 skip**（已确认是 skip 而非红） |
| 文档一致性 | `docs/defect-catalog.md` 与 catalog 规则数、`class`、`severity` 机器对账（`tests/test_catalog_doc.py`） |
| 误报面 | 全语料 51 个 `.eml` 上 `audit_headers` 只在 h-* 出缺陷；b/t/a/c 全簇零 H 缺陷 |

**M4 要做到的东西**：`transfer.py` 的自写 base64 / QP 观察与解码 + MC-T 系列 11 条
（`plan/03` §三）+ 复现 SO 79133579 / SO 6029218 + `t-*` 13 个 case 的引擎侧断言 +
把 T 簇写进 `catalog.json` 与 `docs/defect-catalog.md`（**同轮**，规则数与两处一致性由既有测试自动覆盖）。

---

## 二、当前事实·状态不变量（下一棒动手前必须知道，否则一定会踩）

1. **`rules/catalog.json` 现在是"三源一致"的一环**：`MC-B0x` 的五字段必须与 `scan._RULE_META` 逐值一致，
   `MC-H0x/1x` 必须与 `headers._RULE_META` 逐值一致 —— `tests/test_catalog_consistency.py` 双向断言
   （代码有而 catalog 没有也会红）。**M4 落地 T 簇时同样要在 `transfer.py` 里建一份 `_RULE_META`**，
   并把 `{"scan","headers"}` 之外加上 `"transfer"`（该测试的 `_META_MODULES` 清单）。
2. **`none-by-design` 是哨兵键，不是豁免**（`mimeconform/rules/__init__.py:NO_CLAUSE_KEY`）：
   `rfc = none-by-design` 的规则写 `ledger_key = "none-by-design"`，门禁解析成"键存在、原句为空"
   → 只能 `diff`/`gray` + `note`。**不要把哨兵用在有原句可引的规则上**（那是自降级，不是省事）。
   M4 的 MC-T01 / MC-T08 / MC-T11 走哨兵；MC-T05/T06/T07 有 R8 原句，必须走真键。
3. **MC-T07 的条款论证是"推导"**（`plan/03` §三 / `plan/06` Q1）：R8 全录了"行末 `=` = 软换行"，
   这条把 `=` 的唯一合法语义限定为"软换行或 `=HH`"。落地时 `docs/defect-catalog.md` **必须**同时写
   推导链与"若审阅者要求更保守，把 `klass` 降为 `diff`、`severity` 降为 `note`"这一开关（Q1）。
4. **`translate.py` 不存在**：M4 的模块名是 `transfer.py`（已存在骨架，`observe_body_shape` /
   `decode_base64` / `decode_qp` / `audit_body` 四个入口目前抛 `EngineNotReady`）。
5. **接线点只有一个**：`mimeconform/cli.py::_audit()`（M3 新抽出的函数）。M4 要在这里加
   `transfer` 一趟，并同步改 `_AUDITED_ENGINES` / `_NOT_YET_AUDITED`
   —— `tests/test_cli_contract.py::test_headers_engine_is_wired_into_audit` 断言这两个元组，
   **改一处不改另一处会红**（这是故意的：报告不许把"没查"说成"查过"）。
6. **行切分有两份实现，语义必须一致**：`scan.split_lines()` 与 `headers._iter_lines()`
   （分层不允许 `headers` import `scan`）。`tests/test_golden_engine_headers.py::test_line_splitter_matches_scan`
   交叉断言。**M4 的 `transfer.py` 若需要切行，同样走这条交叉断言**，不要各写一套然后互不知道。
7. **三种"双记"禁令要照 `plan/03` §三 与 `data/README` §7.5 落**：CTE 未知时不判交叉校验（T08 先于 T01）；
   base64 "字母表外字符"在**编码态**合法、只在解码后残留时才是 T11；QP 软换行行宽不计入下一行。
8. **`t-*` 的 `expect.json` 是 M1 手写常量**：`t-cte-mismatch` 带 `expect_extra.suppressed`
   （`MC-T02/T03/T04` 在"observed 完全不是 base64 形态"时不逐条登记）——
   引擎要按这条口径压掉，否则同一个 case 会多出几十条 note 账。
9. **`h-*` 的经验对 t-* 同样有效**：判定顺序写在模块 docstring 里 + 用"构造单元测试"锁住
   （`h-*` 12 个 case 没有覆盖 H06，只能靠 `tests/test_golden_engine_headers.py` 里的构造样本兜住；
   `t-*` 也可能有规则没有 golden case，**不要**为了让语料凑齐去改生成器 —— K13 锁着逐字节一致）。
10. **`gen_golden.py` 的骨架函数不要动**（`_mixed_with_attachment` / `_leaf` / `_plain_headers` 等）：
    改一处会同时动几十个 case 的字节，`--check` 全量变红。
11. **`audit` 的 report 现在多两个字段**：`tree.audited_engines` / `tree.not_yet_audited`。
    M4 接线后 `not_yet_audited` 应为 `["attribution", "container"]`；
    `tests/test_determinism.py` 的引擎层双跑已包含 `headers`（M3 改的），M4 要一并加上 `transfer`。
12. **`plan/03` §二 末尾的「M3 落地口径」是回填块**：M4 落地后请按同格式在 §三 回填「M4 落地口径」
    （实现取的那些边界决定必须写清，否则下一棒只能靠读代码）。
13. **K20 的清单已收窄**：`tests/test_cli_contract.py::test_unimplemented_engines_still_fail_loudly`
    现在只断言 `transfer` / `attribution` / `container` 三个模块抛 `EngineNotReady`。
    M4 落地后要**再收窄一次**（删 `transfer` 三条），并在 M4 的交接单里记这一笔。

---

## 三、下一棒待办（M4 传输编码）

按 `plan/03` §三 实现，顺序不得交换：

1. `transfer.py`：`observe_body_shape(body) -> Shape` / `decode_base64` / `decode_qp` /
   `qp_lines` 的自写实现（不引第三方；`base64` 只在测试端做交叉校验）。
   纪律：行宽按 **octets**（不含 CRLF）；字母表外字符**按 RFC 2045 §6.8 忽略并计数**（不违规）；
   QP 非法 `=HH` **原样保留该字节**（不吞字符 —— SO 79133579 的 `=ustomers` 正是被吞的结果）。
2. 11 条 MC-T 规则（`plan/03` §三 表）。`hard` 只给有原句的子项：T05（R8）、T06（R8）、T07（R8 + 推导）。
   其余（T01/T02/T03/T04/T08/T09/T10/T11）按表落 `diff`/`note`。
3. `transfer._RULE_META`（形态同 `scan` / `headers`）+ `rules/catalog.json` 追加 T 簇 +
   `docs/defect-catalog.md` 追加 T 簇（**同轮**改；`tests/test_catalog_doc.py` 与
   `tests/test_catalog_consistency.py` 会自动把漏改抓出来）。
4. `docs/defect-catalog.md` 补 **MC-T07 的推导链 + Q1 的降级开关**（`plan/06` Q1 点名）。
5. `cli.py::_audit()` 加 `transfer` 一趟；同步 `_AUDITED_ENGINES` / `_NOT_YET_AUDITED`；
   `tests/test_determinism.py` 的 `_engine_ledger_bytes` 加上 `transfer`。
6. 新建 `tests/test_golden_engine_transfer.py`：`t-*` 13 个 case 的引擎侧断言
   （比对键 `rule_id`/`path`/`offset`/`class`；负例零缺陷；**规则集合不得被扩大**），
   外加"判定顺序"与"互斥/压账"的构造单元测试（T08 先于 T01；T01 命中时 T02/T03/T04 进 related 或直接不报）。
7. 收窄 `test_unimplemented_engines_still_fail_loudly`（去掉 `transfer` 三条）。
8. 回写 4 处状态副本（M4 → ✅）、`plan/06` 的 G1 与 Q1/R2 相应行、`plan/03` §三 回填「M4 落地口径」、
   写 `plan/HANDOFF-M5.md`，提交。

**M4 完成的判据**：`t-*` 全部 case 引擎侧命中；`catalog.json` 通过原句门禁（`load_catalog()` 不抛，
规则数 = B10 + H12 + T11 = 33）；`docs/defect-catalog.md` 与 catalog 一致；`gen_golden --check` 仍
`51 cases, 0 diff`；全量 `pytest` 全绿；两门 + 变异验证全绿；`git status --porcelain` 为空。

---

## 四、既定口径清单（K 编号 —— "动了会打挂测试"的约定）

> K1–K20 沿用 `HANDOFF-M3` §四（未变，逐条仍然有效）。下面是 M3 新增 / 修订的条目。

| K | 口径 | 打挂它的测试 |
| --- | --- | --- |
| K7（修订） | 行切分**只有一个语义定义**，但有**两份实现**（`scan.split_lines()` 与 `headers._iter_lines()`，因分层不得互相 import）；按 `\n` 切、不吞 `\r`、不把 `\x0b` 当行界 | `test_golden_engine.py::test_split_lines_*`、`test_golden_engine_headers.py::test_line_splitter_matches_scan` |
| K21（新） | **头块内行号**：`headers` 的 `offset_kind="line"` 是头块内行号（从 1 起），不是整文件行号（对根部件二者相同） | `test_golden_engine_headers.py::test_h07_*` / `::test_h_offsets_are_absolute_or_declared_line` |
| K22（新） | **H12 独占折行**：折行 token 上不报 H03/H04/H05；被压掉的规则号只记 H03 进 `related` | `test_golden_engine_headers.py::test_ew_newline_suppresses_h03_and_records_it_as_related` |
| K23（新） | **2231 只在 `Content-Type` / `Content-Disposition` 上判**；三阶段（编号 → 单引号 → `%HH`）**同一参数只记第一条** | `test_golden_engine_headers.py::test_params_are_only_judged_on_parameter_headers`、`::test_2231_stages_stop_at_the_first_failure` |
| K24（新） | **catalog ↔ 代码三源一致**：`MC-B0x` = `scan._RULE_META`，`MC-H0x/1x` = `headers._RULE_META`（M4 追加 `MC-T*` = `transfer._RULE_META`），且 `detector` 必须能在声明模块里解析到 | `tests/test_catalog_consistency.py` |
| K25（新） | **catalog ↔ 人读表一致**：`docs/defect-catalog.md` 的表格行 == catalog 规则数，`class`/`severity` 逐值相同 | `tests/test_catalog_doc.py` |
| K26（新） | **`none-by-design` 哨兵键**：解析为"键存在、原句为空"，与其它降级走同一判据（拿不到 `hard`） | `tests/test_catalog_gate.py`（注入用例）+ `test_catalog_consistency.py` |
| K27（新） | **报告必须声明覆盖面**：`tree.audited_engines` / `tree.not_yet_audited` 与 `cli._AUDITED_ENGINES` / `_NOT_YET_AUDITED` 同步；未接入的层"未参与本次判定" | `test_cli_contract.py::test_headers_engine_is_wired_into_audit` |
| K28（新） | **B 簇与 H 簇缺陷进同一份台账**（`cli._audit()` 合并后一次性 `ledger.build`） | `test_cli_contract.py::test_headers_and_tree_defects_share_one_ledger` |

---

## 五、本机环境坑（实测，2026-10-28）

| 事实 | 命令与输出 | 后果 |
| --- | --- | --- |
| 解释器 | `py -0p` → `3.8-64`（3.8.8）、`3.12-64`（3.12.10） | **3.8 低于本项目下限 3.11，不得用作验证通道** |
| 跑 Python / 测试 | `py -3.12 -X utf8 -m pytest` | 中文控制台编码；`-X utf8` 只管"我们敲的命令" |
| 全量测试耗时 | 约 4 秒（476 条） | 每改一处都跑全量不心疼 |
| **`mimeconform` console script** | `shutil.which('mimeconform')` → `None` | 本机**没有**装过 editable。`python -m mimeconform` 可跑；裸命令要等 M6 的 venv 验证。**别写"裸命令已冒烟"** |
| Git | `2.54.0.windows.1`，`git remote -v` **为空** | 无远端 → 一切"CI 绿"只能写"本地等价校验（未接远端，CI 待首推验证）" |
| **heredoc 写源码会被拦** | `py - <<'PY'` 改 `.py` 文件被 Mimosa 钩子拒绝 | 改源码一律用 Write/Edit 工具；heredoc 只用来跑只读探针 |
| **`data/golden` 体量** | 51 case × 3 件 | 每次 `--check` 重建全量；改骨架函数会让几十个 case 的 `tree_digest` 变红 |

---

## 六、DoD 逐项 checklist（M4）

- [ ] `transfer.py` 自写 base64 / QP：`observe_body_shape` / `decode_base64` / `decode_qp` 可跑，`foreign_chars` 计数、非法 `=HH` 不吞字符
- [ ] 11 条 MC-T 规则；MC-T01 与语义层规则断言永不 `hard`
- [ ] `transfer._RULE_META` + `catalog.json` T 簇 + `docs/defect-catalog.md` T 簇（同轮），规则数 33
- [ ] `docs/defect-catalog.md` 写出 MC-T07 的推导链与 Q1 降级开关
- [ ] `t-*` 13 个 case 引擎侧断言全绿（比对键 `rule_id`/`path`/`offset`/`class`）
- [ ] 负例（合法 base64 76 列折行 / 合法 QP 软换行）零误报；`t-cte-mismatch` 按 `expect_extra.suppressed` 压账
- [ ] CLI 接线 `transfer`，`audited_engines` / `not_yet_audited` 同步；`test_unimplemented_engines_still_fail_loudly` 收窄
- [ ] 全量 `pytest` 全绿；布局门 + 脱敏门 + 变异验证全绿；`gen_golden --check` 0 diff
- [ ] 状态副本 4 处同翻 M4 → ✅；`plan/HANDOFF-M5.md` 落盘并提交

---

## 七、关键命令速查

```bash
# 续接对话第一件事
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/check_desensitized.py

# 全量测试 + 门的变异验证
py -3.12 -X utf8 -m pytest -q
py -3.12 -X utf8 tools/verify_layout_gate.py

# 语料（M1 落地，M2 回填 tree_digest；M3 未动）
py -3.12 -m mimeconform.devtools.gen_golden --check       # → 51 cases, 0 diff
py -3.12 -m mimeconform selftest                          # → 51 cases, 0 问题

# 引擎侧冒烟（M3 起：树与边界 + 头编码）
py -3.12 -m mimeconform audit data/golden/b-inner-dup/msg.eml --format json     # exit 3
py -3.12 -m mimeconform audit data/golden/h-line-998/msg.eml --format json      # exit 3
py -3.12 -m mimeconform audit data/golden/h-ew-long/msg.eml --format json       # exit 2
py -3.12 -m mimeconform audit data/golden/h-ew-newline/msg.eml --format json    # exit 0，MC-H12（related=MC-H03）
py -3.12 -m mimeconform audit data/golden/h-clean-folded/msg.eml --format json  # exit 0，0 缺陷（负例）
py -3.12 -m mimeconform audit data/golden/t-cte-mismatch/msg.eml --format json  # M4 前：exit 0（transfer 未接线）

# 规则目录
py -3.12 -c "from mimeconform.rules import load_catalog; print(len(load_catalog()))"   # → 22

# 干净环境（发布级，M6）
py -3.12 -m venv <dir> && <dir>/Scripts/python.exe -m pip install "setuptools>=68" && \
  <dir>/Scripts/python.exe -m pip install --no-build-isolation ".[dev]"
```
