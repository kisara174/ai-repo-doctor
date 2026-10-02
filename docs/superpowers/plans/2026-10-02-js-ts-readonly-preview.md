# JS/TS 只读调查预览详细执行清单

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 executing-plans 逐项执行；主代理承担判断、设计、debug 和验收。仅在符合用户 AGENTS 的条件下委派一个机械执行者，不把本计划整体交给 Luna。

**Goal:** 先证明 JS/TS 对真实 Codex 调查的收益，再按条件交付可选安装、独立部署的只读预览，保留 Python v0.5.2 稳定产品。

**Architecture:** 复用现有 RepoIndex、上下文预算、关系图和五个只读命令；Python 与 ESM 分开解析和解析关系，最后合并。新增解析器惰性加载，不引入常驻服务、自动发现插件或第二套图界面。

**Tech Stack:** Python >=3.11、既有 unittest/HTML/SVG；候选 Tree-sitter 0.26.0 + JavaScript grammar 0.25.0 + TypeScript grammar 0.23.2，先由 A2 核对安装与 ABI。

**Spec:** [JS/TS 只读调查预览规格](../specs/2026-10-02-js-ts-readonly-preview-design.md)。执行者必须先读规格；接口和限制以该文档为准。

**状态：** 2026-10-02 开始实施。A0 已完成并写入仓库外 baseline.json / receipts/A0.json；A1–A4、B1–B4 尚未完成。使用隔离 worktree 的 codex/js-ts-readonly-preview 分支，Mac 稳定版仍为 v0.5.2。

## Global Constraints

- Python >=3.11；默认运行依赖为空。
- 默认语言选择为 python；旧命令、旧 Python ID 和旧报告保持兼容。
- 新语言只接入 overview、symbols、context、impact、map 五个只读命令。
- 首期 JS/TS context 不支持 --snapshot-out；组合使用必须在写文件之前返回退出码 2，解释使用 --json。Python 快照和 findings 流程保留。
- 不扩展 JS/TS report/findings、云端诊断、回归执行、自动补丁、跨语言调用、框架注册、缓存或图布局。
- 样本只静态阅读；不运行其代码，不安装其依赖，不调用其 package scripts。
- 测试只对应实际数据契约、未知边界、兼容或交付风险；A 阶段不重复现有 429 项完整测试。
- Mac 稳定入口、Skill、Key、旧报告、发行包和四份用户文档改动保留。
- 主代理负责选择、设计、debug、独立参考答案、审查和发布；执行者不能自行扩大范围。

## 0. 执行方式与终点

依赖顺序：

~~~text
A0 基线/范围 → A1 样本/参考 → A2 解析选择 → A3 隔离原型 → A4 去留
                                                            |
                        no-go → 中文结论，结束探索 ←──────────+
                                                            |
                        go → B1 接入 → B2 最小调用 → B3 图 → B4 交付
~~~

A4 是主代理依据实际证据作出的继续条件，不是自动勾选，也不要求用户为已授权的常规步骤重复确认。缺少证据就保持 B 阶段未开始；发现规格之外的新需求，由主代理形成具体方案，不能由执行模型猜测。

完成终点只有两种：

1. **探索结束：** A4 no-go，六题和失败原因归档，稳定版保留，B 阶段不启动。
2. **预览交付：** A4 go，B1–B4 成立，固定来源的 0.6.0a1 预览包、独立 Mac 环境、中文报告和地图可实际使用；稳定入口仍为 0.5.2。

### 0.1 项目/环境约定

实施时先复用适合的干净执行 worktree，从最新默认分支开始；分支使用 codex/js-ts-readonly-preview。本轮编写文档不切分支。

~~~sh
PROJECT='/Users/kisara/Documents/ChatGPT/AI Repo Doctor'
JST_EVIDENCE='/Users/kisara/.local/share/ai-repo-doctor/evaluations/js-ts-readonly-preview'
JST_STABLE_CLI='/Users/kisara/.local/bin/repo-doctor'
~~~

JST_EVIDENCE 首次执行时创建，重复执行读取已有 receipts，从首个未完成步骤继续。已有原始输出不覆盖，重试创建 attempt-002 等新子目录。不要把临时依赖环境放进目标仓库。

A2 解析环境位于 JST_EVIDENCE/parser-venv；它只用于实验。B4 预览环境位于 ~/.local/share/ai-repo-doctor/previews/v0.6.0a1/venv。执行脚本记录实际工作目录和命令，不凭别名猜调用到哪个 CLI。

### 0.2 文件职责与允许范围

| 文件/目录 | 职责 | 首次阶段 |
| --- | --- | --- |
| 本计划、对应规格 | 跟踪任务与范围；改约束必须注明依据 | A0 |
| docs/evaluations/2026-10-02-js-ts-exploration.md | 探索的真实执行日期、六题、方案与 go/no-go | A1 |
| tools/js_ts_trial.py | 只读证据核对、受限命令记录和去留校验；不是产品命令 | A1 |
| experiments/js_ts/spike.py | 可丢弃原型，独立 CLI 和 AST walker | A3 |
| tests/fixtures/js_ts_contract/ | 本计划规定的静态源码夹具 | A3 |
| tests/test_js_ts_spike.py | 原型输出与夹具行证据 | A3 |
| repo_doctor/languages.py | 语言选择、路径分类、分析范围元数据 | B1 |
| repo_doctor/js_ts.py | 可选后端、AST 提取，不运行目标代码 | B1 |
| repo_doctor/esm.py | 本地 ESM 文件与有限调用关系 | B1/B2 |
| repo_doctor/model.py | 带默认值的新记录；原 Python 记录保留 | B1 |
| repo_doctor/index.py | 各语言子索引、歧义与关系合并 | B1 |
| repo_doctor/source.py、repo_doctor/case.py | 读取编码与选择语言的源码指纹；不改 case schema | B1 |
| repo_doctor/context.py | 新语言类头、导入跨度与统一预算；反向影响复用 | B1/B2 |
| repo_doctor/agent_tools.py、repo_doctor/cli.py | 五个命令、正确统计、范围与错误提示 | B1 |
| repo_doctor/repo_map.py、repo_doctor/resources/map/viewer.js | analyzed/语言元数据与旧地图回退 | B3 |
| tests/test_languages.py、tests/test_js_ts.py、tests/test_esm.py | 语言、解析、ESM 契约 | B1/B2 |
| tests/test_index.py、tests/test_context.py、tests/test_cli.py、tests/test_agent_tools.py | 混合索引、预算、CLI、错误行为 | B1 |
| tests/test_repo_map.py、tests/test_map_viewer.js、tests/test_map_dom.js | 投影与实际 DOM 行为 | B3 |
| tools/validate_js_ts_install.py | stdlib 独立安装验收，不从 worktree 导入 | B4 |
| pyproject.toml | 可选 js extra，默认 dependencies 保留 [] | B1/B4 |
| .github/workflows/ci.yml | 新增 js 安装门槛，保留原 Python/地图门槛 | B4 |
| README.md、docs/CODEX_AND_MAP.md、docs/PRODUCT_GUIDE.md | 完整用户路径与已实现范围 | B4 |
| repo_doctor/resources/skill/SKILL.md | 随预览包导出的 Skill；不改用户已安装 Skill | B4 |
| repo_doctor/_version.py、docs/delivery/2026-10-02-js-ts-preview.md | 条件预览版本与真实交付证据 | B4 |

