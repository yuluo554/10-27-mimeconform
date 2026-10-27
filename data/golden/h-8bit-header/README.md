# golden case: h-8bit-header

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造头编码样本（无外部来源）
- 输入：`msg.eml`（184 bytes；sha256 `d70c023d3e470abdf6d9645bb5387104d66e9f8c55abb500fdf5350095700e16`）
- 期望指纹：`86c5c04838ae460f1ded3bedef5fe2f49a777fd7aa876feeb12012bb2bd60fa1`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/h-8bit-header/msg.eml`

## 说明

`diff`：不硬判，只登记偏移与所在头名。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-H08 | diff | note | 0 | 65 | absolute | none-by-design | Subject 头值含未编码的非 ASCII 字节（RFC 2047 是编码机制，不是禁令；现实实现常直传 8bit） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

