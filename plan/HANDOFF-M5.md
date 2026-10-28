# HANDOFF-M5 — 进入 M5（归属与容器）的收尾交接单

> 产出棒：M4（传输编码：`transfer.py` + MC-T 11 条 + `rules/catalog.json` / `docs/defect-catalog.md` 扩到 33 条），2026-10-28。
> 用法：新对话第一件事 = 跑 `py -3.12 tools/check_sprint_layout.py`（见 `AGENTS.md`）。
> **库内一律相对路径**；绝对路径只出现在会话启动命令里。

---

## 一、当前进度 + 证据

**M4 已完成并验证**（状态以 `plan/00` 里程碑表为准；本节的数字是**当轮实测**）。

| 项 | 实测证据 |
| --- | --- |
| 布局门 | `py -3.12 tools/check_sprint_layout.py` → 9 条判据全 PASS，`这轮扫到：files 14 / sections 8 / handoffs 4 / gap_rows 8 / ledger 1 / doc_tools 3` |
| 脱敏门 | `py -3.12 tools/check_desensitized.py` → **168 个文本文件，0 命中**（豁免 2 份） |
| 布局门变异验证 | `py -3.12 -X utf8 tools/verify_layout_gate.py` → **15 组：15 符合预期 / 0 不符** |
| 全量测试 | `py -3.12 -X utf8 -m pytest` → **561 passed, 1 skipped**（M3 时 476 passed；新增 `test_golden_engine_transfer.py` 71 条 + `test_catalog_consistency.py` 新增 T 簇断言） |
| 生成器可重建 | `py -3.12 -m mimeconform.devtools.gen_golden --check` → **`51 cases, 0 diff`**（exit 0；`data/golden/**` 未改，`--check` 全量重建逐字节一致） |
| 语料数据级校验 | `py -3.12 -m mimeconform selftest` → **`51 cases, 0 问题`**（exit 0） |
| `t-*` 引擎侧 | 13/13 case 命中（比对键 `rule_id`/`path`/`offset`/`class`）；11 正例、2 负例零误报 |
| 误报面 | 38 个非 t 簇 `.eml` case 上 `audit_transfer` **零 T 缺陷**（`tests/test_golden_engine_transfer.py::test_other_clusters_have_no_transfer_defects`） |
| CLI 级退出码（t 簇） | `t-qp-artifact` → 3；`t-qp-long` / `t-qp-soft` → 2；其余 → 0（与各自 `expect.json` 一致） |
| 复现 SO 79133579 | `t-qp-artifact`：MC-T07 `hard/major` ×3，`=us`/`=o:`/`=ur` **各记一条**、精确到字节偏移；非法转义原样保留不吞字符 |
| 复现 SO 6029218 | `t-b64-len`：MC-T03 `diff/note` @ 正文首字节（R9 长度子项未录 → 门禁降级） |
| catalog 门禁 | `load_catalog()` 返回 **33 条**（B 10 + H 12 + T 11）全部过原句门禁 |
| 文档一致性 | `docs/defect-catalog.md` 与 catalog 规则数、`class`、`severity` 机器对账（`tests/test_catalog_doc.py`）；MC-T07 推导链 + Q1 降级开关写进 §4.2 |
| 三源一致 | `tests/test_catalog_consistency.py` 的 `_META_MODULES` 现为 `{scan, headers, transfer}`，三份 `_RULE_META` 与 catalog 逐值一致（正/反向覆盖） |
| CLI 接线 | `audited_engines == ["scan", "headers", "transfer"]`；`not_yet_audited == ["attribution", "container"]`（`tests/test_cli_contract.py`） |

**M5 要做到的东西**：`attribution.py` 的 8 条 MC-A 系列 + `container.py` 的 5 条 MC-C 系列
（`plan/03` §四 / §五）+ 复现 SO 6255202 / SO 12816042 / cpython #93376 + `a-*` 9 个 case 与
`c-*` 6 个 case 的引擎侧断言 + **把 A / C 两簇写进 `catalog.json` 与 `docs/defect-catalog.md`（同轮）** +
把 `filename` 取值顺序（先 2231 后 2047，D10）落成可测入口 + mbox 三变体切分表并出（`split_variants`，
`offset_kind="message-relative"`）+ CLI 接线 `attribution` / `container`
（`--container` / `--mbox-variant` 自此生效）。

