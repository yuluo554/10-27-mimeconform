# golden case: a-body-attach

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：SO 6255202——原话：when someone sends an email with a text attachment, the contents of the text file shows up for the body variable
- 输入：`msg.eml`（454 bytes；sha256 `ee5549c76c0bd138f9c9d009b8a15eadabac4b12d3e311b53aa38ceb25c675c1`）
- 期望指纹：`a21cae8b14afdd636c4d6a658c27c1e2e16bf01626efb64f1c7bb95b223e1518`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/a-body-attach/msg.eml`

## 说明

M4 全部规则无 hard（D11）：`Content-Disposition` 的正式规范不在本题核对的五部 RFC 内 → `rfc` 写 none-by-design。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-A01 | diff | note | 0.2 | 313 | absolute | none-by-design | text/* 叶节点缺可判定 disposition，且 0.1 是兄弟 text/plain 正文候选：下游会把这个文本附件当成正文（SO 6255202 的形状） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

