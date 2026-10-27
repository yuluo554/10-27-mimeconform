# golden case: b-deep-nest

- 期望：正例（缺陷集非空）；缺陷数 1；退出码 0
- 来源：自造边界样本（无外部来源）
- 输入：`msg.eml`（2481 bytes；sha256 `38e9445715cb35ec0652fbdc435159b19f8d8f4bd5287af18fadbfb19aeb9bf5`）
- 期望指纹：`86284bc0456a1eca097d6a4f9eaa513c3ae937572fc030723ff3a430861f3ed2`
- 树指纹：`868f6be6beb363f8c1d2ed67413b7dc124c6f9824d09c2bc9234e94faeb5c414`
- 比对键：`rule_id` / `path` / `offset` / `class`（**不比 `severity`** —— 受原句门禁影响会随里程碑提升）
- 重生成核对：`py -3.12 -m mimeconform.devtools.gen_golden --check`
- 引擎回归（M2 起）：`py -3.12 -m mimeconform audit data/golden/b-deep-nest/msg.eml`

## 说明

`--strict-depth` 才把超深度计入退出码（届时 severity 提为 minor）；默认下本文件退出码 0。引擎超限**停止下钻**并登记 `truncated`，不是崩溃、不是静默截断。

## 期望缺陷

| rule_id | class | severity | path | offset | offset_kind | rfc | detail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MC-B09 | gray | note | 0.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1 | 1941 | absolute | none-by-design | 嵌套深度 33 > --max-depth 32（RFC 未规定深度上限；策略项，默认不影响退出码） |

## 附加期望

```json
{
  "depth_convention": "节点深度 = 路径段数（根部件 `0` 为第 1 层；`0.1` 为第 2 层）",
  "first_over_depth_path": "0.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1.1",
  "max_depth": 32,
  "truncated": true
}
```

## 数据级自检

`expect.json` 由生成器与语料同轮产出；输入 sha256 / 字节数、`defect_count` / `exit_code` /
`fingerprint` 全部由构造算出。任何一条对不上，`--check` 与 `selftest` 都会显式失败。

