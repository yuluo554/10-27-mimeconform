# golden case: a-related-start

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：SO 39328935——原话：Why doesn't my embedded image display in Gmail or Office 365?
- 输入：`msg.eml`（594 bytes；sha256 `e6b5d3ea3a7c77d47f7d2a79d3ab03d5bcd77d084e735b76d7787ee705db0ad0`）
- 期望指纹：`ba7b1bc3fb4b969aaacfd64538d4de35f05c10444591ef4ac85aeed53dd4e0da`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/a-related-start/msg.eml`

## 说明

`start` 缺省时取第一个子部件（本题口径）；显式给出却不指向首部件 → 登记。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-A05 | diff | note | 0 | 179 | absolute | none-by-design | start 指向 0.2（<img001@example.invalid>），而实际首部件是 0.1（<body-root@example.invalid>）：start 与实际首部件不一致（type="text/html" 与首部件一致，只记 start 这一项） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

