# HANDOFF-M3 — 进入 M3（头编码）的收尾交接单

> 产出棒：M2（树与边界：`scan.py` + MC-B 系列 + 两棵候选树），2026-10-27。
> 用法：新对话第一件事 = 跑 `py -3.12 tools/check_sprint_layout.py`（见 `AGENTS.md`）。
> **库内一律相对路径**；绝对路径只出现在会话启动命令里。

---

## 一、当前进度 + 证据

**M2 已完成并验证**（状态以 `plan/00` 里程碑表为准；本节的数字是**当轮实测**）。

| 项 | 实测证据 |
| --- | --- |
| 布局门 | `py -3.12 tools/check_sprint_layout.py` → 9 条判据全 PASS，`这轮扫到：files 14 / sections 8 / handoffs 2 / gap_rows 7 / ledger 1 / doc_tools 3` |
| 脱敏门 | `py -3.12 tools/check_desensitized.py` → **160 个文本文件，0 命中**（豁免 2 份） |
| 布局门变异验证 | `py -3.12 tools/verify_layout_gate.py` → **15 组：15 符合预期 / 0 不符** |
| 生成器可重建 | `py -3.12 -m mimeconform.devtools.gen_golden --check` → **`51 cases, 0 diff`**（exit 0） |
| 语料数据级校验 | `py -3.12 -m mimeconform selftest` → **`51 cases, 0 问题`**（exit 0） |
| 全量测试 | `py -3.12 -X utf8 -m pytest` → **362 passed**（M1 时 241；新增 65 条 `test_golden_engine.py` + 引擎层确定性 45 条参数化 + CLI 退出码矩阵 11 条） |
| `tree_digest` 回填 | 51 case 中 **45 个已回填真值**；余 6 个是容器输入（`c-*`：`mail.mbox` / Maildir），按设计留 `null` 到 M5 |
| `b-*` 引擎侧命中 | 11 个 case 全部命中 `expect.json`（比对键 `rule_id`/`path`/`offset`/`class`） |
| 退出码 CLI 级 | 0（`b-clean-nested`）/ 2（`b-boundary-long`）/ 3（`b-inner-dup`）各一条真命令断言 |
| 复现 #69914 | `b-inner-dup`：MC-B06 `hard/major` @ `0.1`；`tree_alternatives` 长度 2；`divergence.path="0.1"`、`offset=276`；标准库实测 **1 条 `StartBoundaryNotFoundDefect`** 由测试重跑验证 |
| 复现 #56141 | `b-wrapped-header`：**零缺陷** + 根切出 2 个子部件（`text/plain` / `text/html`）；标准库 3.12.10 实测 0 defect 亦由测试重跑验证 |

**M3 要做到的东西**：`headers.py` 的 RFC 2047 / 2231 语法审计 + MC-H 系列 12 条 +
`rules/catalog.json` 与 `docs/defect-catalog.md` 落盘 + 复现 SO 44154520 / SO 52442469；
`h-*` 12 个 case 的引擎侧断言。

---

## 二、当前事实·状态不变量（下一棒动手前必须知道，否则一定会踩）

1. **`scan.py` 的 `_RULE_META` 是 MC-B 系列的 class/severity/rfc 唯一定义点**。M3 落地
   `catalog.json` 时，`MC-B0x` 的这五个字段**必须与 `_RULE_META` 逐值一致**，否则同一个
   rule_id 在代码与 catalog 里各说一套 —— 建议直接加一条测试断言二者相等。
2. **`gen_golden.py` 的自检仍是闸门**：`build()` 里 `_collect()` → 逐 case `_self_check()`
   → `_check_clusters()` → 才写盘。改语料后**必须先跑 `--check`**。
3. **`tree_digest` 现在是真值**（M1 时恒 `null`）。它由 `_tree_digest_for(infile, data)` 产出：
   **`.eml` 输入走 `scan_message`，容器输入返回 `None`**。M3 若调整 `scan.py` 的建树语义
   （例如改 `body_range` / `body_sha256` 口径），**45 个 case 的 `tree_digest` 会全量变红** ——
   那是"解析变了"的正确信号，重跑生成器即可，但**不许**为了让 `--check` 变绿去改算法。
