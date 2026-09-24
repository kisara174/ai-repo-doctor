# AI Repo Doctor V2 设计

## 目标

V2 在保留 V1“只读、仅分析本地源码、静态关系不确定时不猜”的前提下，补齐三个由真实仓库评估暴露的问题：显式包重导出没有连到实现、装饰器注册关系没有进入上下文、以及 `typing.overload` 声明与具体实现被一起当作重复定义。

V2 仍是 Python CLI，不执行目标代码、不安装或导入目标项目、不访问网络、不发送源码，也不自动调用模型或应用补丁。运行时继续只依赖 Python 3.11+ 标准库。

## 评估依据

V1 已完成 `psf/requests` 回归。本轮另外评估了官方 Pallets Click 仓库的固定快照 `06b2a678741131fd577ce170e23e5ca0aeba0309`。V1 扫描该快照得到 91 个 Python 文件、30,174 行、23,119 行非注释非空代码、173 个类、1,346 个函数、460 个方法，且没有语法解析错误。这些规模数据描述扫描范围，不是准确率指标。

观察到的具体缺口：

1. `src/click/__init__.py` 第 70 行显式导出 `echo`：`from .utils import echo as echo`。Click 快照中有 403 个 `click.echo` 调用表达式，但 V1 没有一条从这些调用到 `src/click/utils.py::echo` 的调用边。
2. `examples/repo/repo.py` 用 `@click.group()` 定义 `cli`，再用五个 `@cli.command(...)` 注册 `clone`、`delete`、`setuser`、`commit` 和 `copy`。V1 的 `context` 没有把这些子命令作为 `cli` 的关联上下文。
3. Click `core.py` 中 `Context.invoke`、`Group.command`、`Group.command.decorator`、`Group.group` 和 `Group.group.decorator` 等定义因 overload 声明而出现重复符号歧义；其中带 `@t.overload` 的签名应与唯一的具体实现区分。
4. Click 的 `Group.invoke` 中 `sub_ctx.command.invoke(sub_ctx)` 依赖运行时对象类型；V1 没有解析到 `Command.invoke`。V2 将此作为明确的未解决动态分派案例，不以本次工作承诺解决。

总 unresolved-call 数包含测试、示例、内建函数及外部依赖调用，不能作为精确率或召回率。V2 验收只报告有源码证据的代表性关系，并检查误连。

