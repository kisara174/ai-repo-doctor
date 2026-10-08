# AI Repo Doctor 1.0 产品闭环执行计划

> 执行要求：主代理逐项推进和验收。不得把计划交给简单模型自由设计；仅把已经明确的机械小任务按 AGENTS 规则交给执行器。

日期：2026-10-08。状态：实施中。规划基线：`b4ed82191a7dfd1ccbf8f06e75ea66bcd5760ec8` / 已公开 `0.8.0`。

**Goal：**构建并正式交付闭环、完整、稳定的 `AI Repo Doctor 1.0.0`。

**Architecture：**继续使用现有 Python CLI 和静态分析器；五个只读调查命令为核心。标准 venv/pip 负责安装，绑定 Skill 负责 Codex 入口，既有离线 HTML/SVG 负责人类展示。补齐接口合同、资源边界、平台和发行闭环；不增加服务器、自动修复或新语言。

**Tech Stack：**Python 3.11–3.14、setuptools、unittest；可选 tree-sitter JS/TS extra；既有原生 JavaScript viewer 与 DOM 验证；GitHub Actions/Release。

**Spec：**[产品闭环设计](../specs/2026-10-08-v1-product-closure-design.md)。[总清单](../../V1_TODO.md)负责阶段状态；本文件负责操作细节。

## 全局约束与执行变量

- 未勾选条目尚未完成；阶段状态以真实回执更新。
- 使用现有干净隔离工作树 `/Users/kisara/.codex/worktrees/js-ts-support-closure/AI Repo Doctor`，规划分支 `codex/v1-product-closure`。先检查身份，不移动或清理主目录的既有改动。
- 每阶段前 GraphFlow context；多步设计变更先 plan；变更提交后 index。
- 所有外部目标只读取源码：不安装目标依赖、不导入目标模块、不执行目标测试/构建/脚本。自有受控测试和 Repo Doctor 自身测试不受此限制。
- 不请求或打印 API key，不调用 DeepSeek；核心链无需 API。
- 实际证据放在新的运行子目录，旧证据不可覆盖。失败和中断必须如实保留。
- 每项先完成必要实现与有针对性的验证，主代理检查 diff 后提交；不得每个条目都无目的重跑全套。
- 发布属于主代理责任。许可缺失是明确输入依赖，其余可继续；不把用户未回复当成选择许可。

后续 shell 在工作树运行；先设置以下任务变量，均使用实际绝对路径：

```sh
export RD_WORKTREE='/Users/kisara/.codex/worktrees/js-ts-support-closure/AI Repo Doctor'
export RD_EVIDENCE='/Users/kisara/.local/share/ai-repo-doctor/evaluations/v1-product-closure-v1'
export RD_PY='/Users/kisara/.local/share/ai-repo-doctor/releases/v0.8.0/candidate/venvs/js/bin/python'
```

`RD_PY` 仅是现有可用开发解释器。V2 起 `RD_CLI` 必须是当次候选独立环境的绝对路径，不能使用全局旧入口。`RD_BASE_PY`、`RD_BASE_CLI`、`RD_JS_PY`、`RD_JS_CLI` 由当次新安装位置确定并写入回执；`RD_CLI` 指向该阶段的 JS-extra CLI。`RD_EXPECTED_VERSION` 在 V2–V6 为 `1.0.0.dev1`，V7 为实际 RC，V8 为 `1.0.0`。

每阶段源码变化后，用于集成/规模/真实调查的 CLI 必须从该阶段精确提交重新打包到新的独立环境，并更新上述变量。先比对 runtime 与源码，再运行；不能沿用 V2 旧 wheel 证明 V3 新逻辑。单元测试仍直接验证当前源码。V0/V1 不更改公开版本号。

每条执行回执至少包含 `argv`、`cwd`、`exit_code`、`expected_exit_code`、`duration_seconds`、stdout/stderr 文件引用、源码 SHA、工具版本；只有实际值匹配预期才通过。退出 2 的预期拒绝不应写成“命令退出 0”。

## V0 — 保护基线与收拢范围

**目标：**后续工作可恢复，有单一产品目标，并先修正已经确认的文档缺陷。

**文件：**Modify `README.md`、`docs/V1_TODO.md`；Create 运行证据 `baseline/identity.json`、`baseline/preservation.json`、`defects.json`（仓库外）。

- [x] **V0.1** 检查 `git status --short`、`git branch --show-current`、`git rev-parse HEAD`、worktree/common-dir；确认只在隔离树修改。工作树意外有他人改动时保留，先判断归属再工作。
- [x] **V0.2** 读取 0.8.0 的 delivery/completion/deployment，记录源码、公开产物和现有入口版本。核对全局 0.5.3 是否仍成立，不能把规划时事实当作执行时事实。
- [x] **V0.3** 建立新证据根目录；如果已存在则创建 `run-002` 等新的子目录，不能覆盖旧 receipt。
- [x] **V0.4** 保存保护清单：主目录所有既有未提交文件字节与 Git 状态、旧全局入口类型/链接目标、旧安装 runtime、用户现有 Skill、0.8.0 发行及历史 benchmark 证据。基线后新增的本轮证据不纳入“旧文件不变”比较。
- [x] **V0.5** 修复 README 的已知断链，指向 `docs/delivery/2026-10-08-v0.8.0-js-ts-completion.md`；保留旧报告的原版本归属。
- [x] **V0.6** 建立缺陷账本。初始记录：README 断链、Skill 维护者路径/版本混用、包描述过时、许可/URL 缺失；资源边界和平台缺口标记为待完善能力，不能伪装成已复现 bug。
- [x] **V0.7** 在总清单标记 V0 完成，写入基线回执路径和提交 SHA；仅提交本阶段明确文件。