4. **`MC-B05` 与 `MC-B06` 是互斥口径**（M2 新定，已写进 `plan/03` §一"假阳风险"之后）：
   父 multipart 的子节点里若有"复用 boundary 并吸收父区域余量"的节点，**父级不再登记 B05**。
   `b-inner-dup` 因此只出 MC-B06 一条。M3 不受影响，但别在别的模块里把它"补回来"。
5. **`--strict-depth` 只提 severity、不改 class**（§7.6）：`gray` 永远不是条款判定。
   `tests/test_golden_engine.py::test_deep_nest_strict_depth_escalates_severity_only` 锁住这一点。
6. **`headers.py` 的 `Header.encoded_words` / `Header.params` 现在恒为空**：`scan.py`
   只做头块**定位**（名字 / 值字节 / 行跨度 / 偏移），语法审计属 M3。M3 有两种落法：
   ① 在 `parse_headers()` 里独立解析原始头块；② 让 `scan.py` 回填这两个字段。
   **建议 ①**：`scan.py` 的契约（`plan/02` §二）只讲树与边界，让 M3 从
   `Node.headers[i].line_spans` 回去取字节即可（`line_spans` 已是文件绝对偏移）。
7. **`plan/03` §二 的 H 簇表里 `MC-H03` 被判 `hard`**，依据是 R1 所在节（§2）的形态定义，
   **不是** §6.2（那一条未录）。落地时 `catalog.json` 的 `ledger_key` 必须写
   `RFC2047-2#ew-inner-space-forbidden`（机读台账里该子项 `recorded=true`），
   **不要**写 `RFC2047-6.2#adjacent-ew-lwsp-ignored`（那是 `recorded=false`，会被门禁打红）。
8. **`b-wrapped-header` 的折叠头是合法形态**：`scan.py` 把续行并入前一个头、`raw_value`
   含内部 CRLF。M3 判 `MC-H12`（encoded-word 内折行）时，**必须**能吃这种"值里带 CRLF"的
   原始字节，且与 `MC-H03` 互斥（§7.5 第 2 条）。`h-ew-newline` 的 `expect_extra` 已写明
   `no_double_record: True` + `related: ["MC-H03"]`。
9. **`c-*` 六个 case 的 `tree_digest` 仍是 `null`**：容器输入由 M5 的容器入口切分后
   **逐条消息**建树。M5 回填时**不要**把整个 mbox 喂给 `scan_message` —— 那会得到一个
   "切分前"的伪树，等于给 M5 埋一个假绿（`_tree_digest_for` 的 docstring 已写这条）。
10. **`audit` 只接受单封 `.eml`**：传目录会得到 `UsageError`（"容器层自 M5 起支持"）。
    `--container` / `--mbox-variant` 两个参数**已存在且被 parser 接受**，但当前不影响行为
    —— M5 接线前它们是"接受但未生效"，README 已如实写明。
11. **两处实测修正（与首稿计划不符，已按实测落）**：
    - `b-inner-dup`（#69914）：3.12.10 实测报 **1 条 `StartBoundaryNotFoundDefect`**，
      **不是**"标准库 0 defect"。`plan/03` §一 的验收句已按实测改写（M2 同轮）。
    - `b-wrapped-header`（#56141）：3.12.10 实测标准库**已修复**（0 defect）→ 本 case 是**负例**。
12. **`plan/03` §四 的 A03/A04/A05/A07 severity 仍是 `note`**（M1 裁决）；M5 落地 catalog 时沿用。
13. **`_mixed_with_attachment` / `_mixed_parts` / `_leaf` / `_plain_headers` / `_part` 是生成器骨架**
    （boundary 固定 `mix1` / `rel1`）：改它们会同时动几十个 case 的字节，`--check` 会全量变红。
14. **`expect.json` 的 defects 是 `Defect.as_json()` 形态**（键名 `class`，不是 `klass`）。
15. **非 ASCII 与引号**：生成器源码里的中文引号必须用 `「」`，ASCII `"` 会提前闭合字符串。
16. **状态副本 4 处**（`plan/00` 里程碑表、`plan/00` 台账、`plan/05` 状态表、`README` 状态表）
    翻状态要同轮。台账里写"待后续三棒"这类**不带 M 号**的措辞，才能不触发 `LAYOUT.LEDGER`
    （该门会把已 ✅ 里程碑的 M 号当成"仍挂未完成"）。
