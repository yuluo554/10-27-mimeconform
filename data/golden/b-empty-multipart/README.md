# golden case: b-empty-multipart

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造边界样本（无外部来源）
- 输入：`msg.eml`（208 bytes；sha256 `2cde174f15c75956da71e1f12904f05527de0cb15fac2009284c7bc7ddcd9e3d`）
- 期望指纹：`0479590435195277f1c398a22f6b56977f8459e544ebe11c13357bdad0d978bb`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/b-empty-multipart/msg.eml`

## 说明

「multipart 至少有子部件」是不变量但**无明文原句** → 补齐摘录前只能出 `note`（原句门禁，§7.1）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-B10 | diff | note | 0 | 201 | absolute | none-by-design | multipart/mixed 无任何 body part（RFC 无明文条款；依据 stdlib MultipartInvariantViolationDefect 的实现事实，只登记） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

