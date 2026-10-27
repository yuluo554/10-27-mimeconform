# golden case: b-no-final

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造边界样本（无外部来源）
- 输入：`msg.eml`（293 bytes；sha256 `96961a466c46f083c8af11de89b1d059e9511952726395dd6403004671eb74c4`）
- 期望指纹：`011a815f669aefcc85c39da58839dd0ba4361fcdadb0f1490af615d19f3a9e80`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/b-no-final/msg.eml`

## 说明

`diff/note` 不影响退出码（退出码 0）——证明没把它硬判成错误（难度格：§四.1）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-B05 | diff | note | 0 | 293 | absolute | none-by-design | 缺 final boundary：树在第 293 字节被迫闭合（RFC 只描述 truncated entity，无恢复规程） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

