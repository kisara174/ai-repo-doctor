# JS/TS 保守源码关联 Implementation Plan

> **For agentic workers:** 使用 executing-plans 按任务执行。主代理负责设计、实现决策、审查与验收；不把这些职责委派给 Luna。用户已于“开始实施”消息确认设计；按 S0–S6 推进。

**Goal:** 为无后缀与目录 index 导入提供可追溯的唯一源码关联，让 Codex 完成文件与安全直接调用调查，并通过候选安装和发布门槛。

**Architecture:** 在现有 ESM resolver 内增加有限候选并集分支，先拒绝歧义，再检查选择与解析状态。保留现有调用护栏，用 RepoIndex 内部映射保存文件声明和实际调用绑定的来源，条件性扩充 context/impact JSON。地图使用现有结构投影，不改 viewer。

**Tech Stack:** Python 3.11+、unittest、现有 Tree-sitter 可选依赖、现有静态 HTML/SVG 地图和 GitHub Actions。

**Spec:** [2026-10-07-js-ts-source-association-design.md](../specs/2026-10-07-js-ts-source-association-design.md)。执行前同时读取 [研究报告](../../evaluations/2026-10-07-extensionless-source-survey.md)。

## Global Constraints

- Python 3.11+；现有依赖固定版本不变，不新增依赖。
- 默认语言仍为 Python；JS/TS 需要 `[js]` 与显式 `--languages`。
- 实现扩展仍只有 `.js`、`.mjs`、`.ts`；声明文件、JSX/TSX、CommonJS、alias、运行时调用与多跳再导出调用不新增支持。
- 不新增 CLI 命令、网络服务、API 调用、目标代码执行或自动修复。
- 关联仅限扫描器可见、安全、仓库内文件；沿用 ignore、软链接、源码身份与读取检查。
- 候选唯一性先判断，再判断目标是否被选择和成功解析。
- 地图节点 200、边 500 上限不变；viewer 不修改；人类界面仍只呈现结构关系。
- 0.6.0 发行证据、历史 200 评分、主目录既有 14 个改动、全局 0.5.3 和已安装 Skill 保持原样。
- 任何实际代码缺陷先复现与定位。不得通过扩大支持范围、删除负例或降低验收标准获得通过。

---

## 工作入口与文件责任

复用工作树 `/Users/kisara/.codex/worktrees/js-ts-support-closure/AI Repo Doctor`，研究文档分支 `codex/js-ts-source-association`，起始提交 `c41f9ec4e1a264ef8d7366bccce298335181715e`。主目录不用于实现。

共同命令环境（这些变量仅指路径，不读取任何 key）：

```sh
RD_WORKTREE='/Users/kisara/.codex/worktrees/js-ts-support-closure/AI Repo Doctor'
RD_TEST_PY='/Users/kisara/.local/share/ai-repo-doctor/releases/v0.6.0/venvs/js/bin/python'
RD_EVIDENCE='/Users/kisara/.local/share/ai-repo-doctor/evaluations/js-ts-source-association-v1'
cd "$RD_WORKTREE"
```

| 文件 | 允许职责 |
|---|---|
| repo_doctor/esm.py | 有限候选、缓存、来源记录，保留调用防护 |
| repo_doctor/model.py | ESMSourceAssociation 和 RepoIndex 两个内部映射 |
| repo_doctor/context.py | 共用调用证据序列化；条件性添加 JS/TS 来源 |
| repo_doctor/languages.py | JS/TS analysis 的政策说明 |
| tests/test_esm.py | 更新两个旧未知断言；新增正负解析合同 |
| tests/test_context.py | import 与 call 来源、预算、深度、Python 兼容 |
| tests/test_repo_map.py、tests/test_cli.py | 新边投影与实际 CLI JSON；无新界面 |
| tools/validate_js_ts_install.py | 安装后静态新路径合同 |
| repo_doctor/_version.py、tools/validate_release_install.py | 候选/正式版本一致性，进入 S5 才改 |
| docs/JS_TS_SUPPORT.md、README.md、repo_doctor/resources/skill/SKILL.md | 新边界与 Codex 使用说明；不覆盖用户已安装 Skill |
| evaluation/js-ts-source-association/ | 新定向案例与原始来源身份 |

禁止为了此任务修改 parser、scanner、source、依赖版本、CLI 参数、viewer、历史 cases/oracle。若定位证明必须修改未列出文件，主代理先补充原因与最小范围记录；机械执行器必须停止返回主代理。

