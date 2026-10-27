# golden case: t-cte-unknown

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造传输编码样本（无外部来源）
- 输入：`msg.eml`（259 bytes；sha256 `7ef28af7bf46bf4c068cdda78fb53b9ac62003bf0d33860a4a30cf8b56bb6195`）
- 期望指纹：`559ecae4b063d75ba6b558f90c2ff23b328a2f98acbc2903250422a398d7d447`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/t-cte-unknown/msg.eml`

## 说明

§7.5 第 5 条：先判声明值是否已知（T08）→ 再判声明形态合法性 → 最后才判 declared vs observed；CTE 未知时无法交叉校验。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-T08 | diff | note | 0 | 209 | absolute | none-by-design | 未知 CTE 取值 `x-mystery-enc`（既不是 7bit/8bit/binary/quoted-printable/base64，也不是已知扩展 token） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