评估源码： [Pallets Click 固定快照](https://github.com/pallets/click/tree/06b2a678741131fd577ce170e23e5ca0aeba0309)、[Click 包导出](https://github.com/pallets/click/blob/06b2a678741131fd577ce170e23e5ca0aeba0309/src/click/__init__.py#L10-L74)、[Click Group.command](https://github.com/pallets/click/blob/06b2a678741131fd577ce170e23e5ca0aeba0309/src/click/core.py#L1841-L1888)、[Click Group.invoke](https://github.com/pallets/click/blob/06b2a678741131fd577ce170e23e5ca0aeba0309/src/click/core.py#L2048-L2114)、[Click 示例命令组](https://github.com/pallets/click/blob/06b2a678741131fd577ce170e23e5ca0aeba0309/examples/repo/repo.py#L26-L161)。

## 方案选择

1. **通用静态关系模型，加有限的 Click 注册识别（推荐）**：导入导出、普通调用、装饰器元数据和语义关系各自建模；只对明确识别的 Click API 建立命令注册边。可复用于其他 Python 包，同时把推断边界留在可测试的小范围内。
2. **只针对 Click 加特例**：能较快修复评估样例，但会把框架名和关系类型散落到通用解析逻辑中，之后难以复用于其他包。
3. **运行目标代码来观察注册行为**：可能发现更多动态关系，但会执行用户源码、引入副作用和环境依赖，违反 Repo Doctor 的只读安全边界。

采用方案 1。装饰器语法作为通用 AST 元数据保存；V2 首个语义适配器只理解 Click 命令组注册的有限、静态可确认形式。

## V2 行为与边界

### 显式重导出

- 对无条件的模块级显式导入建立导出表，支持 `from .impl import name as public_name`，以及经由多个本地模块的同类显式重导出链。这里的“重导出”表示可静态解析的模块级导入绑定，不推断作者是否有意将它设为公共 API。识别 `import package as alias` 等现有模块别名时，也允许属性访问沿导出表找到唯一的本地实现。
- 只有唯一、无冲突、最终指向一个本地符号的链才解析。调用边的目标是规范实现符号；边证据保留调用位置和经过的导出链，便于审查。
- 重导出本身单独记录为 `reexport` 语义边，字段为 `kind`、`source_file`、`exported_name`、`target_symbol`、`evidence_file` 和 `line`。它不计入普通调用边。
- 导入别名冲突、模块或符号重名、重导出环、条件分支内的导入、`import *`、动态 `__getattr__`、任意赋值别名及外部目标均不推断。无法唯一解析时保留 unresolved/ambiguous 状态。

### `typing.overload`

- 通过 AST 识别未被遮蔽的 `typing.overload` 和 `typing_extensions.overload`，包括模块导入别名及 `from ... import overload as ...` 别名。
- 对同一词法父级、限定名和作用域的定义分组。若组内有一个具体（非 overload）定义和一个或多个 overload 声明，则具体定义是唯一可执行符号和调用目标；overload 声明保留为签名元数据及源码位置，不再导致该符号歧义。
- 若出现多个具体定义、只有 overload 声明、装饰器无法确认、名称被局部遮蔽，或定义作用域不一致，继续按 V1 的保守规则标记歧义，不选择猜测的实现。
- overload 元数据不进入普通调用图，也不作为额外的可执行符号计数。

Python AST 为函数定义暴露 `decorator_list`；Python typing 文档规定 overload 声明后跟一个具体实现。本设计仅利用静态语法与受支持的导入别名，不导入 `typing` 或目标模块运行时求值。参考：[Python AST 函数定义](https://docs.python.org/3/library/ast.html#ast.FunctionDef)、[Python `typing.overload`](https://docs.python.org/3/library/typing.html#typing.overload)。

### 装饰器与 Click 注册关系

- 每个函数/方法在 `symbols[].decorators` 记录装饰器表达式、起始行号及可选的识别类型；未知装饰器只作为源码元数据，不自动视为调用边或行为结论。
- 静态识别来自未遮蔽 `click` 导入的 `click.group`、`click.command` 及其明确导入/模块别名，例如 `import click as c`、`from click import group as cli_group`。若本地项目模块遮蔽 `click`，不启用该适配器。`@click.group()` 标记其回调符号为可识别的组；`@click.command()` 标记命令回调。
- 仅当注册接收者能唯一解析为同一模块中的已识别组回调，并且绑定没有冲突或重赋值时，才识别 `@group.command(...)` 和 `@group.group(...)`。对每个回调建立方向为“父组 → 回调”的 `command_registration` 语义边，记录装饰器所在文件和行号。
- 挑战集追加的显式注册形式使用 Click 的 `Group.add_command(cmd, name=None)` API。只识别恰好一个位置参数且该参数是同模块顶层、由已识别 `@click.command()` / `@click.group()` 修饰，或已通过上述可信装饰器注册边确认为子命令/子组的简单名称；接收者必须是已识别的组回调名称，或是未在当前方法中重绑定的 `self`，且该类沿同模块静态基类链最终继承自未遮蔽的 `click.Group`（支持模块别名及 `from click import Group` 别名）。语义边记录 `add_command` 调用行。参数重绑定、局部遮蔽、动态接收者、关键字/展开参数和无法确认的跨模块基类继续不推断。
- 不执行装饰器。任意第三方装饰器、动态创建或重绑定的组对象、反射注册、插件加载、工厂返回的组对象及静态信息不足的关系不建立注册边。

### 关系输出、上下文与影响

- `call_edges` 仍只表示代码中的调用，保留现有字段及含义；通过重导出解析的调用指向规范实现，并附带 `via_reexports`（每段的文件、导出名和证据行）。
- 新增独立的 `semantic_edges`。除 `reexport` 外，`command_registration` 记录 `kind`、`source_symbol`（父组）、`target_symbol`（回调）、`evidence_file` 和 `line`。不同关系类型不混入普通调用统计。
- `scan --json` 新增 `semantic_edges`、`symbols[].decorators` 和 `symbols[].overloads`（各 overload 声明的签名与源码行范围）；重导出链也作为可审查证据提供。V1 已有字段保持名称和原意。`schema_version` 升至 2。所有 JSON 命令输出的版本号一致升至 2，消费者可据版本选择兼容策略。
- `context` 保留现有目标优先、源码行数预算和普通调用关系；对组显示注册的命令回调，对回调显示其注册组，关系分别标注 `registered_command` / `registered_by`，行号指向装饰器。语义邻居遵循同一确定性排序和预算，不伪装成 callee/caller。
- `impact` 保留反向普通调用路径和模块导入者；单独增加注册关系结果，并标注方向和证据。注册关系不加入普通调用路径、深度或“运行时受影响”的断言。
- 人类可读输出明确区分普通静态调用、重导出解析证据和装饰器注册关系。所有关系均为静态线索，不代表运行时覆盖或实际执行。

## 非目标

- 通用动态分派、多态推断、猴子补丁、反射、任意赋值别名、任意装饰器语义。
- 动态 import、插件发现、`__getattr__` 导出、通配符导入展开和第三方依赖源代码获取。
- 通用框架注册分析；Click 以外的框架暂不建立专用语义关系。
- API 模型调用、联网、源码上传、补丁生成/应用、目标代码或测试执行、自动评分和跨语言支持。

## 验收标准

1. 现有 V1 测试和 `psf/requests` 回归继续通过，且 V2 的 `schema_version`、字段兼容策略有 CLI 测试覆盖。
2. 本地夹具覆盖显式重导出、别名链、唯一规范目标，以及冲突、环、条件导入、通配符和动态导出保持未解析的情况。
3. 本地夹具覆盖 `typing`/`typing_extensions` 直接与别名 overload，确认“多个 overload + 一个实现”唯一解析到实现；多个实现或仅有 overload 的情况仍歧义。
4. 本地夹具覆盖 Click 模块/函数别名、组注册、子组注册、正确的装饰器行号，以及未知装饰器、重绑定组名和歧义接收者不产生注册边。
5. 对固定 Click 快照，`click.echo` 调用可经 `click` 包显式导出解析至 `src/click/utils.py::echo`；`examples/repo/repo.py::cli` 上下文可标出五个注册回调及其装饰器证据行。
6. Click 动态 `sub_ctx.command.invoke` 仍可以 unresolved 展示；验证输出不会将它计为已解析调用。
7. 检查语义边的重复、冲突和误连；报告关系样例及 unresolved 限制，不把调用总量当作精确率指标。
8. 固定挑战快照中的模块级 `cli.add_command(group)` 和已证明继承 Click `Group` 的类方法 `self.add_command(run_command)` 均产生 `command_registration` 边，证据行分别指向实际调用；未知接收者和动态回调名称仍不产生边。
9. 对方法内重绑定后的 `self.add_command(...)` 不建立语义边；对同模块 `Group` 别名和多层继承仍能识别未重绑定的实例接收者。

## 参考资料

- [Python AST 文档](https://docs.python.org/3/library/ast.html)
- [Python typing.overload 文档](https://docs.python.org/3/library/typing.html#typing.overload)
- [Pallets Click 文档与源码](https://github.com/pallets/click)
- [AI Repo Doctor V1 设计](2026-09-24-repo-doctor-v1-design.md)
