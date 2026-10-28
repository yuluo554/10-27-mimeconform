# HANDOFF-M6 — 进入 M6（发布）的收尾交接单

> 产出棒：M5（归属与容器：`attribution.py` 8 条 MC-A + `container.py` 5 条 MC-C + `rules/catalog.json` /
> `docs/defect-catalog.md` 扩到 46 条 + 容器输入接线），2026-10-28。
> **本文件同时是 M6 的收官记录**：§一–§七 是"进入 M6"的交接（历史事实，保持原样），
> **§八 是 M6 完成后的收官记录**（收尾棒也必须有交接单，见 `plan/05` §五）。
> 用法：新对话第一件事 = 跑 `py -3.12 tools/check_sprint_layout.py`（见 `AGENTS.md`）。
> **库内一律相对路径**；绝对路径只出现在会话启动命令里。

---

## 一、当前进度 + 证据

**M5 已完成并验证**（状态以 `plan/00` 里程碑表为准；本节的数字是**当轮实测**）。

| 项 | 实测证据 |
| --- | --- |
| 布局门 | `py -3.12 -X utf8 tools/check_sprint_layout.py` → 9 条判据全 PASS，`files 14 / sections 8 / handoffs 5 / gap_rows 8 / ledger 1 / doc_tools 3` |
| 脱敏门 | `py -3.12 -X utf8 tools/check_desensitized.py` → **171 个文本文件，0 命中**（豁免 2 份） |
| 布局门变异验证 | `py -3.12 -X utf8 tools/verify_layout_gate.py` → **16 组：16 符合预期 / 0 不符**（M5 收尾：M11 改指 `LAYOUT.RELEASE`、新增 M14 作 M13 的反向对照） |
| 全量测试 | `py -3.12 -X utf8 -m pytest` → **682 passed, 1 skipped**（M4 时 561 passed；新增 `test_golden_engine_attribution.py` 51 条 + `test_golden_engine_container.py` 39 条 + 容器双跑 7 条 + 依赖方向 4 条 + 接线 3 条 + catalog/doc 若干） |
| 生成器可重建 | `py -3.12 -m mimeconform.devtools.gen_golden --check` → **`51 cases, 0 diff`**（exit 0；c-* 的 README 措辞已随重生成同步） |
| 语料数据级校验 | `py -3.12 -m mimeconform selftest` → **`51 cases, 0 问题`**（exit 0） |
| `a-*` 引擎侧 | 9/9 case 命中（**8 正例各 1 条、1 负例 0 条**，共 8 条 A 缺陷），比对键 `rule_id`/`path`/`offset`/`class` |
| `c-*` 引擎侧 | 6/6 case 命中（**5 正例各 1 条、1 负例 0 条**，共 5 条 C 缺陷），比对键另加 `offset_kind` |
| catalog 门禁 | `load_catalog()` 返回 **46 条**（B 10 + H 12 + T 11 + A 8 + C 5）全部过原句门禁；`hard` 12 条仅 B/H/T，**A/C 为空** |
| 复现 SO 6255202 | `a-body-attach`：MC-A01 `diff/note` @ offset 313（`Content-Type: text/plain; name="notes.txt"` 行首） |
| 复现 SO 12816042 | `a-noname`：MC-A03 @ 316（`Content-Disposition: attachment` 行首），detail 内含 "Noname" |
| 复现 SO 10107788 | `a-cid-open`：MC-A04 @ 293（正文 `cid:img002@…` 的 `c` 字节），`path="0.1"` |
| 复现 SO 39328935 | `a-related-start`：MC-A05 @ 179（`multipart/related` 的 `Content-Type` 行首），`path="0"` |
| 复现 cpython #93376 | `c-from-bad`：MC-C01 @ `msg#2` offset 0（`message-relative`），detail 写明缺日期字段 |
| mbox 三变体并出 | `c-from-unescaped`：`variant_counts={mboxo:3, mboxrd:3, mboxcl:2}`；`auto` → `mboxcl`；切分表三个键恒在 |
| 主表可切换 | `--mbox-variant mboxo` → MC-C04（该读法下 `From ` 行真的切出坏片段）；`mboxcl`/`auto` → MC-C02（读法分歧）。**两套结论都可复现** |
| 误报面 | A 簇在非 a 簇上只命中一处**真阳性**：`h-2231-seq` 的 `name="a.pdf"` vs `filename="ע.pdf"` → MC-A02（已由 `test_h_2231_seq_also_bears_a02_and_that_is_a_true_positive` 钉住） |
| 容器路径双跑 | `tests/test_determinism.py` 对 5 个 `.mbox` + 1 个 Maildir 双跑逐字节一致 |
| 性能基线（末态） | 45 个 `.eml` 全链 `scan+headers+transfer+attribution` **0.045 s**；合成 3.05 MiB / 2000 条 mbox 三变体切分 **0.171 s**（数字只进文档，不进断言） |

