# golden case: a-no-disposition

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：SO 24246391——原话：message-text always goes into attachment
- 输入：`msg.eml`（444 bytes；sha256 `5fb66303d2d3b45665a3e72a1b297e4851bbb46a49b6177a536d7f79ac1d3a8d`）
- 期望指纹：`2e0973cb57f64c7429d53d6284b7f16535161e84afa09781bf9555e5ff02c643`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/a-no-disposition/msg.eml`

## 说明

登记在 multipart 节点（path `0`）：现象是「整棵树归属不可判定」，不是单个叶节点的账。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-A08 | diff | note | 0 | 174 | absolute | none-by-design | 两个叶节点都缺可判定 disposition，且没有 text/plain 正文候选：下游的正文/附件归属无法判定（SO 24246391 的形状） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

