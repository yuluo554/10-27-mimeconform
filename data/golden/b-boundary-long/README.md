# golden case: b-boundary-long

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 2
- 来源：自造边界样本（无外部来源）
- 输入：`msg.eml`（485 bytes；sha256 `e92f2c8a084448eb2b44242883d0f8286d85863ab0e2cded097c5dd59da38aff`）
- 期望指纹：`816a105a8f100502bcabf1355a7aad9bf3d1cf87bedeccfb78bbc687c8f967ad`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/b-boundary-long/msg.eml`

## 说明

`minor` → 退出码 2（无 blocker/major）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-B02 | hard | minor | 0 | 160 | absolute | RFC 2046 §5.1.1 | boundary 长度 71 > 70（不含前导两个连字符） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