未列文件不能顺手改。不要修改 repo_doctor/graph.py / repo_doctor/semantics.py 的 Python 解析规则；在 repo_doctor/index.py 通过 Python 子索引隔离它们。需要超出此表时，由主代理解释缺口并更新计划后再做。

### 0.3 每项任务的收尾记录

完成一节前，主代理检查实际 diff、该节验证退出码、产物路径与未覆盖边界；只在证据成立后勾选。A1/A3/B1/B2/B3 分别保存一个聚焦提交，A2/A4 只提交方案与真实记录，B4 记录最终来源与交付；不把虚拟环境、克隆样本或 Key 纳入 Git。stage 名称作为提交主题，例如 feat: add optional JS TS source indexing。暂存前按本节文件表逐个选择路径，不使用 git add .。

证据保存在 JST_EVIDENCE/receipts/A0.json 至 B4.json，字段固定为 stage、status、source_sha、changed_paths、validation（argv/cwd/exit_code/evidence_path）、artifacts、limits、recorded_at。status 只允许 completed、blocked、no-go；已有收据保留，重试写新的 attempt 子目录。没有执行命令的记录不得写 exit_code=0。A4 no-go 时 B1–B4 没有 completed 收据。

## A0｜冻结基线和支持范围

**责任：** 主代理。**允许改动：** 本计划/规格的执行记录，JST_EVIDENCE/baseline.json。**禁止：** 产品源码、依赖、部署与用户配置。

**输入：** 当前 worktree、稳定安装、部署收据、规格。
**输出契约：** baseline.json 包含 base_commit、branch、CLI 路径/版本、tag 源码、wheel SHA256、用户四文档/Skill/旧报告哈希、允许范围、运行环境路径。

- [x] 调用 GraphFlow context，读取当前状态和规格；确认没有另一任务修改同一执行文件。
- [x] 读取 git status 和默认分支 HEAD。已有改动按归属保留，不能 reset/clean。
- [x] 在仓库外执行稳定 CLI --version，记录真实 stdout 和退出码。
- [x] 读取 deployment-v0.5.2.json 与 build-receipt.json，核对 tag、wheel 和 31 个运行文件；不要重新安装或跑完整套件。
- [x] 保存四份用户文档、Skill 和旧报告的当前 SHA256；不读 Key 值。
- [x] 把规格的支持范围保存到 baseline.json；默认 Python、新语言仅五个只读命令、JS 快照禁用三项写为断言。
- [x] 验证基线，更新本节完成状态与 receipt 路径。

实际核对命令：

~~~sh
git status --short --branch
git rev-parse HEAD
git rev-parse 'v0.5.2^{commit}'
/Users/kisara/.local/bin/repo-doctor --version
~~~

独立核对代码：

~~~python
import hashlib, json
from pathlib import Path

state = Path("/Users/kisara/.local/share/ai-repo-doctor")
build = json.loads((state / "releases/v0.5.2/build-receipt.json").read_text())
assert build["source_sha"] == "ada493946525329d3bd0e842eaf94b7a8c025fca"
assert hashlib.sha256(Path(build["wheel"]).read_bytes()).hexdigest() == build["wheel_sha256"]
assert len(build["runtime_hashes"]) == 31
installed_roots = list((state / "venv/lib").glob("python*/site-packages"))
assert len(installed_roots) == 1
for relative, expected in build["runtime_hashes"].items():
    assert hashlib.sha256((installed_roots[0] / relative).read_bytes()).hexdigest() == expected, relative
~~~

**通过：** 正式来源与稳定安装一致，保留项有哈希，scope 冻结。
**停止：** CLI/tag/包不一致或未知本地改动；先由主代理处理，不能以新版本覆盖问题。

## A1｜固定两个样本、六题和独立参考

**责任：** 主代理。**允许改动：** tools/js_ts_trial.py、探索文档、JST_EVIDENCE。**禁止：** 产品源码、候选依赖安装、目标仓库执行。

**输入：** A0 基线；下表已核对的官方候选。
**输出：** sources.json、questions.json、oracle.json、baseline/ 原始命令/补读、探索文档初稿。

| 样本 | 提交 | 官方来源 | 查找起点 |
| --- | --- | --- | --- |
| np | 591e003bfc57371cfb8236694e8d784ae5d6fe5f | https://github.com/sindresorhus/np.git | package.json 的 bin / source/cli.js |
| ts-extras | 323908522c9f90f07f99378b43891da742f2319f | https://github.com/sindresorhus/ts-extras.git | package.json exports 与实际 source/index.ts 的区别 |

- [ ] 先写 questions.json，再下载这两个 commit；问题 J1/J2/J3 与 T1/T2/T3分别为入口到核心、选定函数关系/影响、图定位文件和局部关系。
- [ ] 使用 Git fetch 指定 SHA，不用执行时漂移的 main：

~~~sh
git -c core.hooksPath=/dev/null -c core.fsmonitor=false init "$JST_EVIDENCE/repos/np"
git -C "$JST_EVIDENCE/repos/np" remote add origin https://github.com/sindresorhus/np.git
git -c core.hooksPath=/dev/null -c core.fsmonitor=false -C "$JST_EVIDENCE/repos/np" fetch --depth 1 origin 591e003bfc57371cfb8236694e8d784ae5d6fe5f
git -C "$JST_EVIDENCE/repos/np" -c core.hooksPath=/dev/null checkout --detach FETCH_HEAD
git -c core.hooksPath=/dev/null -c core.fsmonitor=false init "$JST_EVIDENCE/repos/ts-extras"
git -C "$JST_EVIDENCE/repos/ts-extras" remote add origin https://github.com/sindresorhus/ts-extras.git
git -c core.hooksPath=/dev/null -c core.fsmonitor=false -C "$JST_EVIDENCE/repos/ts-extras" fetch --depth 1 origin 323908522c9f90f07f99378b43891da742f2319f
git -C "$JST_EVIDENCE/repos/ts-extras" -c core.hooksPath=/dev/null checkout --detach FETCH_HEAD
~~~

目录已存在则核对来源后复用，不重复 init/remote add，也不删除。禁止 submodule update、npm install、npm test、np CLI、TS 构建或发布。

- [ ] 针对两个本地根调用 GraphFlow context；仅按锚点或必要的有界源码补读选真实函数。
- [ ] 手工建立 oracle；每仓库至少 3 个关键符号、2 条本地文件依赖。正/负调用参考也保存，但 A3 不要求已经实现调用能力。
- [ ] 每条源码依据保存 file、start_line、end_line、quote、whole-file SHA256、固定 commit URL。oracle 由源文件建立，不能从原型输出反推。
- [ ] 区分 np 的命令入口文件与具体函数；区分 ts-extras 的源码与 distribution 输出，缺失构建文件不造边。
- [ ] 用稳定 CLI 做 overview/symbols 的兼容性记录；若没有返回 JS/TS ID，不猜一个 ID 去调用 context/impact。这两次命令不计入源码调查的效率基线；baseline_steps 只记录实际源文件搜索/補读。
- [ ] 六题分别记录 baseline_steps：每次实际命令或独立源码读取算一步，已有材料复用列出 references，不重复计数。不填估计的“人类耗时”。
- [ ] 编写单一辅助脚本 tools/js_ts_trial.py，冻结下节契约；不扩成通用评估平台。
- [ ] 校验 sources/oracle，更新探索文档的来源/未执行项。

