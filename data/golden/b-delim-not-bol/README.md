# golden case: b-delim-not-bol

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造边界样本（无外部来源）
- 输入：`msg.eml`（317 bytes；sha256 `c24aad26ed028b8e68dbef1c936f4726e090393a8481824d4158cdc4adfccfab`）
- 期望指纹：`ed2ad54d40c235ceab5495f6c93057d13d7aa2bf8dca287cdb825a4628627da3`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/b-delim-not-bol/msg.eml`

## 说明

该行按字节是首部件正文内容（前导空白使其不构成 delimiter）；登记用于解释下游切分差异。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-B03 | diff | note | 0 | 274 | absolute | RFC 2046 §5.1.1 | 疑似 delimiter `--S` 未出现在行首（前导空白）——R7 的 delimiter 形态子项原句未留档，只登记 |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

