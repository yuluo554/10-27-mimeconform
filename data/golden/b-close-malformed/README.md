# golden case: b-close-malformed

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造边界样本（无外部来源）
- 输入：`msg.eml`（347 bytes；sha256 `1aebcaa3b692998699138c3a64299005b69be0c891d0c6dd1ddd82d37503268d`）
- 期望指纹：`e33171314c72674cd868046f139203d200eaa06732c4771734c085f6c737c526`
- 树指纹：`2172edf40171bb0e9c4b8b43ea53bf0f5acb035d74e44fe5aab50626ede65d24`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/b-close-malformed/msg.eml`

## 说明

文件里同时存在一个**合法**的 `--C--` 收尾 → 不记 MC-B05（缺 final boundary）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-B04 | diff | note | 0 | 271 | absolute | RFC 2046 §5.1.1 | close-delimiter 形态错误：`--C--` 之后还有 `junk`（只允许可忽略的空白与行尾） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