---

## 二、当前事实·状态不变量（下一棒动手前必须知道，否则一定会踩）

1. **`rules/catalog.json` 现在是"三源一致"的一环**：`MC-B0x` ↔ `scan._RULE_META`、`MC-H0x/1x` ↔
   `headers._RULE_META`、`MC-T*` ↔ `transfer._RULE_META` —— `tests/test_catalog_consistency.py` 双向断言
   （代码有而 catalog 没有也会红）。**M5 落地 A / C 簇时同样要在 `attribution.py` / `container.py` 里各建
   一份 `_RULE_META`**，并把 `"attribution"` / `"container"` 加进该测试的 `_META_MODULES` 清单。
2. **`SEMANTIC_RULES` 已含 `MC-A01`–`A08` 与 `MC-C01`–`C05`**（`mimeconform/rules/__init__.py`）：
   这些规则**永不 `hard`**（D11：`Content-Disposition` / `multipart/related` / mbox 均不在五部 RFC 内）。
   `tests/test_catalog_gate.py::test_semantic_rules_set_covers_the_documented_families` 断言名字集合，
   新增/改名会红。A / C 全部落 `diff/note`（golden 亦如此）。
3. **`none-by-design` 是哨兵键，不是豁免**：A 簇缺 `Content-ID` / B 类归属问题等凡无条款可引者，
   `ledger_key = "none-by-design"`，门禁解析成"键存在、原句为空" → 只能 `diff`/`gray` + `note`。
   **别把哨兵用在有原句可引的规则上。**
4. **接线点只有一个**：`mimeconform/cli.py::_audit()`。M5 要在这里加 `attribution` / `container` 两趟，
   并同步改 `_AUDITED_ENGINES` / `_NOT_YET_AUDITED`
   —— `tests/test_cli_contract.py::test_headers_engine_is_wired_into_audit` 与
   `::test_transfer_engine_is_wired_into_audit` 断言这两个元组，**改一处不改另一处会红**（故意的）。
   注意：`_NOT_YET_AUDITED` 在 M5 落地后应为 **空元组**（五模块全接入），`report.py` 对空列表不出"尚未接入"行。
5. **`--container` / `--mbox-variant` 目前是"能解析但未生效"**：`cli._read_input` 对目录显式报
   "容器层自里程碑 M5 起支持"，`audit` 只走单封路径。M5 要把容器输入接进来（`.mbox` / Maildir，
   `offset_kind="message-relative"`），并让 `--mbox-variant` 决定"主表"是哪一份、**同时输出 `split_variants`**。
6. **`filename` 取值顺序 D10 不可交换**（`plan/00` D10）：先 RFC 2231（含续行合并）→ 再 RFC 2047。
   `headers.decode_filename(params, raw_value)` 已实现并被 `test_golden_engine_headers.py` 单测；
   M5 的 `attribution.py` 是它的**调用点**（属具名验收项）。
7. **两种"并出"是硬性报告要求**：MC-B06（复用 boundary）必须并出**两棵候选树**；MC-C02（`>From` 变体）
   必须并出**三变体切分表**（`plan/03` §五、`data/README` §7.7）。二者已由 `test_golden_engine.py` /
   `test_golden_engine_transfer.py` 同风格断言 —— M5 照抄结构。
8. **容器输入不进单封扫描**：`gen_golden._tree_digest_for(infile, data)` 对 `mail.mbox` / Maildir 返回
   `None`（`data/golden/c-*/expect.json` 的 `tree_digest` 现在是 `null`）。
   **M5 若要回填容器 `tree_digest`**：改 `_tree_digest_for` 的容器分支（**别碰** `_mixed_with_attachment` /
   `_leaf` / `_plain_headers` 等骨架函数，那会动几十个 eml case 的字节）→ 用生成器**写模式重建** c-* 的
   `expect.json` → `--check` 必须仍 `51 cases, 0 diff`。这是本棒唯一预期会改 `data/golden/**` 的地方。
