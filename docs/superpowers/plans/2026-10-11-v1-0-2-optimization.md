# 1.0.2 可靠性与后续体验优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 主代理负责技术决策、排错、审查、验收与发布；本计划不授权将这些职责交给Luna。Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复六项已确认缺陷，交付可下载安装、供Codex调用、生成可信静态关系图且可回滚的1.0.2；随后按收益推进独立体验优化。

**Architecture:** 复用现有AST/索引和CLI，增加作用域/重绑定保护及解析输入摘要校验。优先保留未知关系，消除错误“已解析”关系；不引入新依赖或重写整体分析器。

**Tech Stack:** Python3.11+、unittest、现有Tree-sitter/companion、离线HTML/SVG、GitHub CI/Release。

**Spec:** [可靠性设计](../specs/2026-10-11-v1-0-2-reliability-design.md)。执行前同时阅读设计和2026-10-11审查报告。

## Global Constraints

- 按设计中的版本、依赖、平台、资源限制、JSON兼容、MIT署名及证据保护要求执行。
- 用户已批准实施。按实际完成事实更新勾选；发布、安装和部署仅在相应门禁通过后标记。未创建新goal。
- 实施在干净正式工作树进行；主目录旧0.5.3及15份改动不动。不要使用reset/clean覆盖既有内容。
- 基线稳定提交348b956778bb5538c05181c2fcefae50fe23583a。远端已变化时先重新核对差异，不盲目沿用SHA。
- 不给1.0.1wheel改名，不移动v1.0.1tag，不覆盖旧安装/Skill/历史评估。
- 不为本轮重复跑200/500全量；不把“6个反例脚本成功”当作修复成功，该脚本当前断言缺陷存在。
- 不运行被调查公开仓库代码、不安装其依赖、不调用云诊断。允许执行本产品、自有测试和构建工具。
- 每项只有行为验收与对应回归通过才勾选；一个范围外问题须记录并由主代理重新判断，不能自行扩大修复。

## 范围和顺序

| 批次 | 任务 | 目的 | 是否阻塞1.0.2 |
| --- | --- | --- | --- |
| 可靠性 | R0 | 工作入口、保护清单、固定反例 | 是 |
| 可靠性 | R1 | 当前作用域事实，修复F05 | 是，F01/F02前置 |
| 可靠性 | R2 | 闭包不得误连全局，F01 | 是 |
| 可靠性 | R3 | 局部函数重绑定保护，F02 | 是 |
| 可靠性 | R4 | self身份/重绑定保护，F03 | 是 |
| 可靠性 | R5 | 解析输入与输出一致，F04 | 是 |
| 可靠性 | R6 | 跨语言提示，F06 | 是 |
| 可靠性 | R7 | 集成、固定真实仓库、安装/CI | 是 |
| 可靠性 | R8 | 正式发行、部署/回滚、报告 | 是 |
| 后续体验 | U1–U4 | 输出预算、扫描复用、帮助、安装便利 | 否 |

R0→R1→R2→R3→R4→R5→R6→R7→R8。R1先修绑定采集，因为调用解析依赖该事实。先发布可靠性修复，再单独评估体验批次，避免交付目标无限扩展。

## 文件职责

- repo_doctor/parser.py：Python当前作用域绑定事实与解析输入摘要。
- repo_doctor/model.py：追加兼容默认值的内部事实，不改公开JSON。
- repo_doctor/graph.py：普通调用、闭包遮蔽、局部定义和self守卫。
- repo_doctor/source.py：安全有界读取、摘要捕获、索引来源校验。
- repo_doctor/index.py：聚合Python/JS/TS来源摘要及选中路径集合。
- repo_doctor/js_ts.py：捕获实际解析输入；不修改原生grammar。
- repo_doctor/context.py、case.py、agent_tools.py、repo_map.py、cli.py：证据/指纹/写入边界及文案的调用接入。
- tests/test_python_binding_safety.py：R1–R4行为反例/正例。
- tests/test_source_consistency.py：R5变更时序和稳定源码正例。
- tests/test_review_lead_languages.py：R6文案正确性。
- evaluation/reliability-v1/cases.json：固定反例、禁止/必须存在的边及语言。
- tools/validate_reliability_install.py：安装后独立检查，CLI作为显式输入。
- evaluation/reliability-v1/README.md：每条案例来源、验证方式及非评分边界。
- docs/delivery/2026-10-11-v1.0.2-reliability.md：实施后实际结果；日期变化用实际日期新建，不回写历史。

## 通用执行方式

