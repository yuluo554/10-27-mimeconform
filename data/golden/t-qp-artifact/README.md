# golden case: t-qp-artifact

- 期望：正例（缺陷集非空）；缺陷数 3；退出码 3
- 来源：SO 79133579——实样 We request all our =ustomers … =o:p> … please make =ure
- 输入：`msg.eml`（378 bytes；sha256 `8d8004c1ea4e1af81e8d3632a9971ee3d6e8605cac9cf070cdb581d681fd10da`）
- 期望指纹：`4329adcc8dc4af1d3c24a467596766173eda5d72864242dfb6ee232e122f6a3c`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/t-qp-artifact/msg.eml`

## 说明

**每处非法转义各记一条**（精确到字节偏移），不是合并成一条 —— M4 落地时引擎与 golden 取同一口径。条款论证：R8 把行末 `=` 的唯一合法语义限定为软换行，故 `=` 后非 `HH` 即违反 §6.7；推导链写进 `docs/defect-catalog.md`（`plan/06` Q1 留了「降为 diff」的开关）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-T07 | hard | major | 0 | 281 | absolute | RFC 2045 §6.7 | QP 非法转义 `=us`：`=` 后不是两位十六进制（原帖实样 =ustomers） |
| MC-T07 | hard | major | 0 | 316 | absolute | RFC 2045 §6.7 | QP 非法转义 `=o:`：`=` 后不是两位十六进制（原帖实样 =o:p>） |
| MC-T07 | hard | major | 0 | 362 | absolute | RFC 2045 §6.7 | QP 非法转义 `=ur`：`=` 后不是两位十六进制（原帖实样 =ure） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

