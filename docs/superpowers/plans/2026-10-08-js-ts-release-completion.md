# JS/TS 完善正式版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 主代理inline执行；Luna/Harness仅可承担用户路由策略允许的小型机械任务，不能判断设计或发版。Steps use checkbox syntax for tracking.

**Goal:** 在0.7.0基础上修复错误证据泄漏，新增真实JSX/TSX调查覆盖，交付稳定可安装的0.8.0。

**Architecture:** 复用现有扫描、模型、ESM、context/impact和地图。修复错误检查遍历；只对.tsx选择现有TSX grammar，新增.jsx/.tsx语言映射，保持安全直接调用边界。真实源码定向验证后冻结候选与正式包。

**Tech Stack:** Python >=3.11；tree-sitter==0.26.0、tree-sitter-javascript==0.25.0、tree-sitter-typescript==0.23.2；Node仅用于本项目离线DOM验收。

**Spec:** `docs/superpowers/specs/2026-10-08-js-ts-release-completion-design.md`，后续执行者必须先完整阅读。

## Global Constraints

- 工作树 `/Users/kisara/.codex/worktrees/js-ts-support-closure/AI Repo Doctor`；分支 `codex/js-ts-release-completion`；基线4c3a709。
- 新证据E：`/Users/kisara/.local/share/ai-repo-doctor/evaluations/js-ts-release-completion-v1`；正式R：`/Users/kisara/.local/share/ai-repo-doctor/releases/v0.8.0`。输出目录每次新建，失败attempt保留。
- Python默认及JSON不新增JS字段；三个固定依赖不变；无新命令；地图200节点/500边；原0.7.0源码关联歧义/目录配置/类型及调用护栏不放宽。
- 全局0.5.3、用户Skill、原改动、旧评分/证据和0.7.0发行不覆盖。目标仓库只读，代码不执行，依赖不安装，无在线诊断。
- 只对真实剩余风险扩大测试；原80仓库研究不是200全量产品回归；本轮真实案例为已见定向验证，不叫盲测。
- 所有正式发行与Git操作由主代理执行。会话已授权自主推进和发布；不添加重复用户审阅门槛。

## P0：冻结基线与研究缺口（D1/D2/D5）

**Files:** E/protection-before.json、E/baseline-contracts.log、E/research/。

- [x] 核对工作树隔离且干净，建立新分支；保护0.7.0的2426文件/8链接，并核对原14文件/65runtime/用户Skill。
- [x] 用0.7.0独立解释器在工作树运行110项相关合同，无skip；结果写baseline-contracts.log。
- [x] `research/classify-rejections.py`复核130个固定后端排除文件，保存rejections.json、summary.json和每仓库commit/tree。确认37个匿名MISSING错误泄漏。
- [x] `research/frontend-inventory.py`及frontend-parse.py按固定inventory/source SHA复核3332文件；3291 grammar parsed/41 rejected。记录为可行性而非产品成功数。
- [x] 查询官方ERROR/MISSING、TS/TSX方言与PyPI说明，确定不换依赖方案。

## P1：设计与清单（D1–D5）

**Files:** 本清单、对应spec、docs/evaluations/2026-10-08-js-ts-release-gap-review.md。

- [x] 编写spec及本清单，明确实际改进、接口、未知、保护和发行完成条件。
- [x] 写gap review，引用固定摘要与结果，不把解析拒绝说成目标源码bug；列选定修复、JSX/TSX增强和后续未纳入项。
- [x] 自审spec/plan：每项D1–D5都有下述任务；无未定义接口或占位步骤。提交文档。

## P2：修复匿名MISSING错误隔离（D1）

**Files:** 修改repo_doctor/js_ts.py；新增tests/test_js_ts_dialects.py中的错误合同。
**Interfaces:** 既有extract(source, *, file, language)->dict；错误返回结构不变，symbols/imports/exports/calls及辅助集合全部为空。

- [ ] 先加入最小失败合同（JS缺大括号、TS缺右括号），保留已有named ERROR合同。示例：

```python
source = ('export function target() { return 1; }\n'
          'export function broken() {\n  return target();\n')
data = extract(source, file='truncated.js', language='javascript')
self.assertIsNotNone(data['error'])
self.assertEqual(data['error']['line'], 3)
for key in ('symbols', 'esm_imports', 'esm_exports', 'calls', 'identifier_uses',
            'top_level_symbols', 'unsafe_bindings'):
    self.assertEqual(data[key], [])
self.assertEqual(data['class_header_spans'], {})
```

