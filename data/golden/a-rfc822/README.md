# golden case: a-rfc822

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造归属样本（无外部来源）
- 输入：`msg.eml`（556 bytes；sha256 `9bd71ca0c40add3d65082ef7ecab978976b8a3563cda0cebf37872ca8f9041ac`）
- 期望指纹：`70b66b73ded9aec591b7f6e94fbf3abe495813ea34c7dff7c46fe297efdcf5d3`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/a-rfc822/msg.eml`

## 说明

嵌套消息的头块属于内层部件（引擎递归下钻），外层只登记归属无法判定。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-A06 | diff | note | 0.2 | 322 | absolute | none-by-design | message/rfc822 转发体没有 disposition：它是转发副本还是附件无法判定（内层消息自己的头块单独成节） |

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

