# JS/TS 只读调查预览规格

日期：2026-10-02。依据：用户认可的 A0–A4 探索与 B1–B4 产品化清单。
状态：**首次 A0–A4 于 2026-10-03 完成，decision=no-go，原结果保留。随后[按需流程复核](../../evaluations/2026-10-03-js-ts-adaptive-workflow.md)观察到两仓库结构题各减少一次动作，独立 follow-up gate=go，符合 B 阶段继续条件。六题总计 19 次仍高于源码基线 18 次；[B1 源码接入](../../evaluations/2026-10-03-js-ts-B1.md)已核对完成；B2–B4 尚未实施，已部署产品仍是 Python v0.5.2。**

## 1. 目标与完成形态

在已部署 Python v0.5.2 保持稳定的前提下，验证 JS/TS 是否帮助 Codex 找入口、查符号、获取源码上下文和解释局部关系；收益成立后交付可选安装的只读预览。

人查看项目结构和有来源的关系图。详细判断、补读和修改由 Codex 承担。新能力沿用 overview、symbols、context、impact、map，不添加新的用户命令或 MCP 服务。

本轮终点是：两个固定仓库的六题调查、明确去留决定；若继续，再交付独立安装且能实际使用的预览包。不是整仓缺陷发现，也不是动态运行验证。

## 2. 已核对的基线

项目主目录：/Users/kisara/Documents/ChatGPT/AI Repo Doctor。

- 基线文档 HEAD：337c1cae1a068ce46e60f83343ccfdab52249023。
- 稳定代码 tag v0.5.2：ada493946525329d3bd0e842eaf94b7a8c025fca。
- Python 要求 >=3.11；默认运行依赖为空；现有 CI 为 Python 3.11–3.13。
- build_index(root: Path) 只发现 .py，调用 parse_python_file，再调用 resolve_graph / resolve_semantic_edges。
- model.py 的 RepoIndex、Symbol、FileRecord、CallEdge、ImportEdge 为共享记录。ImportRef 和 Python 图解析包含 Python 导入语义，不能拿来表示 ESM。
- context.py 用 Python AST 选择类头、基类和导入。JS/TS 必须提供自己的源码位置元数据。
- agent_tools.py、cli.py、case.py、repo_map.py 有 python_files 等统计；JS 文件不能加入这些计数。
- repo_map.py 和 viewer.js 的默认关系图按 node.python 过滤。文件路径可见不等于符号已分析。
- case.source_fingerprint 已按 index.files 的路径与源码排序计算；扩大文件选择时必须包括新增语言，同时保留纯 Python 算法的结果。

这些是编写计划时的只读核对，不代表 A 阶段执行完成。

## 3. 硬约束

- Python >=3.11；默认运行依赖为空。
- 默认语言选择为 python；旧命令、旧 Python ID 和旧报告保持兼容。
- 显式选择 javascript / typescript 后才加载新增解析后端。
- 新语言只接入 overview、symbols、context、impact、map 五个只读命令。
- 首期 JS/TS context 不支持 --snapshot-out；组合使用必须在写文件之前返回退出码 2，解释使用 --json。Python 快照和 findings 流程保留。
- 本期不扩展 JS/TS report/findings、云端诊断、回归执行、自动补丁、跨语言调用、框架注册、缓存或图布局。
- 样本只静态阅读；不运行其代码，不安装其依赖，不调用其 package scripts。
- GraphFlow 在读代码/实现前使用；改动后更新索引。
- 现有安全读取、路径边界、忽略目录、隐藏数和源码一致性检查保持。
- 主代理负责选择、设计、debug、独立参考答案、审查和发布。Luna / Harness 只接收符合用户 AGENTS 的机械包。
- Mac 稳定入口、Skill、Key、旧报告、发行包和四份用户文档改动保留。

## 4. 首期支持边界