17. **`tools/verify_layout_gate.py` 的 M07 marker 已改为 `| G1 | 规则判定实现 |`**（前缀匹配）：
    M2 同轮改了 G1 行的内容，marker 必须同步 —— 改 `plan/06` 缺口行时记得一起改。

---

## 三、下一棒待办（M3 头编码）

按 `plan/03` §二实现，顺序不得交换：

1. `headers.py` 的 `parse_headers(raw_header_block, base_offset)`：按 §7.5 第 1–2 条
   **先**判头行 > 998（MC-H07）→ **再**判 encoded-word 跨行（MC-H12）→ **最后**判内空白（MC-H03）；
   命中 H12 即**不**报 H03，被压掉的规则号进 `related`。
2. 12 条 MC-H 规则。`hard` 只能给有原句的子项：H01（R1 全录）/ H02（R2 全录）/ H03（§2 形态，
   `ew-inner-space-forbidden` 子项）/ H06（R4 §5 全录）/ H07（R5 全录）。其余（H04/H05/H08/H09/H10/H11/H12）
   按 `plan/03` §二 的表落 `diff/note`。
3. `rules/catalog.json` 落盘：B 簇 10 条 + H 簇 12 条（M4/M5 的簇在各自里程碑加）。
   `MC-B0x` 的五个字段必须与 `scan._RULE_META` 逐值一致（见 §二.1）。
4. `docs/defect-catalog.md` 与 `catalog.json` 规则数一致（机器断言，`plan/05` §二 M3 DoD）。
5. `decode_filename(params, raw_value)`：本棒只做 RFC 2231 合并 + 2047 解码的**顺序骨架**
   （D10：先 2231 后 2047）；真正的取值调用点在 M5 的 attribution，本棒只需可被单测。
6. 让 `h-*` 12 个 case 的引擎侧断言通过（扩展 `tests/test_golden_engine.py` 或新建
   `tests/test_golden_engine_headers.py`，比对键仍是 `rule_id`/`path`/`offset`/`class`）。
7. **`tests/test_catalog_gate.py::test_real_catalog_is_absent_and_reports_cleanly` 会转 skip**
   （`catalog.json` 一旦存在该测试自动跳过）。确认它确实转成 skip 而不是红。
8. 回写 4 处状态副本（M3 → ✅）、`plan/06` 的 G1 与 Q2/R1/R2 相应行、写 `plan/HANDOFF-M4.md`，提交。

**M3 完成的判据**：`h-*` 全部 case 引擎侧命中；`catalog.json` 通过原句门禁（`load_catalog()` 不抛）；
`docs/defect-catalog.md` 与 catalog 规则数一致；`gen_golden --check` 仍 `51 cases, 0 diff`；
`git status --porcelain` 为空。

---

## 四、既定口径清单（K 编号 —— "动了会打挂测试"的约定）