**M6 要做到的东西**：干净环境验证（仅 CPython 的 venv 里跑 README 逐条 + 全量 golden）+
脱敏四步 + 建仓（公开）+ CI 首推 + tag + GitHub Release 附手工源码包 + `plan/RELEASE-M6.md`
（两栏 + 阶段 7 覆盖对账）。**M6 不改代码面**（`AGENTS.md` 禁忌：tag 之后不改代码面）。

---

## 二、当前事实·状态不变量（下一棒动手前必须知道）

1. **五模块全部接入，`_NOT_YET_AUDITED == ()`**：`cli.py` 里有三个常量，语义**不同**：
   `_AUDITED_ENGINES`（已落地的五层**清单**）、`_MESSAGE_ENGINES`（单封路径**本次真跑**的四层）、
   `_CONTAINER_ENGINES`（容器路径本次真跑的一层）。报告按后两者写 `audited_engines` /
   `not_applicable` —— **别把清单当覆盖面**（那等于把"没查"说成"查过"）。
2. **两条输入路径**：`_run_audit` 按形态分流 —— 单封 `.eml` 跑 `_audit(data, args)`（返回
   `(ScanResult, defects, AttributionResult)`，三元组已加 attribution）；`.mbox` / Maildir 目录 /
   `--container` 走 `container`。**`_read_input` 对目录不再报错**（报错的是它上面那层分流判断）。
3. **容器模式空表 = exit 1**：`.mbox` 里 0 条消息、Maildir 目录 0 个条目、或 `--container`
   指一个非容器 → `UsageError` → exit 1。测试 `test_container_mode_on_a_non_container_fails_loudly`
   断言文案含"**没有找到任何** mbox 消息"（注意措辞，`assert in` 是逐字的）。
4. **`tree_digest` 对容器恒为 `null`**（M5 裁决）：§7.8 的该字段主语是"一棵树"。容器输入的
   回归基线是 `fingerprint` + `split_variants` + `expect_extra.variant_split_counts` + `file_offset`。
   **不要**为了"填满字段"而发明多棵树合并摘要 —— 那要先进 `data/README` §7.8。
5. **`report.py` 仍然零判定**：M5 只加了排版分支（`mode == "container"` 走容器小节、
   `tree_digest is None` 写"不适用"、新增 `_coverage_lines`）。`test_report_has_no_engine_imports`
   仍绿；`_tree_section` / `_coverage_lines` 里的每个值都来自 `tree_info`。
6. **`container.py` 是最底层**：不 import 任何业务模块（`test_container_does_not_import_higher_layers`）。
   切行有一份本地实现 `_iter_lines`，与 `scan.split_lines` 的一致性由
   `test_golden_engine_container.py::test_line_splitter_matches_scan` 交叉断言（K7）。