主代理自行执行主路径；只有全部决策已确定的单一机械编辑才可按 AGENTS 路由规则委派。不得为“研究设计”“修复解析器”“发布”创建 Luna 任务。

## S0：确认合同、冻结定向来源

**Files:** 新建 `evaluation/js-ts-source-association/README.md`、`cases.json`；新回执写入 `/Users/kisara/.local/share/ai-repo-doctor/evaluations/js-ts-source-association-v1/product-validation/`，不得覆盖已完成 attempt。

**Interfaces:** 消费已确认设计、attempt-002/declarations.jsonl、旧 oracle-review.jsonl；产生 `cases.json` schema_version=1、status=prepared-not-run、positive_file_imports（七条）、direct_call（pyRound）、ambiguous_imports（四条）。每条保留 repo_id、commit、source_file、source_sha256、start_line、end_line、specifier、candidate_paths、expected_classification。调用另存 caller/callee 的查找词与预期调用行，不把猜测的 ID 当执行输入。

- [x] 核对设计确认记录；把确认时间与本计划路径写入新 receipt。没有确认时停在文档，不开始实现。
- [x] 用 `git status --porcelain`、`git rev-parse HEAD` 确认任务拥有的工作树；恢复已有实现时先核对实际 diff，不能重建或覆盖。
- [x] 从 `attempt-002/validation.json.old_oracle_matches` 和声明记录机械复制七条来源；从同一声明记录选出四条 ambiguous；复制 dembrane usage.ts 第 2 行记录及 numbers.ts 摘要。不得改历史 oracle。
- [x] 形成 `cases.json` 时按以下校验合同验证：

```python
import json, hashlib
from pathlib import Path
p = Path('evaluation/js-ts-source-association/cases.json')
c = json.loads(p.read_text())
assert c['schema_version'] == 1 and c['status'] == 'prepared-not-run'
assert len(c['positive_file_imports']) == 7
assert len(c['ambiguous_imports']) == 4
assert c['direct_call']['expected_call_line'] == 76
root = Path('/Users/kisara/.local/share/ai-repo-doctor/evaluations/benchmark200-v1/checkouts')
for r in c['positive_file_imports'] + c['ambiguous_imports'] + [c['direct_call']]:
    raw = (root / r['repo_id'] / r['source_file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == r['source_sha256']
```

- [x] 保存旧正式版对这十二个声明的定向基线。只需选定仓库的 map JSON 和 pyRound symbols/context/impact，全部明确使用 0.6.0 独立 CLI；保存 argv/cwd/stdout/stderr/exit_code/源码身份。旧结果应为未知路径，不修改评分。
- [x] README 写清：八个不同仓库均已看过；四条负例与正例共用 sunanakgo；这一组不是新盲测或 200 全量。
- [x] 审查并提交本任务文件。出口：来源校验通过，baseline 成功保存且尚无新产品通过声明。

## S1：有限候选分支与调用护栏

**Files:** 修改 `repo_doctor/esm.py`、`tests/test_esm.py`。不改 parser 或扫描规则。

**Interfaces:** 新 helper `_resolve_source(file: str, specifier: str, path_set: set[str], file_languages: dict[str, str], failed: set[str]) -> tuple[str | None, str]`。成功第二项为 resolution_kind，失败为设计固定 reason。resolve_esm_graph 对每个 `(file,specifier)` 缓存该结果，沿用 ImportEdge 和 ESMImportRef 字段。

- [x] 先在 tests/test_esm.py 增加 `SourceAssociationTests`（使用已有 HAS_EXTRA 装饰）和以下最小红测：

```python
def test_unique_extensionless_and_index_keep_safe_direct_calls(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        (root / 'dir').mkdir()
        (root / 'core.ts').write_text('export function inc(v: number) { return v+1; }')
        (root / 'dir/index.ts').write_text('export function next(v: number) { return v+1; }')
        (root / 'app.ts').write_text(
            "import {inc} from './core';\nimport {next} from './dir';\n"
            'export function run() { return next(inc(1)); }\n')
        index = build_index(root, languages=('typescript',))
        self.assertEqual({(r.specifier, r.resolved_file, r.resolution_kind) for r in index.esm_imports},
            {('./core','core.ts','unique-extensionless-source'),
             ('./dir','dir/index.ts','unique-directory-index-source')})
        self.assertEqual({(e.caller,e.callee,e.line) for e in index.call_edges},
            {('app.ts::run','core.ts::inc',3),('app.ts::run','dir/index.ts::next',3)})
```