**验证：**`git diff --check`；逐一检查上述部署链接目标存在；保护清单可读取且记录实际入口版本。文档改动不跑完整产品测试。

**完成条件：**后续改动与旧数据可区分，已知断链消失，V0 无待办。停止条件：无法辨别工作树所有权或保护清单无法建立；先解决，不删除数据。

## V1 — 冻结核心接口与迁移合同

**目标：**Codex 和调用脚本知道可以依赖哪些字段和退出行为，1.x 更新不靠猜测。

**文件：**Create `docs/CLI_CONTRACT.md`、`tests/test_v1_contract.py`；Modify `repo_doctor/cli.py`、`docs/CODEX_AND_MAP.md`、`docs/JS_TS_SUPPORT.md`（只改合同相关描述/错误文案）。使用既有 `tests/fixtures/js_ts_contract/`；新增小样本须放 `tests/fixtures/v1_contract/`。

- [x] **V1.1** 从当前源码和实际自有样本输出，列出五个命令的参数、默认语言、必填参数、schema_version、字段类型/可选性、符号 ID 规则、行号含义、排序及截断字段。
- [x] **V1.2** 为 `overview → symbols → context → impact → map` 各写一个最小成功合同用例，逐个复用工具返回的 ID；不能手造“不存在但看起来像”的 ID。
- [x] **V1.3** 写必要失败用例：不存在路径、歧义符号、不存在符号、未装 extra 却选择 JS、JS snapshot 拒绝、输出目录已存在。记录实际预期退出码，核心操作错误为 2。
- [x] **V1.4** 验证 `--json` stdout 可被一次 `json.loads` 消费；成功没有日志污染，失败没有伪成功 JSON。明确文件解析错误计数可以伴随成功查询，不把退出 0 等同于“目标代码没有错误”。
- [x] **V1.5** 明确 `impact` 返回已解析关系；空结果、深度范围、隐式/动态调用的限制写进合同。不要为提高覆盖率添加推测边。
- [x] **V1.6** 将过时的 JS/TS “preview” 拒绝文案更新为准确的只读支持说明；先补有意义的文案/行为回归，再改实现。
- [x] **V1.7** 写 1.x 兼容政策：新增字段可忽略、现有字段语义不改、内部 Python API 不作为 SDK；列出 0.8→1.0 有意变化，并由 V3 回填资源边界。
- [x] **V1.8** 主代理评审合同与实际输出一致，提交本阶段文件并更新账本/总清单。

**验证命令：**

```sh
"$RD_PY" -m unittest discover -s tests -p test_v1_contract.py -v
"$RD_PY" -m unittest discover -s tests -p test_agent_tools.py -v
git diff --check
```

**预期：**合同用例全部通过；安装缺 extra 场景由 V2 在独立 base 环境再次证明。若现有 API 与文档冲突，主代理以真实兼容风险作决策，执行器不得自行改 schema。

## V2 — 可移植安装、绑定 Skill、升级与回滚

**目标：**文档复制到另一台 Mac/Linux 仍能工作，Codex 不会误调用机器上旧版。

**文件：**Modify `repo_doctor/_version.py`、`repo_doctor/skills.py`、`repo_doctor/cli.py`、`repo_doctor/resources/skill/SKILL.md`、`tools/validate_release_install.py`、`tools/validate_js_ts_install.py`、`.github/workflows/ci.yml`（仅预期版本传参）、`tests/test_agent_tools.py`、`docs/CODEX_AND_MAP.md`；Create `docs/INSTALL.md`、`tests/test_skill_binding.py`、`tools/validate_v1_install.py`。工具使用标准库，不新增依赖。

- [x] **V2.0** 设置内部版本 `1.0.0.dev1`。安装验证器增加 `--expected-version VERSION`，调用者明确传入；旧验证器可保留与源码当前版本一致的默认值供既有调用兼容，但不能用“读到什么就期待什么”的方式自我验证。同步 CI 调用需要的预期版本，旧发行证据不改。

### V2A Skill 绑定

