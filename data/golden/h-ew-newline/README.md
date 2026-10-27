# golden case: h-ew-newline

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：SO 52442469——实样 `=?UTF-8?Q?=C3=A5 =C3=A4?=`；原话：Are newlines in MIME headers using encoded-words legal?
- 输入：`msg.eml`（205 bytes；sha256 `63744b3760f99c86610aef217e3493e47f8a9b30fa84210ed3e636c44733b614`）
- 期望指纹：`96f49706ec47b0dc9ae26c45d3b4d319f6c17b7e685b23141b3669c28a019f2f`
- 树指纹：`5c7d2edfce79ff71b63546792e45936677d2edb888760b007f0f563b76f0d5fd`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/h-ew-newline/msg.eml`

## 说明

命中 MC-H12 后**不得**同时报 MC-H03（§7.5 第 2 条）；`related` 记录被压掉的规则号。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-H12 | diff | note | 0 | 63 | absolute | none-by-design | encoded-word 跨折行：`=?UTF-8?Q?=C3=A5` 与 `=C3=A4?=` 被 FWS 折在一个 encoded-word 内（先折叠还是先解码，RFC 未定） |

## 附加期望

```json
{
  "no_double_record": true,
  "related": [
    "MC-H03"
  ]
}
```

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

