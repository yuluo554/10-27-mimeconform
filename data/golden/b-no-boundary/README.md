# golden case: b-no-boundary

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 3
- 来源：自造边界样本（无外部来源）
- 输入：`msg.eml`（235 bytes；sha256 `9cab21fdb3e2402f7e335ee95380ec7717d1d176d70ddfa9341f38deb7380b41`）
- 期望指纹：`08b76339acfb16abd628b5145918b83d280da540bbc8156b30676f52036493de`
- 树指纹：`2a5863bfd5b3a638194304d39b42f7397b579fa15de3fbf6f9d39e5cd07d4104`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/b-no-boundary/msg.eml`

## 说明

结构无法建立（无任何可用 delimiter）→ `blocker`，退出码 3。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-B01 | hard | blocker | 0 | 162 | absolute | RFC 2046 §5.1.1 | multipart/mixed 缺 boundary 参数（RFC 2046 §5.1.1 要求多部件实体必须有一个 boundary 参数） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