- [x] **V2.1** 给现有 `skill export` 增加可选 `--cli`，对应 `export_skill(destination, *, cli_path=None)`；保留已有无参数调用方式和拒绝覆盖行为。
- [x] **V2.2** 先写失败测试：相对路径、缺失/不可执行 CLI、版本不匹配、已有目录、已有符号链接目标。失败后原文件不变，不能留下完整导出假象。
- [x] **V2.3** 绑定时以 argv 数组运行显式 CLI 的 `--version`，使用短超时；只接受与当前包版本完全匹配的安装。禁止 shell 拼接和偷偷查找 PATH 替代。
- [x] **V2.4** 在新导出目录写 `installation.json`：`schema_version=1`、`cli` 为核验的绝对路径、`version` 为包版本。先完成输入验证再创建目录；写入失败由主代理处理本轮新建的残留，不碰已有目录。
- [x] **V2.5** 将 Skill 名称设为 `repo-doctor-v1`，移除维护者路径与旧发行专用文案。写明读取绑定、核对版本、使用返回 ID、明确语言、预算/未知、只输出结构图给人类。
- [x] **V2.6** 无绑定的导出仍可生成通用模板，但明确需要绑定后使用；当前安装合同测试继续验证旧调用不被破坏。
- [x] **V2.7** 覆盖含空格/中文路径和重复导出。不要依赖 shell 对路径的隐式解释。

### V2B 安装与部署说明

- [x] **V2.8** 写标准 Mac/Linux 安装流程：新 venv、固定 wheel URL/SHA、纯 Python 与 `js` extra 两条命令、显式 CLI `--version`、绑定导出、一次五步例子。
- [x] **V2.9** 用户示例使用其自己的版本目录，不包含 `/Users/kisara`。区分“安装依赖需要联网”和“安装后的只读分析不需要 API/网络”。
- [x] **V2.10** 写升级/回滚：保留旧环境 → 新环境验证 → 保存旧入口 → 切换链接 → 核对版本 → 恢复链接再核对 → 再切到新版。遇到原入口是普通文件时保留文件并由主代理处理，不能强制覆盖。
- [x] **V2.11** 新 Skill 另行导出到 `~/.agents/skills/repo-doctor-v1` 或用户指定的新目录；保留现有 `repo-doctor` 内容。明确在新会话使用 `$repo-doctor-v1`，验证时不依赖自动匹配。
- [x] **V2.12** 编写安装验证器，参数固定为 `--mode base|js --python ABS --cli ABS --expected-version VERSION --out NEW_ABS`。在仓库外运行，去除 PYTHONPATH/API 环境，核对安装包来源、版本、Skill 绑定和五步产物；输出 `summary.json` 和逐命令回执。测试实际包，不导入工作树冒充安装。
- [x] **V2.13** 使用临时候选 wheel 的两个新环境跑验证器；暂不切换全局入口。所有临时路径写到 `v2/products.json`，不得写进用户模板。
- [x] **V2.14** 主代理查看真实 diff、回执和绑定 JSON，提交并更新状态。

**验证命令：**

```sh
"$RD_PY" -m unittest discover -s tests -p test_skill_binding.py -v
"$RD_PY" -m unittest discover -s tests -p test_agent_tools.py -v
"$RD_BASE_PY" tools/validate_v1_install.py --mode base --python "$RD_BASE_PY" --cli "$RD_BASE_CLI" --expected-version "$RD_EXPECTED_VERSION" --out "$RD_EVIDENCE/v2/base-install"
"$RD_JS_PY" tools/validate_v1_install.py --mode js --python "$RD_JS_PY" --cli "$RD_JS_CLI" --expected-version "$RD_EXPECTED_VERSION" --out "$RD_EVIDENCE/v2/js-install"
```

**预期：**两个 summary 完整通过；每条实际/预期退出码匹配；新 Skill 指向本次包；旧入口和 Skill 未变。若候选版本不是 1.0，绑定记录候选实际版本，不能硬写 1.0。

## V3 — 正常规模可用与超限清楚失败

**目标：**解决无边界读取和等待，知道用户能分析到什么规模；避免无证据的缓存重构。

**文件：**Create `repo_doctor/limits.py`、`tests/test_analysis_limits.py`、`tools/profile_analysis.py`、`docs/RESOURCE_LIMITS.md`；Modify `repo_doctor/source.py`、`repo_doctor/scanner.py`、`repo_doctor/index.py`、`repo_doctor/parser.py`、`repo_doctor/js_ts.py`、`repo_doctor/cli.py`、`repo_doctor/repo_map.py`、`repo_doctor/model.py`、`repo_doctor/context.py`、`repo_doctor/case.py`、`repo_doctor/evidence.py`、`tests/test_v1_contract.py`、`docs/CLI_CONTRACT.md`、`docs/INSTALL.md`。只有需要传播预算的现有调用点才修改，先用引用搜索列出。

实现前调用点核对（2026-10-08）：`context._read_lines`、`case.source_fingerprint`、`evidence.validate_findings` 和 CLI 的预览证据读取均需传播同一预算；`RepoIndex` 保存单次预算及发现路径供地图复用。累计字节是本次分析**实际读取的总量**，包含指纹和上下文的再次读取，并非去重后的仓库大小。60 秒从本次索引开始，延续到证据准备的检查点；不含最终文件写入或强制中断 native parser。案件目录在证据准备成功后创建，避免预算失败留下空目录。旧 diagnose 的提供方等待使用既有独立 timeout，从分析检查点时间中扣除（字节预算不重置），避免兼容流程因网络等待误报源码超限；以假时钟/假响应验证，不调用 API。

