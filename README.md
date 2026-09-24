# AI Repo Doctor

一个以证据为先的 Python 代码库诊断 CLI。它先建立符号、局部导入和可静态解析的调用关系，再按图谱收集有行号的源码；模型提出的问题必须通过文件、行号、原文和符号校验。当前版本只读本地文件，不运行被扫描仓库的代码，也不需要 API Key。

## 安装与快速开始

需要 Python 3.11+；安装 Git 后可自动遵循目标仓库的 ignore 规则。可以直接从源码运行：

```bash
python3 -m repo_doctor scan /path/to/python-repo
python3 -m repo_doctor scan /path/to/python-repo --json > repo-map.json
```

或在虚拟环境中安装 CLI：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/repo-doctor scan /path/to/python-repo
```

`scan` 文本输出会给出示例符号 ID。完整索引在 `--json` 输出中，包括文件、符号、导入声明、调用点、局部导入边、已解析调用边、语义关系、导入环和解析错误。

JSON 命令使用 `schema_version: 2`。`call_edges` 只表示普通静态调用；`semantic_edges` 单独记录显式本地重导出和 Click 命令注册。符号包含装饰器和 overload 签名元数据，调用边通过 `via_reexports` 保留重导出链。`context` 会为命令组和回调标出注册关系，`impact` 将语义关系与普通调用影响分开列出。

## 让 ChatGPT 诊断一个函数

```bash
python3 -m repo_doctor context /path/to/python-repo 'app/services/user.py::UserService.create' --max-lines 120 > context.txt
```

把 `context.txt` 内容交给 ChatGPT。它要求返回一个 finding 对象、finding 数组，或 `[]`。将模型返回的纯 JSON 保存为 `findings.json`，再运行：

```bash
python3 -m repo_doctor validate /path/to/python-repo findings.json
```

finding 结构：

```json
{
  "title": "可能的资源泄漏",
  "category": "reliability",
  "confidence": 0.8,
  "evidence": [
    {
      "file": "app/database.py",
      "start_line": 17,
      "end_line": 20,
      "quote": "session = SessionLocal()",
      "symbol": "app/database.py::get_db"
    }
  ],
  "reasoning": "说明为什么这些代码可能导致问题",
  "impact": "说明受影响的路径",
  "suggested_fix": "说明建议的修改"
}
```

`validate` 对有拒绝项的文件返回退出码 1；参数、路径或 JSON 无法读取时返回 2。通过校验只说明引文真实且定位正确，**不代表诊断结论一定成立**；仍需人工审查推理和实际运行验证。

## 影响分析

```bash
python3 -m repo_doctor impact /path/to/python-repo 'app/services/user.py::UserService.create' --depth 2
```

它沿已解析的反向调用边显示直接与间接调用者，并列出目标文件的局部导入者。`--json` 可用于工具集成。

## 当前精度边界

- 只解析当前 Python 解释器支持的语法。解析失败的文件会出现在错误列表中，其他文件继续分析。
- 显式本地重导出只沿可唯一解析的模块级导入绑定处理；此处的“重导出”表示静态可解析的绑定，不推断作者是否打算公开该名称。经过重导出的调用会指向规范实现，并附带每段导出证据。
- `typing.overload` 声明在同名唯一具体实现下作为签名元数据保留，不会成为额外的可执行符号或普通调用目标；缺少唯一实现时继续标记为歧义。
- Click 支持通过未遮蔽的显式 `click` 导入识别 `group`、`command` 装饰器，以及同一模块中唯一命令组的 `.command()` / `.group()` 注册关系（包括嵌套组）。这些注册边保留装饰器行号，但不计入普通调用统计或 impact 调用深度。
- Git 仓库采用 Git 标准 ignore 规则；非 Git 目录使用常见生成目录排除规则，不解释 `.gitignore`。
- 调用图只连向静态可定位的局部目标。对局部变量，只解析调用前唯一且无条件的简单本地类构造绑定（例如 `client = Client()`）；`with ... as client` 还要求对应的 `__enter__` / `__aenter__` 能直接证明返回 `self`、无需额外必填参数，并且类上存在匹配的 `__exit__` / `__aexit__`。复杂工厂、重绑定和多态分派仍可能无法解析。重名的条件定义会标为歧义；函数内部 import 的别名、动态 import、反射、猴子补丁、别名传播和外部包调用也可能无法解析。关联测试仅表示静态引用，不等于测试覆盖率。
- 上下文预算以源码行数计算；片段被截断时会标记。每次命令重新扫描当前工作树，不保留旧索引。
- 自动 API 诊断、补丁生成/应用与测试执行尚未实现。

详细设计和实施范围见 [V2 设计文档](docs/superpowers/specs/2026-09-24-repo-doctor-v2-design.md)。
