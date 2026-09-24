# AI Repo Doctor V1 设计

## 目标与边界

首版是一个可以安装和直接运行的 Python CLI。输入一个本地 Python 仓库，生成可复用的代码结构索引；指定一个函数或方法时，输出沿已解析关系收集的有行号的上下文；对外部模型提出的诊断做程序化证据校验。这是用户提供的项目定义中“第一阶段”的完整纵向切片。

首版无需 API Key，也不发送源码到网络。用户可把 `context` 输出交给已有的 ChatGPT 会话，要求返回约定 JSON，再用 `validate` 校验。自动调用模型、自动生成/应用补丁、运行目标仓库命令、评分、跨语言解析和 Web UI 属于后续阶段。它们不会以空壳命令出现在首版 CLI 中。

## 接口

Python 版本：3.11+。运行时仅依赖标准库。

```text
repo-doctor scan PATH [--json]
repo-doctor context PATH SYMBOL [--max-lines N] [--json]
repo-doctor impact PATH SYMBOL [--depth N] [--json]
repo-doctor validate PATH FINDINGS.json [--json]
```

`SYMBOL` 为 `仓库相对路径::限定名`，例如 `app/services/user.py::UserService.create`。`scan --json` 输出带 `schema_version: 1` 的结构索引；文本模式展示统计、解析错误、局部导入环和可选的符号列表提示。`context` 输出可直接复制给模型的 prompt，包含目标符号、直接依赖、调用者、关联测试及每段源码的真实路径和行号。`impact` 输出沿已解析的反向调用边的直接和间接调用者，以及所在模块的直接导入者；这些是静态近似，不宣称运行时覆盖率。`validate` 接受一个 finding 对象或对象数组，逐条返回 accepted/rejected 和具体理由；至少需要 `title`、`category`、`confidence`（0 到 1）、非空 `evidence`、`reasoning`、`impact`、`suggested_fix`。每条证据需要 `file`、`start_line`、`end_line`、`quote`，可选 `symbol`。

## 数据流与模块

1. `scanner`：Git 仓库用 `git ls-files --cached --others --exclude-standard -z` 列出工作树内已跟踪及未忽略文件；过滤非 `.py`、不存在的路径和符号链接。非 Git 目录使用遍历与明确的常见生成目录排除规则，并在输出元数据中标明无法应用 Git ignore 规则。扫描只读取本地文件。
2. `parser`：用标准库 `ast` 读取每个文件，提取类、函数、方法、限定名、准确的 1-based 起止行、导入声明和调用点。语法或解码错误被记录为解析错误，其他文件继续处理。索引不保存完整源码；上下文构建和证据校验时按需重新读取。
3. `graph`：把局部模块名映射至文件（兼容常见 `src/` 布局），解析相对/绝对导入并标注来源行；只为可静态定位的局部调用建立调用边。对于局部变量，仅当调用前有且只有一次无条件的简单构造赋值，或 `with ... as` 的对应 `__enter__` / `__aenter__` 能静态确认返回 `self`，才解析该变量的方法调用；歧义类型、重绑定、遮蔽和条件赋值仍保留为 unresolved。检测局部模块导入环。
4. `context`：以目标符号优先，接着已解析的被调函数、调用者和相关测试，按确定性顺序与行数预算选取源码片段；输出实际行号、裁剪说明及关系类型。无法解析的外部依赖不当作“无依赖”。
5. `evidence`：检查 finding 形状、文件是否在扫描集合内、行号是否合法、引用原文是否在指定行段内、可选符号是否存在且与行段相交。校验通过只代表引用真实且可定位，不代表推理结论正确。
6. `cli`：解析参数、统一非零错误退出码、人类可读文本及稳定 JSON 输出。

## 准确性与失败处理

- 符号、调用和导入图来自 AST 静态分析。动态 import、猴子补丁、反射、别名传播和多态调用不会被推断；关联测试表示静态引用，不表示测试覆盖率。
- 局部实例方法调用仅支持调用前唯一且无条件的简单本地类构造绑定，例如 `client = Client()`；上下文管理器绑定还要求对应的 `__enter__` / `__aenter__` 只有一个直接的 `return self`。复杂工厂、属性赋值、实例重绑定和外部类保持未解析。
- 编码按 Python 源码声明读取。单个文件解析失败不会抹掉其他文件的结果。
- `context` 在预算内优先保留目标；超预算明确标记截断。预算是源码行数，不是 token 数。
- 解析、上下文和校验共用源码读取器。在支持 `dir_fd` 与 `O_NOFOLLOW` 的平台上，从文件系统根目录开始逐级打开目录与文件描述符，并核对仓库目录在建索引时的设备号与 inode；其他平台使用路径检查。绝对路径、`..`、符号链接、越界行号和不存在的符号均拒绝，避免用任意路径伪造证据。
- 同一限定名出现多个定义时，索引把它及其子符号标为歧义，不建立相关调用边。
- 输出排序确定，供人审查与后续版本比较。索引不持久化，每次命令针对当前工作树重建，避免陈旧证据。

## 验收

1. 一个含包、相对导入、类方法、测试和 `.gitignore` 的临时仓库可生成符号图和导入图，并能把唯一可解析的调用连到正确符号。
2. `context` 选中函数时输出有行号且受预算限制的真实源码；`impact` 给出可解释的反向关系。
3. 真实引用通过 `validate`；虚构文件、越界行号、错误原文和不存在符号被拒绝。
4. 完整测试集、模块入口、安装后的命令和真实仓库烟测通过。

## 依据与后续阶段

AST 节点提供 1-based `lineno` / `end_lineno`；Git 的 `--exclude-standard` 使用标准 ignore 来源；项目命令入口使用 `[project.scripts]`。资料：[Python `ast`](https://docs.python.org/3/library/ast.html)、[Python `os.open`](https://docs.python.org/3/library/os.html)、[Python `tokenize`](https://docs.python.org/3/library/tokenize.html)、[Git `ls-files`](https://git-scm.com/docs/git-ls-files)、[Python Packaging User Guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)。

后续阶段按实际使用反馈依次考虑：可选 API 诊断、更多确定性分析器、隔离环境中的补丁与验证、架构重建、跨语言解析。每项都应保留“模型提出、程序验证”的约束。