### V3A 最小边界实现

- [x] **V3.1** 新建内部 `AnalysisLimits`（不可变 dataclass）与每次查询独立 `AnalysisBudget`。默认：单文件 2 MiB、累计 64 MiB、选中 5,000 文件、Git 15 秒、索引检查点 60 秒。测试允许注入小预算和时钟，不新增用户配置系统。
- [x] **V3.2** 定义 `AnalysisLimitError(ValueError)`，错误包含边界名、上限与当前文件（适用时）。不在异常中倾倒源码。
- [x] **V3.3** 先写边界测试：恰好上限成功，多 1 字节/文件失败；按原始字节计数；文件扫描顺序不改变整体失败结果；不同分析不共享预算。
- [x] **V3.4** 源码读取改为最多剩余预算+1 的有界读取，并保持现有安全打开、编码检测和路径限制。不能只看 stat 后再无界 read；不能为预算放松符号链接/根目录检查。
- [x] **V3.5** `build_index(root, *, languages=("python",), limits=None)` 增加内部可选参数，解析前检查选中文件数；Python 与 JS 共用单次累计预算，不将限制只加到一种语言。
- [x] **V3.6** Python parser 在普通 ValueError 捕获前重新抛出 `AnalysisLimitError`；JS 路径同样向上抛出。任何整体超限都不生成部分成功 JSON、快照或 map 目录。
- [x] **V3.7** Git rev-parse/ls-files 设置 15 秒 timeout；TimeoutExpired 转为明确操作错误，不把超时当作非 Git 仓库后静默回退。用 mock 验证超时，不真实等待 15 秒。
- [x] **V3.8** 索引阶段和文件边界用 monotonic 时钟检查预算。文档和错误明确 cooperative；不要声称能中断单次 native parse。
- [x] **V3.9** `impact --depth` 限为 1–10，默认 2，map 的既有 1/2 选择不变。补参数边界与深度结果测试。
- [x] **V3.10** 五个核心 JSON 顶层追加 `resource_limits`，固定键 `max_file_bytes`、`max_total_bytes`、`max_files`、`git_timeout_seconds`、`index_timeout_seconds`、`timeout_kind`。现有 `analysis.limits` 列表和 schema_version 不改。map 数据携带相同资源说明。
- [x] **V3.11** 补合同断言：新增字段准确，错误退出 2/stdout 空，普通解析错误仍计数；检查所有旧读取调用点，防止案件流程因签名变化失效。

### V3B 规模证据与决策

- [x] **V3.12** 编写 profiler：`--cli ABS --out NEW_ABS --sizes 100,1000 --runs 4`，仅生成自有静态 Python/JS/TS 文件；为每个规模执行一次首次和三次重复五步调查，记录单命令和总耗时，不执行样本代码。
- [x] **V3.13** 使用 subprocess 外部 timeout 为实验兜底，区分 profiler 截止与产品 cooperative 超限；不将被杀死的查询计为通过。
- [x] **V3.14** 从 V3 精确源码重建内部 wheel 到新环境并核对 runtime，更新 RD_CLI 后在当前参考机运行一次 profiler。标准查询每条 <60 秒，五步总计 ≤120 秒；记录机器/Python/规模/符号数与首次/重复差异，不只提供平均值。
- [x] **V3.15** 若未达标，主代理分析最慢阶段并只解决已证实瓶颈。若必须引入缓存/进程隔离或扩大默认边界，先更新本设计和计划，再实施；执行器禁止临场扩展架构。
- [x] **V3.16** 写资源说明，包含超限示例、如何缩小调查范围、支持范围、协作超时和 RSS 的限制；同步 V1 合同和迁移说明。
- [x] **V3.17** 主代理复核正确性/安全打开逻辑，提交并更新状态。

**验证命令：**

```sh
"$RD_PY" -m unittest discover -s tests -p test_analysis_limits.py -v
"$RD_PY" -m unittest discover -s tests -p test_scanner.py -v
"$RD_PY" -m unittest discover -s tests -p test_v1_contract.py -v
"$RD_PY" tools/profile_analysis.py --cli "$RD_CLI" --out "$RD_EVIDENCE/v3/scale" --sizes 100,1000 --runs 4
```

**预期：**边界准确、没有部分成功；正常规模符合参考机目标或有经过主代理批准的明确产品边界调整。源码安全逻辑变更必须主代理评审，不委派 Luna。

## V4 — 平台承诺与持续门禁

**目标：**正式承诺对应真实运行组合，并让以后更新可重复检查。

**文件：**Modify `.github/workflows/ci.yml`、`pyproject.toml`、`docs/INSTALL.md`、`README.md`、`docs/CODEX_AND_MAP.md`；Create `docs/SUPPORT_MATRIX.md`、`tools/check_public_docs.py`、`tests/test_public_docs.py`。复用 V2 安装验证器和现有 JS-extra/地图门禁。