7. **`attribution.py` 可以 import `headers`，不可以 import `scan`/`transfer`**：
   `test_attribution_does_not_import_higher_layers` + `test_transfer_and_attribution_do_not_import_each_other`。
   参数事实来自 `headers.parse_headers`（`scan` 的 `Header.params` 恒空）。
8. **A01 / A08 的保守边界（改窄会掉真阳性、改宽会误报）**：
   A01 要求叶节点**自带 `name`/`filename`**（没有名字的 `text/html`+`text/plain` 并列不报 ——
   `b-wrapped-header` 就是这一形态）；A08 只在 **`multipart/mixed`** 上判且要求**没有**正文候选
   （`related` 的首部件本身即正文、`alternative` 是正文同义）。
9. **C01 → C03 → C04 → C02 的判定顺序**：分隔行形态坏（C01）→ 片段 0 字节（C03）→
   片段无头块（C04）→ 只有片段正常时才看"其它变体是否在此切分"（C02）。**一个片段只出一条**。
   `c-from-unescaped` 在 mboxcl 主表下出 C02、在 mboxo 主表下出 C04 —— 同一文件两种读法两种结论，
   这不是矛盾，是 §7.7 的口径。
10. **`h-2231-seq` 会同时出 MC-A02 与 MC-H09**：那是真阳性（`name="a.pdf"` vs 解码后
    `filename="ע.pdf"`）。它的 `expect.json` 只登记 H09（那是该 case 的立意），但
    **CLI 整封审计会如实报两条**（`test_h_2231_seq_also_bears_a02_and_that_is_a_true_positive`）。
    若 M6 想改这条，必须显式决定"是否丢掉这条真阳性"。
11. **`_pending.py` 已无引擎使用**：保留它是因为 `cli._run_audit` 里那条防御分支仍用它产出
    **具名异常**（→ exit 1 的统一映射），而不是裸 `NotImplementedError`。`test_no_engine_remains_unwired`
    断言"没有引擎再抛它"。
12. **`data/golden/**` 本轮只改了 6 份 c-* 的 `README.md`**（`_tree_digest_for` 的说明文案由
   "自 M5 起回填" 改成"M5 裁决：不适用"）。**没有**改任何 `msg.eml` / `mail.mbox` / `expect.json`
   的字节，`--check` 仍 `51 cases, 0 diff`。
13. **M6 是发布棒，代码面冻结**：`AGENTS.md` 明确"禁止：在 tag 之后改代码面"。若 M6 期间发现
    真缺陷，只能：修 → 重跑全部门 → 重写 `plan/RELEASE-M6.md` 的 tag 前事实 → 再 tag。
    **不要**用"发布后再补一个 commit"的方式绕过。

---

## 三、下一棒待办（M6 发布）

按 `plan/05` §二 M6 DoD 与 `plan/02` §十一 执行，顺序不得交换：

1. **交付面定稿**：`README.md` 的状态表 / 用法示例 / 三场景命令逐条实跑；版本号四处一致
   （`pyproject.toml` / `mimeconform/__init__.py` / `README` 若提及 / 发布包名）。
2. **干净环境验证**：新建 venv（只有 CPython），`pip install --no-build-isolation ".[dev]"`，
   在**无本机 editable** 的前提下跑：`mimeconform --version`、README 的每条命令、
   `mimeconform selftest --data-dir <repo>/data/golden`、全量 `pytest`。
   **`mimeconform` 裸命令首次真实可用的时刻就在这里** —— 在此之前只验证过 `python -m mimeconform`。
3. **脱敏四步**：`tools/check_desensitized.py` 绿 + `git ls-files` 扫描（无真实 `.eml`/`.mbox` 入仓）
   + 提交身份 / tagger 邮箱检查留档 + 源码包解包后再扫一次。
4. **建仓（公开）+ CI 首推**：`gh repo create` → push → 等 4 矩阵 + 离线无网络 job 绿 → 记 run id。
   **在此之前所有"CI 绿"只能写"本地等价校验（未接远端，CI 待首推验证）"**。