9. **`a-*` / `c-*` 的 `expect.json` 是 M1 手写常量**（K13 锁 `--check` 逐字节一致）：
   `defect_count` / `exit_code` / `fingerprint` 由构造算出，`tree_digest`（eml）由引擎回填。
   **不要为了让语料凑齐去改生成器骨架**；`a-*` 里缺哪条规则就让引擎去补，不是让语料补。
10. **`audit_transfer` 的形态口径（M4 定，A 簇复用）**：`observe_body_shape` 的 `binary` 判据是"含 >= 0x80
    的八位组" —— 但**叶节点正文不是唯一天地**：A 簇要读头参数（`Content-Disposition` / `Content-ID` /
    `Content-Type` 的 `name`），落点常在**头部**而非正文。MC-A* 的 `offset` 口径写死在 golden（多为
    正文或头行首），落地前先读 `a-*/expect.json` 的 `offset` + `path` 对齐。
11. **分层**：`attribution.py` / `container.py` 只可 import 基础设施 + 其下层；`attribution` 可 import
    `headers`（`filename` 取值），**不得** import `scan`（`test_engine_guards.py::test_scan_does_not_import_higher_layers`
    只查 `scan`，但同类纪律适用于 `attribution`/`container`）。行切分若需要，走 K7 的"本地等价实现 + 交叉断言"。
12. **`report.py` 零判定**：`attribution` / `container` 的判定不得进 `report.py`；报告只搬运
    `ledger` 与 `tree_info`（`test_engine_guards.py::test_report_has_no_engine_imports` 断言）。
13. **M4 新增的两处 catalog 门禁副作用**：① `tests/test_catalog_consistency.py::test_catalog_is_not_empty`
    的下界已提到 **>= 33**（M5 再加 13 条 → 46）；② `test_class_distribution_is_what_the_plan_says`
    现同时断言 B / H / T 三簇的 `hard` 集合，M5 若加 A / C 断言请**同步扩这一段**（A/C 全 `hard` 为空的显式证据）。

---

## 三、下一棒待办（M5 归属与容器）

按 `plan/03` §四 / §五 实现，顺序不得交换：

1. `attribution.py`：8 条 MC-A（全 `diff/note`）。入口建议照 `audit_headers` / `audit_transfer` 的形态
   写一个 `audit_attribution(root, data) -> tuple[Defect, ...]`（遍历树，逐叶节点判归属/引用）；
   `filename` 取值调 `headers.decode_filename`（**顺序 2231 → 2047，D10**，写死并用单测锁）。
2. `container.py`：5 条 MC-C（全 `diff`）。`split_container(data, variant) -> ...` 三变体切分表
   （`mboxo` / `mboxrd` / `mboxcl`），`auto` 按 §7.7 纯字节规则只决定"主表"；
   `offset_kind="message-relative"`（容器层），文件级偏移另记 `file_offset`。
3. `attribution._RULE_META` + `container._RULE_META`（形态同 `scan` / `headers` / `transfer`）
   + `rules/catalog.json` 追加 A / C 簇 + `docs/defect-catalog.md` 追加 A / C 簇（**同轮**改；
   `test_catalog_doc.py` 与 `test_catalog_consistency.py` 会自动把漏改抓出来）。规则数 → **46**。
4. `cli.py::_audit()` 加 `attribution` / `container` 两趟；同步 `_AUDITED_ENGINES`（→ 5 个）与
   `_NOT_YET_AUDITED`（→ 空）；`tests/test_determinism.py` 的 `_engine_ledger_bytes` 加上两个模块。
5. 容器输入接线：`_read_input` 支持 `.mbox` / Maildir 目录；`--mbox-variant` 生效并输出 `split_variants`；
   `--container` 语义落 `offset_kind="message-relative"`；CLI 退出码矩阵补容器输入一条。
6. 新建 `tests/test_golden_engine_attribution.py` / `tests/test_golden_engine_container.py`：
   `a-*` 9 个 / `c-*` 6 个 case 的引擎侧断言（比对键 `rule_id`/`path`/`offset`/`class`；负例零缺陷；
   **规则集合不得被扩大**），外加构造单元测试（归属三态、cid 双向闭合、`related` 的 `start`/`type` 比对、
   mbox 三变体切分表、`auto` 规则）。
