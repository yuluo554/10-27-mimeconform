# golden case: c-body-from

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造容器样本（无外部来源）
- 输入：`mail.mbox`（261 bytes；sha256 `416295b45487a2b8d9287929df65740da42aa9775ff661312326ff71be66e6f8`）
- 期望指纹：`84f4552e673bc0d98b2050d3abb723a3a896b1525628ef5df66a6fcf19ef16d1`
- 树指纹：`None`（容器输入：§7.8 的 tree_digest 主语是一棵树，容器不适用）
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/c-body-from/mail.mbox`

## 说明

与 MC-C02 的分工：C02 = 变体读法**不一致**（有 Content-Length 兜住的那类）；C04 = 三种读法**一致**误切（片段不成消息）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-C04 | diff | note | msg#2 | 0 | message-relative | none-by-design | 该 `From ` 行信封完整，但它是被误当分隔行的正文内容 —— 切出的片段不具备消息头块：正文含裸 `From ` 行的直接证据（本节无 Content-Length，三种读法一致误切） |

## 附加期望

```json
{
  "auto": "mboxo",
  "file_offset": 195,
  "variant_split_counts": {
    "mboxcl": 2,
    "mboxo": 2,
    "mboxrd": 2
  }
}
```

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