| 项目 | 首期行为 |
| --- | --- |
| .js / .mjs / .ts 实现文件 | 提取具名函数、const 绑定的箭头/函数表达式、类、方法、异步标记与源码行 |
| ESM 导入/导出 | 保存名称、别名、specifier、整条声明跨度、type_only；本地路径唯一时给文件关系 |
| 顶层匿名默认函数 | 使用明确的 <default> 名称；相同 ID 冲突标歧义 |
| TS 重载 | 仅一个具体实现加具名签名时合并，复用 OverloadSignature；无实现是声明，不当作运行函数 |
| 普通调用 | 先仅解析不被遮蔽/改写的顶层具名函数或 const 函数绑定，以及直达导出的 ESM 导入函数 |
| 类方法调用、this、对象链、回调 | 方法符号可查；调用目标未知，不靠同名连接 |
| 嵌套/块级具名函数 | 可提取；首期不解析其调用，避免猜测 JS 词法作用域 |
| re-export | 有来源的文件依赖与原始导出记录；多跳符号目标/调用首期不解析 |
| JSX/TSX、CommonJS、.mts/.cts/.d.ts | 路径展示并明确不支持的层级；.js 内 CommonJS 不当作 ESM 导入 |
| namespace / computed / dynamic import | 记录限制；不生成普通调用目标 |
| bare package、路径别名、目录 index、extensionless | 保留来源与未解析原因，不读取 node_modules，不猜映射 |
| TS 从 ./x.js 导入 | 按官方扩展替换候选核对；仅仓库内唯一 .ts 或 .js 实现且无其他候选时连接 |
| 解析错误 | 记录第一处 ERROR / missing 的文件与行；该文件不输出部分符号或关系 |
| 纯 Python、混合仓库 | 各语言独立解析和解析关系，最后合并；不形成 Python↔JS/TS 调用 |

支持范围是有界语法集合，不宣称支持任意 JS/TS 工程或完整 TypeScript 类型检查。支持能力随阶段变化，不能先显示已完成的 calls。

## 5. 技术与依赖决策

探索优先核对 Tree-sitter Python 绑定。编写计划时已从 PyPI 官方元数据核对以下候选及 Mac arm64/x86_64 wheels：