7. 收窄 `test_engine_guards` 无关项；M5 后 `test_unimplemented_engines_still_fail_loudly` 应删空
   （五模块全落地 → 该测试的"仍未实现"面为空，应改为"空起点"或移除并说明）。
8. 回写 4 处状态副本（M5 → ✅）、`plan/06` 的 G1 / R2 相应行、写 `plan/HANDOFF-M6.md`，提交。

**M5 完成的判据**：`a-*` / `c-*` 全部 case 引擎侧命中；`catalog.json` 通过原句门禁（规则数 = 46）且
`docs/defect-catalog.md` 与之一致；`gen_golden --check` 仍 `51 cases, 0 diff`（若回填容器 `tree_digest`
则须先重建再核对）；全量 `pytest` 全绿；两门 + 变异验证全绿；`git status --porcelain` 为空。

---

## 四、既定口径清单（K 编号 —— "动了会打挂测试"的约定）

> K1–K28 沿用 `HANDOFF-M4` §四（未变，逐条仍然有效）。下面是 M4 新增的条目。

| K | 口径 | 打挂它的测试 |
| --- | --- | --- |
| K29（新） | **CTE 判定顺序 §7.5 第 5 条**：先判声明值是否已知（T08）→ 再判声明形态 → 最后判 declared vs observed；**未知声明时不做任何交叉校验** | `test_golden_engine_transfer.py::test_unknown_cte_precedes_cross_check_and_suppresses_everything`、`t-cte-unknown` |
| K30（新） | **MC-T01 只在声明 `base64` 时判**（其它声明是兼容性超集）；命中时**压掉 MC-T02/T03/T04** | `::test_declared_base64_but_observed_text_emits_t01_only`、`t-cte-mismatch` 的 `expect_extra.suppressed` |
| K31（新） | **含非法转义（T07）的 QP 行不再记行宽（T05）**：非法行已不是合法 encoded line | `::test_qp_line_width_is_not_recorded_on_a_line_with_an_illegal_escape`、`t-qp-artifact` |
| K32（新） | **MC-T04 是 `hard`/`note`**：R9 的字母表外字符子项**全录** → 证据强度 hard；但"须忽略"→ 现象不违规 → severity note（`class` 与 `severity` 正交） | `test_catalog_consistency.py::test_class_distribution_is_what_the_plan_says`（`hard_t == ["MC-T04","MC-T05","MC-T06","MC-T07"]`） |
| K33（新） | **`observed_shape` 分界线 = 行内是否有 SP/TAB**：无空白且全 ASCII ⇒ `base64`（字母表外字符忽略、仍算 base64）；有空白且含 `=` ⇒ `qp`；含 8bit ⇒ `binary` | `test_golden_engine_transfer.py::test_observe_body_shape_classifies_the_documented_kinds`、`t-cte-mismatch` |
| K34（新） | **transfer 只跳过 `multipart/*` 节点的正文**（其"正文"是 delimiter 拼装，非编码产物）；`message/rfc822` 等非 multipart 节点照审 | `::test_other_clusters_have_no_transfer_defects`（a-rfc822 不得误报） |

---

## 五、本机环境坑（实测，2026-10-28；M4 未新增坑）