每个R1–R6任务：写行为测试→运行指定单测确认失败→最小修改→重跑该测试及关联正例→主代理看diff和新回执→独立提交。测试失败必须来自目标行为，不是fixture编码错误或缺失JS依赖。不能为使测试通过删掉正确关系、放宽资源限制或修改固定预期。

以下命令在正式工作树运行；`python`应是已核对有js extra的开发解释器。源码测试从工作树import本产品；安装验收必须离开源码cwd，明确核对site-packages与metadata。

### R0 — 建立执行入口与保护基线

**文件：** 新证据目录baseline.json；evaluation/reliability-v1/cases.json、README.md；本计划状态。

- [x] 使用list_artifacts/git worktree list检查可复用正式工作树，核对HEAD、tree、分支及待提交文件。
- [x] 先保存本计划与设计；在稳定基线创建`codex/v1-0-2-reliability`实施分支。不得直接在已合并的旧release分支堆实现提交。
- [x] 保护主目录15份内容/状态、当前1.0.1入口及runtime/Skill、旧1.0.0、rc1/rc2和历史评估manifest，记录SHA与版本。
- [x] 新建`.../evaluations/v1-0-2-reliability-v1`；存在时选择递增新目录，不覆盖。
- [x] 从审查fixtures复制六条静态源码及真实预期到cases.json：旧wrong边禁止，新正确直接边必需；先在已安装1.0.1记录旧结果。
- [x] F04不能直接复制已被复现钩子改写的app.py：使用审查source-change-result.json的old_source建立初始文件、new_source作为钩子替换内容，requested_symbol保持app.py::original。

验证：`git status --short`、`git rev-parse HEAD`、已安装1.0.1 `--version`；所有保护记录可重读，六条发现ID与审查一致。提交：`docs: freeze1.0.2 reliability scope and regression cases`。

### R1 — 正确采集当前函数绑定，先解决F05

**修改：** parser.py:_bindings，model.py:Symbol；新建tests/test_python_binding_safety.py。

**接口：** `_bindings(node) -> frozenset[str]`保持；Symbol追加`unsafe_call_bindings=frozenset()`、`is_instance_method=False`。本任务填充当前作用域事实，R2/R3读取该事实。

- [x] 在新unittest类建立`make_index(source)`辅助方法：TemporaryDirectory写app.py，build_index后返回index；测试不执行source。

辅助方法保留目录直到该测试结束，以便context/impact/map验证继续读取同一份源码：

```python
import tempfile
import unittest
from pathlib import Path
from repo_doctor.index import build_index

class PythonBindingSafetyTests(unittest.TestCase):
    def make_index(self, source):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / 'app.py').write_text(source, encoding='utf-8')
        return build_index(root)
```

- [x] 写以下失败测试，并先确认F05反例失败：

```python
def test_comprehension_name_does_not_shadow_module_call(self):
    index = self.make_index(
        'def helper():\n    return 1\n'
        'def caller():\n'
        '    values = [helper for helper in (1, 2)]\n'
        '    return helper()\n')
    self.assertIn(('app.py::caller', 'app.py::helper'),
                  {(e.caller, e.callee) for e in index.call_edges})
```

- [x] 用作用域感知visitor替代跨全部嵌套正文的ast.walk。采集参数、当前Store/Del/import/except/match；定义名字采集，嵌套正文隔离；定义创建表达式与推导式特殊绑定按设计处理。
- [x] 正例/反例覆盖list/set/dict推导式、嵌套函数局部名、普通参数遮蔽、普通赋值、except别名、global/nonlocal保守标记；不要因清除污染导致真实遮蔽失效。
- [x] 运行验证、审查事实字段和公开序列化兼容，提交。

验证：`python -m unittest tests.test_python_binding_safety tests.test_parser tests.test_graph -v`。提交：`fix: isolate Python lexical binding scopes`。

### R2 — 阻止闭包跳过外层绑定，解决F01

**修改：** graph.py:_resolve_call；测试test_python_binding_safety.py。

**接口：** 消费Symbol.parent/local_bindings/unsafe_call_bindings；保留CallEdge和Symbol ID合同。

- [x] 固定审查closure_shadow源码，写`test_enclosing_binding_blocks_global_fallback`；断言禁止outer.inner→模块helper。
- [x] 沿parent链检查函数作用域，跳过类属性作用域；发现外层同名绑定或风险标记时保留未知，不做本轮之外的闭包目标推断。
- [x] 正例：外层不绑定helper时原全局调用仍成立；类属性同名不被错当方法闭包；外层参数同名不误连模块。
- [x] 将同一反例送入build_context/build_impact/build_map，三处均不得出现错误边；不是只改context输出过滤。
- [x] 验证、审查、提交。