5. **手工源码包**：`git archive --format=tar --prefix=mimeconform-<ver>/ <tag> | gzip -9n` +
   `SHA256SUMS`（同命令再跑一次必须 `cmp` 逐字节一致）+ 本地留副本。
6. **tag + Release + 留档**：`plan/RELEASE-M6.md` **tag 前**落盘（§一 tag 前事实 / §二 tag 后追加 /
   §覆盖对账 三态逐条）；tag push 后补 §二；Release 附源码包 + sha256。

**M6 完成的判据**：`plan/RELEASE-M6.md` 两栏齐 + 覆盖对账逐条有结论；干净 venv 全绿；
CI 首推全绿（run id 留档）；tag 存在且 `git cat-file -e <tag>:plan/RELEASE-M6.md` 通过；
Release 有 ≥1 个手工上传附件且 sha256 与本地副本一致；`git status --porcelain` 为空。

---

## 四、既定口径清单（K 编号 —— "动了会打挂测试"的约定）

> K1–K34 沿用 `HANDOFF-M4` §四（未变，逐条仍然有效）。下面是 M5 新增的条目。

| K | 口径 | 打挂它的测试 |
| --- | --- | --- |
| K35（新） | **A 簇全部 `diff/note` + `none-by-design`**（D11）：`Content-Disposition` / `multipart/related` 不在五部 RFC 内 | `test_catalog_consistency.py::test_class_distribution_is_what_the_plan_says`（`hard_a == []`）、`test_golden_engine_attribution.py` 的逐 case 断言 |
| K36（新） | **C 簇全部 `diff/note` + `none-by-design`**（D3）：mbox / Maildir 都不是 RFC | 同上（`hard_c == []`） |
| K37（新） | **A01 需要 `name`/`filename` 参数作证据**：无名字的 `text/html`+`text/plain` 并列不报（`b-wrapped-header` 的形态） | `test_a01_requires_a_name_parameter`、`test_golden_engine.py::test_wrapped_header_parses_as_multipart_with_two_children` |
| K38（新） | **A08 只在 `multipart/mixed` 上判**，且要求"≥2 叶节点 + 全部无 disposition + 无正文候选" | `test_a08_requires_all_leaves_without_disposition_and_no_body_candidate`、`a-no-disposition` |
| K39（新） | **`cid:` 比较按尖括号内字面值、不 URL 解码**；同一字面值只记首次 | `test_cid_comparison_is_literal_and_not_url_decoded`、`a-cid-open` |
| K40（新） | **三张切分表总在全出，缺陷只从主表产出**；主表可切换，缺陷随主表变 | `test_switching_the_primary_variant_changes_which_rule_fires`、`test_variant_tables_match_expect_extra` |
| K41（新） | **C01 → C03 → C04 → C02 的判定顺序**，一个片段只出一条 | `test_reproduces_cpython_93376_malformed_from_line`、`test_c04_is_recorded_when_all_variants_agree_to_mis_split`、`test_c02_is_recorded_where_variants_disagree` |
| K42（新） | **容器空表 = exit 1**（空分母 ≠ 通过）；单封 `.eml` 走容器模式也落这条 | `test_container_mode_on_a_non_container_fails_loudly`、`test_maildir_with_no_entries_fails_loudly` |
| K43（新） | **`tree_digest` 对容器恒 `null`**（§7.8 的主语是一棵树） | `test_golden_engine_container.py` 的负例断言 + `gen_golden --check` 的字节基线 |
| K44（新） | **报告覆盖面 = 本次真跑的层**（`_MESSAGE_ENGINES` / `_CONTAINER_ENGINES`），不是 `_AUDITED_ENGINES` 清单 | `test_headers_engine_is_wired_into_audit`、`test_container_engine_is_wired_into_audit` |

---

## 五、本机环境坑（实测，2026-10-28；M5 未新增坑）