- [x] 运行 `PYTHONDONTWRITEBYTECODE=1 "$RD_TEST_PY" -m unittest tests.test_esm.SourceAssociationTests -v`，其中 RD_TEST_PY 为既有 0.6.0 releases/v0.6.0/venvs/js/bin/python 的绝对路径。预期失败在 resolved_file / 缺边，不接受因为导入错误或 extra 未安装而红。
- [x] 从现有 target_for 提取 helper，明确扩展/TS.js 替换分支逐字保留判定；无后缀分支按设计候选并集实现。判定顺序为路径合法性、目录 package 阻断、候选数、目标选择/实现扩展、解析状态。用 set 查交集；不遍历 path_set 找前缀，不读取 package.json。
- [x] 在现有循环外建立 `resolution_cache = {}`，只在 key 不存在时调用 helper；调用护栏与 unresolved-call 逻辑不放宽。
- [x] 同一测试类用 subTest 覆盖下表，逐项构造独立临时目录。正例 target 文件定义 `export function inc() { return 1; }`；consumer 用 `import {inc} from 'SPEC'; export function run() { return inc(); }`。断言具体文件边、具体调用边和 reason，不能只断言“有结果”。

| 输入/候选 | 文件边 | 调用边或失败 reason |
|---|---|---|
| ./core 唯一 core.js、core.ts 或 core.mjs（分别运行） | 有，目标扩展对应已选语言 | 有 |
| ./dir 唯一 dir/index.ts 或 index.js（分别运行） | 有 | 有 |
| ../core、../. 规范化后唯一实现 | 有 | 有，仍在仓库内 |
| core.ts + core.js；core.ts + core.d.ts；dir.ts + dir/index.ts（导入 ./dir） | 无 | ambiguous-local-source-candidates |
| exact stem 文件 + 同名 .ts；index.ts + index.tsx；core.ts + core.json；core.ts + core.node | 无 | ambiguous-local-source-candidates |
| 仅 .d.ts/.tsx/.jsx/.mts/.cts/.cjs/.d.mts/.d.cts/.json/.node（逐一） | 无 | unselected-or-unsupported-local-source |
| 唯一 core.js 但只选 typescript | 无 | unselected-or-unsupported-local-source |
| 唯一 core.ts 内容为 export function broken( { | 无 | parse-error-local-source |
| 无候选 | 无 | no-local-source-candidate |
| 唯一 index.ts，stem/package.json 可见 | 无 | directory-package-configuration |
| 唯一 core.ts，同时 core/package.json 可见 | 无 | directory-package-configuration |
| ./core?x、./core#x、./core%x、./core/ | 无 | unsupported-source-specifier |
| ../../../outside | 无 | outside-source-root |
| alias/pkg、反斜杠路径、require、dynamic import | 无新增 | 保持既有未知合同 |
| type-only 导入、namespace 导入 | 有 | 无调用 |
| 导入函数被遮蔽/重赋值、对象方法、回调、多跳桶导出 | 可有文件边 | 无虚构调用 |
| .gitignore 排除目标、目标软链接、node_modules/build 内来源 | 无 | 不越界读取，既有扫描合同保持 |

- [x] 更新两个旧测试：`test_external_dynamic_extensionless_invalid_and_type_only_do_not_become_runtime_calls` 中第 3 行文件边改为存在，其余负例原样保留；`test_extensionless_directory_index_stays_unknown` 改名并要求唯一 index 成功。旧 J5 冻结来源不编辑，不回写 C12 历史合同。
- [x] 测试重复 resolve_esm_graph 不重复添加边或 limits；保留已有 limit_dedup 比较上限测试，增加同一声明多 named bindings 的 cache 调用次数检查（mock helper，唯一 specifier 只调用一次）。
- [x] 运行 `"$RD_TEST_PY" -B -m unittest tests.test_esm tests.test_js_ts tests.test_languages tests.test_index -v`，必须无失败、无 skipped。审查 diff，按目标提交 S1。出口：唯一与拒绝规则均可复现，旧明确路径及调用防护保持。

## S2：实际来源进入 context/impact

**Files:** 修改 `repo_doctor/model.py`、`esm.py`、`context.py`、`languages.py`、`tests/test_context.py`、`tests/test_esm.py`。

**Interfaces:** 严格使用设计第 6 节的 ESMSourceAssociation、RepoIndex.esm_source_associations、RepoIndex.js_call_imports。新增 `_call_edge_data(index: RepoIndex, edge: CallEdge) -> dict`；字段只有真实 JS/TS import 来源存在时才增加。

- [x] 先增加 context 红测，使用 S1 的 app.ts、core.ts 临时源码并检查：

```python
context = build_context(index, 'app.ts::run', max_lines=120)
edge = next(e for e in context['call_evidence'] if e['callee']=='core.ts::inc')
proof = edge['via_esm_import']
self.assertEqual((proof['file'], proof['specifier'], proof['resolved_file']),
                 ('app.ts', './core', 'core.ts'))
self.assertEqual((proof['start_line'],proof['end_line'],proof['alias'],proof['imported']),
                 (1,1,'inc','inc'))
self.assertEqual(proof['resolution_kind'], 'unique-extensionless-source')
self.assertFalse(proof['type_only'])
impact = build_impact(index, 'core.ts::inc', depth=2)
hop = next(a for a in impact['affected_symbols'] if a['symbol']=='app.ts::run')['call_path_evidence'][0]
self.assertEqual(hop, edge)
self.assertEqual(impact['import_evidence'][0]['esm_source_association']['specifier'], './core')
self.assertFalse(context['analysis']['esm_source_resolution']['runtime_resolution'])
```

- [x] 运行 `"$RD_TEST_PY" -B -m unittest tests.test_context -v`，确认新测试缺少来源字段而失败。
- [x] 在 model.py 新增设计中的冻结 dataclass，RepoIndex 两字典使用 `field(default_factory=dict)`，不改变 CallEdge/ImportEdge 或 Python asdict 合同。
- [x] 在 resolver 的文件边成功处记录实际 ref 的 file/specifier/target/start/end/kind；不记录失败声明。多 named binding 同声明合并一条文件来源；同键的不同声明按 `(specifier,end_line)` 选最小来源。
- [x] 将内部 direct_target 的返回改为 `tuple[str, ESMImportRef | None] | None`：本地函数用 `(sid,None)`；实际通过全部护栏的导入函数用 `(sid,ref)`。循环解包后保存绑定来源。相同键按设计的五元组取最小，不扫描源码猜 ref。
- [x] `_call_edge_data` 先产生旧五个字段，再按键查来源增加 via_esm_import。context 与 impact 的重复字典构造都改调用 helper；Python 返回字典必须与旧字段集合和值相同。
- [x] impact 文件依赖按 `(source,target,line)` 查 esm_source_associations 条件性添加来源。languages.analysis_metadata 在 JS/TS 被选择时增加政策对象；Python-only 不增加。
- [x] 增加四种来源验证：明确扩展路径、无后缀文件、index、多行 import；再增加二层 impact（entry -> imported wrapper -> imported leaf），每个 hop 来源指向自己的真实声明。
- [x] 对 type-only、namespace、多跳再导出验证可有文件来源但无 call 来源；对同一行两个导入别名调用同一函数验证单条确定性来源和重复解析稳定。
- [x] max_lines=1 与 120 均核对 blocks 实际行数不超预算；来源 metadata 不复制源码引文；截断状态与省略数符合原合同。用现有 ContextTests Python fixture 核对默认 context/impact 完整字典与 0.6.0 基线一致，不允许新增空键。
- [x] 运行 `"$RD_TEST_PY" -B -m unittest tests.test_context tests.test_esm tests.test_agent_tools -v`，无 skipped。审查 diff 后提交 S2。出口：来源来自实际解析绑定，两个消费接口口径一致。

## S3：地图、CLI 与公开支持范围

**Files:** 修改 `tests/test_repo_map.py`、`tests/test_cli.py`、`docs/JS_TS_SUPPORT.md`、`README.md`、`repo_doctor/resources/skill/SKILL.md`。repo_map.py 原则上不改，现有代码已消费 import_edges/call_edges 和 analysis_metadata。

- [x] 构造 app.ts -> dir/index.ts 的临时源码，build_map 输出必须有对应 import/call，完整边与 file_edges 的来源行准确，relations 端点存在，nodes/edges 上限不变；有 type-only 导入的地图不能增加虚构 call。
- [x] 用已有 CLI 测试方式运行 overview/symbols/context/impact/map，全部显式 typescript。检查 policy/runtime_resolution、call/import 来源、HTML/map.json/两份 SVG 均产生；解析 SVG XML 并对照实际投影节点/边。
- [x] Python CLI 默认输出不新增 JS policy 或 via_esm_import；混合语言输出保留各语言统计。无 extra 仍报原安装提示而不加载后端。
- [x] 支持矩阵把无后缀/index 改为“唯一可见实现源码关联；非运行时解析”；列明同时存在 .d.ts、不同实现或目录配置时拒绝，以及类型依赖与函数调用差别。
- [x] packaged Skill 写明：先 symbols 取真实 ID；读 analysis 和来源；context 行预算 120；impact depth 2；空结果与省略限制；不能把唯一候选理解为运行时保证。不改用户目录中已安装 Skill。
- [x] README 保留正式安装版本 0.6.0，先链接新设计作为未发布能力；正式发版时才替换发行安装链接。
- [x] 执行 `"$RD_TEST_PY" -B -m unittest tests.test_repo_map tests.test_cli -v`。viewer 字节必须与 0.6.0 相同；不要启动 Chrome 排障，也不将 DOM 测试说成实际浏览器验收。
- [x] 审查并提交 S3。出口：人类地图仍是结构关系，Codex JSON 与文档说明一致。

## S4：八仓库定向调查与收益复核

**Files:** `evaluation/js-ts-source-association/cases.json` 保持 prepared 来源不改写为结果；结果仅写 product-validation 新 attempt 的 `commands/`、`review.jsonl`、`summary.json`、`maps/`。

- [x] 先提交 S3 并保存本地实现 SHA 与干净工作树状态。S4 使用这个源码提交的 CLI，不把它写成正式版 0.6.0 验收；S5 安装后另跑一次。为避免误用旧环境中已安装的 CLI，定义以下函数，并在每个回执中保存展开后的真实 argv：

```sh
rd_candidate() {
  env -u PYTHONPATH -u DEEPSEEK_API_KEY "$RD_TEST_PY" -B -m repo_doctor "$@"
}
RD_DEMBRANE='/Users/kisara/.local/share/ai-repo-doctor/evaluations/benchmark200-v1/checkouts/dembrane__echo'
```

- [x] 用 rd_candidate 对七条旧案例各生成一次 map JSON（按仓库复用一次命令），检查完整 edges 中对应 source/target/import_start_line。投影因 200/500 限制不展示全部边不能算解析失败；完整数据必须存在。只验证文件依赖，不强制类型/桶文件产生函数边。
- [x] 同一 sunanakgo map 检查四条 preload/index 歧义：不能出现任一候选文件边，limits 中包含对应拒绝来源或明确计入省略；必要时 API 单项 index 检查全部 limits，并注明 CLI 最多 50 条。
- [x] 用 symbols `--query pyRound` 与 `--query withCapSignals` 取得真实 ID；再执行以下四步，每步保存完整回执：

```sh
rd_candidate overview "$RD_DEMBRANE" --languages javascript,typescript --json
rd_candidate symbols "$RD_DEMBRANE" --query pyRound --languages javascript,typescript --json
rd_candidate context "$RD_DEMBRANE" "$RD_PYROUND_ID" --include-symbol "$RD_CAPSIGNALS_ID" --max-lines 120 --languages javascript,typescript --json
rd_candidate impact "$RD_DEMBRANE" "$RD_PYROUND_ID" --depth 2 --languages javascript,typescript --json
```

RD_DEMBRANE 为 benchmark200 固定 checkouts/dembrane__echo；两个 ID 从刚才 symbols 响应精确选取，找不到或不唯一即失败，不拼接猜测。第二个 query 命令也保留，不把上列四步称为实际命令总数。

- [x] 主代理逐条比对 context 源码行，确认 usage.ts:76 的 withCapSignals -> numbers.ts::pyRound 与 usage.ts:2 的 via_esm_import；impact path/hop 指向相同调用及来源。额外返回的其他调用单独核验，不以未列出的调用数量作为门槛。
- [x] 对照 S0 基线，报告“7/7 文件声明的关联变化”“4/4 歧义拒绝”“1 个真实调查是否闭环”，实际源码行预算/截断、额外手工读取次数。没有计时和 token 仪表就不报告节省比例。
- [x] 每个仓库执行前后核对固定 commit、tree、干净 Git 状态与所用来源文件摘要。目标代码/依赖不运行，不更改历史成绩。
- [x] 主代理审查所有新增正边的来源，拒绝条件全部通过才能进入 S5。若结果需要新语义，暂停该扩展并回到设计，不通过猜测补绿。

## S5：冻结候选、独立安装与 CI

**Files:** 修改 `_version.py`、两个安装验证器的版本常量；扩充 `tools/validate_js_ts_install.py` 静态 fixture；本轮冻结 SHA 及安装证据写新 candidate 目录。

- [x] 安装验证器 JS 模式新增独立子目录 association：core.ts 导出 inc；dir/index.ts 导出 next；consumer.ts 无后缀导入并直接调用；types.ts type-only 导入；ambiguous 子目录放 core.ts/core.d.ts。不把这些文件并入原固定 fixture 根，避免改变原统计。
- [x] 增加 CLI 检查：正例 context/impact 的实际 binding 来源、index 文件依赖、歧义负例没有调用、type-only 无调用、地图文件边/端点/SVG。执行前后逐文件摘要保持相同。base 模式维持缺 extra 提示和无副作用，不安装 JS 依赖。
- [x] 候选版本三处同步设为 0.7.0a1，审查后提交。只从该提交 git archive 构建 wheel；保存 source SHA、tree、版本、wheel SHA256，禁止从脏工作树打包。依赖安装由主代理执行。
- [x] 用既有 JS 环境运行相关合同并硬性禁止 skipped：

```sh
"$RD_TEST_PY" -B - <<'PY'
import unittest
names=['tests.test_languages','tests.test_js_ts','tests.test_esm','tests.test_index',
       'tests.test_context','tests.test_cli','tests.test_agent_tools','tests.test_repo_map','tests.test_js_ts_spike']
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
assert r.wasSuccessful() and not r.skipped
PY
"$RD_TEST_PY" -B -m unittest discover -s tests -v
```

- [x] 新 candidate 目录设置以下绝对路径变量，再从冻结 source 构建。目录都必须不存在；恢复时核对身份并使用新 attempt，不能覆盖。

```sh
RD_CANDIDATE_ROOT="$RD_EVIDENCE/candidate/attempt-001"
test ! -e "$RD_CANDIDATE_ROOT"
test -z "$(git -C "$RD_WORKTREE" status --porcelain)"
RD_CANDIDATE_SHA=$(git -C "$RD_WORKTREE" rev-parse HEAD)
mkdir -p "$RD_CANDIDATE_ROOT"
RD_SOURCE="$RD_CANDIDATE_ROOT/source"
RD_SOURCE_TAR="$RD_CANDIDATE_ROOT/source.tar"
RD_WHEELS="$RD_CANDIDATE_ROOT/wheels"
RD_WHEEL="$RD_WHEELS/ai_repo_doctor-0.7.0a1-py3-none-any.whl"
RD_BASE_ENV="$RD_CANDIDATE_ROOT/venvs/base"
RD_JS_ENV="$RD_CANDIDATE_ROOT/venvs/js"
RD_BASE_RECEIPTS="$RD_CANDIDATE_ROOT/install-base"
RD_JS_RECEIPTS="$RD_CANDIDATE_ROOT/install-js"
RD_LIFECYCLE_RECEIPTS="$RD_CANDIDATE_ROOT/install-python-lifecycle"
```

以上步骤逐条检查退出码，任一 test 失败立刻停止，不允许继续执行后面的 mkdir。实际执行可由 Python subprocess(check=True) 编排，不能忽略 shell 非零退出。

```sh
git -C "$RD_WORKTREE" archive "$RD_CANDIDATE_SHA" -o "$RD_SOURCE_TAR"
mkdir "$RD_SOURCE"
tar -xf "$RD_SOURCE_TAR" -C "$RD_SOURCE"
python3 -m pip wheel --no-deps --wheel-dir "$RD_WHEELS" "$RD_SOURCE"
python3 -m venv "$RD_BASE_ENV"
python3 -m venv "$RD_JS_ENV"
"$RD_BASE_ENV/bin/python" -m pip install --no-index "$RD_WHEEL"
"$RD_JS_ENV/bin/python" -m pip install "$RD_WHEEL[js]"
"$RD_BASE_ENV/bin/python" "$RD_SOURCE/tools/validate_js_ts_install.py" --mode base --python "$RD_BASE_ENV/bin/python" --cli "$RD_BASE_ENV/bin/repo-doctor" --out "$RD_BASE_RECEIPTS"
"$RD_JS_ENV/bin/python" "$RD_SOURCE/tools/validate_js_ts_install.py" --mode js --python "$RD_JS_ENV/bin/python" --cli "$RD_JS_ENV/bin/repo-doctor" --out "$RD_JS_RECEIPTS"
"$RD_JS_ENV/bin/python" "$RD_SOURCE/tools/validate_release_install.py" --python "$RD_JS_ENV/bin/python" --cli "$RD_JS_ENV/bin/repo-doctor" --out "$RD_LIFECYCLE_RECEIPTS"
```

RD_SOURCE_TAR、三个 RECEIPTS 路径位于相同 candidate attempt 下；RD_WHEEL 是该目录唯一的 ai_repo_doctor-0.7.0a1-py3-none-any.whl。先检查 wheel 只有一个且 metadata 版本正确，再赋值，不用 glob 猜版本。

- [x] 从 source/wheel/安装环境逐文件核对全部 packaged runtime 字节；确认 import 来自 site-packages，后端固定版本正确，base 没有后端。实际通过命令数在回执中计数：原基线 base 9、JS 18、Python 生命周期 33，加项后不能继续照抄旧总数。
- [x] 从独立安装 CLI 再执行 S4 定向案例并审查，不把源码环境结果替代安装验证。
- [x] 创建 PR 并附到当前任务；必须得到精确冻结提交的七项 CI：Python 3.11/3.12/3.13、JS preview Python 3.11/3.12/3.13、Offline map interaction and SVG。不要使用分支最新绿色代替候选 SHA。
- [x] 完成主代理独立 diff 审查与必要修正。若代码改变，冻结新 SHA 并重做受影响门槛，不能继承旧候选 pass 标签。

## S6：正式交付闭环

**Files:** 三处正式版本号、README 发行链接、packaged Skill 的版本路径、支持矩阵、`docs/delivery/2026-10-08-v0.7.0-source-association.md`；发行证据位于新的 releases/v0.7.0。

- [x] 只有 S0–S5 全部满足后才准备正式 0.7.0。候选到正式的每个 runtime 差异列清，禁止假设只差版本；正式冻结 SHA 必须重做独立安装、字节一致和精确提交 CI。
- [x] 发布前报告包含：新增功能、保守边界、八仓库逐条结果、实际命令计数、Python 兼容、已知限制、源码/wheel/安装身份、旧证据归属和回滚路径。prepared、blocked、failed 与 passed 分开，失败尝试保留。
- [x] 按会话已有授权处理合并和 GitHub wheel 发行；如果新的用户指令缩小授权，遵循最新指令。Luna/Harness 不得执行 push、合并、tag 或 release。
- [x] 正式 wheel 与 SHA256SUMS 可下载且摘要相符；独立 JS 安装路径版本为 0.7.0。保持全局 0.5.3 不切换，不覆盖用户 Skill；需要切换时单独按明确用户意图办理。
- [x] 复核主目录既有 14 个文件、受保护旧候选 runtime、旧评估证据与安装 Skill 摘要；沿用原保护清单，报告实际覆盖数量与 mismatch，不能只看 Git status。
- [x] graphflow_index 增量刷新；更新本清单完成勾选和交付状态。只有发行可下载、安装可运行、功能闭环、原状态受保护时才称正式交付完成。

## 自审与执行顺序

S0 来源 → S1 解析 → S2 来源接口 → S3 地图和公开说明 → S4 真实调查 → S5 候选门槛 → S6 正式交付。不得跳过负例直接发版；不追加完整 200 回归、Chrome 排障、多语言/alias/自动修复等独立目标。

每个任务的后续执行者必须拿到本计划和设计全文。没有独立可验证输出的事项由主代理处理，不为了使用简单模型而把判断压进机械任务。

当前状态：S0–S6 已完成。0.7.0 已公开发布，来源提交 `552b23f7e26462b084b0ac3744a801e66ab26bad`，PR #41 已合并。正式独立安装65条命令（含预期非零负例）、110项相关合同、八仓库13条定向命令及合并提交七项CI通过；公开下载wheel逐字节等于验收产物。全局0.5.3、用户Skill及原14文件/150789份证据/65旧runtime不变。最终证据与报告：`/Users/kisara/.local/share/ai-repo-doctor/releases/v0.7.0/delivery-report.md`、`/Users/kisara/.local/share/ai-repo-doctor/releases/v0.7.0/completion.json`。