辅助脚本子命令：

~~~text
python -m tools.js_ts_trial check-sources --evidence-root DIR
python -m tools.js_ts_trial check-oracle --evidence-root DIR
python -m tools.js_ts_trial check-fixtures --root tests/fixtures/js_ts_contract
python -m tools.js_ts_trial record --evidence-root DIR --question J1 --producer stable --out NEW_JSON -- COMMAND ARGS
python -m tools.js_ts_trial check-trial --evidence-root DIR
python -m tools.js_ts_trial check-gate --evidence-root DIR
~~~

record 只允许 baseline.json 配置的稳定 CLI，或 experiments.js_ts.spike、后续预览 CLI的五个只读命令；shell=False，移除 PYTHONPATH/DeepSeek Key，30 秒超时，stdout/stderr 各 1 MiB 上限。禁止任意命令、目标 scripts、--pre、npm/node 目标执行。用 x 模式写新输出；超时/截断单独记录，不算成功。出图 cwd、输出必须在证据新目录。记录 argv/cwd/finished_at/duration_seconds/exit_code/stdout/stderr/truncated，不误把完成时间叫 started_at。

check-trial 只验证材料的真实性与结构：answered/bounded 条目必须指向实际命令和源码；blocked 条目必须保存阻断原因与已有证据，不得填虚拟成功命令。完整且如实的 blocked 记录可通过结构检查，仍不能通过 go 门槛。check-gate 对 go 强制检查五项都为真；对 no-go 检查至少一项为假、原因和阻断证据齐全，不要求伪造未执行的原型结果。

oracle.json 最小条目：

~~~json
{
  "schema_version": 1,
  "questions": [{
    "id": "J1",
    "repo": "np",
    "baseline_steps": [],
    "reference_symbols": [],
    "reference_edges": [],
    "negative_edges": [],
    "source_evidence": []
  }]
}
~~~

这段描述字段形态，不是可提交的空参考答案：check-oracle 必须拒绝题目缺少基线/符号/源码依据。J1–T3 条目 ID 固定；实际文件/行/符号由主代理从固定源码填写并逐条核对。

**独立验证：** check-sources 核对 git HEAD 和工作区未改；check-oracle 用 git show SHA:path 逐条核对引文/哈希，确认六题和最低参考数。
**停止：** 提交不可获得、样本超出范围或参考答案依赖目标运行；主代理解释并更新样本记录，不悄悄换仓库。

## A2｜核对候选安装、API 与范围

**责任：** 主代理；依赖、外部事实、兼容判断不委派。
**允许改动：** JST_EVIDENCE/parser-venv、dependency-check.json、探索文档的方案记录。
**禁止：** pyproject.toml、全局 Python/Node、稳定 venv。

- [ ] 读取规格的官方资料，记录 TypeScript Compiler API 与 Tree-sitter 的运行环境、符号定位和语义解析区别。
- [ ] 创建单独环境，优先只安装已核对的 binary wheels：

~~~sh
python3 -m venv "$JST_EVIDENCE/parser-venv"
"$JST_EVIDENCE/parser-venv/bin/python" -m pip install --only-binary=:all: tree-sitter==0.26.0 tree-sitter-javascript==0.25.0 tree-sitter-typescript==0.23.2
~~~

- [ ] 保存 Python 路径/版本、平台架构、pip 安装退出码、三包实际版本与分发哈希，不声称不同版本号必然 ABI 兼容。
- [ ] 使用下段代码，仅解析本计划自写字符串：

~~~python
from tree_sitter import Language, Parser
import tree_sitter_javascript as js
import tree_sitter_typescript as ts

for grammar, source in [
    (js.language(), b"export function answer() { return 42; }\n"),
    (ts.language_typescript(), b"export function answer(): number { return 42; }\n"),
]:
    tree = Parser(Language(grammar)).parse(source)
    assert tree.root_node.type == "program"
    assert not tree.root_node.has_error
    assert tree.root_node.start_point.row == 0
~~~

- [ ] 再解析含中文/emoji、CRLF、BOM、无末尾换行和明显语法错误的自写字符串；核对字节列与人类行号不混用。
- [ ] 记录三个候选包在当前 Mac 的结果。选择 Tree-sitter 的条件是能够满足有限源码提取，不要求类型检查。
- [ ] 写 dependency-check.json 的 status=passed/failed，chosen_backend、versions、checks、limits 和 source_urls。写实际退出码，不能仅引用 PyPI wheel 列表称安装通过。

**通过：** 三包可安装/API 可用，行号和错误行为有证据；不需 Node 来运行分析。
**停止：** 无匹配 wheel、ABI/API 不合、编码/行号错误。由主代理提出具体修订；不默默换包、源码编译、安装 Node 或做多轮框架竞赛。若现有约束无法满足，保留 A1 的六题，把原型步骤标 blocked，直接进入 A4 写技术 no-go；A3 不得勾为完成，B 阶段不启动。

## A3｜隔离原型与六题试验

**责任：** 主代理负责 walker、接口与补读；固定夹具复制可按附件委派。
**允许改动：** experiments/js_ts/spike.py、tests/test_js_ts_spike.py、tests/fixtures/js_ts_contract/、tools/js_ts_trial.py 的检查实现、探索文档与证据目录。
**禁止：** repo_doctor 源码、产品 pyproject、CI、版本、稳定安装。

### A3.1 原型接口与 AST 提取

- [ ] 先创建附件 1 的固定夹具和独立行证据；check-fixtures 通过后再写 parser。
- [ ] 在 tests/test_js_ts_spike.py 写下面的契约测试，先确认因不存在 extract 而失败：

~~~python
from pathlib import Path
import unittest
from experiments.js_ts.spike import extract

class SpikeContractTests(unittest.TestCase):
    def test_named_function_and_arrow_have_exact_spans(self):
        source = Path("tests/fixtures/js_ts_contract/core.js").read_text()
        data = extract(source, file="core.js", language="javascript")
        by_id = {s["id"]: s for s in data["symbols"]}
        self.assertEqual((by_id["core.js::add"]["start_line"], by_id["core.js::add"]["end_line"]), (1, 3))
        self.assertEqual(by_id["core.js::twice"]["start_line"], 4)
        self.assertIsNone(data["error"])
~~~

- [ ] 实现 extract(source: str, *, file: str, language: str) -> dict；输出 symbols、esm_imports、esm_exports、calls、identifier_uses、unsafe_bindings、class_header_spans、limits、error。字段以规格的记录契约为准。
- [ ] 用如下边界代码加载后端、编码与计算行终点，不保存整棵 tree：

~~~python
def parse_tree(source, language):
    from tree_sitter import Language, Parser
    if language == "javascript":
        import tree_sitter_javascript as grammar
        parser = Parser(Language(grammar.language()))
    elif language == "typescript":
        import tree_sitter_typescript as grammar
        parser = Parser(Language(grammar.language_typescript()))
    else:
        raise ValueError("spike supports javascript/typescript only")
    raw = source.encode("utf-8")
    return raw, parser.parse(raw)

