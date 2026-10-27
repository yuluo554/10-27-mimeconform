"""开发期工具（**不进入报告路径**）。

* :mod:`mimeconform.devtools.gen_golden` —— golden 语料生成器（里程碑 M1）
* :mod:`mimeconform.devtools.stdlib_compare` —— 用标准库 ``email`` 做对照取证

**`stdlib_compare` 是全项目唯一允许 `import email` 的地方**（`plan/00` D6）：
它只用于测试与证据（证明"标准库记为可解析、本工具记为缺陷"），
**不得被 `mimeconform/report.py` 或 `mimeconform/cli.py` 导入**
（`tests/test_engine_guards.py::test_devtools_isolation` 以 AST 断言）。
"""