实施决定：Ubuntu runner 固定 ubuntu-24.04；macOS 选 macos-15，实际架构以 machine.json 为准。七份文档对公开 0.8.0 下载示例与开发 1.0.0.dev1 使用显式版本标记，INSTALL 的正式 1.0.0 示例仍注明未发布。允许 README/CODEX_AND_MAP 补候选入口并移除维护者路径，不批量改历史报告。

- [ ] **V4.1** 将 Linux Python 核心/JS-extra 矩阵补到 3.11/3.12/3.13/3.14。保留现有 viewer/search/DOM 验证，不能删掉旧门禁以减少失败。
- [ ] **V4.2** 加 macOS Python 3.11/3.14 的 wheel 独立安装与 base/js 核心流程；每个 runner 记录 `uname`/Python/实际架构。不要把一台 ARM Mac 的结果宣传为所有架构通过。
- [ ] **V4.3** CI 从构建 wheel 安装到新 venv，调用 installed CLI 并在源码目录外执行 V2 验证器；不能只通过 PYTHONPATH 运行源码。
- [ ] **V4.4** 加公开文档检查工具：`--root .`；检查 README、INSTALL、CODEX_AND_MAP、JS_TS_SUPPORT、CLI_CONTRACT、RESOURCE_LIMITS、SUPPORT_MATRIX 的本地相对链接、标注代码块中的维护者绝对路径、当前版本示例一致性。历史报告允许保留历史路径，不做全历史替换。
- [ ] **V4.5** 用缺失本地目标和正常链接写工具回归；不访问外网来验证普通 Markdown 链接，不把在线页面暂时失败变成产品测试。
- [ ] **V4.6** 将上述文档门禁接入 CI。支持矩阵分别写 Python-only、JS-extra、地图和系统/版本组合；Windows 明确未验收。
- [ ] **V4.7** 推送当前实现分支并创建/附加 PR。等待精确 HEAD 的所有必需 job 完成，记录 job 名、SHA 与结论；新矩阵数量按实际读取，不能继续硬编码“7项通过”。
- [ ] **V4.8** 处理失败的首个根因；如果 native dependency 不支持某组合，主代理选择兼容修复或缩小承诺，同步元数据和矩阵，不允许 skip 后标绿。
- [ ] **V4.9** 提交并更新状态。

**验证：**`"$RD_PY" tools/check_public_docs.py --root .`；`"$RD_PY" -m unittest discover -s tests -p test_public_docs.py -v`；精确提交 CI 无失败、取消或缺失必需 job。

**完成条件：**公开支持范围可逐项追溯真实回执。外部 CI 不可达时保留待执行状态，继续不依赖它的文档/调查准备，不宣称门禁通过。

## V5 — 新调查与真实 Codex 使用闭环

**目标：**证明工具对实际调查有益，并发现命令测试之外的使用缺陷。

**文件：**Create `docs/evaluations/2026-10-08-v1-user-workflow.md`；新仓库、问题、回执与报告全部放本轮证据 `v5/`。仅在复现产品缺陷后修改直接相关源码/测试，先在账本登记允许文件。

- [ ] **V5.1** 选三个新的公开仓库：Python、JS/JSX、TS/TSX 各一；查询旧 benchmark/试用清单确认未被选择。记录 URL、固定 SHA、选择理由和源码规模。不要求 200 仓库重跑。
- [ ] **V5.2** 每个仓库先写一个真实问题，例如入口到业务函数路径、修改某导出函数的已解析调用者、组件相关源码结构；写预期需要的证据类别，不预填正确答案。
- [ ] **V5.3** 以本次候选 installed CLI 完成五步链；记录符号搜索命中、选中 ID、上下文/深度预算、截断/未知、产物路径和退出码。重跑仅限出现明确失败的步骤。
- [ ] **V5.4** 主代理查看关键源码，核对每份报告至少一条调用/影响结论的文件、行号和原文；记录源码可见但工具未解析的关系。不得为完整叙事把未知升级成证据。
- [ ] **V5.5** 为三份 map 做搜索选中、结构/关系切换、路径展开和当前视图 SVG 导出；核对导出节点/边与当前投影一致。既有 DOM 回归覆盖程序行为，另用可用浏览器核对至少一份真实离线 HTML；不反复修 Chrome 连接。
- [ ] **V5.6** 浏览器不可用时把实际视觉验收列为未完成；可继续其他任务，不能把 DOM 当成真实浏览器截图。如果 V7 前仍不可用，提供单份本地 HTML 的明确手工验收动作，由实际验收者回填事实。
- [ ] **V5.7** 创建一个全新 Codex 会话，仅提供新 Skill、安装位置、仓库和问题；让其独立完成核心链。需要由主代理通过工具创建新聊天时取得用户明确的新任务授权；没有该授权则使用可用 Codex CLI 的独立一次性会话，不冒充人工验收。
- [ ] **V5.8** 保存会话实际加载的 Skill/CLI 版本证据及回答；主代理核对结论。记录人工纠偏次数、误调旧版、ID 猜测、超预算源码读取等失败。如果没有可用的独立会话接口，此项明确待完成，不用当前会话代替。
- [ ] **V5.9** 每份中文报告回答：工具帮助定位什么、源码证据是什么、哪些仍未知、还需手工读什么。记录手工步骤减少和纠偏情况，不编造节省百分比。
- [ ] **V5.10** 对发现的真实缺陷：最小复现 → 定位 → 针对性回归失败 → 最小修复 → 回归通过 → 重做受影响调查。主代理负责策略；不能顺势扩展新语言/动态解析。
- [ ] **V5.11** 汇总价值和局限，形成 V5 报告；目标仓库 Git 状态/源码摘要前后一致。若某题只能靠大量人工读取才答出，标记收益不足并解决具体入口问题，不能只写“全部成功”。
- [ ] **V5.12** 提交产品修复和报告摘要，更新状态与账本。