def span(node):
    start = node.start_point.row + 1
    end = node.end_point.row + (1 if node.end_point.column else 0)
    return start, max(start, end)
~~~

- [ ] walker 按节点类型处理：export_statement、function_declaration、generator_function_declaration、lexical_declaration 中 const 的箭头/函数表达式、class_declaration、method_definition、TS function_signature、import_statement、export_clause、call_expression。
- [ ] 通过 child_by_field_name / named_children 取名称、body、parameters、source；只根据真实 AST 节点生成记录，不用正则猜函数边界。
- [ ] 具名嵌套维护 parent；没有明确名称的普通回调不生成假符号，也不把其调用归到外层函数。匿名默认导出用 <default>。
- [ ] 遍历最早 ERROR/missing；有错误则返回 error 和文件行，symbols/imports/calls 清空，禁止“错误前看着可用”的部分图。
- [ ] 提取参数、局部声明、catch/解构绑定和赋值/更新涉及的名称；无法识别的绑定形态限制整个相关调用范围。先不解析 calls，只保存调用点和限制。
- [ ] TS 重载签名与唯一实现归并；声明-only 与重复具体实现不当成唯一可调用目标。
- [ ] 通过以下验证，不跑全项目套件：

~~~sh
python -m tools.js_ts_trial check-fixtures --root tests/fixtures/js_ts_contract
"$JST_EVIDENCE/parser-venv/bin/python" -m unittest tests.test_js_ts_spike -v
~~~

### A3.2 原型只读命令

- [ ] 实现 python -m experiments.js_ts.spike 的 overview/symbols/context/impact/map；使用 --languages javascript,typescript 参数，输出与正式接口的公共字段兼容。
- [ ] overview 有限统计与样例；symbols 搜索真实 ID；context target-first 与显式 includes，行预算至多 120。
- [ ] ESM 本地文件依赖按规格唯一路径规则提取；原型 impact 的普通调用能力明确 not-supported，空列表必须同时给限制说明，不宣称无影响。
- [ ] map 复用现有 render_html/render_svg 和数据结构，实验适配 analyzed / python 字段，不改正式 viewer 文件。原型对视图筛选的临时适配必须标实验，不算 B3 完成。
- [ ] 保存每題的实际 overview/symbols/context/impact 命令；context/impact 用本轮 symbols 返回 ID。图问题再生成总览/聚焦新目录。
- [ ] 记录补读、复用、实际耗时、源码/图缺口。原型未解析的关系仍由 Codex 补读，不写回图边。
- [ ] 对照 oracle 核对选定符号与文件关系；可追溯输出、限制和参考答案均归档。
- [ ] check-trial 验证全部实际命令与源码/图来源；写六题结果表。

执行形式：

~~~sh
"$JST_EVIDENCE/parser-venv/bin/python" -m experiments.js_ts.spike overview "$JST_EVIDENCE/repos/np" --languages javascript --json
"$JST_EVIDENCE/parser-venv/bin/python" -m experiments.js_ts.spike symbols "$JST_EVIDENCE/repos/np" --languages javascript --query main --json
~~~

main 是搜索词，不是假定存在的 ID；不存在时按真实 candidates 和 A1 参考符号搜索。上下文/影响 argv 写入实际返回 ID，不能照抄虚构符号。

**通过：** 夹具范围、源码行、六题输出与补读均核对；不要求已经实现 calls。
**停止：** 假符号/错行、忽略语法错误、未知边伪装确定关系、原型必须更改稳定包。主代理一次针对性纠正后重新验证；更广缺陷重新规划。

## A4｜按收益作 go / no-go

**责任：** 主代理。**允许改动：** 探索文档、gate.json、计划状态。**禁止：** 为了得到 go 修改 oracle、弱化负例或先做 B。

- [ ] 每题填写 status=answered/bounded/blocked、baseline_steps、trial_steps、supplement_reads、reused_records、source_evidence、command_durations、remaining_limits。
- [ ] 用同一问题与源码范围比较步骤：基线只做源码调查，试验使用原型加补读；两边真正执行并留记录。差值是观察，不能外推人类效率。
- [ ] 逐项核对规格 §7 的五项 gate：
  1. 六题记录齐全；支持范围内至少 4 题回答，每仓库至少 2 题；
  2. 选定符号/行/引文与正关系正确，负例无造边；
  3. 每仓库至少 1 题少一次定位/补读动作；
  4. 实际命令都在记录机器上 30 秒内返回，无截断当成功；
  5. 隔离安装可用，无 Node 分析运行时，无目标执行和稳定目录变更。
- [ ] gate.json 保存 schema_version=1、decision=go/no-go、每项 met 布尔值、evidence_paths、recorded_at、reason、actor=codex。
- [ ] 执行 check-gate；脚本只能核对材料/数值一致性，不能替主代理判断有效调查收益。
- [ ] no-go 时写实际原因和最小可能继续点，A阶段结束，B仍未开始。
- [ ] 若 A2/A3 因技术约束无法完成，六题明确列出未执行步骤和阻断原因；A4 用失败的依赖/原型证据结束探索，不填编造的试验时间或命令。
- [ ] go 时引用此 receipt，并冻结 B 阶段允许文件、候选版本与依赖；不扩展语法清单。

~~~sh
python -m tools.js_ts_trial check-trial --evidence-root "$JST_EVIDENCE"
python -m tools.js_ts_trial check-gate --evidence-root "$JST_EVIDENCE"
~~~

**通过：** decision=go 且五项真实成立；否则是已完成的 no-go 探索。
**禁止：** 以 AST 能解析、未解析数量下降或测试数量增加代替收益。

## B1｜正式接入五个只读命令

**前置：** A4 go。**责任：** 主代理。**范围：** 文件表中 B1 所列文件与对应聚焦测试。
**输出接口：** 规格 §6 的 typed records / build_index / parse_js_ts_file / resolve_esm_graph、五个 --languages 输出。

### B1.1 语言、读取和可选依赖

- [ ] 先写 tests/test_languages.py 的路径/CSV断言：

~~~python
from repo_doctor.languages import language_for_path, normalize_languages
assert normalize_languages("typescript,python,javascript,python") == ("python", "javascript", "typescript")
assert language_for_path("src/main.mjs") == "javascript"
assert language_for_path("src/main.ts") == "typescript"
assert language_for_path("src/main.d.ts") is None
for value in ["", "python,", "go", "auto", "python,,typescript"]:
    try:
        normalize_languages(value)
    except ValueError:
        pass
    else:
        raise AssertionError(value)
~~~

- [ ] 实现 languages.py 三个规格接口；不引入用户配置/插件注册。
- [ ] 在 model.py 加带默认值的规格记录，保留原 FileRecord/Symbol/ImportRef/CallEdge 字段。已有 RepoIndex(root, scan_mode, root_identity) 仍能构造。
- [ ] read_source 只添加 keyword-only language 默认 python。使用相同安全 FD 打开；JS/TS decode utf-8-sig，Python保留 tokenize encoding-cookie。
- [ ] source_fingerprint 取 index.file_languages.get(path, "python") 传读取语言；纯 Python digest 顺序/字节不变。
- [ ] pyproject 增加下段，仅 A2 验证的版本：

