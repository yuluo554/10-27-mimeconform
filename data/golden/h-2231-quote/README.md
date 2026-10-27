# golden case: h-2231-quote

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造头编码样本（无外部来源）
- 输入：`msg.eml`（427 bytes；sha256 `b00c1155742e330fc0ee56a02eca747fda65da1dcd5b0f48cbeb11071a878638`）
- 期望指纹：`17d829dfafb7c99b715f0556919e8a12976113d95c792161a2833ac74765e512`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/h-2231-quote/msg.eml`

## 说明

R10 未录 → 只登记。判定顺序按 §7.5 第 3 条（合并续行 → 三段解析 → %HH → 2047）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-H10 | diff | note | 0.2 | 371 | absolute | RFC 2231 §3/§4/§4.1（R10 整行未录原句 → 门禁降级，只登记） | `charset'language'value` 的单引号不完整（`UTF-8'sample.pdf` 只有一个 `'`；应为 `UTF-8''sample.pdf`） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

