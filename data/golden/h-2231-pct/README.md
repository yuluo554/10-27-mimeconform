# golden case: h-2231-pct

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造头编码样本（无外部来源）
- 输入：`msg.eml`（411 bytes；sha256 `c41598ca206c9a939dd8d6a8e94c573f426bc99b5c2aae527cae67ab8d1d3508`）
- 期望指纹：`ef5c4b525d4c94c60b86837ea50f4db89757d68b27f1861c3dc29b78e9413e87`
- 树指纹：`37957cc07bae4f8dbf256fb609168f1a646464e9766f566510520213b67a0ba8`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/h-2231-pct/msg.eml`

## 说明

R10 未录 → 只登记（§7.1）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-H11 | diff | note | 0.2 | 373 | absolute | RFC 2231 §3/§4/§4.1（R10 整行未录原句 → 门禁降级，只登记） | `%ZZ` 不是合法的 %HH 转义（H 必须是两位十六进制） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