**预期：**三份可核对中文调查、一个独立会话成功记录、真实地图使用证据。无目标代码执行/依赖安装；缺失独立会话或实际地图验收时 V5 不标完整通过。

## V6 — 许可、文档与维护闭环

**目标：**用户知道安装什么、能做什么、不能做什么、怎么更新和反馈，发行有明确许可。

**文件：**Modify `pyproject.toml`、`README.md`、`docs/CODEX_AND_MAP.md`、`docs/JS_TS_SUPPORT.md`、`docs/INSTALL.md`；Create `LICENSE`（用户决定后）、`CHANGELOG.md`、`SUPPORT.md`、`docs/COMPATIBILITY.md`、`.github/ISSUE_TEMPLATE/bug_report.yml`、`docs/delivery/2026-10-08-v1-readiness.md`。

- [ ] **V6.1** 记录用户明确的许可决定；若尚未回复，保持此项待完成并继续 V6.3–V6.8 等无依赖条目。不得默认 MIT/Apache/商业许可。
- [ ] **V6.2** 按用户选择写正确许可文本与权利人信息；同步 `project.license`/`license-files`。如果选择商业许可，等用户提供适用文本，不由简单模型自行起草法律条款。
- [ ] **V6.3** 更新包描述为 Python 与可选 JS/TS 的静态源码证据工具，补 Homepage/Repository/Issues/Changelog URL；分类器只声明实际支持的平台/版本。
- [ ] **V6.4** README 首屏只保留产品定位、支持范围、安装入口、五步最小使用链、离线图示例与限制；诊断/案件命令移到次级文档入口，保留兼容命令。
- [ ] **V6.5** 完整列出从 0.8 升级的变化：新 Skill 名称/绑定、资源边界、impact 深度范围、旧入口处理和回滚。旧案件/证据不做批量迁移重写。
- [ ] **V6.6** 写 CHANGELOG 的 1.0 条目和已发布 0.8 参考；写 SUPPORT/问题模板，要求版本、系统、语言、最小源码/命令、预期/实际、退出码和限制说明，不要求密钥或完整私人仓库。
- [ ] **V6.7** 写兼容政策：1.x 稳定 CLI/JSON；内部 API 无稳定承诺；支持边界和弃用流程；维护由 GitHub Issues/Release 承接，不虚构 SLA。
- [ ] **V6.8** Readiness 表逐项列 A1–A8 的状态、回执位置和未关闭缺陷；区分准备完成与正式产物发布完成。
- [ ] **V6.9** 构建临时 wheel 读取 METADATA/许可文件，核对 Name/Version/Summary/Requires-Python/Project-URL/License-Expression/License-File；未声明或未打包许可则不能通过。
- [ ] **V6.10** 运行公开文档门禁，主代理核对安装例子可复制且无维护者路径；提交更新。

**验证：**`"$RD_PY" tools/check_public_docs.py --root .`；读取真实 wheel zip 内 metadata；A1–A8 readiness 无虚假完成。缺许可时本阶段不完整，禁止进入正式发行。

## V7 — RC 构建与发布阻塞清零

**目标：**冻结一组可发行的代码和文档，以实际安装产物验收。

**文件：**Modify `repo_doctor/_version.py`、`tools/validate_release_install.py`、`tools/validate_js_ts_install.py`、V2 新验证器中的版本处理、当前用户文档版本示例；RC 产物/回执放 `v7/rc1/`，重建使用 rc2 等新目录。