验证：`python -m unittest tests.test_python_binding_safety tests.test_context tests.test_repo_map -v`。提交：`fix: guard module fallback against enclosing Python bindings`。

### R3 — 局部定义被重绑后保留未知，解决F02

**修改：** parser.py的不安全绑定事实，graph.py当前nested提前返回；同一测试文件。

- [x] 写审查反例`test_rebound_nested_function_is_unresolved`，断言helper=replacement后不得有caller→caller.helper。
- [x] 在nested返回前核对unsafe_call_bindings；记录赋值/增量赋值/删除、import冲突、重复或条件定义等风险。不新增赋值别名推断。
- [x] 正例：普通单一定义且未重绑的嵌套helper仍有正确边；有效overload和已有歧义处理保持；参数与局部import的真实遮蔽不失效。
- [x] 用“普通定义”与“仅增加一条重绑语句”成对测试，避免让所有嵌套调用都变未知。
- [x] 验证、审查、提交。

验证：`python -m unittest tests.test_python_binding_safety tests.test_graph tests.test_index -v`。提交：`fix: reject rebound nested callable targets`。

### R4 — 守住真实self身份，解决F03

**修改：** parser.py:_add_symbol实例身份填充，graph.py:self分支；model.py已有新默认字段；同一测试文件。

- [x] 写`test_rebound_self_does_not_resolve_original_method`：Worker.caller中self=Other()后禁止Worker.work边；原Other构造调用仍可存在。
- [x] 在self快捷分支要求is_instance_method且self不在reassigned_parameters；有身份不明或重绑定风险时保留未知，不猜新类实例。
- [x] 覆盖正常self.work、self删除、增量/解包赋值、嵌套nonlocal写；staticmethod/classmethod参数恰好叫self时不得凭名字按原类连接。
- [x] 运行模块实例、Click语义与正常本地构造实例正例，保证现有支持保留。
- [x] 验证、审查、提交。

验证：`python -m unittest tests.test_python_binding_safety tests.test_graph tests.test_module_instances tests.test_module_instance_outputs tests.test_semantics -v`。提交：`fix: verify instance receiver identity before method resolution`。

### R5 — 绑定解析输入和输出证据，解决F04

**修改：** source.py、model.py、parser.py、js_ts.py、index.py、context.py、case.py、agent_tools.py、repo_map.py、cli.py；新建tests/test_source_consistency.py。涉及多个环节，由主代理执行。

**接口：** 设计规定的source_digests可选捕获、ParsedFile.source_digest、RepoIndex.source_digests、SourceConsistencyError、read_index_source。公开fingerprint算法和read_source默认返回str不变。

- [x] 写失败测试：在cli.main的一次context过程中，patch index.parse_python_file使其读取后把original改名replacement；必须退出2，stdout不输出成功JSON，snapshot不存在。
- [x] 写Python与JS/TS解析输入摘要测试：摘要来自同一次实际raw读取，不能在解析结束后再读文件作为基线；不增加无界读取。
- [x] 捕获raw SHA并传入索引；所有后续源证据读取使用read_index_source。区分稳定坏编码/语法覆盖错误与分析中来源变化。
- [x] 五命令输出准备、快照与地图写入前核对来源/集合；JS/TS候选集合变化不得继续使用旧关联。指纹except分支必须显式传播SourceConsistencyError。
- [x] 复用已有指纹/预算检查；仅R5需要的同次扫描复用可提前实现，传已有budget，不单独创建隐形新预算。
- [x] 反例覆盖目标/相关调用者变更、删除、解析后变编码、选中实现文件新增、JS/TS候选新增；稳定源码、稳定坏编码、语法错误覆盖提示仍按合同返回。
- [x] 地图失败时目录不存在，快照失败时文件不存在；已有案件/输出未改变。资源超限仍退出2，不返回部分成功。
- [x] 核对物理行、BOM/编码cookie、CRLF、2MiB/64MiB预算及旧fingerprint稳定值，审查后提交。

验证：`python -m unittest tests.test_source_consistency tests.test_source_lines tests.test_analysis_limits tests.test_agent_tools tests.test_context tests.test_repo_map tests.test_cli -v`。提交：`fix: keep repository evidence tied to parsed source identity`。

### R6 — 语言与后端提示正确，解决F06

**修改：** case.py:_static_issues、leads.py仅需文案时；新建tests/test_review_lead_languages.py；关联public docs。