~~~toml
[project.optional-dependencies]
js = [
  "tree-sitter==0.26.0",
  "tree-sitter-javascript==0.25.0",
  "tree-sitter-typescript==0.23.2",
]
~~~

- [ ] 缺包/不兼容转换为清楚的 ValueError 安装提示；仅导入 JS backend 时加载原生包，Python-only 不检查它。
- [ ] 聚焦验证：

~~~sh
python -m unittest tests.test_languages -v
python -m unittest tests.test_parser tests.test_context -q
~~~

新编码/安全用例放 tests/test_languages.py，含 BOM/CRLF/中文/非法 UTF8，以及沿用已有源读取边界；不要为无关 Python 行为加新测试。

### B1.2 提取与索引合并

- [ ] 将 A3 已验证 walker 迁到 js_ts.py，转换成 JSParsedFile；实验工具改为调用正式后端，不保留两份 parser。
- [ ] 添加 parse_js_ts_file 的 exact-span、重载、歧义、错误、异步和绑定负例测试；同时核对 public IDs来自文件/qualname。
- [ ] build_index 添加 keyword-only languages，先 normalize/validate，再用 discover_files 选择现有忽略/安全范围内的文件。
- [ ] 分别构造 Python 子索引与 JS/TS 元数据。Python 的 resolve_graph/resolve_semantic_edges 只接收 .py 子索引，避免 m.js、m.ts 与 m.py 的点号模块名冲突。
- [ ] 只对 Python保留已有 overload/Click/module-instance 规则；JS/TS 歧义与唯一实现按规格处理。
- [ ] ESM resolver 此阶段使用 resolve_calls=False，只产生有依据的本地文件 ImportEdge与原始导出数据；能力 metadata 不含 calls。
- [ ] 聚合子索引的原记录/边，排序去重；file_languages 只标真实选择的实现文件。
- [ ] 将下面代码放进 tests/test_index.py 的 unittest 测试方法。它自己建立混合目录、补上 Python 文件，并验证两个方向都没有跨语言调用：

~~~python
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from repo_doctor.case import source_fingerprint
from repo_doctor.index import build_index

with TemporaryDirectory() as temp:
    root = Path(temp) / "repo"
    shutil.copytree(Path("tests/fixtures/js_ts_contract"), root)
    (root / "app.py").write_text("def entry():\n    return 42\n", encoding="utf-8")
    idx = build_index(root, languages=("python", "javascript", "typescript"))
    assert {"app.py::entry", "core.js::add", "core.ts::inc"} <= set(idx.symbols)
    assert all(
        idx.file_languages[idx.symbols[e.caller].file]
        == idx.file_languages[idx.symbols[e.callee].file]
        for e in idx.call_edges
    )
    before = source_fingerprint(idx)
    python_before = source_fingerprint(build_index(root))
    (root / "core.ts").write_text("export function inc(n: number) { return n + 2; }\n", encoding="utf-8")
    assert source_fingerprint(build_index(root, languages=("python", "javascript", "typescript"))) != before
    assert source_fingerprint(build_index(root)) == python_before
~~~

仅修改 TemporaryDirectory 中的副本；不能指真实样本或用户仓库。

~~~sh
"$JST_EVIDENCE/parser-venv/bin/python" -m unittest tests.test_js_ts tests.test_esm tests.test_index -v
~~~

### B1.3 上下文、命令和范围

- [ ] context 的 _source_lines 保留 root_identity 的既有位置参数，再传 language=index.file_languages.get(path, "python")；不能把 JS 编码交给 Python encoding-cookie 规则。
- [ ] context 中对 Python保留 AST 类头、基类、导入。JS/TS 使用 class_header_spans 和 identifier_uses / ESMImportRef 的整条 import start/end。
- [ ] 所有新 block 继续包含 symbol/relation/file/start_line/end_line/truncated/lines，import 的 relation 为 import_binding；计入同一个 max_lines。
- [ ] targets/includes 在自动邻居前；JS 构造类正文不自动抢占整个预算。未知引入可显式 include 真实 ID。
- [ ] 在五个 argparse 子命令添加 --languages CSV，默认 python；其他命令不添加这个参数。分析五命令的 build_index 调用传选择语言，旧 case/diagnose 路径继续默认。
- [ ] context 非纯 Python选择且有 --snapshot-out 时，索引/写文件前返回 2，说明只读预览限制；不生成无效快照。
- [ ] overview 的 python_files 严格计 .py；新增 analysis 字段通过 analysis_metadata 统一生成。context/impact/symbols/map 同步给范围。
- [ ] 保持旧 schema 与字段含义，仅附加 analysis。symbols matches 内原字段保留；语言可由 analysis 或 file path 获取。
- [ ] terminal 输出同时说明选择语言、各语言文件数、错误/限制；empty影响不写“无影响”。
- [ ] 首期 snapshot/case/findings 的 Python接口保持；不为了 JS context 改 report 或 findings schema。
- [ ] 在 tests/test_cli.py 增加缺后端、无效 CSV、显式混合语言、空 JS影响有界说明、快照禁用且不写文件的用例；在 context 测试核对 multiline import 和 5/120 行预算。

~~~sh
"$JST_EVIDENCE/parser-venv/bin/python" -m unittest tests.test_languages tests.test_js_ts tests.test_esm tests.test_index tests.test_context tests.test_cli tests.test_agent_tools -q
~~~

**B1完成：** 五命令能给真实 ID/上下文/范围；纯 Python 与旧快照保留，JS尚无普通调用承诺。
**停止：** 新字段污染 Python module解析、指纹忽略新语言、旧案例读取改变、假装支持 JS快照。主代理定位并修正，不扩 case 接口来绕过错误。

## B2｜有限普通调用与影响

**范围：** repo_doctor/esm.py、repo_doctor/js_ts.py、repo_doctor/index.py 中启用 resolve_calls 的调用点，tests/test_esm.py、tests/test_context.py；必要的 model.py 元数据须先解释并更新规格。
**输入：** B1 记录、附件正负例。**输出：** 已确认 CallEdge与同源 impact，capabilities 在通过后加 calls。

- [ ] 先写以下测试方法内的正/负断言，不先扩白名单。全套夹具中 core.js 与 core.ts 同时存在，consumer 的 ./core.js 必须保留歧义；TS 唯一候选正例在另一个只含两份源码的目录验证：

~~~python
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from repo_doctor.index import build_index

fixtures = Path("tests/fixtures/js_ts_contract")
with TemporaryDirectory() as temp:
    root = Path(temp) / "mixed"
    shutil.copytree(fixtures, root)
    idx = build_index(root, languages=("javascript", "typescript"))
    pairs = {(e.caller, e.callee) for e in idx.call_edges}
    assert ("core.js::twice", "core.js::add") in pairs
    assert ("consumer.ts::run", "core.ts::inc") not in pairs
    assert ("shadow.js::entry", "shadow.js::add") not in pairs
    assert not any(caller == "dynamic.js::entry" for caller, callee in pairs)
    assert not any(caller == "type_only.ts::bad" for caller, callee in pairs)
    unique = Path(temp) / "unique-ts"
    unique.mkdir()
    for name in ("core.ts", "consumer.ts"):
        shutil.copyfile(fixtures / name, unique / name)
    ts_index = build_index(unique, languages=("typescript",))
    assert ("consumer.ts::run", "core.ts::inc") in {
        (e.caller, e.callee) for e in ts_index.call_edges
    }