| 候选 | 版本 | Python 元数据 |
| --- | --- | --- |
| [tree-sitter](https://pypi.org/project/tree-sitter/0.26.0/) | 0.26.0 | >=3.10 |
| [tree-sitter-javascript](https://pypi.org/project/tree-sitter-javascript/0.25.0/) | 0.25.0 | >=3.10 |
| [tree-sitter-typescript](https://pypi.org/project/tree-sitter-typescript/0.23.2/) | 0.23.2 | >=3.9 |

**A2 在独立 Mac arm64 / Python 3.14.5 环境完成安装、API 和编码检查。** A3 真实输入发现 Point 属性崩溃，受控输入复现；原型改用字节偏移推导行号，回归与所选源码证据通过。详情见 [探索报告](../../evaluations/2026-10-02-js-ts-exploration.md)。这不表示所有平台或所有原生 API 无缺陷；不默默换版本或增加后端。

A2 只与 TypeScript Compiler API 做官方资料层面的范围/运行环境比较。若 Tree-sitter 满足限定需求，就选它；不展开性能竞赛，不安装另一套后端来增加任务。

选择成立后，pyproject.toml 保留 dependencies = []，增加 js 可选项并精确固定上述三个已验证版本。普通 Python 调用不导入 Tree-sitter。缺少后端时，显式 JS/TS 命令退出 2，给出安装 js 可选项的可操作提示；不静默退回 Python。

## 6. 冻结的接口

### 6.1 语言与数据

新增 languages.py，不建可配置插件注册系统：

~~~python
SUPPORTED_LANGUAGES = ("python", "javascript", "typescript")

def normalize_languages(value: str) -> tuple[str, ...]: ...
def language_for_path(path: str) -> str | None: ...
def analysis_metadata(index: RepoIndex) -> dict: ...
~~~

normalize_languages 按固定顺序返回去重语言；拒绝空项、空值、未知名称。language_for_path 对 .py/.js/.mjs/.ts 实现文件分别返回语言；声明/其他扩展返回 None。路径展示分类独立于解析选择。

共享记录新增字段都必须有默认值。FileRecord、Symbol、Python ImportRef、CallEdge 的既有字段与 ID 不改。RepoIndex 新增：

~~~python
analysis_languages: tuple[str, ...] = ("python",)
file_languages: dict[str, str] = field(default_factory=dict)
analysis_limits: list[AnalysisLimit] = field(default_factory=list)
esm_imports: list[ESMImportRef] = field(default_factory=list)
esm_exports: list[ESMExportRef] = field(default_factory=list)
identifier_uses: list[IdentifierUse] = field(default_factory=list)
unsafe_js_bindings: dict[str, set[str]] = field(default_factory=dict)
class_header_spans: dict[str, tuple[int, int]] = field(default_factory=dict)
~~~

记录字段：

- AnalysisLimit(file: str, line: int | None, reason: str, message: str)。
- ESMImportRef(file: str, specifier: str, imported: str | None, alias: str | None, start_line: int, end_line: int, type_only: bool = False, resolved_file: str | None = None, resolution_kind: str | None = None)。imported="*" 表示 namespace，None 表示 side-effect；默认导入用 "default"。
- ESMExportRef(file: str, exported: str, local_name: str | None, specifier: str | None, imported: str | None, start_line: int, end_line: int, type_only: bool = False)。
- IdentifierUse(file: str, name: str, line: int)；用于选择上下文导入，不证明调用目标。
- JSParsedFile(parsed: ParsedFile, esm_imports: list[ESMImportRef], esm_exports: list[ESMExportRef], identifier_uses: list[IdentifierUse], unsafe_bindings: set[str], class_header_spans: dict[str, tuple[int, int]], limits: list[AnalysisLimit])。

符号 ID 仍为相对路径::qualname，例如 src/core.ts::inc、src/core.js::Box.get。使用路径区分语言，不给 Python ID 加前缀。块级同名冲突和多个具体实现标 ambiguous，不靠行号生成看似唯一的假目标。

### 6.2 解析与合并

~~~python
def parse_js_ts_file(root: Path, relative_path: str,
                     *, root_identity: tuple[int, int] | None = None) -> JSParsedFile: ...

def resolve_esm_graph(index: RepoIndex, *, resolve_calls: bool = True) -> None: ...

def build_index(root: Path, *,
                languages: tuple[str, ...] = ("python",)) -> RepoIndex: ...
~~~

原 Python resolve_graph 和 resolve_semantic_edges 只接受 Python 子索引。JS/TS 使用独立 ESM 数据和 resolver；随后合并去重边与歧义，不让 Python 点号模块算法处理 JS 路径。纯 Python走原流程，不要求 js extra。

read_source 增加 keyword-only language: str = "python"。安全打开过程复用；python 仍识别 encoding cookie，javascript/typescript 用 UTF-8-sig。所有新增语言的 context 和 source_fingerprint 根据 file_languages 传语言。拒绝解码错误，不用替换字符制造引文。

### 6.3 命令与分析范围

五个只读命令增加 --languages CSV，默认 python；CSV 仅接受 python,javascript,typescript。没有 auto 或持久全局配置。

新字段 analysis 使用独立 schema_version = 1，附加在五个输出中，不修改旧字段含义：

~~~json
{
  "schema_version": 1,
  "requested_languages": ["javascript", "typescript"],
  "files_by_language": {"python": 0, "javascript": 2, "typescript": 3},
  "capabilities": {
    "javascript": ["symbols", "esm-file-imports", "context"],
    "typescript": ["symbols", "esm-file-imports", "context"]
  },
  "limits": [],
  "limits_omitted": 0,
  "scope": "static selected source languages; no runtime completeness"
}
~~~

capabilities 的 calls 只有 B2 完成验证后才添加。limits 按文件/行/原因排序，最多 50 条并保留省略数。分析错误为明确记录；输入/依赖错误退出 2；有解析错误的概览可退出 0，但必须显示错误与分析范围。空 affected_symbols 不表述为完整无影响。

python_files / python_lines 只统计 .py；纯 Python 的 source_fingerprint 不变。JS/TS 源码变更必须改变选择了该语言的指纹；未选择的 JS 变更不改变纯 Python 指纹。

context 保留 target-first、--include-symbol、行预算、truncated、budget_exhausted、omitted_imports 与 import_binding。新语言类头与导入跨度取自 parser 元数据，不交给 ast.parse。

### 6.4 图

保留 schema_version = 1、200 节点/500 边和当前布局。文件节点新增 language、analyzed，既有 python 字段仍严格表示 Python。Python 与 JS/TS 来源仍是同一个 RepoIndex。

Python/SVG 与 HTML 关系投影改用 analyzed；读取旧地图时用 node.analyzed ?? node.python 回退。语言与“未解析关系”的说明帮助人理解范围；不添加源码正文、诊断、补丁或详细调查报告面板。

## 7. 探索样本与继续门槛

已读取官方 package.json 的候选：

- JavaScript CLI：[sindresorhus/np，591e003bfc57371cfb8236694e8d784ae5d6fe5f](https://github.com/sindresorhus/np/blob/591e003bfc57371cfb8236694e8d784ae5d6fe5f/package.json)，ESM，bin 指向 source/cli.js。
- TypeScript 库：[sindresorhus/ts-extras，323908522c9f90f07f99378b43891da742f2319f](https://github.com/sindresorhus/ts-extras/blob/323908522c9f90f07f99378b43891da742f2319f/package.json)，ESM，包 exports 指向 distribution。A1 要区分源码入口与构建产物，不能把不存在的 distribution 当源码。

A1 已固定这两个提交并建立独立源码参考；A3 完成六题调查、补读和图产物。上下文/影响使用实际 symbols 返回的 ID。A4 的动作收益门槛未通过（18 → 30 次），因此本轮不进入产品接入。原问题、源码与原始输出保留。候选后续变更仍须由主代理解释并更新记录，不能由机械执行者替换。

A4 的 go 必须同时满足：

1. 两仓库六题均有工具输出、独立源码参考与补读记录，至少 4 题完成支持范围内的回答；每仓库至少 2 题。
2. 首期支持范围内所选符号位置、引用和正边全部核对正确；负例无造边；不存在会误导调查的已知错误。
3. 每仓库至少 1 题，原型比仅源码搜索基线少一次补读或定位动作；按实际动作记录，不能把未解析数量或模型评分当收益。
4. 两仓库实际新命令在记录的机器上均能 30 秒内返回；超时记真实结果，由主代理定位，不能声称 universal performance。
5. 三个候选包在隔离 Mac 环境可安装，原型不需要 Node 运行时、不执行目标代码，稳定安装与用户文件未变。

缺任一项：A4 写 no-go 和原因，B1–B4保持未开始。本阶段以报告闭环；不自动转向其他语言、框架或复杂后端。

若 A2 安装/API 或 A3 原型遭遇不能在范围内解决的阻断，六题保留源码基线并标明 trial 未执行/blocked，直接以真实失败证据进入 A4 no-go。没有发生的命令、耗时或输出不能填成成功；结束探索不等于完成 A3。

## 8. 交付

若 A4 go，完成 B1–B4 后首个候选版本为 0.6.0a1，标明 JS/TS 只读预览。它不是 Python 稳定版的自动升级。

发行必须固定来源提交、CI 与 wheel 哈希；普通安装的 Requires-Dist 仅含 extra 条件依赖。独立 Mac 预览环境放在 ~/.local/share/ai-repo-doctor/previews/v0.6.0a1/venv，使用绝对 CLI 路径；不替换 ~/.local/bin/repo-doctor 或现有 Skill。官方稳定 deployment.json 不改，新预览写自己的 receipt.json。

没有 A4 go、六题复核、Python 兼容门槛与干净安装证据，不发布。任务停止条件来自具体证据，不以测试数量增长代表产品完成。

## 9. 官方资料

- [Python Tree-sitter 官方使用说明](https://github.com/tree-sitter/py-tree-sitter)：Language / Parser API。
- [tree-sitter 0.26.0](https://pypi.org/project/tree-sitter/0.26.0/)、[JavaScript 0.25.0](https://pypi.org/project/tree-sitter-javascript/0.25.0/)、[TypeScript 0.23.2](https://pypi.org/project/tree-sitter-typescript/0.23.2/)：包版本与 Python / wheel 元数据。
- [TypeScript 官方模块引用说明](https://www.typescriptlang.org/docs/handbook/modules/reference.html#file-extension-substitution)：扩展替换候选；唯一来源规则是本产品为保守性增加的限制，不冒充完整编译器解析。
- [TypeScript Compiler API](https://github.com/microsoft/TypeScript/wiki/Using-the-Compiler-API)：A2 比较的替代方案。
