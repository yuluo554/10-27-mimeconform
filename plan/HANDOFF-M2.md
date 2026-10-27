# HANDOFF-M2 — 进入 M2（树与边界）的收尾交接单

> 产出棒：M1（数据先行：golden 语料 + 生成器），2026-10-27。
> 用法：新对话第一件事 = 跑 `py -3.12 tools/check_sprint_layout.py`（见 `AGENTS.md`）。
> **库内一律相对路径**；绝对路径只出现在会话启动命令里。

---

## 一、当前进度 + 证据

**M1 已完成并验证**（状态以 `plan/00` 里程碑表为准；本节的数字是**当轮实测**）。

| 项 | 实测证据 |
| --- | --- |
| 布局门 | `py -3.12 tools/check_sprint_layout.py` → 9 条判据全 PASS，`这轮扫到：files 14 / sections 8 / handoffs 1 / gap_rows 7 / ledger 1 / doc_tools 3` |
| 脱敏门 | `py -3.12 tools/check_desensitized.py` → **157 个文本文件，0 命中**（豁免 2 份） |
| 布局门变异验证 | `py -3.12 tools/verify_layout_gate.py` → **15 组：15 符合预期 / 0 不符** |
| 生成器可重建 | `py -3.12 -m mimeconform.devtools.gen_golden --check` → **`51 cases, 0 diff`**（exit 0） |
| 语料数据级校验 | `py -3.12 -m mimeconform selftest` → **`51 cases, 0 问题`**（exit 0） |
| 全量测试 | `py -3.12 -X utf8 -m pytest` → **241 passed, 0 skipped**（M1 起两条 fixture-hygiene skip 已转真判据；`test_real_catalog_is_absent` 仍按 M3 前状态生效，未跳过） |
| 语料规模 | `data/golden/` = **51 个 case**（b 11 / h 12 / t 13 / a 9 / c 6），每 case 恰 3 个文件 = **153 个文件** |
| 负例 | 7 组（`b-clean-nested`、`b-wrapped-header`、`h-clean-folded`、`t-clean-b64`、`t-clean-qp`、`a-clean-mixed`、`c-clean-mbox`）缺陷数均为 0 |
| 题面点名复现项 | 11 项全部落地：`b-inner-dup`(#69914) / `b-wrapped-header`(#56141) / `c-from-bad`(#93376) / `h-2231-seq`(SO 44154520) / `h-ew-newline`(SO 52442469) / `t-qp-artifact`(SO 79133579) / `t-b64-len`(SO 6029218) / `a-body-attach`(SO 6255202) / `a-noname`(SO 12816042) / `a-cid-open`(SO 10107788) / `a-related-start`(SO 39328935) |

**M2 要做到的东西**：`scan.py` 字节状态机 + MC-B 系列 10 条 + 两棵候选树 + 复现 #69914 / #56141；`b-*` 11 个 case 的引擎侧断言。

---

## 二、当前事实·状态不变量（下一棒动手前必须知道，否则一定会踩）

1. **`gen_golden.py` 的自检是闸门**：`build()` 里 `_collect()` → 逐 case `_self_check()` → `_check_clusters()` → 才写盘。任何改动后**必须先跑 `--check`**，红了不许绕。
2. **`_self_check` 的七条判据**（改语料时逐条会被考）：case 名一致、输入文件在产出里且 sha/bytes 可复算、正例非空/负例为空、六元组 + `rfc` 非空、落盘即有序、`defect_count`/`exit_code`/`fingerprint` 可复算、证据锚点在字节里、隐私红线。
3. **`_NEEDLES` 是构造期登记的**（`_case(...)` 里 `_NEEDLES[name] = tuple(needles)`）：新增 case 必须给 `needles`，否则"文件确实含它声称的字节"这条判据空转。
4. **`tree_digest` 现在恒为 `null`**（`_case` 写死）。M2 引擎产出树后**必须**由生成器回填真值（`ledger.tree_digest(root)` 同算法），否则"结构指纹基线"这条承诺一直是空的 —— 这是 M2 的必做项，不是可选项。
5. **两处实测修正（与首稿计划不符，已按实测落）**：
   - `b-inner-dup`（#69914）：CPython 3.12.10 实测**报 1 条 `StartBoundaryNotFoundDefect`**（内层 multipart 被当非 multipart），**不是"标准库未报缺陷"**。`expect.json` 的 `stdlib_compare` 记录实测值；M2 落地时 `tests` 里的 `stdlib_compare` 断言要按这组实测写。
   - `b-wrapped-header`（#56141）：3.12.10 实测标准库**已修复**（0 defect，解析正常）→ 本 case 是**负例**，M2 必须让它切出 2 个子部件、零缺陷。
6. **`plan/03` §四 的 A03/A04/A05/A07 severity 已从 `minor` 改为 `note`**（与 `data/README` §7.1 原句门禁一致，M1 同轮修正了摘录）。M4/M5 落地 catalog 时**沿用 `note`**，不要按旧稿提级。
7. **`_mixed_with_attachment` / `_mixed_parts` / `_leaf` / `_plain_headers` 是生成器的四个骨架函数**（boundary 固定 `mix1` / `rel1`）：改它们会同时动几十个 case 的字节，`--check` 会全量变红 —— 改前先想清楚。
8. **mtime/顺序无关性**：`_tree_diff` 只比文件集合 + 字节，不比 mtime；`_write_case` 一律 `write_bytes()`。**不要**在生成器里引入文本模式写盘。
9. **`expect.json` 的 defects 是 `Defect.as_json()` 形态**（键名 `class`，不是 `klass`）；重建对象走 `_parsed_defects()`，不要自己拼。
10. **非 ASCII 与引号**：生成器源码里的中文引号必须用 `「」`，写成 ASCII `"` 会把字符串提前闭合（M1 踩过一次，AST 直接红）。
11. **`Mail.app` 这类带点的产品名通不过域名门**（`_DOMAIN_RE` 把它读成 `mail.app`）。引文只引编号、原话指回 `data/README` §1.4，不要改写成别的域名形态。
12. **状态副本 4 处**（`plan/00` 里程碑表、`plan/00` 台账、`plan/05` 状态表、`README` 状态表）翻状态要同轮；`plan/06` G2/G3 已关闭，`tools/verify_layout_gate.py` 的 N02 变异 marker 已同步新行文本（改 plan/06 缺口行必须同改它）。

---

## 三、下一棒待办（M2 树与边界）

按 `plan/03` §一实现，顺序不得交换：

1. `scan.py` 的字节状态机：`scan_message(data, max_depth=32)` → `ScanResult(root, defects, tree_alternatives, divergence, facts)`；行切分只走 `split_lines()`（K7）。
2. 10 条 MC-B 规则（B01/B02 hard；B06 hard；B03/B04/B05/B07/B08/B09/B10 diff/gray），判定顺序按 §7.5 第 6 条：B01 → B02 → B03/B04 → B06 → B05。
3. MC-B06 必须给**两棵候选树**（`tree_alternatives` 长度 2 + `divergence.path="0.1"`），默认 `tree` = 内层先闭合；报告须声明"默认展示不构成判定"（`plan/00` D9）。
4. **回填 `tree_digest`**：`gen_golden.py` 里 `_case` 的 `expect["tree_digest"]` 改为真实值（同算法 `ledger.tree_digest`），重跑 `--check`。
5. 让 `b-*` 11 个 case 的引擎侧断言通过（新增 `tests/test_golden_engine.py` 之类，按 case 跑 `scan_message` 后与 `expect.json` 比对**键 = rule_id/path/offset/class**，不比 severity）。
6. `b-inner-dup` 的 `stdlib_compare` 断言按 §二.5 的实测值写；`b-wrapped-header` 断言 0 缺陷。
7. 回写 4 处状态副本（M2 → ✅），写 `plan/HANDOFF-M3.md`，提交。

**M2 完成的判据**：`b-*` 全部 case 引擎侧命中；`py -3.12 -m mimeconform.devtools.gen_golden --check` 仍 `51 cases, 0 diff`；`git status --porcelain` 为空。

---

## 四、既定口径清单（K 编号 —— "动了会打挂测试"的约定）

| K | 口径 | 打挂它的测试 |
| --- | --- | --- |
| K1 | 数值口径只有一处：`data/README.md` §七；代码常量只在 `mimeconform/constants.py` | 全仓无第二处定义；新增阈值必须先进 §七 |
| K2 | `class` 三值 / `severity` 四档的代码侧来源只有 `constants.CLASSES` / `SEVERITIES` | `test_ledger_invariants.py`、`test_catalog_gate.py` |
| K3 | 指纹算法按 `data/README` §7.8 逐字实现，键序固定，**不含 `detail`** | `test_ledger_invariants.py::test_fingerprint_ignores_detail_wording`、`test_generator_check.py::test_fingerprint_is_reproducible` |
| K4 | 退出码 `--fail-on` **只会更严**，永不推翻 major/blocker → 3 | `test_exit_codes.py::test_fail_on_never_softens_baseline` |
| K5 | `argparse` 的用法错误一律映射为 **1**（不是 argparse 自带的 2） | `test_cli_contract.py`（未知子命令 / 缺参 / 坏枚举各一条） |
| K6 | 路径语法：`0` / `0.1` / `msg#3` / `msg#3/0.1`；`msg#n` 的 n 从 1 起 | `test_ledger_invariants.py::test_path_*` |
| K7 | 行切分只走 `scan.split_lines()`（按 `\n`，不吞 `\r`，不把 `\x0b` 当行界） | M2 起加"与 `bytes.splitlines` 差异"回归 |
| K8 | `SEMANTIC_RULES` == `data/README` §7.1 升级禁令列表；**golden 里也不许把它们标 hard** | `test_catalog_gate.py::test_semantic_rules_set_covers_the_documented_families`、`test_generator_check.py::test_semantic_rules_never_claim_hard` |
| K9 | `ENGINE_MODULES` 是守门的显式清单，新增模块必须同步 | 新增模块漏加时守门静默失效 → 检视 `test_engine_guards.py` |
| K10 | 脱敏门扫描面收编规则：`.gitignore` 声明的本地产物目录必须在 `SKIP_DIRS` 有对应项 | `test_gates.py::test_desensitized_skips_local_artifacts` |
| K11 | 布局门判据 id 集合固定（9 条），改门必须同改 `test_gates.py` 的期望集合 | `test_gates.py::test_layout_gate_reports_every_check` |
| K12 | 状态副本 4 处 + 每副本命中行数必须 > 0 | `LAYOUT.STATUS` + `test_gates.py::test_layout_gate_status_copies_all_contribute_rows` |
| K13（新） | **语料只由生成器产出**：`data/golden/**` 三件（输入 + `expect.json` + `README.md`）必须与 `--check` 位级一致，手改语料即红 | `test_generator_check.py::test_build_into_temp_dir_matches_repo_corpus`、`::test_check_detects_a_single_byte_change` |
| K14（新） | **矩阵下界**：b/h/t/a/c 每簇 ≥2 正例 + ≥1 负例；case 数 51 固定 | `gen_golden._check_clusters`（在 `build()` 内）、`test_generator_check.py::test_every_case_has_exactly_three_files` |
| K15（新） | **镜像同源**：`data/README` §三 与人读台账、`data/rfc-ledger.json` 三处 `(RFC号, 节号)` 集合相等 | `test_ledger_mirror.py`（M1 已绿） |

---

## 五、本机环境坑（实测，2026-10-27）

| 事实 | 命令与输出 | 后果 |
| --- | --- | --- |
| 解释器 | `py -0p` → `3.8-64`（3.8.8）、`3.12-64`（3.12.10） | **3.8 低于本项目下限 3.11，不得用作验证通道**；本机只有 3.12 一条可用 |
| 跑 Python | `py -3.12 -X utf8 <cmd>` | 中文控制台编码；`-X utf8` 只管"我们敲的命令"，管不到子进程与 CI |
| PyYAML | `py -3.12 -c "import yaml"` → `6.0.3` | 已装；但 CI 必须靠 `[dev]` 声明，不能靠"本机碰巧有" |
| Node | `node --version` → `v24.15.0` | 本项目**不用** Node：两道门是 Python 标准库实现（D14） |
| Git | `2.54.0.windows.1`，`git remote -v` **为空** | 无远端 → 一切"CI 绿"只能写"本地等价校验（未接远端，CI 待首推验证）" |
| 建立 venv | `py -3.12 -m venv <dir>` | **3.12 的 venv 不再自带 setuptools**：`pip install -e .` 直接报 `BackendUnavailable`；先装 `setuptools>=68`（本机走 `-i https://pypi.tuna.tsinghua.edu.cn/simple` + `NO_PROXY="*"`）再 `--no-build-isolation` 安装 |
| pip 代理 | 系统代理可能污染 pip | 用 `NO_PROXY="*" no_proxy="*"` + 镜像；本项目运行时零依赖，只有 dev extra 需要网络 |
| `gh` 未使用 | — | M6 才需要；注意 `gh` 是原生程序，不认 Git Bash 的 `/tmp` 路径 |
| **`data/golden` 体量** | `find data/golden -type f \| wc -l` → **153** | 每次 `--check` 会重建 51 case；改骨架函数（`_mixed_with_artachment` 等）会全量变红，先想清楚再改 |

---

## 六、DoD 逐项 checklist（M2）

- [ ] `scan.py` 实现 `scan_message()`，返回 `ScanResult`；`split_lines` 仍是唯一切行入口
- [ ] 10 条 MC-B 规则按 §7.5 第 6 条顺序判定；B03/B04/B07/B08/B10 只出 `note`
- [ ] `b-inner-dup` 输出两棵候选树 + `divergence`（`path="0.1"`、`offset` 精确）
- [ ] `b-wrapped-header` 零缺陷、树有 2 个子部件（负例）
- [ ] `tree_digest` 由生成器回填真值；`--check` 仍 `51 cases, 0 diff`
- [ ] `b-*` 11 个 case 引擎侧断言全绿（比对键 rule_id/path/offset/class）
- [ ] `stdlib_compare` 断言按实测（#69914 报 1 条 `StartBoundaryNotFoundDefect`）
- [ ] 全量 `pytest` 全绿；布局门 + 脱敏门 + 变异验证全绿
- [ ] 状态副本 4 处同翻 M2 → ✅；`plan/HANDOFF-M3.md` 落盘并提交

---

## 七、关键命令速查

```bash
# 续接对话第一件事
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/check_desensitized.py

# 全量测试 + 门的变异验证
py -3.12 -X utf8 -m pytest -q
py -3.12 -X utf8 tools/verify_layout_gate.py

# 语料（M1 已落地）
py -3.12 -m mimeconform.devtools.gen_golden --check       # → 51 cases, 0 diff
py -3.12 -m mimeconform selftest                          # → 51 cases, 0 问题
py -3.12 -m mimeconform.devtools.gen_golden               # 写了语料就重跑这个

# CLI 冒烟（两条通路都要）
py -3.12 -m mimeconform --version
mimeconform --version

# 干净环境（发布级）
py -3.12 -m venv <dir> && <dir>/Scripts/python.exe -m pip install "setuptools>=68" && \
  <dir>/Scripts/python.exe -m pip install --no-build-isolation ".[dev]"
```