~~~

- [ ] type_only 单独在唯一候选目录追加该静态文件后验证没有 bad→inc，确保拒绝原因是类型导入，不能被双文件歧义掩盖。
- [ ] 在一个新受控目录写入以下文本为 rewritten.js，断言不存在 rewritten.js::entry→rewritten.js::target；赋值必须让候选绑定进入 unsafe_js_bindings，而不只处理参数遮蔽：

~~~javascript
export function target() { return 1; }
target = () => 2;
export function entry() { return target(); }
~~~

- [ ] 同文件仅解析顶层具名函数与 const 绑定函数；候选唯一、非歧义、未写入/更新、caller 参数/局部/捕获作用域没有遮蔽才连接。
- [ ] 嵌套/块级函数调用全部保留未知；无法确认绑定作用域的 caller不解析，不按最近同名猜。
- [ ] 直达 named/default ESM import：仅导出文件内一个具体实现，import非 type_only/namespace，alias 未被遮蔽，目标未改写。多跳 re-export未知。
- [ ] TS ./x.js 的候选包括实际 x.ts/x.tsx/x.d.ts/x.js/x.jsx；只有一个且为选中的 .ts/.js 实现时连接。双文件冲突和声明-only拒绝；保存 resolution_kind 和 specifier来源。
- [ ] 不解析 receiver.method、this、computed、新对象实例、外部包、dynamic import、CommonJS；保留理由。
- [ ] 没有合法 caller符号的顶层调用不编造 module 函数；保存限制供源码补读。
- [ ] 每条 CallEdge 的 line 来自 CallSite。import_binding 保留来源行，target文件与导出依据能在原始元数据重查。
- [ ] resolve_esm_graph 默认 resolve_calls=True。build_index 在 B2 通过后启用；不修改 Python graph.py。
- [ ] build_impact 沿统一的真实 call_edges 反向遍历，保留每跳 call_path_evidence；不把文件导入当作函数调用影响。
- [ ] 针对遮蔽/改写/类型导入/同名双文件运行负例；再复查六题原有输出，不增加新仓库。

~~~sh
"$JST_EVIDENCE/parser-venv/bin/python" -m unittest tests.test_esm tests.test_context -v
python -m tools.js_ts_trial check-trial --evidence-root "$JST_EVIDENCE"
~~~

**通过：** 选定正例有源位置，负例不造边，六题未变成错误的完整影响结论。
**停止：** 为命中样本扩展未审批框架、对象链或类型推断；先冻结现有结果，由主代理修正一项具体规则。

## B3｜同源混合关系图

**范围：** repo_doctor/repo_map.py、repo_doctor/resources/map/viewer.js、对应图测试。**不改：** 布局、缩放/拖动架构、图输出数量与目录覆写规则。

- [ ] 先在 tests/test_repo_map.py 的 TemporaryDirectory 复制附件 12 个文件，并用 UTF-8 写 app.py 的两行正文 "def entry():\n    return 42\n"；build_index 选择 python,javascript,typescript。图包含三个语言的文件/符号，只有同语言有依据边，无悬空 endpoint。consumer→core.ts 在此双文件目录必须保持未解析，不挪用 B2 唯一候选正例。
- [ ] 文件节点新增 language 与 analyzed；python仅表示被选中的 .py。analyzed 表示参与所选语言分析，解析错误另在 coverage中显示。
- [ ] Python/SVG 关系投影以 analyzed 为入口；HTML selector以同样规则回退旧数据：

~~~python
is_analyzed = node.get("analyzed", node.get("python", False))
~~~

~~~javascript
const isAnalyzedFile = n => n.kind === 'file' && (n.analyzed ?? n.python);
~~~

- [ ] 默认关系视图、文件聚焦和指定符号图使用相同节点筛选，不允许 SVG有 JS但 HTML没有。
- [ ] 保留 contains/import/call/reexport/command_registration 类型；缺来源就没有边，跨语言只展示组成。
- [ ] coverage.python_files仍只计 Python，新analysis列出所选语言与限制。图的人类说明仅增加语言/静态边界，不嵌入源码或调查正文。
- [ ] 生成八份 SVG（两仓库总览/聚焦各两份）及相应 HTML/JSON新目录；核对 fixed commit、指纹、选定节点/边、隐藏数。
- [ ] 使用现有 Node DOM 工具核对搜索 JS/TS ID、展开祖先、聚焦文件、SVG导出节点与页面一致。Node仅用于测试，不成为产品运行要求。
- [ ] 核对新 viewer能读取原 v0.5.2无 analyzed字段的地图。必要时创建旧结构的受控 fixture，不改真实旧 map。

~~~sh
"$JST_EVIDENCE/parser-venv/bin/python" -m unittest tests.test_repo_map -v
node tests/test_map_viewer.js
~~~

真实 DOM 使用既有 CI 的 jsdom@30.1.1 与 tests/test_map_dom.js；为混合数据补一个 fixture。缺少 DOM环境先记录未验证，再在现有 CI gate验证；不改用静态 JSON假称点击通过。若原生浏览器拒绝 file://，如实记录，不能绕过策略。

**通过：** HTML/SVG 同源，新语言可定位，旧图可读，隐藏数准确，图不呈现诊断。
**停止：** 顺手加布局/框架/可视化库或抹去未知关系；主代理缩回到已复现的选择/投影问题。

## B4｜预览包、独立安装和完整交付

**责任：** 主代理；依赖、CI、Git、发布、部署不委派。
**范围：** B4文件表、JST_EVIDENCE、独立 preview目录。**前置：** A4 go、B1–B3明确通过。

### B4.1 用户文档与安装 validator

- [ ] 编写 tools/validate_js_ts_install.py，stdlib-only，参数与原 validator对齐：

~~~text
python tools/validate_js_ts_install.py --mode base|js --python INSTALLED_PYTHON --cli INSTALLED_CLI --out NEW_EVIDENCE_DIR
~~~

- [ ] --mode 是 required argparse choices=("base", "js")；上面的 base|js 是二选一的参数契约，不能当 shell 管道执行。base 校验 Python 与显式 JS 缺依赖错误，js 校验完整新语言能力；每个环境写自己的新输出目录。
- [ ] validator 从包目录外运行，移除 PYTHONPATH / DeepSeek Key；确认 repo_doctor导入自该 installed Python 的 site-packages。
- [ ] 内嵌或复制附件夹具到 validator的新证据目录，只运行安装后五个静态命令，不执行夹具函数。
- [ ] 验证 symbols真实 ID、context行/预算、已确认 impact路径、metadata、map四文件和SVGXML；拒绝覆盖已有目录。
- [ ] base 模式验证显式 JS 缺包时退出2且有安装提示；js 模式验证非法语言/禁用JS snapshot均不产生文件，空影响有边界说明。不能在已安装 extra 的环境假称验证了缺包。
- [ ] 保存每条 argv/exit/timing、CLI/version、源码指纹与地图哈希；validator失败不得发版。
- [ ] README/CODEX_AND_MAP 增加一条完整路径：可选安装→显式 languages→选返回ID→context/impact→HTML/SVG。写清只读、不支持的语法与JS快照限制。
- [ ] 更新包内 Skill给出显式语言参数，指向独立 preview CLI；不自动覆盖用户 ~/.agents/skills/repo-doctor。
- [ ] 将实际状态写回 PRODUCT_GUIDE，旧云端/修复章节保持历史定位。