| K | 口径 | 打挂它的测试 |
| --- | --- | --- |
| K1 | 数值口径只有一处：`data/README.md` §七；代码常量只在 `mimeconform/constants.py` | 全仓无第二处定义；新增阈值必须先进 §七 |
| K2 | `class` 三值 / `severity` 四档的代码侧来源只有 `constants.CLASSES` / `SEVERITIES` | `test_ledger_invariants.py`、`test_catalog_gate.py` |
| K3 | 指纹算法按 `data/README` §7.8 逐字实现，键序固定，**不含 `detail`** | `test_ledger_invariants.py::test_fingerprint_ignores_detail_wording`、`test_generator_check.py::test_fingerprint_is_reproducible` |
| K4 | 退出码 `--fail-on` **只会更严**，永不推翻 major/blocker → 3 | `test_exit_codes.py::test_fail_on_never_softens_baseline`、`test_cli_contract.py::test_audit_fail_on_can_be_stricter_but_never_softer` |
| K5 | `argparse` 的用法错误一律映射为 **1**（不是 argparse 自带的 2） | `test_cli_contract.py`（未知子命令 / 缺参 / 坏枚举 / 零 max-depth 各一条） |
| K6 | 路径语法：`0` / `0.1` / `msg#3` / `msg#3/0.1`；`msg#n` 的 n 从 1 起 | `test_ledger_invariants.py::test_path_*` |
| K7 | 行切分只走 `scan.split_lines()`（按 `\n`，不吞 `\r`，不把 `\x0b` 当行界；`end` 限定窗口） | `test_golden_engine.py::test_split_lines_does_not_split_on_bare_cr_or_vt`、`::test_split_lines_offsets_are_absolute` |
| K8 | `SEMANTIC_RULES` == `data/README` §7.1 升级禁令列表；**golden 里也不许把它们标 hard** | `test_catalog_gate.py::test_semantic_rules_set_covers_the_documented_families`、`test_generator_check.py::test_semantic_rules_never_claim_hard` |
| K9 | `ENGINE_MODULES` 是守门的显式清单，新增模块必须同步 | `test_engine_guards.py` |
| K10 | 脱敏门扫描面收编规则：`.gitignore` 声明的本地产物目录必须在 `SKIP_DIRS` 有对应项 | `test_gates.py::test_desensitized_skips_local_artifacts` |
| K11 | 布局门判据 id 集合固定（9 条），改门必须同改 `test_gates.py` 的期望集合 | `test_gates.py::test_layout_gate_reports_every_check` |
| K12 | 状态副本 4 处 + 每副本命中行数必须 > 0 | `LAYOUT.STATUS` + `test_gates.py::test_layout_gate_status_copies_all_contribute_rows` |
| K13 | **语料只由生成器产出**：`data/golden/**` 三件必须与 `--check` 位级一致，手改语料即红 | `test_generator_check.py::test_build_into_temp_dir_matches_repo_corpus`、`::test_check_detects_a_single_byte_change` |
| K14 | **矩阵下界**：b/h/t/a/c 每簇 ≥2 正例 + ≥1 负例；case 数 51 固定 | `gen_golden._check_clusters`（在 `build()` 内）、`test_generator_check.py::test_every_case_has_exactly_three_files` |
| K15 | **镜像同源**：`data/README` §三 与人读台账、`data/rfc-ledger.json` 三处 `(RFC号, 节号)` 集合相等 | `test_ledger_mirror.py` |
| K16（新） | **引擎侧比对键 = `rule_id`/`path`/`offset`/`class`，且 `rule_id` 集合不得被扩大**（不比 severity） | `test_golden_engine.py::test_b_cluster_matches_expectation`、`::test_b_cluster_has_no_stray_notes` |
| K17（新） | **`tree_digest` 是引擎真值**：`.eml` 输入必须非 null 且可复算；容器输入留 null 到 M5 | `test_golden_engine.py::test_b_cluster_tree_digest_is_reproducible`、`test_determinism.py::test_engine_double_run_is_byte_identical` |
| K18（新） | **MC-B05 × MC-B06 互斥**：复用 boundary 的父 multipart 不再登记 B05 | `test_golden_engine.py::test_b_cluster_matches_expectation`（`b-inner-dup` 只一条） |
| K19（新） | **`--strict-depth` 只提 severity（note→minor），`class` 恒为 `gray`** | `test_golden_engine.py::test_deep_nest_strict_depth_escalates_severity_only` |
| K20（新） | **骨架期语义的活口**：`audit` 不再抛未就绪，但未实现的四个模块必须继续抛 `EngineNotReady` | `test_cli_contract.py::test_unimplemented_engines_still_fail_loudly` |

---

## 五、本机环境坑（实测，2026-10-27）