- [ ] 运行红例并存E/local-verification/p2-red.log：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/kisara/.local/share/ai-repo-doctor/releases/v0.7.0/candidate/venvs/js/bin/python -B -m unittest tests.test_js_ts_dialects -v
```

- [ ] 仅错误检测遍历完整children，valid AST提取仍用named_children。实现前先检查root.has_error；错误找最早byte位置，使用现有span，不访问Point.column。
- [ ] 同命令转绿；增加坏文件作为import目标的index合同，确认无symbols/imports/calls及指向坏目标的边。
- [ ] 另存新研究attempt，以工作树代码复核原130文件；所有has_error文件extract.error非空且证据为空。不要覆盖原baseline研究文件。
- [ ] 主代理审diff、记录根因/红绿/真实样本变化，提交fix。

## P3：前端方言、选择与有界证据（D2/D3）

**Files:** repo_doctor/languages.py、js_ts.py、index.py、esm.py；tests/test_languages.py、test_js_ts_dialects.py、test_esm.py、test_context.py、test_repo_map.py。
**Interfaces:** 新parse_tree(source, language, *, tsx=False)与private _parser(language, *, tsx=False)；extract原签名不变。JS/TS analysis.source_extensions为dict[str,list[str]]，默认Python无该键。

- [ ] 写失败合同：language_for_path('a.jsx')=='javascript'、('a.tsx')=='typescript'；其他未知扩展保持None。
- [ ] 写TSX/JSX完整流程合同，fixture内容如下（每个文件均UTF-8）：

```python
files = {
 'helper.ts': 'export function value() { return 1; }\n',
 'Card.tsx': 'export function Card() { return <div />; }\n',
 'App.tsx': "import {value} from './helper.js';\nimport {Card} from './Card';\n"
            'export function App() { return <Card onClick={() => value()}>{value()}</Card>; }\n',
 'Legacy.jsx': 'export const Legacy = () => <section>中文😀</section>;\n',
}
```

要求App→helper::value只返回实际直接调用；Card JSX标签、event callback无函数边；App到Card有文件依赖；context/impact含真实import来源；源码行不超预算；map/SVG只含实际边。

- [ ] .ts尖括号类型断言和generic箭头仍按TS grammar通过；.tsx用TSX grammar且错误整文件排除；BOM/CRLF/Unicode位置与源码引文一致；默认Python不加载前端或native extra。
- [ ] 红例记录后修改映射；_parser缓存三个有效variant且拒绝JS+tsx；extract按后缀选择，parse_js_ts_file用对应parser检查依赖。
- [ ] index不再把已支持jsx/tsx标unsupported；未选择语言仍不读取。JS/TS metadata加入当前选择语言source_extensions。
- [ ] ESM TypeScript.js替换来源扩展扩大为.ts/.tsx；有限候选并集、类型-only、namespace、重写、歧义、parse失败/ignore/链接拒绝均保持。
- [ ] JSX实际节点加入jsx-render limitation（物理行，说明标签/事件引用不是运行调用）。遍历实际表达式，不把标签或props引用转为CallSite。
- [ ] 更新原合同的旧unsupported JSX/TSX断言，保留其他原边界；不能为适配新功能删除负例要求，需用未选择语言或其他不支持扩展维持验证。
- [ ] 运行受影响合同后审查并提交feat；只有未覆盖的具体风险才增加测试。

## P4：真实调查与公开使用闭环（D3/D4/D5）

**Files:** 新evaluation/js-ts-release-completion/cases.json及README.md；tools/validate_js_ts_install.py；README.md、docs/JS_TS_SUPPORT.md、resources/skill/SKILL.md；E/product-validation/。

- [ ] 从research/frontend-parse-files.json冻结三个来源：jenkins-infra/plugin-site(JSX)、emircanagac/voxpery(TSX)、roseforljh/qoneagent(TSX)。固定commit/tree、source SHA、组件符号行段和直接helper调用来源；主代理手工核对原文后写cases，不从工具结果反填正确答案。
- [ ] JSX案例至少搜索具名组件并核对文件依赖、context引文及无虚构标签调用。TSX两个案例至少一条安全helper直接调用含via_esm_import/impact逐跳证据。不能把包调用、匿名callback或标签当作函数调用题。
- [ ] 每仓库执行overview→symbols→context(120行)→impact(depth2)→map。真实ID取symbols输出，复制全部命令、stdout/stderr/exitcode与输出hash；前后核对目标commit、Git状态和来源字节不变。
- [ ] 使用既有0.7.0独立CLI作三个同题baseline，记录不支持范围；新增结果按实际证据回答，拒绝文件或未知保持unknown。
- [ ] 在安装验证器新增独立frontend夹具，与旧case不混用：前端overview/symbols/context/impact/map、MISSING坏文件隔离、JSX标签/props/callback无假边、两种语言选择与无extra错误提示。
- [ ] 验证器每条命令显式expected exit；最终计数从回执读取。不能继续写旧23或要求负例exit0。
- [ ] 文档支持矩阵、README五命令教程、packaged Skill同步后缀、源码证据及JSX限制；用户安装Skill不改，新的包内Skill另行导出到交付目录并比对。
- [ ] 运行一次完整本地unit及受影响合同无skip；运行既有map viewer/search DOM检查，验证新前端地图四份产物和上限。viewer未变不要求重复无关Chrome排障。
- [ ] 主代理检查实际diff与真实题答案，处理具体发现，不把单元绿色当作语义正确替代。提交集成代码。

## P5：候选安装和精确CI（D4）

**Files:** 三处版本repo_doctor/_version.py、tools/validate_js_ts_install.py、tools/validate_release_install.py；E/candidate/attempt-001、E/ci。

- [ ] 设0.8.0a1并冻结干净SHA；用git archive打包源码，pip wheel --no-deps，仅构建本项目。
- [ ] 独立base和js两个venv，base --no-index安装wheel，js安装wheel[js]；verify import来自site-packages和三个固定backend版本。
- [ ] 从wheel枚举全部repo_doctor runtime文件，与archive/source及两个安装runtime逐文件比对；实际数量从包读取，记录版本与wheel SHA。
- [ ] 独立安装执行validate_js_ts_install.py的base/js两模式以及validate_release_install.py完整Python生命周期。正负例按expected code计数；新frontend夹具必须能拒绝旧0.7语义。
- [ ] 使用安装CLI再跑P4三个真实调查，源码环境不能替代。输出重复字段差异逐项核对；不得用结果“类似”代替证据一致。
- [ ] 创建PR附到任务，必须精确候选SHA七项CI：Python3.11/3.12/3.13、JS对应三项、Offline map interaction and SVG。
- [ ] 冻结来源之后若生产行为变化，重新建attempt并重跑受影响门槛；不能继承旧候选通过标签。

## P6：正式发布和独立部署（D4/D5）

**Files:** 正式0.8.0三处版本、README发行URL、支持矩阵、packaged Skill版本路径、docs/delivery/2026-10-08-v0.8.0-js-ts-completion.md；R。

- [ ] 列清候选→正式runtime diff；准备正式版本后冻结提交，重新独立构建/安装/字节验证/真实题和精确提交CI。
- [ ] 主代理用精确head guard合并PR，核对merge tree与验收tree一致；正式wheel最终来源为merge SHA，七项CI必须对merge SHA绿色。
- [ ] 正式wheel源码、安装、version与SHA记录；写Chinese release-notes、SHA256SUMS和可读发布前报告，分别列功能、保守限制、真实调查、安装计数和回滚路径。
- [ ] 创建GitHub v0.8.0正式release，公开wheel与摘要文件。匿名下载并逐字节比对本机已验收wheel及所有安装runtime。不能用authenticated gh download代替公开下载验证。
- [ ] 本机R/candidate/venvs/js/bin/repo-doctor实际返回0.8.0；从该CLI导出Skill到R/skill-export，并核对与包内一致。新独立入口的五步命令及map路径写部署文档；全局0.5.3和用户Skill不切换。

## P7：完成审计（D1–D5）

**Files:** R/completion.json、delivery-report.md、preservation.json、deployment.json、graphflow-index.json；本清单完成状态。

- [ ] 对Goal逐项审计：P2修复有效、P3新覆盖、P4实际Codex调查与地图、P5/P6安装CI及公开发行都有来源证据。任何未知交付项保留pending，不改成功定义。
- [ ] 原manifest完整核对14文件/150789证据/65旧runtime/用户Skill；本轮补充manifest核对0.7.0的2426文件和8链接；mismatch必须0。源仓库commit/源码摘要保持。
- [ ] 更新清单实际完成状态、正式交付文档和中文最终报告，文档提交同步远端；发行tag保留精确已验收来源，不移动tag。
- [ ] GraphFlow增量刷新并保存回执；只有全部门槛满足才update_goal complete。否则保持active并继续处理实际缺口。

## 当前进度

P0–P1完成；研究、设计、gap review与实施清单已审查。P2–P7未开始；尚无0.8.0候选或新正式发行。0.7.0现有发行仍保持。
