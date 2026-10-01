# AI Repo Doctor v0.5.1：模块实例调用关系 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` task-by-task. 主代理负责设计、实现决策、排错、审查、整合与发布；Luna/Harness 仅可执行本文给出的有界机械任务包，不能接管整个阶段。

**Goal:** 补出来源明确的同模块实例方法调用，使 Codex 的改动影响回答和人的关系图包含真实公共入口。

**Architecture:** 保留现有局部实例、导入、遮蔽与歧义保护；新增一个保守的模块实例候选表。只有候选来源、调用作用域和目标方法同时满足本计划条件时，才将现有 `module_bindings` 拒绝分支替换为白名单解析；context、impact 和 map 继续消费既有 CallEdge。

**Tech Stack:** Python 3.11+、标准库 ast/dataclasses/unittest、既有 CLI 和离线地图；无新增依赖。

**Spec:** 本文第二、三节为本阶段设计与行为合同；依据已接受的“提高调用关系与改动影响分析实用性”方向。

日期：2026-10-02。状态：**实施中：T0–T3 已完成，T4–T8 待完成。**

## 一、基线与实际问题

- 公开稳定版本和 Mac 安装为 v0.5.0。正式发行源码：`206e418bfa4b26e3aa1ad7663056b2c04da8640d`。
- 已收尾文档基线：`ad97e6427c67dc09d36877de13751d24ea96bcec`。旧 R1–R5 已闭合，不重新打开这些复选框。
- 主目录：`/Users/kisara/Documents/ChatGPT/AI Repo Doctor`。
- 可复用工作树：`/Users/kisara/.codex/worktrees/diagnosis-evaluation/AI Repo Doctor`。
- 固定样本：`/Users/kisara/.local/share/ai-repo-doctor/evaluations/2026-09-30-schedule/repo`，修订 `82a43db1b938d8fdf60103bd41f329e06c8d3651`。
- schedule 的 `default_scheduler = Scheduler()` 位于 `schedule/__init__.py:837`；模块级 `run_pending` 在第 854 行调用 `default_scheduler.run_pending()`。
- v0.5.0 的已记录 impact 没有返回这条公共入口边。既有 `Scheduler.run_pending → Scheduler._run_job` 边在第 101 行，应当保留。
- 根因：`parser.py` 已采集函数内 `local_constructors`；`graph.py::_resolve_call` 对 `receiver in index.module_bindings` 直接返回 None，没有模块实例候选表。
- 当前样本存在未跟踪的 `.graphflow-cache/`、`graphflow-out/`；T0 保存实际状态，不把“无源码修改”写成“Git 完全干净”，也不删除这些目录。