| 事实 | 命令与输出 | 后果 |
| --- | --- | --- |
| 解释器 | `py -0p` → `3.8-64`（3.8.8）、`3.12-64`（3.12.10） | **3.8 低于本项目下限 3.11，不得用作验证通道** |
| 跑 Python / 测试 | `py -3.12 -X utf8 -m pytest` | 中文控制台编码；`-X utf8` 只管"我们敲的命令" |
| 全量测试耗时 | 约 4–5 秒（682 条） | 每改一处都跑全量不心疼 |
| **`mimeconform` console script** | `shutil.which('mimeconform')` → `None` | 本机**没有**装过 editable。`python -m mimeconform` 可跑；裸命令要等 M6 的 venv 验证。**别写"裸命令已冒烟"** |
| Git | `2.54.0.windows.1`，`git remote -v` **为空** | 无远端 → 一切"CI 绿"只能写"本地等价校验（未接远端，CI 待首推验证）" |
| **heredoc 写源码会被拦** | `py - <<'PY'` 改 `.py` 文件被 Mimosa 钩子拒绝 | 改源码一律用 Write/Edit 工具；heredoc 只用来跑只读探针 |
| 测试摘要行常被控制台吞 | `pytest -q` 末尾的 `N passed` 有时不打印 | 用 `pytest --junitxml=<临时文件>` 再解 XML 看真值（退出码仍是准的）。**临时文件必须落在仓库外**（`$TEMP`），否则脱敏门会扫到它自己的输出 |
| **脱敏门会扫仓库内的临时产物** | 在仓库里留 `.pytest.out` / `.junit.xml` → `check_desensitized.py` 命中 `absolute-session-path`（pytest 的 traceback 里带盘符路径） | 临时文件一律写 `$TEMP`；已踩过两次 |
| **`data/golden` 体量** | 51 case × 3 件 = **153** 个文件 | 每次 `--check` 重建全量；改骨架函数会让几十个 case 的 `tree_digest` 变红 |

---

## 六、DoD 逐项 checklist（M6）

- [ ] 版本号四处一致；README 状态表 M6 → ✅（与 `plan/00`、`plan/05` 逐字一致）
- [ ] 干净 venv（仅 CPython）：`pip install --no-build-isolation ".[dev]"` → `mimeconform --version` = 0
- [ ] README 每条命令在干净 venv 里逐条跑通（含容器两条：`.mbox` / Maildir）
- [ ] 干净 venv 里 `pytest` 全绿（682 passed）；`selftest --data-dir <repo>/data/golden` = 0
- [ ] 脱敏四步留档（门输出 / `git ls-files` / 提交身份 / 解包后再扫）
- [ ] 建仓公开 + CI 首推全绿（4 矩阵 + 离线 job），run id 记进 `plan/RELEASE-M6.md` §二
- [ ] 手工源码包 + `SHA256SUMS`（两次 `git archive` 逐字节一致）+ 本地留副本
- [ ] `plan/RELEASE-M6.md`：§一 tag 前事实 / §二 tag 后追加 / §覆盖对账（阶段 7 逐条三态）
- [ ] tag push 后 `git cat-file -e <tag>:plan/RELEASE-M6.md` 通过
- [ ] GitHub Release 附源码包（≥1 附件），sha256 与本地副本一致
- [ ] `git status --porcelain` 为空

---

## 七、关键命令速查