- [ ] **V7.1** 主代理逐项检查 V0–V6，缺陷账本中发布阻塞归零；缺许可/新会话/地图实用验收/平台门禁不能以“以后补”跳过。
- [ ] **V7.2** 设置 `1.0.0rc1`；安装验证器通过明确的候选版本核对实际 metadata/CLI，去掉散落的旧版本号。旧历史证据不改。
- [ ] **V7.3** 给旧生命周期验证器的逐命令回执补齐 `expected_exit_code`，保留既有预期失败语义；不得全量把负向用例改成 0。
- [ ] **V7.4** 在已安装 JS extra 的开发环境跑一次完整 unittest；记录实际总数、失败、跳过及解释。预期不能存在未解释的 JS 缺依赖跳过，不硬编码沿用 498。
- [ ] **V7.5** 跑现有 viewer/search/DOM 门禁，并构建受控超 200 节点地图覆盖搜索选中祖先链；保持 200/500 投影上限。
- [ ] **V7.6** 从精确 RC 提交构建 wheel，保存 SHA256、构建命令/工具版本、源码 SHA；逐文件比对源码→wheel→base/js 安装 runtime。资源新增文件必须自动枚举，不能沿用“34文件”硬编码。
- [ ] **V7.7** 将 wheel 安装到新的 base/js 两套 venv；在源码目录外跑旧 Python 生命周期、旧 base/js-extra 验证器和 V2 新安装验证器；预期失败逐条匹配。
- [ ] **V7.8** 在最终 RC installed CLI 上重做 V5 中受本轮改动影响的调查链；无关目标不重复全量。记录实际版本/JSON/地图证据。
- [ ] **V7.9** 推送 RC 提交，等待该 SHA 必需 CI 全部通过；检查 PR 实际 diff，只合入本计划工作。已有未提交文件不进入提交。
- [ ] **V7.10** 主代理独立检查接口、资源异常传播、Skill 绑定、许可 metadata、安装来源、地图和回执；确认无已知阻塞。修复后形成新 RC，不覆盖旧 RC 的失败记录。

**核心本地命令：**

```sh
"$RD_PY" -m unittest discover -s tests -v
node tests/test_map_viewer.js
node tests/test_map_search.js
"$RD_BASE_PY" tools/validate_release_install.py --python "$RD_BASE_PY" --cli "$RD_BASE_CLI" --expected-version "$RD_EXPECTED_VERSION" --out "$RD_EVIDENCE/v7/rc1/python-lifecycle"
"$RD_BASE_PY" tools/validate_js_ts_install.py --mode base --python "$RD_BASE_PY" --cli "$RD_BASE_CLI" --expected-version "$RD_EXPECTED_VERSION" --out "$RD_EVIDENCE/v7/rc1/base"
"$RD_JS_PY" tools/validate_js_ts_install.py --mode js --python "$RD_JS_PY" --cli "$RD_JS_CLI" --expected-version "$RD_EXPECTED_VERSION" --out "$RD_EVIDENCE/v7/rc1/js"
```

DOM 按现有 CI 的 fixture/依赖路径命令执行并保存回执；无需临时增加另一套地图框架。上述输出目录若已存在，换新运行子目录，不清除重跑。

**完成条件：**RC 精确提交、安装结果、CI 和证据一致；所有发布阻塞关闭。此阶段没有公开 1.0 成功结论。

## V8 — 正式发行与本机部署

**目标：**公开下载件与实际可用安装一致，用户机器真正切到可用 1.0。

**文件：**Modify `_version.py`、当前用户文档/CHANGELOG；Create `docs/delivery/2026-10-08-v1.0.0-product-closure.md`；正式产物放新目录 `~/.local/share/ai-repo-doctor/releases/v1.0.0/`。实际交付若跨日，报告文件日期按真实日期，并统一引用，不伪造完成日期。

- [ ] **V8.1** 将版本设为 `1.0.0`，更新所有当前用户示例和 CHANGELOG；历史文件原样保留。提交并记录精确源码 SHA。
- [ ] **V8.2** 重新构建正式 wheel 和 SHA256SUMS；不可将 rc1 wheel 改名。比对正式 wheel 与最终 RC 的 runtime 差异，预期只允许明确的版本/最终说明变化；出现分析器变化则回到 V7。
- [ ] **V8.3** 从正式 wheel 建新的 base/js 环境，运行安装验证器、关键合同和地图门禁。即使 RC 已通过，也要确认正式 artifact 版本和 runtime 身份。
- [ ] **V8.4** 等待正式提交必需 CI 全通过再合并 PR；获取合并后 SHA/树，确认与验收 runtime 一致。创建精确提交的 `v1.0.0` tag 和 GitHub Release，附 wheel、SHA256SUMS、发布说明。PR 创建后必须 attach 到本任务。
- [ ] **V8.5** 检查 tag 指向、Release 非草稿/非预发布、资产名称/大小/SHA；匿名重新下载 wheel 与 checksum，记录 HTTP 状态并逐字节校验。
- [ ] **V8.6** **直接使用公开下载件**安装到另一个新环境，跑 V2 核心链/Skill 绑定；不只以“与本地 wheel 相等”代替安装事实。
- [ ] **V8.7** 在本机保留旧环境和原入口信息，部署带 js extra 的版本化 1.0 环境；导出新 `repo-doctor-v1` Skill 到未存在的目录，旧用户 Skill 字节不变。
- [ ] **V8.8** 切换全局入口后在普通新终端检查 `command -v repo-doctor` 与 `--version`；既有 shell hash 需要刷新时写明操作。Skill 绑定仍用绝对路径，不依赖这个链接。
- [ ] **V8.9** 实演恢复旧入口，检查旧版可运行，再恢复 1.0；留下操作回执和原链接信息。不得删除旧环境来证明新版独立。
- [ ] **V8.10** 新 Codex 会话明确加载 `repo-doctor-v1`，确认绑定的正式 1.0 CLI；用一个 V5 目标完成实际最小调查。旧会话未重载不能作为失败或成功的唯一依据。
- [ ] **V8.11** 交付报告列精确版本、提交、下载、安装、Skill 路径、支持范围、已知局限和回滚入口；如公开下载或最终部署失败，明确写“发行未闭环”，继续修复，不更新 Goal 完成。