设计依据：[Python 名称绑定与作用域](https://docs.python.org/3/reference/executionmodel.html#naming-and-binding)、[AST 访问器](https://docs.python.org/3/library/ast.html#ast.NodeVisitor)。局部绑定可以遮蔽模块变量，自由变量的实际解析发生在运行时。因此本版新增的是受约束的静态关系，不能称为运行时证明。

### Global Constraints

1. Python 下限保持 `>=3.11`；运行依赖保持 `[]`。
2. 保持 CLI 参数、公开 JSON schema_version、CallEdge 和已有报告格式兼容。
3. 不运行、导入或修改 schedule 源码，不调用 DeepSeek。
4. 不按方法同名猜类型，不承诺动态调用完整覆盖。
5. 不增加 MCP、缓存、新模型评估、UI 功能或通用类型推导系统。
6. 保留 Mac Key 设置、既有 Skill、旧发行包及四份用户原文。
7. 每次代码探索先调用 GraphFlow context；项目修改后增量索引。GraphFlow 计划需完成 submit/merge；不能把建议节点当成已审定方案。
8. 本阶段新任务从 T0 开始；已完成的 0.5.0 验收不重复执行。

## 二、方案选择与范围

| 方案 | 取舍 | 决定 |
| --- | --- | --- |
| 按方法名称或变量名称猜目标 | 实现短，但会制造错误影响路径 | 不采用 |
| 增加跨模块、分支、别名、继承的对象数据流系统 | 范围大，难以在本轮独立验证 | 留作后续有证据的任务 |
| 同模块唯一构造来源的保守白名单 | 能解决已知入口缺口，保留未知和既有保护 | 本轮采用 |

### 支持的完整模式

```python
class Client:
    def send(self):
        return 1
client = Client()
def run():
    return client.send()
```

允许 `client: Client = Client()`；类型注解不作为推断依据。允许调用函数有一个同名 `Client` 参数：实例在模块作用域中已构造，不能错误地使用调用函数的局部作用域解释构造表达式。

必须同时满足：

- 类是同文件、模块顶层直接定义的唯一 ClassDef；不经导入或重导出。
- 类无装饰器、显式基类、metaclass 等 class keywords。
- 赋值是 tree.body 中直接的单目标 Name Assign，或有值的 Name AnnAssign；右侧为直接 Name 构造调用。
- 类定义结束在赋值前；实例赋值结束在调用函数定义开始前。定义在实例构造之前的包装函数，本轮保守地不新增边。
- 模块名字绑定计数证明实例名只绑定一次，类名只由该 ClassDef 绑定一次。
- 调用者是模块顶层 function，parent 为 None；调用形式是简单 `instance.method(...)`。
- receiver 不在调用者 local_bindings 中；函数参数和局部变量的现有解析优先级保持原样。
- 方法是该类直接定义、唯一、无装饰器、首个位置参数名为 self 的 def/async def。
- 没有下节定义的可见重新绑定、方法改写或实例逃逸。
- 目标 Symbol 存在，kind 为 method，parent 为该类；歧义 Symbol 不产生新边。

### 保守拒绝规则

| 情况 | 处理 |
| --- | --- |
| 条件/循环/try/with 中构造，多目标或解包赋值 | 不建立候选 |
| 重复赋值，即使重复同一种构造；del；导入名冲突 | 不建立候选 |
| 文件中对实例名或类名出现 global 声明 | 拒绝对应候选，包含只读 global 的保守情况 |
| 文件中 NamedExpr 写实例名或类名；类内 NamedExpr 写方法名 | 拒绝对应候选或移除方法，覆盖定义默认值中的绑定 |
| 文件中出现星号导入 | 本文件不启用新增模块实例解析，无法证明名称未被替换 |
| 文件中出现直接 exec/eval/globals/locals 调用 | 本文件不启用新增模块实例解析 |
| `alias = instance`、`configure(instance)` 或返回实例本身 | 视为实例逃逸，拒绝候选 |
| 对实例/类的直接属性或下标写入、删除；直接 setattr/delattr | 拒绝对应候选；不做别名追踪 |
| 类内 self.method 写入/删除或同名类属性赋值 | 从可解析方法中移除该方法 |
| 类内直接 setattr/delattr(self, ...)，或 self.__dict__/self.__class__ 访问 | 不为该类建立可解析方法集 |
| 自定义 __new__/__getattr__/__getattribute__/__setattr__/__delattr__ | 不启用该类候选 |
| 工厂、导入实例、实例链、继承、属性/静态/类方法、嵌套函数 | 本轮不增加边，保留既有行为 |

“实例逃逸”的检查方式：建立 AST 父节点表；实例名的 Load 只允许作为普通 Attribute.value。访问其 __dict__/__class__ 也拒绝。`jobs = default_scheduler.jobs` 是允许的属性读取；`alias = default_scheduler` 则拒绝。

这些规则不声称能识别外部猴子补丁、通过类或方法别名进行的间接改写，或间接反射。当前静态模型假定没有超出上述检查范围的运行时替换；结果必须保留此边界。

## 三、文件与接口合同

| 文件 | 责任 / 允许改动 |
| --- | --- |
| `repo_doctor/model.py` | 新增内部 ModuleInstanceBinding，以及两个带默认值的候选表字段 |
| `repo_doctor/parser.py` | 复用 _ModuleBindings，采集并过滤模块实例候选；不改 local_constructors 算法 |
| `repo_doctor/index.py` | 将 ParsedFile 候选表按文件传入 RepoIndex |
| `repo_doctor/graph.py` | 新增候选解析 helper，接入现有 module_bindings 拒绝分支 |
| `tests/test_module_instances.py` | 附录 A 的新增正反例，验证调用边的真实行为 |
| `tests/test_module_instance_outputs.py` | 验证相同新边到 context、impact、map 的传递 |
| `pyproject.toml` | T6 通过后将版本改为 0.5.1 |
| `README.md`、`docs/CODEX_AND_MAP.md`、`docs/PRODUCT_GUIDE.md` | 发布后更新稳定版本和新增覆盖范围 |
| `docs/delivery/2026-10-02-v0.5.1-call-coverage.md`、本文 | 保存实际证据、完成状态与使用入口 |

`context.py`、`repo_map.py`、`semantics.py`、地图 JS/CSS/HTML 和 Skill 默认不修改。若 T4 发现真实传递缺陷，主代理先定位、记录最小修复范围并更新计划，再修改对应文件；不能顺手扩大范围。

新增内部记录：

```python
@dataclass(frozen=True, slots=True)
class ModuleInstanceBinding:
    class_name: str
    line: int                 # 赋值语句结束位置
    column: int
    methods: tuple[str, ...]

# ParsedFile 的现有字段末尾追加：
module_instances: dict[str, ModuleInstanceBinding] = field(default_factory=dict)

# RepoIndex 的现有字段末尾追加：
module_instances: dict[str, dict[str, ModuleInstanceBinding]] = field(default_factory=dict)
```

追加在字段末尾，兼容现有位置参数构造。不要将它们自动加入公开 JSON。

内部 helper 签名：

```python
# parser.py
def _attribute_root(node: ast.AST) -> str | None:
    """剥离 Attribute/Subscript，返回简单根 Name；否则 None。"""

def _eligible_instance_methods(node: ast.ClassDef) -> tuple[str, ...]:
    """按第二节规则输出可解析的直接实例方法名，排序且去重。"""

def _module_instance_bindings(tree: ast.Module) -> dict[str, ModuleInstanceBinding]:
    """返回唯一、非条件、未见失效或逃逸的模块实例候选。"""

# graph.py
def _resolve_module_instance_call(
    call: CallSite, caller: Symbol, index: RepoIndex
) -> str | None:
    """解析白名单候选；不访问调用者局部作用域来解释构造来源。"""
```

## 四、执行顺序：T0 → T8

### T0：保存基线与确认工作区

**责任：主代理。产物：外部 baseline.json、before-context.json、before-impact.json。**

- [x] 确认已加载 AGENTS、相关技能与 GraphFlow；核对主目录、工作树、默认分支和实际 HEAD。
- [x] 优先复用上述干净工作树。在执行时创建 `codex/v0-5-1-module-instance-calls` 分支；若同名分支已存在，先判断是否就是本任务，不能覆盖。
- [x] 保存四份用户文档哈希，参照 `~/.local/share/ai-repo-doctor/workspace-preservation/2026-10-01-product-closure/manifest.json`。
- [x] 将运行证据保存到新建的 `~/.local/share/ai-repo-doctor/evaluations/v0.5.1-module-instance-calls/`。目录已有内容时复用已确认的同任务记录，不覆盖历史。
- [x] 用当前安装入口只收集一次固定目标的 context 和 impact；记录 argv、退出码、源码修订、Git 状态和输出。已有可核对的同版原始输出可直接引用。
- [x] 确认第 854 行的包装调用尚未解析；若已出现，停止本修复路径，核对是否已有他人实现，不能重复添加。
- [x] 样本 Git 状态按实际保存；本计划不清理其 GraphFlow 未跟踪目录。

命令：

```sh
/Users/kisara/.local/bin/repo-doctor context /Users/kisara/.local/share/ai-repo-doctor/evaluations/2026-09-30-schedule/repo 'schedule/__init__.py::Scheduler.run_pending' --max-lines 120 --json
/Users/kisara/.local/bin/repo-doctor impact /Users/kisara/.local/share/ai-repo-doctor/evaluations/2026-09-30-schedule/repo 'schedule/__init__.py::Scheduler.run_pending' --depth 2 --json
```

**退出条件：** 基线可追溯，缺口仍存在，用户原文已核对。只读操作不等于目标仓库 Git 必须为空。

### T1：固定支持与拒绝行为，取得 RED

**文件：新建 `tests/test_module_instances.py`。责任：主代理；复制材料可按第六节有条件委派。**

- [x] 原样采用附录 A；所有输入只通过 build_index 静态解析，不导入或执行样例。
- [x] 运行下列单文件命令。预期四个支持子例缺少调用边，拒绝子例保持无边；保存真实输出。
- [x] 若拒绝子例已出现错误边，由主代理定位是否属于现有行为或本计划必要范围，不能修改断言让它通过。
- [x] 保存新边合同：`app.py::run → app.py::Client.send`，实际调用行 6。
- [x] 本阶段只提交测试材料和计划状态，不改解析器。

```sh
python3 -B -m unittest discover -s tests -p 'test_module_instances.py' -v
```

**退出条件：** RED 来自缺少预期新边，非语法、导入、路径或环境错误。不要把预期 RED 计为产品回归失败。

### T2：采集内部候选与失效信息

**文件：model.py、parser.py、index.py。责任：主代理。**

- [x] 添加第三节的 ModuleInstanceBinding 和带默认值字段，保留所有现有 dataclass 字段顺序。
- [x] 实现 _attribute_root；只剥离 ast.Attribute/ast.Subscript 的 value，末端不是 Name 则返回 None。
- [x] 实现 _eligible_instance_methods：采集直接 def/async def；核对唯一性、装饰器、self 参数和第二节方法失效条件。类体复杂情况采取保守拒绝，不引入类型注解推断。
- [x] 实现 _module_instance_bindings：先复用 _ModuleBindings 统计整文件模块绑定，再遍历 tree.body 的直接 Assign/AnnAssign。
- [x] ClassDef 必须是 tree.body 中的直接定义；其绑定条目必须只对应这个 ClassDef。实例绑定条目必须只对应当前 Name target。不借助一个临时 Symbol 模拟模块作用域。
- [x] 先计算文件级反射/global/属性改写/逃逸，再生成候选；不能生成后忽略后续重新赋值。
- [x] 使用 _end_position 保存构造结束位置；确认类定义在赋值之前。
- [x] 在 parse_python_file 返回 ParsedFile 时按关键字加入 module_instances；解析错误仍返回空默认表。
- [x] build_index 增加下面的传递语句，保留原 module_bindings：

```python
index.module_instances[path] = parsed.module_instances
```

- [x] 独立检查附录 A 四个支持例会建立候选。构造来源、改写或逃逸类负例不得建立候选，或候选方法集中不得包含 send；parameter_shadow、nested_scope、function_defined_before_binding 可以保留候选，由 T3 的调用作用域与位置保护拒绝。图解析尚未接入时，正例的 RED 仍应保留。

**退出条件：** 候选生成符合合同；没有改变局部实例和导入的解释规则。构造证据与调用者局部变量分离。

### T3：接入图解析并取得 GREEN

**文件：graph.py。责任：主代理。**

helper 的关键逻辑：

```python
def _resolve_module_instance_call(call, caller, index):
    if caller.kind != "function" or caller.parent is not None:
        return None
    binding = index.module_instances.get(caller.file, {}).get(call.receiver)
    if binding is None or call.name not in binding.methods:
        return None
    if (binding.line, binding.column) >= (caller.start_line, 0):
        return None
    class_id = f"{caller.file}::{binding.class_name}"
    cls = index.symbols.get(class_id)
    if cls is None or cls.kind != "class" or cls.parent is not None:
        return None
    target = f"{class_id}.{call.name}"
    method = index.symbols.get(target)
    if method is None or method.kind != "method" or method.parent != class_id:
        return None
    return target
```

- [x] 将上面逻辑加上第三节类型签名。
- [x] 保留现有 simple receiver/expression 检查与 local_bindings 分支的优先级。
- [x] 只替换现有 `receiver in index.module_bindings` 分支的返回值：

```python
if receiver in index.module_bindings.get(caller.file, set()):
    return _resolve_module_instance_call(call, caller, index)
```

- [x] 不删除 module_bindings，不放宽 import alias/同名类/局部遮蔽保护，不改 _reexport_binding_for_call。
- [x] 新增边仍由 resolve_graph 创建原 CallEdge：caller、callee、调用行；不新增关系类型。
- [x] 运行 T1 单文件命令，取得真实 GREEN。
- [x] 运行既有图解析与 Click 语义相关检查，保护局部实例、导入遮蔽、重导出和注册关系：

```sh
python3 -B -m unittest discover -s tests -p 'test_graph.py' -v
python3 -B -m unittest discover -s tests -p 'test_semantics.py' -v
```

**退出条件：** 新边正确，负例无新误边，原解析路径通过相关检查。提交 T2/T3 实现及必要测试，保存 RED/GREEN 证据。

### T4：确认 context、impact、HTML/SVG 使用同一条边

**文件：新建 `tests/test_module_instance_outputs.py`；默认不改生产下游模块。责任：主代理。**

受控仓库使用附录 A 的 plain 源码，再追加：

```python
def dynamic(obj):
    return obj.send()
```

- [ ] 使用 build_context(index, "app.py::Client.send")，断言 call_evidence 有 run→Client.send，file=app.py、line=6。
- [ ] 使用 build_impact(index, "app.py::Client.send", depth=2)，断言 run 距离 1，call_path_evidence 指向 app.py:6。
- [ ] 通过既有 cli.main 的 map 入口生成到临时新目录，参数为 `--symbol app.py::Client.send --depth 1 --json`。
- [ ] 读取 map.json，断言 call edge 的 source 为 `symbol:app.py::run`、target 为 `symbol:app.py::Client.send`、evidence 为 `[{"file": "app.py", "line": 6}]`；局部视图含两端节点。
- [ ] 断言动态 obj.send 没有指向 Client.send 的边；coverage.unresolved_calls 保留 1。
- [ ] 生成的 map.html、structure.svg、relations.svg、map.json 均存在；用 ElementTree 解析 SVG。沿用现有渲染格式，不改 UI。
- [ ] 若下游漏边，先确认它们实际消费的 index.call_edges；主代理只修复已证明的传递问题，保持 schema 和 budgets。
- [ ] 运行新输出测试及相关既有检查：

```sh
python3 -B -m unittest discover -s tests -p 'test_module_instance_outputs.py' -v
python3 -B -m unittest discover -s tests -p 'test_context.py' -v
python3 -B -m unittest discover -s tests -p 'test_repo_map.py' -v
```

**退出条件：** 同一源码边在三种输出中一致，未知对象调用仍未知。UI 没有改动时，不重复要求用户确认已通过的原生目录操作。

### T5：回到固定 schedule，证明实际收益

**允许范围：样本只读；新证据和地图目录。责任：主代理。**

- [ ] 核对固定修订与 T0 保存的状态；从工作树源码入口执行一次 after context 和 impact，不误用仍为 0.5.0 的已安装 CLI。
- [ ] 必须出现 `schedule/__init__.py::run_pending → schedule/__init__.py::Scheduler.run_pending`，调用证据第 854 行。
- [ ] 保留第 101 行 run_pending→_run_job 的旧边和已有直接测试调用者。
- [ ] impact 的公共包装入口距离为 1；第二层只按实际解析结果说明，不规定新增调用者总数。
- [ ] 对比所有新增 call_edges，逐条审查来源，不能只看总数提高。其他 Scheduler 公共包装方法如符合相同合同，可形成新边。
- [ ] 不把 Job.should_run、__lt__、job.run() 参数对象或 self.job_func() 当作本次新增规则已解析的完整执行链。
- [ ] 生成针对 Scheduler.run_pending 的新局部地图到本轮输出目录，不覆盖 0.5.0 地图。
- [ ] 保存中文前后对照：以前需手工补充的公共入口，现在可由 impact/context/map 直接提供；注明调用、预算和静态边界。
- [ ] 核对样本 Git 状态与 T0 一致、已跟踪文件未变。记录缓存目录原状，不清理。

源码入口命令（cwd 为功能工作树）：

```sh
python3 -B -m repo_doctor context /Users/kisara/.local/share/ai-repo-doctor/evaluations/2026-09-30-schedule/repo 'schedule/__init__.py::Scheduler.run_pending' --max-lines 120 --json
python3 -B -m repo_doctor impact /Users/kisara/.local/share/ai-repo-doctor/evaluations/2026-09-30-schedule/repo 'schedule/__init__.py::Scheduler.run_pending' --depth 2 --json
```

**退出条件：** 实际遗漏的公共入口已补出，证据可查、动态边界保留。计数变化只作记录，不作为准确率或 token 节省证明。

### T6：代码冻结、版本与审查

**文件：pyproject.toml、本文及新交付记录。责任：主代理。**

- [ ] 确认 T1–T5 通过；将版本改为 0.5.1，依赖与 Python 下限不变。
- [ ] 冻结功能代码后，按现有发布门槛运行一次全套离线回归：

```sh
python3 -B -m unittest discover -s tests -q
git diff --check
```

- [ ] 审查实际 diff：必须没有下游 UI、Key、依赖和无关解析器重构。确认旧公开 schema/命令参数兼容。
- [ ] 新交付记录写实际命令、退出码、源码提交、新增边审查和边界；不能提前宣称正式发行。
- [ ] 提交并推送功能分支，创建到实际默认分支 `codex/repo-doctor-v1` 的 PR；创建后附加到当前任务。
- [ ] 核对当前 PR head 的 Python 3.11–3.13 与地图 CI，全通过才整合。
- [ ] 不因为说明文字再重复本地全套测试。发现具体失败时运行对应检查。

**退出条件：** 提交可审查，代码冻结结果和当前 head CI 均通过。主代理完成审查，不委派 Luna 作接受判断。

### T7：正式构建、发布与 Mac 部署

**责任：主代理。不得委派 Luna/Harness。**

- [ ] 按已授权项目流程合并 PR，记录真实合并 SHA。
- [ ] 从该正式合并提交导出干净源码，构建 `ai_repo_doctor-0.5.1-py3-none-any.whl`；不要直接发布工作区残留包。
- [ ] 核对 METADATA 版本、Python 下限、无 Requires-Dist、入口，以及全部包内运行文件与正式源码的字节一致性；记录 SHA256。
- [ ] 干净 venv 安装同一 wheel，复查 T5 的目标调用边与 impact；只验证新覆盖和包资源，不重新做模型盲测。
- [ ] 重开 0.5.0 的既有 schedule case，确认可读且不会因查看而改写记录。保留已有 Skill。
- [ ] 核对合并 SHA 的既有 CI；发布指向该提交的稳定 v0.5.1 标签、wheel 和 SHA256SUMS。
- [ ] 下载公开发行包并比较 SHA256，使用同一包更新 Mac 持久 venv；普通登录终端入口仍为 `/Users/kisara/.local/bin/repo-doctor`。
- [ ] 记录正式源码、下载、安装路径和包哈希；0.5.0 正式 wheel、部署收据及本轮候选保留。
- [ ] Mac 部署失败时先恢复原 0.5.0 wheel，使终端可用；由主代理排错，不动 Key 或全局配置。

**退出条件：** 正式来源、公开下载、干净安装、Mac 安装具有同一包哈希，并显示预期新边。不能仅靠版本号宣布部署成功。

### T8：同步源码与中文交付，结束本轮

**责任：主代理。**

- [ ] 主目录仅快进同步正式源码和交付文档；四份用户原文逐一核对哈希，冲突时保留原文并定位，不强制覆盖。
- [ ] 更新 README、Codex 用法和产品指导书的当前版本，说明新增支持与拒绝范围；旧 0.5.0 R1–R5 完成记录保留为历史。
- [ ] 更新本轮交付记录和部署收据。文档在发行后补充时分别记录标签源码与文档 HEAD，标签不移动。
- [ ] 刷新主目录 GraphFlow，并核对真实 root 与索引状态；不能把一次调用成功等同缓存已新鲜。
- [ ] 勾选本文完成项，最终提供：稳定发行链接、Mac 可用入口、中文前后对照、新 HTML/关系 SVG、已知静态边界。
- [ ] 以“同一真实问题现在能直接找到公共调用入口”作为完成结论。完成后停止扩展本轮。

## 五、验证纪律与阻塞处理

- T1 的正反例用于防止补边时破坏遮蔽/失效保护；T4 验证产品输出传递；T5 验证实际收益；T6/T7 采用既有发布门槛。
- 只为具体失败重跑对应检查；没有新 UI 改动时不扩大浏览器测试，没有性能证据时不增加缓存实验。
- 若规则保守导致 sample 第 854 行仍不能解析，主代理先定位是哪条保护阻断，回到设计处理；不能删掉整个保护分支来制造通过。
- 若需要跨文件实例、继承或通用别名系统才能满足要求，本轮停止范围扩张，保存现有稳定版和调查结果。
- 任何执行者遇到不在允许清单的文件需求，都先返回主代理。主代理可设计必要最小修复并更新计划，不让执行器自行扩大范围。
- 全部步骤通过后不增加另一个“验证清单”阶段；T8 就是本轮闭合。

## 六、执行器政策与可选机械任务包

默认主代理执行 T0–T8。只有附录 A 的固定复制可能符合 Luna 条件；复制成本低于协调成本时直接由主代理完成。本轮写计划不创建子代理。

考虑委派时先获取新鲜 weekly get_usage_limits。usedPercent > 90 且任务符合 Harness 条件时使用 `delegating-to-dsh-executor` 与指定 wrapper；其余 Luna 合格情形使用 `luna_executor`（Luna Max），一次最多一个。缺失周额度不推断，按 AGENTS 处理。

### Objective

把主代理准备的附录 A 逐字写入新测试文件，只做固定材料复制。

### Allowed changes

只允许功能工作树内 `tests/test_module_instances.py`。输入材料由主代理事先保存为 `/private/tmp/repo-doctor-v051-plan/test_module_instances.py.expected`，执行器只读此文件。

### Forbidden changes

禁止生产代码、其他测试、Git、依赖、网络、Key、权限、发布或创建子代理。不得撤销其他人的改动；目标已存在，或输入与主代理任务包不符时，先返回主代理。

### Exact steps

1. 确认输入存在，目标不存在。
2. 将输入原样复制到允许的目标。
3. 运行下面的独立校验；不运行 RED/GREEN，不替主代理判断测试。
4. 返回校验输出与目标文件路径；主代理检查实际 Git diff 并重新校验。

### Validation

cwd 为功能工作树：

```sh
python3 -B -c 'import ast; from pathlib import Path; p=Path("tests/test_module_instances.py"); expected=Path("/private/tmp/repo-doctor-v051-plan/test_module_instances.py.expected"); assert p.read_bytes()==expected.read_bytes(); ast.parse(p.read_text()); print("exact copy and syntax OK")'
```

### Expected result

只有指定新测试文件；字节完全相同；校验退出 0，输出 `exact copy and syntax OK`。主代理独立运行 T1 的 RED 后才接受材料。

### Stop conditions

目标已存在、输入缺失、需要其他文件、发现歧义/兼容性或安全问题、一次机械纠正后仍未通过校验时，立即返回主代理。不能修改断言、重试扩大权限或进行修复设计。

## 附录 A：T1 的完整固定行为测试

保存为 `tests/test_module_instances.py`。支持四例，拒绝例逐一使用 subTest；临时源码不会被执行。

```python
import tempfile
import unittest
from pathlib import Path

from repo_doctor.index import build_index


CLASS = "class Client:\n    def send(self):\n        return 1\n"
CALL = "def run():\n    return client.send()\n"
BIND = "client = Client()\n"

POSITIVES = {
    "plain": CLASS + BIND + CALL,
    "annotated": CLASS + "client: Client = Client()\n" + CALL,
    "constructor_name_is_caller_parameter": (
        CLASS + BIND + "def run(Client):\n    return client.send()\n"
    ),
    "unrelated_local_receiver": (
        CLASS + BIND + CALL
        + "def other(client):\n    return client.send()\n"
    ),
}

NEGATIVES = {
    "conditional": CLASS + "if flag:\n    client = Client()\n" + CALL,
    "repeated": CLASS + BIND + BIND + CALL,
    "reassigned": CLASS + BIND + "client = None\n" + CALL,
    "deleted": CLASS + BIND + "del client\n" + CALL,
    "factory": CLASS + "client = factory()\n" + CALL,
    "imported_instance": CLASS + "from provider import client\n" + CALL,
    "wildcard_import": CLASS + BIND + "from provider import *\n" + CALL,
    "class_import_collision": "from provider import Client\n" + CLASS + BIND + CALL,
    "class_rebound": CLASS + "Client = object\n" + BIND + CALL,
    "parameter_shadow": CLASS + BIND + "def run(client):\n    return client.send()\n",
    "nested_scope": (
        CLASS + BIND
        + "def outer(client):\n    def run():\n        return client.send()\n"
    ),
    "function_defined_before_binding": CLASS + CALL + BIND,
    "global_write": (
        CLASS + BIND
        + "def reset():\n    global client\n    client = None\n" + CALL
    ),
    "instance_method_patch": CLASS + BIND + "client.send = lambda: 2\n" + CALL,
    "class_method_patch": CLASS + BIND + "Client.send = lambda self: 2\n" + CALL,
    "escaped_alias": CLASS + BIND + "alias = client\n" + CALL,
    "passed_to_callback": CLASS + BIND + "configure(client)\n" + CALL,
    "setattr": CLASS + BIND + "setattr(client, 'send', replacement)\n" + CALL,
    "reflective_globals": CLASS + BIND + "globals()['client'] = replacement\n" + CALL,
    "decorated_method": (
        "class Client:\n    @staticmethod\n    def send():\n        return 1\n"
        + BIND + CALL
    ),
    "inherited_class": CLASS.replace("class Client:", "class Client(Base):") + BIND + CALL,
    "metaclass": CLASS.replace("class Client:", "class Client(metaclass=Meta):") + BIND + CALL,
    "custom_new": (
        "class Client:\n    def __new__(cls):\n        return None\n"
        "    def send(self):\n        return 1\n" + BIND + CALL
    ),
    "self_method_patch": (
        "class Client:\n    def __init__(self):\n        self.send = lambda: 2\n"
        "    def send(self):\n        return 1\n" + BIND + CALL
    ),
    "ambiguous_class": CLASS + CLASS + BIND + CALL,
}


class ModuleInstanceTests(unittest.TestCase):
    def index_for(self, source):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / "app.py").write_text(source, encoding="utf-8")
        return build_index(root)

    def test_supported_module_instance_calls(self):
        for name, source in POSITIVES.items():
            with self.subTest(case=name):
                index = self.index_for(source)
                matches = [
                    edge for edge in index.call_edges
                    if edge.caller == "app.py::run"
                    and edge.callee == "app.py::Client.send"
                ]
                self.assertEqual(len(matches), 1)
                self.assertEqual(matches[0].line, 6)
                self.assertEqual(index.parse_errors, [])

    def test_uncertain_module_instance_calls_remain_unresolved(self):
        for name, source in NEGATIVES.items():
            with self.subTest(case=name):
                index = self.index_for(source)
                self.assertEqual(index.parse_errors, [])
                self.assertFalse(
                    any(edge.callee == "app.py::Client.send" for edge in index.call_edges)
                )


if __name__ == "__main__":
    unittest.main()
```

## 七、最终完成合同

T0–T8 全部完成时，必须同时满足：

1. schedule 公共入口边和 app.py 正例边有准确调用行，Codex 不需要再手工补出这条公共入口关系。
2. 拒绝例没有新增错误边，动态 Job 回调仍按未知说明。
3. context、impact、map 消费同一条 CallEdge，JSON 和渲染入口兼容。
4. 中文前后对照解释实际改善，不把覆盖数提高当成准确率证明。
5. 正式 v0.5.1 来源、公开 wheel、Mac 安装可追溯，旧记录与用户原文保留。
6. 用户得到稳定版本、复制提示和地图入口，本阶段结束。

实施过程中以真实输出更新复选框和交付记录。计划代码与步骤是未来操作说明，不能据此宣称功能已经实现。

编写复核：已检查 8 个 Python 文档代码块的语法、4 个支持样例和 24 个拒绝样例的源码语法，并核对支持样例调用均位于第 6 行。本次未执行文档中的测试、样本仓库代码、发布或部署步骤。

T3 审查补充：星号导入不能提供精确名称绑定证据。新增 wildcard_import 负例取得 RED 后，新增白名单对此文件保守禁用；现为 4 个支持例、25 个拒绝例。原有解析行为保持，未扩展到跨模块类型推导。证据保存在本轮外部目录。

T3 绑定复核补充：共享 _ModuleBindings 不进入定义默认值。新增 definition_default_rebinds_instance 与 method_default_rebinds_method 两个 RED 后，以 NamedExpr 写入禁用候选/方法，未修改共享 visitor 或局部构造算法。最终为 4 个支持例、27 个拒绝例；见 t3-definition-binding-red.txt、t3-final-green.txt。
