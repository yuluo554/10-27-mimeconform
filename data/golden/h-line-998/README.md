# golden case: h-line-998

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 3
- 来源：自造头编码样本（无外部来源）
- 输入：`msg.eml`（1178 bytes；sha256 `158b066a900ad67c49365c0bf285f109d1a34ce8cfd9692ea47e934a322bea4b`）
- 期望指纹：`722d6db4be16fbf64cbc425e8ec853fd896ed8ce607f0a2107152b324f8c4f7a`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/h-line-998/msg.eml`

## 说明

R5 全录；头行 > 998 先于 encoded-word 检查（§7.5 第 1 条）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-H07 | hard | major | 0 | 3 | line | RFC 5322 §2.1.1 | 头行 1009 > 998 octets（不含 CRLF） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