| 事实 | 命令与输出 | 后果 |
| --- | --- | --- |
| 解释器 | `py -0p` → `3.8-64`（3.8.8）、`3.12-64`（3.12.10） | **3.8 低于本项目下限 3.11，不得用作验证通道** |
| 跑 Python / 测试 | `py -3.12 -X utf8 -m pytest` | 中文控制台编码；`-X utf8` 只管"我们敲的命令" |
| 全量测试耗时 | 约 4–5 秒（561 条） | 每改一处都跑全量不心疼 |
| **`mimeconform` console script** | `shutil.which('mimeconform')` → `None` | 本机**没有**装过 editable。`python -m mimeconform` 可跑；裸命令要等 M6 的 venv 验证。**别写"裸命令已冒烟"** |
| Git | `2.54.0.windows.1`，`git remote -v` **为空** | 无远端 → 一切"CI 绿"只能写"本地等价校验（未接远端，CI 待首推验证）" |
| **heredoc 写源码会被拦** | `py - <<'PY'` 改 `.py` 文件被 Mimosa 钩子拒绝 | 改源码一律用 Write/Edit 工具；heredoc 只用来跑只读探针 |
| 测试摘要行常被控制台吞 | `pytest` 末尾的 `N passed` 有时不打印 | 用 `pytest > 文件 2>&1` 再 `grep -a passed` 看真值（退出码仍是准的） |
| **`data/golden` 体量** | 51 case × 3 件 | 每次 `--check` 重建全量；改骨架函数会让几十个 case 的 `tree_digest` 变红 |

---

## 六、DoD 逐项 checklist（M5）

- [ ] `attribution.py` 8 条 MC-A（全 `diff/note`）；`filename` 取值顺序 2231 → 2047 写死并有单测
- [ ] `container.py` 5 条 MC-C；三变体切分表同时输出；`auto` 规则按 §7.7 纯字节判定；`offset_kind="message-relative"`
- [ ] `attribution._RULE_META` / `container._RULE_META` + `catalog.json` A/C 簇 + `docs/defect-catalog.md` A/C 簇（同轮），规则数 46
- [ ] `a-*`（9）/ `c-*`（6）全部 case 引擎侧断言全绿（比对键 `rule_id`/`path`/`offset`/`class`）
- [ ] 负例（`a-clean-mixed` / `c-clean-mbox`）零误报；正例规则集合不被扩大
- [ ] CLI 接线 `attribution` / `container`，`audited_engines` 5 个 / `not_yet_audited` 空；容器输入与 `--mbox-variant` 生效
- [ ] `catalog.json` `load_catalog()` 不抛，规则数 = 46；A/C 全 `diff`/`gray`
- [ ] 全量 `pytest` 全绿；布局门 + 脱敏门 + 变异验证全绿；`gen_golden --check` 0 diff
- [ ] 状态副本 4 处同翻 M5 → ✅；`plan/HANDOFF-M6.md` 落盘并提交

---

## 七、关键命令速查

```bash
# 续接对话第一件事
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/check_desensitized.py

# 全量测试 + 门的变异验证
py -3.12 -X utf8 -m pytest -q
py -3.12 -X utf8 tools/verify_layout_gate.py

# 语料（M1 落地，M2 回填 eml 的 tree_digest；M4 未动）
py -3.12 -m mimeconform.devtools.gen_golden --check       # → 51 cases, 0 diff
py -3.12 -m mimeconform selftest                          # → 51 cases, 0 问题

# 引擎侧冒烟（M4 起含传输编码）
py -3.12 -m mimeconform audit data/golden/t-qp-artifact/msg.eml --format json   # exit 3，MC-T07 ×3
py -3.12 -m mimeconform audit data/golden/t-qp-long/msg.eml --format json       # exit 2，MC-T05
py -3.12 -m mimeconform audit data/golden/t-qp-soft/msg.eml --format json       # exit 2，MC-T06
py -3.12 -m mimeconform audit data/golden/t-cte-mismatch/msg.eml --format json  # exit 0，MC-T01（压掉 T02/T03/T04）
py -3.12 -m mimeconform audit data/golden/t-b64-foreign/msg.eml --format json   # exit 0，MC-T04 hard/note
py -3.12 -m mimeconform audit data/golden/t-clean-b64/msg.eml --format json     # exit 0，0 缺陷（合法 base64 折行）
py -3.12 -m mimeconform audit data/golden/t-clean-qp/msg.eml --format json      # exit 0，0 缺陷（合法 QP 软换行）

# 规则目录
py -3.12 -c "from mimeconform.rules import load_catalog; print(len(load_catalog()))"   # → 33

# 干净环境（发布级，M6）
py -3.12 -m venv <dir> && <dir>/Scripts/python.exe -m pip install "setuptools>=68" && \
  <dir>/Scripts/python.exe -m pip install --no-build-isolation ".[dev]"
```