### B4.2 针对性验证与 CI

- [ ] 在无 extra环境验证普通 Python工作、不导入Tree-sitter、现有 Python安装validator通过。
- [ ] 新CI任务安装 .[js]，先明确断言三个候选包可导入；不允许整套JS测试因 skip变绿。
- [ ] JS聚焦测试覆盖Python 3.11–3.13；保留原Python与地图CI gate，不改GitHub权限和既有 action pin。
- [ ] extra的 missing依赖测试单独在base环境运行；编码/路径/负例与相应任务一起验证。
- [ ] B阶段代码冻结后仅跑一次完整现有项目套件；失败按第一个具体问题定位，不扩成无目标压力测试。

~~~sh
"$JST_EVIDENCE/parser-venv/bin/python" -m unittest discover -s tests -q
python -m compileall -q repo_doctor tools
~~~

同一提交的既有 CI还包含安装与DOM；本地没有相应运行环境时不能把CI推测作通过。

### B4.3 固定来源、干净安装与独立部署

- [ ] 验证完成后版本改为 0.6.0a1，更新version/文档；不修改正式 v0.5.2 tag。
- [ ] 主代理审查实际 diff、独立 oracle和正确/未知边界；创建PR时附加当前任务，等当前head CI通过再合并。最终合并提交也须有同 SHA 的成功 CI，不把旧 PR head 当交付来源。
- [ ] 保存 JST_EVIDENCE/release/source.json：source_sha、ci_source_sha、ci_url、pr_url、recorded_at 全部取真实合并/CI记录；前两者必须相等。禁止猜 source_sha 或复用稳定版来源。
- [ ] 从该 SHA 的干净 Git archive 构建 wheel，写 JST_EVIDENCE/release/build-receipt.json：source_sha、wheel（绝对路径）、wheel_sha256、requires_python、requires_dist、runtime_hashes、ci_url、build_argv、recorded_at。Requires-Python 为 >=3.11；Requires-Dist 只能是已验证的三个 extra 条件依赖，普通安装不能需要它们。
- [ ] 下面是构建与保存收据的实际调用结构。source.json 必须已由上一步写出，任何目录冲突停止核对，不覆盖旧构建：

~~~python
import hashlib, json, subprocess, sys, zipfile
from datetime import datetime, timezone
from email.parser import BytesParser
from pathlib import Path

project = Path("/Users/kisara/Documents/ChatGPT/AI Repo Doctor")
release = Path("/Users/kisara/.local/share/ai-repo-doctor/evaluations/js-ts-readonly-preview/release")
source = json.loads((release / "source.json").read_text())
assert source["source_sha"] == source["ci_source_sha"]
resolved = subprocess.check_output(
    ["git", "rev-parse", source["source_sha"] + "^{commit}"], cwd=project, text=True
).strip()
assert resolved == source["source_sha"]
archive = release / "source.tar"
assert not archive.exists()
checkout = release / "source"
checkout.mkdir()
subprocess.run(["git", "archive", "--format=tar", "--output", str(archive), resolved], cwd=project, check=True)
subprocess.run(["tar", "-xf", str(archive), "-C", str(checkout)], check=True)
wheels = release / "wheels"
wheels.mkdir()
argv = [sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheels), str(checkout)]
subprocess.run(argv, check=True)
candidates = list(wheels.glob("ai_repo_doctor-0.6.0a1-*.whl"))
assert len(candidates) == 1
wheel = candidates[0].resolve()
with zipfile.ZipFile(wheel) as package:
    metadata_names = [n for n in package.namelist() if n.endswith(".dist-info/METADATA")]
    assert len(metadata_names) == 1
    metadata = BytesParser().parsebytes(package.read(metadata_names[0]))
    assert metadata["Version"] == "0.6.0a1"
    assert metadata["Requires-Python"] == ">=3.11"
    dependencies = metadata.get_all("Requires-Dist", [])
    assert len(dependencies) == 3
    assert all('extra == "js"' in entry or "extra == 'js'" in entry for entry in dependencies)
    runtime_hashes = {
        name: hashlib.sha256(package.read(name)).hexdigest()
        for name in package.namelist()
        if name.startswith("repo_doctor/") and not name.endswith("/")
    }
receipt = {
    "source_sha": resolved, "wheel": str(wheel),
    "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
    "requires_python": metadata["Requires-Python"], "requires_dist": dependencies,
    "runtime_hashes": runtime_hashes, "ci_url": source["ci_url"],
    "build_argv": argv, "recorded_at": datetime.now(timezone.utc).isoformat(),
}
with (release / "build-receipt.json").open("x", encoding="utf-8") as stream:
    json.dump(receipt, stream, ensure_ascii=False, indent=2)
~~~

- [ ] 在两个干净环境安装同一wheel：base 不带js，preview带js；从仓库外运行validator。

~~~python
import hashlib, json, os, subprocess, sys, venv
from pathlib import Path

evidence = Path("/Users/kisara/.local/share/ai-repo-doctor/evaluations/js-ts-readonly-preview")
release = evidence / "release"
receipt = json.loads((release / "build-receipt.json").read_text())
wheel = Path(receipt["wheel"])
assert wheel.is_absolute() and wheel.is_file()
assert hashlib.sha256(wheel.read_bytes()).hexdigest() == receipt["wheel_sha256"]
scripts = release / "source/tools"
child_env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "DEEPSEEK_API_KEY"}}
for mode in ("base", "js"):
    directory = evidence / ("install-" + mode)
    assert not directory.exists()
    directory.mkdir()
    environment = directory / "venv"
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / "bin/python"
    cli = environment / "bin/repo-doctor"
    requirement = str(wheel) + ("[js]" if mode == "js" else "")
    subprocess.run([str(python), "-m", "pip", "install", requirement], cwd=directory, env=child_env, check=True)
    if mode == "base":
        subprocess.run([
            sys.executable, str(scripts / "validate_release_install.py"),
            "--python", str(python), "--cli", str(cli), "--out", str(directory / "python-validation"),
        ], cwd=directory, env=child_env, check=True)
    subprocess.run([
        sys.executable, str(scripts / "validate_js_ts_install.py"),
        "--mode", mode, "--python", str(python), "--cli", str(cli),
        "--out", str(directory / "js-ts-validation"),
    ], cwd=directory, env=child_env, check=True)
~~~

