# golden case: b-preamble-epilogue

- 期望：正例（缺陷集非空）；缺陷数 2；退出码 0
- 来源：自造边界样本（无外部来源）
- 输入：`msg.eml`（369 bytes；sha256 `c5df61daeecdb1fcbf63f218ae6bb10e0ecb7b598dc77b44b5a56df2e85ee8f5`）
- 期望指纹：`2d1d4753553a1073531b04acc7eaeba08a47c1544a55722d8da750c2fbfae580`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/b-preamble-epilogue/msg.eml`

## 说明

两条都是 `note`（登记字节区间，用于解释「多出来的内容去哪了」）；preamble/epilogue **不计入** `body_sha256`。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-B07 | diff | note | 0 | 209 | absolute | RFC 2046 §5.1.1 | 存在 preamble 字节区间（RFC 2046 §5.1.1 要求忽略；存在本身不是违规） |
| MC-B08 | diff | note | 0 | 323 | absolute | RFC 2046 §5.1.1 | 存在 epilogue 字节区间（RFC 2046 §5.1.1 要求忽略；存在本身不是违规） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

