# golden case: b-inner-dup

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 3
- 来源：cpython #69914（open）—— issue 原话：email parser ignores inner multipart boundary when outer message duplicates it
- 输入：`msg.eml`（348 bytes；sha256 `d675beb8c7e91569b50ff4a6f080752af4e1ffbb351002084d21a81c67aaff4a`）
- 期望指纹：`852f6f859643edd119a8c89f64402b8d6703b9102bd863da8234f6ea454c0e12`
- 树指纹：`a6a8a93a2dce26c743e91564cbc9ed58db3e515f668c94e70d1fcd47efd3081d`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/b-inner-dup/msg.eml`

## 说明

字节层无法唯一确定 close-delimiter 归属（外层先闭合 / 内层先闭合都成立）→ 本工具必须输出**两棵候选树**（`tree_alternatives` 长度 2 + `divergence` 指向 `0.1`），不替用户选一个（`plan/00` D9）。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-B06 | hard | major | 0.1 | 223 | absolute | RFC 2046 §5.1.1/§5.1.2 | 内层 multipart/alternative 复用了外层 boundary "X"（RFC 2046 §5.1.1/§5.1.2 要求每层用不同 boundary） |

## 附加期望

```json
{
  "divergence_path": "0.1",
  "tree_alternatives": 2
}
```

## 标准库对照（实测留证）

```json
{
  "defects": 1,
  "note": "3.12.10 实测：标准库把内层 multipart/alternative 当作**非 multipart**（is_multipart=False）并记 StartBoundaryNotFoundDefect —— 即 #69914 的「忽略内层 boundary」；它**不报告 boundary 复用本身**，也不给两棵候选树。",
  "types": [
    "StartBoundaryNotFoundDefect"
  ]
}
```

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