这两段是 B4 未来执行代码，本轮不运行。所有路径来自固定收据或本计划的证据目录；不依赖 worktree 的 dist 中恰好存在的包。validator 的输出和调用状态纳入 B4.json，不能只留下安装日志。
- [ ] 再用安装后的CLI复查两个固定仓库的六题，保存实际结果/补读/地图；不重跑目标代码。
- [ ] 若门槛全过，发布 v0.6.0a1为 prerelease；先核对同名远端tag/release不存在，不覆盖。附wheel、SHA256SUMS和中文范围说明。
- [ ] 匿名下载公开wheel核对hash，不能把gh上传成功当公开安装完成。
- [ ] 在 ~/.local/share/ai-repo-doctor/previews/v0.6.0a1/venv 安装已核对包；用绝对CLI验证一次真实四步与map，稳定入口仍是0.5.2。
- [ ] 新 preview receipt.json 写version/source/wheel/CI/六题/安装/地图/限制/回退方式；不改稳定 deployment.json。
- [ ] 预览Skill导出到 previews/v0.6.0a1/skill，给出Codex可复制指令；不自动注册或覆盖已安装Skill。
- [ ] 中文交付文档记录真实执行日期、支持层级、CLI路径、安装命令、六题、公开包与已知限制。
- [ ] 再核对A0保留项hash、稳定CLI版本与入口link。失败由主代理定位，不能以覆盖旧文件解决。

预览环境已经存在时先核对receipt；不覆盖未知安装。回退是继续使用原稳定入口，不删除旧环境/报告。

**完成：** 固定来源、公开包、base/extra干净安装、独立Mac预览和六题闭环均有实际证据。
**停止：** 同名发布冲突、CI与HEAD不一致、无extra安装受影响、缺包静默退回、稳定Skill/Key/入口变化；先处理具体风险。

## 附件 1｜固定静态夹具

以下文件在 A3创建，不在写清单时创建。文件内容全部 UTF-8，保留末尾换行。tests中的 root由 TemporaryDirectory建立后复制这些内容；不运行它们。

### core.js

~~~javascript
export function add(a, b) {
  return a + b;
}
export const twice = value => add(value, value);
export class Box {
  get() { return this.value; }
}
export default function main() {
  return twice(2);
}
~~~

### core.ts

~~~typescript
export function inc(value: number): number {
  return value + 1;
}
export function entry(value: number): number {
  return inc(value);
}
export function overloaded(value: string): string;
export function overloaded(value: number): number;
export function overloaded(value: string | number): string | number {
  return value;
}
export class Counter {
  next(value: number): number { return inc(value); }
}
~~~

### consumer.ts

~~~typescript
import {inc as step} from './core.js';
export function run() {
  return step(2);
}
~~~

### shadow.js

~~~javascript
function add(value) { return value + 1; }
export function entry(add) {
  return add(1);
}
~~~

### dynamic.js

~~~javascript
export function entry(obj) {
  return obj.run();
}
export function later(name) {
  return import(name);
}
~~~

### type_only.ts

~~~typescript
import type {inc} from './core.js';
export function bad() {
  return inc(1);
}
~~~

这个负例故意只有语法可解析、类型/运行时不合法。目标是证明不会把 type_only当value调用，不执行它，也不称它为合法TypeScript程序。

### unicode.js

~~~javascript
// 中文与 emoji 😀
export function café(value) {
  return value;
}
~~~

### bad.js

~~~javascript
export function broken( {
~~~

### duplicate.ts

~~~typescript
export function same() { return 1; }
export function same() { return 2; }
~~~

### unsupported.cjs、unsupported.tsx、declarations.d.ts

~~~text
unsupported.cjs: module.exports = () => 1;
unsupported.tsx: export const View = () => <div />;
declarations.d.ts: export declare function onlyType(): void;
~~~

这三个文件每个只写冒号后的独立一行正文。scope必须说路径可见/语义未支持，不能误计成已解析实现。

check-fixtures必须与以上内容逐字节比较，并核对 core.js::add 1–3、twice 4、Box 5–7、Box.get 6、main 8–10；core.ts::inc 1–3、entry 4–6、overloaded签名7/8与实现9–11、Counter12–14、Counter.next13；consumer.ts::run2–4；Unicode函数2–4；bad有错误；duplicate非唯一目标。

## 附件 2｜有界机械执行包

仅当 tools/js_ts_trial.py的 check-fixtures已可用，且主代理确认当前子任务值得委派时使用。先依照用户AGENTS读取fresh weekly quota：>90% used且符合Harness条件才选受限Harness；其他情况合格任务选luna_executor。不能把这份整项计划发给执行者。

**Objective**

逐字创建附件1的12个静态文件，不实现解析器。

**Allowed changes**

仅 tests/fixtures/js_ts_contract/ 下附件列出的12个文件。

**Forbidden changes**

产品源码、测试逻辑、helper、依赖、Git、网络、删除、重命名、发布、任何目标代码执行。你不独占工作区；保留其他人的改动，不回退它们。

**Exact steps**

检查这些路径尚不存在；按附件正文复制文件，UTF-8和末尾换行。若已有同内容文件保留；不同内容停止。运行下面的validator一次；仅复制差异可修正一次，不更改validator。

**Validation**

~~~sh
python -m tools.js_ts_trial check-fixtures --root tests/fixtures/js_ts_contract
~~~

**Expected result**

退出0；12文件内容与固定正文一致；只允许目录发生diff；回报实际命令/退出码及文件清单。

**Stop conditions**

已有不同内容、文件数量/内容含糊、需要改helper或范围外文件、validator一次修正后仍失败。停止返回主代理；不创建子代理，不扩范围。

主代理收到结果后检查实际diff并独立再跑validator。复制文件不代表parser或功能完成。

## 附件 3｜下一会话执行文案

~~~text
继续 AI Repo Doctor 的 JS/TS 只读预览，先读用户 AGENTS、
GraphFlow context、docs/superpowers/specs/2026-10-02-js-ts-readonly-preview-design.md
与 docs/superpowers/plans/2026-10-02-js-ts-readonly-preview.md。
从第一项未完成任务按 A0–A4执行，保持 v0.5.2稳定安装。
本计划写出不代表实施完成；先核对worktree、receipt和实际输出，避免重复。
固定np与ts-extras源码，目标仓库只静态分析；Key/Skill/旧报告/用户四文档保留。
A4由主代理按真实收益作go/no-go，no-go归档结束；go才执行B1–B4。
后续预览独立安装，不替换稳定CLI/Skill，不扩大为JS issue闭环或跨语言调用。
主代理负责设计/debug/参考答案/审查/发布，执行者仅领取合格机械包。
测试对应具体风险与现有CI门槛；最终交付中文报告、实际CLI、固定来源和HTML/SVG。
~~~

## 附件 4｜计划自审（文档工作）

- [x] 当前执行基线、设计/规划与实际实现状态分开。
- [x] A0–A4、B1–B4都对应用户认可的目标，阶段产物和停止条件明确。
- [x] ESM记录与Python ImportRef/解析隔离，不能按点号模块名猜跨语言边。
- [x] 默认无依赖、惰性extra、旧ID/快照/报告、稳定安装保留。
- [x] 统计、context AST、图过滤、指纹、TS扩展替换风险有专门任务。
- [x] 来源固定、参考答案独立、实际步骤/耗时记录，不制造准确率。
- [x] 去留条件是调查收益而非解析成功或测试数量。
- [x] B阶段调用边有正负例，未知范围有说明。
- [x] 预览完成包含干净安装、公开包、Mac独立环境、六题和中文交付。
- [x] Luna只复制固定夹具，选择与审查保留在主代理。

此自审只确认清单完整性；上面的功能、安装、评估和交付复选框仍未完成。