```bash
# 续接对话第一件事
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/check_desensitized.py

# 全量测试（临时产物写仓库外，否则脱敏门会扫到）
py -3.12 -X utf8 -m pytest -q
py -3.12 -X utf8 -m pytest --junitxml="$TEMP/mc.xml" -q     # 摘要行被吞时看真值

# 门的变异验证
py -3.12 -X utf8 tools/verify_layout_gate.py

# 语料
py -3.12 -m mimeconform.devtools.gen_golden --check       # → 51 cases, 0 diff
py -3.12 -m mimeconform selftest                          # → 51 cases, 0 问题

# 单封消息路径冒烟（A / 容器两簇）
py -3.12 -m mimeconform audit data/golden/a-body-attach/msg.eml --format json   # exit 0，MC-A01
py -3.12 -m mimeconform audit data/golden/a-cid-open/msg.eml --format json      # exit 0，MC-A04
py -3.12 -m mimeconform audit data/golden/a-noname/msg.eml --format json        # exit 0，MC-A03
py -3.12 -m mimeconform audit data/golden/a-clean-mixed/msg.eml --format json   # exit 0，0 缺陷

# 容器路径冒烟
py -3.12 -m mimeconform audit data/golden/c-from-bad/mail.mbox --format json    # exit 0，MC-C01
py -3.12 -m mimeconform audit data/golden/c-from-unescaped/mail.mbox --format json  # exit 0，MC-C02（auto→mboxcl）
py -3.12 -m mimeconform audit data/golden/c-from-unescaped/mail.mbox --mbox-variant mboxo --format json  # exit 0，MC-C04
py -3.12 -m mimeconform audit data/golden/c-maildir-name/maildir --format json  # exit 0，MC-C05

# 规则目录
py -3.12 -c "from mimeconform.rules import load_catalog; print(len(load_catalog()))"   # → 46

# 干净环境（发布级）
py -3.12 -m venv <dir> && <dir>/Scripts/python.exe -m pip install "setuptools>=68" && \
  <dir>/Scripts/python.exe -m pip install --no-build-isolation ".[dev]"

# 手工源码包（M6）
git archive --format=tar --prefix=mimeconform-<ver>/ <tag> | gzip -9n > mimeconform-<ver>.tar.gz
sha256sum mimeconform-<ver>.tar.gz
```

---

## 八、M6 收官记录（2026-10-28）

> 本节是 M6 **完成后**写的。§一–§七 是"进入 M6"的交接内容，**未修改**（历史事实）。
> 发布事实的逐条证据在 `plan/RELEASE-M6.md`（两栏 + 覆盖对账 34 条）。

### 8.1 M6 做了什么（按 `plan/05` §二 M6 DoD 顺序）

| # | 事项 | 结论 |
| --- | --- | --- |
| 1 | 交付面定稿 | 版本 `0.0.0.dev0` → **`1.0.0`**；`pyproject.toml` + `mimeconform/__init__.py` + `README.md` 三处同串，发布包名第四处；classifier 从 `2 - Pre-Alpha` 改 `5 - Production/Stable`；README 安装节补"不发 PyPI、交付形态是 Release 上的手工源码包" |
| 2 | 干净环境验证 | 仓库外新 venv（仅 CPython + setuptools）→ `pip install --no-build-isolation ".[dev]"` → `mimeconform --version` = `mimeconform 1.0.0` rc 0（**裸命令首次真实可用**）；`python -m mimeconform --version` 同；`selftest --data-dir data/golden` = `51 cases, 0 问题`；`pytest` = `682 passed, 1 skipped`。README 全部命令在**仓库外 cwd** 逐条敲过（`plan/RELEASE-M6.md` §1.3 有 rc 对照表） |
| 3 | 脱敏四步 | 见 §8.2 |
| 4 | 建仓（公开）+ CI 首推 | 见 §8.3 |
| 5 | 手工源码包 | 见 §8.4 |
| 6 | tag + Release + 留档 | 见 §8.5 |

### 8.2 脱敏四步（实测）

1. `tools/check_desensitized.py` → **172 个文本文件，0 命中**（豁免 2 份）。
2. `git ls-files '*.eml' '*.mbox' '*.mbx' '*.msg'` → **50 个，全部在 `data/golden/**`**。
3. 内容级复核（密钥赋值 / `.env` 与私钥文件名 / 非 `example.invalid` 邮箱 / 手机号 / 身份证 /
   真实盘符路径 / 内网 IP / 回环端口）→ 仅 2 处命中，均为 `tests/test_fixture_hygiene.py` 的
   **故意阳性对照**（`alice@mail.google.com`，该测试的存在理由是证明真实域名必须被检出），非泄漏。