- [x] Python/JS/TS各造一个静态语法失败样本；先确认app.js的review_leads错误写Python。
- [x] 依据index.file_languages生成实际语言/后端文案；JS/TS解释为Tree-sitter覆盖失败，不直接建议修补“非法源码”。
- [x] 保留issue ID/category、evidence、人工状态、case schema；未知语言使用中性提示。
- [x] 五命令帮助描述补充optional JS/TS事实；不在本任务重新设计全部legacy命令分组。
- [x] 验证、审查、提交。

验证：`python -m unittest tests.test_review_lead_languages tests.test_agent_tools tests.test_product_cli tests.test_public_docs -v`；`python tools/check_public_docs.py --root .`。提交：`fix: report parse coverage using the actual language backend`。

### R7 — 集成和安装后的行为验证

**新建/修改：** tools/validate_reliability_install.py、evaluation/reliability-v1/*、tests/test_v1_contract.py、CI接入安装validator；发行版本/文档准备。

- [ ] 新validator必须显式接收`--python --cli --expected-version --cases --out`，cwd设新输出目录，逐条记录argv/exit/stdout/stderr；确认import来自site-packages和metadata匹配。
- [ ] 安装validator断言“正确行为”而非审查脚本的“旧bug存在”：F01/F02/F03错误边不在context/impact/map，F05正确边存在，F06语言提示正确。
- [ ] F04以安装Python加载自己的产品模块并施加受控钩子；不执行fixture代码。退出2、无成功JSON、无snapshot/map产物作为验收。
- [ ] 加入普通模块调用、稳定嵌套函数、正常self、稳定快照/地图正例，防止通过全删关系来消除误报。
- [ ] 选择一个固定公开Python仓库，人工先核对含相关结构再做五命令只读调查；保存commit/tree/来源SHA、范围限制、发现前后差异。没有真实受影响结构就如实记录，不编造命中率。
- [ ] 原R051复查保持JSX修复、45符号/0解析错误及源码引用正确；核心五命令与HTML/SVG均能交付。
- [ ] 六项修复集成后执行一次完整源码回归；有js extra，skip必须逐项说明，不以旧563数目代替新执行结果。
- [ ] 准备真实候选版本，精确提交构建主wheel；native源码未变时验证同提交平台产物的runtime等价，不把旧bundle来源改写为新SHA。
- [ ] 独立base/js安装执行本计划validator、现有生命周期/base/js/v1和R051validators。源码、wheel、安装35份runtime按实际新文件数核对；不得盲写固定35如果增加runtime模块。
- [ ] 在既有CI矩阵接入新安装validator，等待精确候选head全部15任务成功；审核后合并，核对最终tree。

核心命令：

执行前将INSTALLED_PYTHON和INSTALLED_CLI分别设为本轮新建安装venv内的绝对python与repo-doctor路径，CANDIDATE_VERSION设为该wheel的实际metadata版本，NEW_RECEIPTS设为尚不存在的本轮回执绝对目录。验证器必须拒绝已有回执目录；不要使用源码解释器冒充安装解释器。首次R7执行时，先完成上面的validator实现与候选安装，再运行这些命令。

```sh
python -m unittest discover -s tests -v
python tools/check_public_docs.py --root .
python tools/validate_reliability_install.py --python "$INSTALLED_PYTHON" --cli "$INSTALLED_CLI" --expected-version "$CANDIDATE_VERSION" --cases evaluation/reliability-v1/cases.json --out "$NEW_RECEIPTS"
```

现有validator均使用真实候选版本与新目录，不复用历史receipt。主代理在代码/接口/资源边界完成后做独立审查；不得有未解决P1或发布阻塞。

### R8 — 正式1.0.2发布与本机闭环

**文件：** _version.py、CHANGELOG.md、README.md、INSTALL/SUPPORT_MATRIX/COMPATIBILITY/CLI_CONTRACT，实际日期交付记录；新证据products/preservation/completion/中文报告。

- [ ] 版本真实设为1.0.2；同步安装链接/验证器及正式SHA后重新构建，不重命名候选wheel。版本改变的最终head需自己的CI与安装事实。
- [ ] 发布主wheel、native后端zip、校验件、来源提交和release-receipt；native0.1.0不改版本或内容时仍按已审计发布规则保留真实来源。
- [ ] 从公开URL匿名下载四文件，在新目录原样执行tagged安装文档；再执行六项修复validator和真实仓库调查，校验源码/wheel/安装/公开资产一致。
- [ ] 公开安装复验后，备份当前1.0.1全局入口并原子切换；验证1.0.2→1.0.1→1.0.2，旧1.0.0/1.0.1环境均保留。
- [ ] 导出新目录Skill并绑定1.0.2绝对CLI，保留旧Skill。格式/绑定验证和新会话实际加载分别报告，不把导出成功写成会话加载成功。
- [ ] 发布后再核对保护清单、Git状态、旧证据归属，完成中文报告；已知限制仍明确，记录修复反例与公开样本不同性质。
- [ ] 指导书完成标记、独立审查、收尾文档合并，GraphFlow增量索引；所有事实已验证才写completion=closed。

最终出口：六项问题关闭、普通正例保留、公开下载安装成功、五命令/地图可交付、Codex绑定正确、升级回滚成功、旧文件/证据未覆盖。未达到出口不得称1.0.2已闭环。

## 后续独立体验优化清单

下列是候选批次，不阻塞R8。进入实施前由主代理补充具体接口合同并评估兼容性；当前不承诺未测量的性能提升。

### U1 — Codex输出更精简

- [ ] 固定本轮build_index查询基线：120行context=66006bytes；depth2 impact=172526bytes、214符号。记录来源和本机耗时，不当通用性能指标。
- [ ] 设计可选关系/总输出预算或分页，明确优先级、遗漏计数与继续查询方式；旧默认和1.x字段兼容。
- [ ] 验证被保留的证据引用不变、遗漏不会冒充完整结果、同一调查能继续取得完整必要证据。
- [ ] 在一个真实调查对比总输入体积和查询次数，再决定是否默认启用。

### U2 — 同次扫描复用

- [ ] esm.py优先使用index.discovered_paths；备用discover_files传已有budget。
- [ ] 用计数spy证明同一索引没有多余Git发现；用候选变化/歧义反例验证结果不误连。
- [ ] 记录真实仓库前后耗时；没有收益也如实记录。持久缓存不在本任务范围。

R5若已经完成该复用，本项记为由R5覆盖，不重复实施。

### U3 — 产品入口更清楚

- [ ] README和help按“核心五命令/Skill/旧兼容工作流”分组；主描述准确覆盖Python和optional JS/TS。
- [ ] 旧diagnose/doctor/reproduce/verify仍可用且明确opt-in，不删命令、不自动联网。
- [ ] 维护者默认工作入口指向正式工作树；旧主目录15份改动先整理清单再单独迁移，不做reset。
- [ ] 用首次用户五步调查验证能找到正确入口；保持自动化argv兼容。

### U4 — 安装与维护便利性

- [ ] 检查四文件安装中可合并的重复操作，给出单一清晰入口和失败定位；继续校验资产SHA和平台匹配。
- [ ] 独立评估PyPI主包/companion双包发行，不将未发布包视为可pip获取；无明确收益时保持已可用GitHub发行路径。
- [ ] 只有实际需求与维护能力支持时再规划Windows/Intel Mac/Linux ARM等；单独多平台构建/实机验证，不改当前支持声明。

## 执行责任与异常处理

主代理执行作用域、绑定、来源一致性、依赖、审查与发布。本轮不派Luna做设计或debug。未来仅在步骤完全确定且只是限定文件的机械操作时，按AGENTS读取fresh周配额，选择合规executor；任务包包含Objective、Allowed changes、Forbidden changes、Exact steps、Validation、Expected result、Stop conditions。一次最多一个；不得处理依赖、权限、发布、推送或外部事实。返回后主代理看实际diff并重新验证。

任何资料冲突、缺少源码身份、预算/兼容风险或范围外缺陷都返回主代理；保留失败证据，重新拆分，不扩大权限或削弱验证。R1–R6阶段内只跑相应回归；R7/R8所需完整门禁才执行一次完整回归或精确提交CI。

## 完成状态

- [x] 当前版本/六项问题已调查并独立复现。
- [x] 可靠性设计、任务范围、顺序与完成条件写入指导书。
- [x] R0–R6实现与定向回归。
- [ ] R7–R8安装、CI与发行闭环。
- [ ] U1–U4按真实收益择项实施。

本清单是产品优化指导书；验证步骤用于证明每项优化成立，不是另起一个扩大测试数量的项目。

## 实施记录补充

R5复用同次ESM发现路径（U2由R5覆盖）。ESM解析使用整个已发现路径集合判断扩展名为空、JSON/node和package.json等歧义，因此集合校验必须覆盖它实际消费的所有路径。完整回归发现旧诊断失败记录会重读旧索引，已增加源码变化时保留原target、只记录失败身份的兼容修复；不新增云端功能。
