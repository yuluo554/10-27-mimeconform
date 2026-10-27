# golden case: t-qp-long

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 2
- 来源：自造传输编码样本（无外部来源）
- 输入：`msg.eml`（335 bytes；sha256 `9fc20144f18e9c1241bf318d0a959ff3d867f4ddf74696d0be9a52692a10cf52`）
- 期望指纹：`fc55c636cad93403ff8d49f0c4f9f03575c8584fd11a24cb1a2f40baeffd25d6`
- 树指纹：`ed274d2dcf499ba93a88d3eccdd17fa368f9ac4d40e92a78b945d0580ae36573`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/t-qp-long/msg.eml`

## 说明

R8 全录原句：encoded lines be no more than 76 characters long。行宽按 octets、不含 CRLF。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-T05 | hard | minor | 0 | 253 | absolute | RFC 2045 §6.7 | QP 编码行 80 > 76 octets（不含 CRLF） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