4. 提交身份全历史去重 → 唯一 `yuluo554 <282769740+yuluo554@users.noreply.github.com>`。
5. `git rev-list --all` 全树强标记 grep → 仅 golden 的 sha256 十六进制串 + 上述测试样本。
6. 源码包解包后再扫 → 见 `plan/RELEASE-M6.md` §二。

**姊妹项目表述**：全仓 grep 只命中本仓自己的目录名与 Homepage（有意公开的项目坐标），
**无**对其他项目的提名 → 品牌隔离成立，无需掩码。

### 8.3 建仓 + CI 首推

- 名字占用在建仓**之前**核过：PyPI `mimeconform` = 404（未占用）；`gh api` 检索
  `mimeconform in:name` / `10-27-mimeconform in:name` 的 `total_count` 均 = **0**（成功响应，非限流假 0）。
- 公开仓库 + push + 等 run 绿 → run id 与矩阵结论记在 `plan/RELEASE-M6.md` §二。

### 8.4 手工源码包

`git archive --format=tar --prefix=mimeconform-1.0.0/ v1.0.0 | gzip -9n` → 同命令再跑一次 `cmp`
逐字节一致（D15 的可复算口径）；`SHA256SUMS` 与 Release 正文同源；本地留副本在仓库外。
**哈希字面值只写在 `plan/RELEASE-M6.md` §二 与 Release 正文**（§一 与包内文档不写——写进去就失效）。

### 8.5 tag + Release

- tag `v1.0.0`（annotated）打在"交付面定稿 + 留档 §一 落盘"这笔提交上；tag 之后只允许**只动 `plan/`** 的提交。
- Release 附 `mimeconform-1.0.0.tar.gz`（≥1 附件），正文含：变更摘要 / 规则集与台账版本（46 条规则、
  11 行台账的 `data/rfc-ledger.json`）/ 是否需要重跑历史报告（首个版本无历史报告 → 口径写"无需重跑"）/
  sha256 / 已知问题。

### 8.6 本轮修掉的两类真缺陷（不是"顺手改"）

1. **瞬态变异靶子**：`tools/verify_layout_gate.py` 的 M11/M13/M14 原本靠"把 `plan/00` 的 M6 行临时翻 ✅"
   来激活 `LAYOUT.RELEASE` / `LAYOUT.HANDOFFS`。M6 真翻 ✅ 后该前提消失，三组会变成"期望红实际绿"。
   处置 = 加 `ensure_m6_done` seam（待办态时临时翻 ✅、逐字节还原；已是 ✅ 时不动），
   并把 M11 的靶子从"翻状态行"改成"删发布留档"。**判据面一条不减**，从此与项目进度解耦。
2. **README 安装面叙事与交付形态不一致**：原安装节写 `pip install .` 而不提"不发 PyPI"，
   读者会去找 PyPI 包名。已补"交付形态 = Release 上的手工源码包"一段 + 附件名 + 复算方法。

### 8.7 已知未验证项（M6 结束后仍如实保留）

| 项 | 原因 | 处理 |
| --- | --- | --- |
| 跨解释器（3.11 / 3.13） | 本机只有 3.12.10 可用（3.8.8 低于下限 3.11） | 只由 CI 矩阵证；本机一律写"本地等价校验" |
| 真实邮件语料 | 隐私红线 | 只用合成语料；不声称"大规模真实语料验证" |
| 客户端实测（Outlook / Gmail / iOS） | 未实测 | 只做字节层判定，不承诺客户端显示行为 |
| 本机离线闭环 | 本机无 docker | `offline` job 的"嵌套 `docker run --network none`"只在 CI 跑；本机以"零网络 import 的 AST 守门"作等价证明 |
