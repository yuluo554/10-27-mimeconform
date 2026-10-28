# golden case: c-empty-msg

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造容器样本（无外部来源）
- 输入：`mail.mbox`（412 bytes；sha256 `5c018af604729ff099b47eca23c745238c6634c3fb37cfc73a2ed78960bc1439`）
- 期望指纹：`00f50ee15bd050270d7b14f7946e1a05cf77f68d16d4f4de02d6d14c90995d6d`
- 树指纹：`None`（容器输入：§7.8 的 tree_digest 主语是一棵树，容器不适用）
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/c-empty-msg/mail.mbox`

## 说明

空消息仍占一个 `msg#N` 序号（后面的消息序号不回收）——序号按分隔行出现顺序、不按内容长度。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-C03 | diff | note | msg#2 | 0 | message-relative | none-by-design | 零长度消息：`From ` 分隔行（bob）与下一条分隔行（carol）之间没有任何字节（文件内位置见 expect_extra.file_offset） |

## 附加期望

```json
{
  "auto": "mboxo",
  "file_offset": 180,
  "variant_split_counts": {
    "mboxcl": 3,
    "mboxo": 3,
    "mboxrd": 3
  }
}
```

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