**预期：**用户在本机直接使用 1.0，公开下载件也能独立安装；旧安装/Skill 可恢复且未被覆盖。发布权限/远端失败不得由执行器绕过，交给主代理定位。

## V9 — 最终闭环与精简维护

**目标：**结论和产品一致，停止无目的扩展，留下下一次维护的明确入口。

**文件：**Modify `docs/V1_TODO.md`、1.0 delivery report、readiness；Create 外部 `completion.json`、`preservation-after.json`、`open-items.json`、`deployment.json`。

- [ ] **V9.1** 按 A1–A8 逐条关联最后的正式产物证据，不能用旧候选的测试计数代替。最终使用链缺一环就仍未完成。
- [ ] **V9.2** 比较 V0 保护清单：主目录既有文件/Git 状态、旧 runtime、原用户 Skill、历史发行/benchmark。允许变化只包括有授权且被记录的全局入口切换和本轮新增文件。
- [ ] **V9.3** 盘点本轮新增的参数、模块、工具与文档。每个都关联实际目标；删除本轮无用途的临时仓库内文件。不得借精简删除旧功能或历史证据。
- [ ] **V9.4** 记录尚未支持的能力和非阻塞问题；只有真实证据必要才列 1.0.1 修复项，不立即开启新语言、MCP 或其他产品线。
- [ ] **V9.5** 保存 completion：正式版本、tag/source/CI、下载/安装回执、A1–A8 状态、保护审计、已知限制。任何必需项缺失则 `complete=false` 并列下一动作。
- [ ] **V9.6** 更新总清单真实状态、提交最后报告、GraphFlow index；向用户交付中文简报和一条可运行的正式入口。
- [ ] **V9.7** 只有 A1–A8 全通过、无发布阻塞、公开产物及本机正式版都已核验时，调用 Goal update 为 `complete`。否则保持 active 并继续具体未完成工作。

**验证：**JSON 可解析、路径/下载链接可核对、`git diff --check`、保护比较无未经授权差异。若最终 runtime 没有变化，不重复全套测试。

## 需求覆盖与依赖

| 完成定义 | 主阶段 | 最终依据 |
| --- | --- | --- |
| A1 安装与正确版本 | V2、V8 | 下载件的新环境安装及版本回执 |
| A2 Codex 证据调查 | V1、V5、V8 | 合同、真实中文报告、新会话 |
| A3 人类结构图/SVG | V5、V7、V8 | 交互/实际页面、投影及正式包产物 |
| A4 诚实支持与稳定接口 | V1、V4、V6 | CLI 合同、支持矩阵、兼容政策 |
| A5 规模和边界 | V3 | 边界回归及参考机 profile |
| A6 升级回滚/保护 | V0、V2、V8、V9 | 原入口恢复及保护清单 |
| A7 精确正式产物 | V7、V8 | SHA、CI、下载与 installed runtime |
| A8 许可/维护 | V6 | 用户许可决定、包 metadata、文档 |

主顺序：`V0 → V1 → V2 → V3 → V4 → V5 → V6 → V7 → V8 → V9`。许可决定可以早于 V6 收集；没有它仍可做 V0–V5 与 V6 无依赖条目。平台/独立会话等外部等待不允许伪造完成，可推进不依赖的准备工作。

## 简单执行器任务包规则

主代理不得把整阶段或设计决策交给 Luna。只有如“在列出的当前用户文档中替换已确定的版本示例，并运行已存在的文档门禁”这类机械小任务适合委派。

每次委派必须先提供：**Objective、Allowed changes、Forbidden changes、Exact steps、Validation、Expected result、Stop conditions**；先读 fresh weekly quota 按 AGENTS 路由，最多一个执行器。安装/依赖、权限、安全打开、架构、外部选库、许可、发布、Git push 均留给主代理。

执行器一次有针对性的修正后仍验证失败、遇到未列文件或含义不清，立即停止返回。主代理查看实际 diff 和新回执再接受，不能只信“完成”文字。

## 当前规划完成情况

- [x] 已建立 active Goal，并确定 A1–A8 的闭环完成条件。
- [x] 已记录 0.8.0 的真实基线和当前缺口。
- [x] 已写设计、阶段总清单及详细执行步骤。
- [x] V0 保护基线及已知文档断链修复已完成，见总清单证据入口。
- [x] V1 核心合同及错误语义已完成，资源字段在 V3 回填。
- [x] V2 开发候选、版本绑定、安装指南及独立安装已完成，V5 新会话与 V8 正式部署未提前计入。
- [x] V3 边界、119 项冻结相关测试、独立安装和 100/1,000 文件规模实验已完成。
- [ ] V4–V9 产品实施待完成。

下一动作：V4.1。阶段通过不等于 1.0 产品完成。
