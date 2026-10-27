# golden case: t-7bit-long

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造传输编码样本（无外部来源）
- 输入：`msg.eml`（1244 bytes；sha256 `b9528d6c48592634cca0784e8e315be0be6e6edd33ab53b34329cf8aeda898be`）
- 期望指纹：`4b0346453a63d5557bc3c903b26cbd5bfff26409421d244fd9db7741f9afde87`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/t-7bit-long/msg.eml`

## 说明

正文行宽与头行宽是两条账：头行超 998 走 MC-H07（R5 已录），正文行超 998 走本条（R11 未录 → note）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-T09 | diff | note | 0 | 242 | absolute | RFC 2045 §2.7/§2.8/§6.1（R11 整行未录原句 → 门禁降级，只登记） | 7bit 正文行 1000 > 998 octets（R11 整行未录 → 只登记） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