| 事实 | 命令与输出 | 后果 |
| --- | --- | --- |
| 解释器 | `py -0p` → `3.8-64`（3.8.8）、`3.12-64`（3.12.10） | **3.8 低于本项目下限 3.11，不得用作验证通道** |
| 跑 Python | `py -3.12 -X utf8 <cmd>` | 中文控制台编码；`-X utf8` 只管"我们敲的命令" |
| PyYAML | `py -3.12 -c "import yaml"` → `6.0.3` | 已装；CI 必须靠 `[dev]` 声明 |
| Node | `node --version` → `v24.15.0` | 本项目**不用** Node（两道门是 Python 标准库实现） |
| Git | `2.54.0.windows.1`，`git remote -v` **为空** | 无远端 → 一切"CI 绿"只能写"本地等价校验（未接远端，CI 待首推验证）" |
| **`mimeconform` console script** | `shutil.which('mimeconform')` → `None`；`pip show mimeconform` → 未安装 | 本机**没有**装过 editable。`python -m mimeconform` 可跑；裸命令要等 M6 的 venv 验证。**别写"裸命令已冒烟"** |
| 建立 venv | `py -3.12 -m venv <dir>` | 3.12 的 venv 不再自带 setuptools：先装 `setuptools>=68` 再 `--no-build-isolation` |
| pip 代理 | 系统代理可能污染 pip | 用 `NO_PROXY="*" no_proxy="*"` + 镜像 |
| **heredoc 写源码会被拦** | `py - <<'PY'` 改 `.py` 文件被 Mimosa 钩子拒绝 | 改源码一律用 Write/Edit 工具，不要用重定向写文件 |
| **heredoc 里的 `\b` / `\d`** | 用 heredoc 生成测试代码时 `\b`、`\[` 被吃 | 正则字面量用 Edit 工具写，或写双反斜杠 |
| **`data/golden` 体量** | `find data/golden -type f \| wc -l` → **153** | 每次 `--check` 重建 51 case；改骨架函数会让几十个 case 的 `tree_digest` 变红 |

---

## 六、DoD 逐项 checklist（M3）

- [ ] `headers.py` 实现 `parse_headers()`，判定顺序 §7.5 第 1–2 条写死并被测试锁住
- [ ] 12 条 MC-H 规则；H12 命中时**不**报 H03，被压掉的进 `related`
- [ ] `rules/catalog.json` 落盘（B 10 + H 12），`MC-B0x` 与 `scan._RULE_META` 逐值一致
- [ ] `docs/defect-catalog.md` 与 `catalog.json` 规则数一致（机器断言）
- [ ] `load_catalog()` 通过原句门禁；`test_real_catalog_is_absent_and_reports_cleanly` 转为 skip
- [ ] `h-*` 12 个 case 引擎侧断言全绿（比对键 `rule_id`/`path`/`offset`/`class`）
- [ ] `h-ew-newline` 与 MC-H03 互斥被断言（`related` 含 `MC-H03`）
- [ ] `h-2231-seq` / `h-ew-newline` 的复现断言按题面口径（看 rule_id 与偏移，不看 severity）
- [ ] 全量 `pytest` 全绿；布局门 + 脱敏门 + 变异验证全绿
- [ ] 状态副本 4 处同翻 M3 → ✅；`plan/HANDOFF-M4.md` 落盘并提交

---

## 七、关键命令速查

```bash
# 续接对话第一件事
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/check_desensitized.py

# 全量测试 + 门的变异验证
py -3.12 -X utf8 -m pytest -q
py -3.12 -X utf8 tools/verify_layout_gate.py

# 语料（M2 已回填 tree_digest）
py -3.12 -m mimeconform.devtools.gen_golden --check       # → 51 cases, 0 diff
py -3.12 -m mimeconform selftest                          # → 51 cases, 0 问题
py -3.12 -m mimeconform.devtools.gen_golden               # 写了语料就重跑这个

# 引擎侧冒烟（M2 起可跑）
py -3.12 -m mimeconform audit data/golden/b-inner-dup/msg.eml --format json     # exit 3
py -3.12 -m mimeconform audit data/golden/b-clean-nested/msg.eml --format json  # exit 0
py -3.12 -m mimeconform audit data/golden/b-no-final/msg.eml --format md        # exit 0
py -3.12 -m mimeconform --version                                              # exit 0

# 干净环境（发布级，M6）
py -3.12 -m venv <dir> && <dir>/Scripts/python.exe -m pip install "setuptools>=68" && \
  <dir>/Scripts/python.exe -m pip install --no-build-isolation ".[dev]"
```
