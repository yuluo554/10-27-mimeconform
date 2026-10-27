# golden case: c-maildir-name

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造容器样本（无外部来源）
- 输入：`maildir/cur/1700000000-bad-name`（150 bytes；sha256 `99bbbd6af7333d9dba3f121e4b698b52a7c70a84a240e951676c21663733bdde`）
- 期望指纹：`670b37f306e66c3b72a51036f5dc8b8623a9503290eb08b6c5bcb620ecc2311b`
- 树指纹：`None`（容器输入，自 M5 起回填）
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/c-maildir-name/maildir/cur/1700000000-bad-name`

## 说明

输入是目录形态（Maildir）：`input.file` 指向目录里的条目，M5 的 golden 回归按 case 目录下的 `maildir/` 定位容器。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-C05 | diff | note | msg#1 | 0 | absolute | none-by-design | cur/ 下的条目名 `1700000000-bad-name` 缺 `:2,<flags>` 信息段（Maildir 约定：cur 条目应为 `<unique>:2,<flags>`）；Maildir 没有 RFC 依据 → 只登记 |

## 附加期望

```json
{
  "container": "maildir",
  "entry": "cur/1700000000-bad-name",
  "offset_note": "规则作用于文件名、无字节偏移 → offset=0 是占位"
}
```

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

