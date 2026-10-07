# JS/TS 基础支持：测试准备与交付执行计划

> **For agentic workers:** 使用 `executing-plans` 逐项执行。主代理负责范围、独立参考答案、样本判断、调试、审查和发布。按用户 AGENTS.md 路由；不将规划或判断交给 Luna。仅范围固定且验证合同明确的机械小任务可考虑委派。

**Goal:** 将现有 JS/TS 本地只读预览推进到具有明确支持边界、源码证据可信、可安装并能帮助 Codex 实际调查的基础版本；建议正式晋级目标为 0.6.0，Python 0.5.3 持续可用。

**Architecture:** 延用现有语言选择、Tree-sitter 可选后端、统一 RepoIndex 和五个只读入口；复用现有契约测试、安装验证器及 benchmark 材料。准备、运行、修复、发布各有独立门槛，不新建测试平台或用户接口。

**Tech Stack:** Python >=3.11；现有 `js` extra；unittest；Node/jsdom 地图检查；GitHub Actions；GitHub wheel。

**Spec:** 现有 `docs/superpowers/specs/2026-10-02-js-ts-readonly-preview-design.md` 的只读合同；预览工作树 `docs/delivery/2026-10-06-v0.6.0a5-local-candidate.md`；稳定版 `docs/delivery/2026-10-07-v0.5.3-release.md`。前两份文档中的旧日期状态为历史，不据此将本机版本判断为 0.5.2。

**本计划状态：** 2026-10-07 已执行 J0–J4 准备，材料为 `prepared-not-run`。J5 产品测试/补充断言及 J6 发布尚未执行。详见 `evaluation/js-ts-support/README.md` 与本机证据根 `evaluations/js-ts-support-v1/preparation-report.md`；准备就绪不等于产品通过。

## 1. 已核实的起点

| 项目 | 实际状态 |
|---|---|
| 当前 Python 稳定版 | 0.5.3 已发布、已部署，主目录 HEAD `c9342b41490852744669aae2430a7274f566fd0e` |
| 稳定 tag 源码 | `0a68ff6834963ad13f03230c87018b21c81386d4`，后续文档不改变 runtime |
| JS/TS 预览工作树 | `/Users/kisara/.codex/worktrees/dom-preview-delivery/AI Repo Doctor` |
| 预览 HEAD / 包源码 | `2b786cf22eecaed29327b9d8a453a00429875782` / `4c001259a0e498643c32f9d26b49670e63229da8` |
| 预览版本 / wheel SHA-256 | 0.6.0a5 / `b8459b4da69962e7399948fb529618c9870f640b40e4ea5b73675ee637dbb7e9` |
| 已有本地验证 | Python 3.14 环境：466 项单元测试，Python 生命周期 33 条、base 9 条、JS-extra 18 条 |
| 新预览远端矩阵 | 尚未取得当前 HEAD 的完整 7-job 通过证据 |
| 已有语言支持 | `.js/.mjs/.ts` 的有限符号、ESM 文件关系、保守直接调用、上下文、影响与地图 |
| 历史 benchmark | 200 仓库：120 Python、40 JS、40 TS；80 个 JS/TS 仓库均已进入历史评估 |
| 历史问题 | 7 条 TS 导入 oracle 误配候选，涉及无后缀与目录 index；不能直接全部归为分析器 bug |
| 浏览器状态 | Chrome 连接问题搁置；既有实际交互证据保留 |

预览中的 `repo_doctor/graph.py` 与稳定版本没有差异；语言共享模块、地图语言字段及 Skill 有预览专属差异。不能用整目录覆盖完成集成。

## 2. 完成形态与硬约束

- Codex 可通过 `overview → symbols → context/impact` 获取 JS/TS 结构、真实符号 ID、源码行和已解析关系。
- 人通过离线 HTML、结构 SVG、关系 SVG 查看组成与关系；不增加诊断、源码全文或补丁面板。
- 沿用五个命令和 `--languages javascript,typescript`；默认仍为 Python，没有自动语言猜测。
- 首个基础版范围沿用已批准只读合同；JS/TS snapshot、案件/findings、自动修复、框架运行语义不在该合同内。
- 无后缀/index 源码关联是优先覆盖扩展候选。先量化影响，再另写最小语义增补并评审；没有批准前仍按旧合同未知处理。
- Python >=3.11；基础安装不引入无条件运行依赖。保留三个精确固定的 extra：tree-sitter 0.26.0、javascript grammar 0.25.0、typescript grammar 0.23.2。
- 不执行目标仓库代码、不安装目标依赖、不运行 npm/package scripts、不调用 DeepSeek API。
- 保留节点 200、边 500、analysis limits 50 条并显示省略数量，以及 context 行预算和截断标识。
- 只从已选择、未忽略、可安全读取、解析成功且唯一的源码获得关系；不靠同名猜边，不将类型引用算作运行调用。
- 保留 Python 0.5.3 入口、Skill、Key、14 个原未提交文件和历史评估；不改历史 dataset-lock、oracle、评分、候选包或收据。
- 旧 holdout 已经查看和运行过，本阶段全部属于开发/回归评估，不能继续称为新的盲测。
- J0–J4 是准备；J5 才运行产品和测试；J6 才进行发行与部署。准备产物的状态为 `prepared-not-run`。

## 3. 推荐路线与取舍

推荐“现有只读合同 → 有来源的正负例 → 小规模真实任务 → 定向修复 → CI/安装/正式交付”。直接发布 alpha 可以较快提供入口，但不能补足当前版本的远端兼容性和真实任务证据；一次补齐 CommonJS、TSX、别名及完整类型解析会同时改变多个语义系统，超出本轮基础支持范围。

本轮测试回答三个问题：支持范围内是否准确；遇到范围外输入是否明确而保守；Codex 是否能完成实际调查并减少定位成本。命令退出 0、测试数量、未解析数量均不能单独回答这些问题。

## 4. 位置与文件责任

```sh
RD_PROJECT='/Users/kisara/Documents/ChatGPT/AI Repo Doctor'
RD_PREVIEW='/Users/kisara/.codex/worktrees/dom-preview-delivery/AI Repo Doctor'
RD_HARNESS='/Users/kisara/.codex/worktrees/diagnosis-evaluation/AI Repo Doctor'
RD_HISTORY='/Users/kisara/.local/share/ai-repo-doctor/evaluations/benchmark200-v1'
RD_NEXT='/Users/kisara/.local/share/ai-repo-doctor/evaluations/js-ts-support-v1'
RD_EXISTING_CLI="$RD_HISTORY/delivery/revision-001/candidates/0.6.0a5/venv/bin/repo-doctor"
```

执行工作树由原生 worktree 工具从已核实预览 HEAD 创建并附加；记录返回的绝对路径为 `RD_WORKTREE`，发行开发分支建议 `codex/js-ts-support-closure`。旧预览只读。路径若已存在先检查来源，不覆盖。

**J0–J4 允许新建的准备材料：** `RD_NEXT/baseline.json`、`protection-before.json`、`support-matrix.json`、`oracle-review.jsonl`、`cohort.json`、`questions.jsonl`、`reference.jsonl`、`test-plan.json`、`readiness.json`、`preparation-report.md`。使用同一 schema_version=1，准备产物明确未运行。

**允许在新工作树增加：** `evaluation/js-ts-support/README.md`、`cases.json`、`cohort.json`；仅确实缺少断言时修改现有 `tests/test_js_ts.py`、`test_esm.py`、`test_languages.py`、`test_index.py`、`test_context.py`、`test_agent_tools.py`、`test_repo_map.py`、`test_cli.py` 及 `tests/fixtures/js_ts_contract/`。本轮写计划不创建这些材料或测试代码。

**J5 缺陷修复候选责任：** parser=`repo_doctor/js_ts.py`；ESM=`esm.py`；选择/扫描=`languages.py,index.py,source.py`；输出=`agent_tools.py,context.py,cli.py,repo_map.py,map_render.py`；图交互=`resources/map/viewer.js`。遇到缺陷先定位，再登记实际最小文件清单；不自动将整份列表视为修改授权。

**安装和发布复用：** `tools/validate_js_ts_install.py`、`tools/validate_release_install.py`、`.github/workflows/ci.yml`。benchmark 开发工具在独立 harness 工作树，不属于发行 runtime。

## J0：锁定来源与保护稳定版

**Owner:** 主代理。**Consumes:** 上述来源及稳定部署收据。**Produces:** baseline、保护清单、干净执行工作树。

- [x] 读取稳定 `releases/v0.5.3/completion.json`、`deployment-v0.5.3.json`，确认全局入口仍为 0.5.3。
- [x] 核验预览 HEAD、wheel SHA、安装 runtime 与包源码；记录 Python、操作系统、架构及已有 extra 版本，不升级依赖。
- [x] 记录 14 个原文件哈希、稳定 CLI 链接、Skill 哈希；复用稳定交付保护清单核对历史条目，新增材料另列。
- [x] 通过原生工具建立隔离执行工作树；记录 worktree/branch/HEAD，确认无用户脏文件。
- [x] 比较稳定与预览 runtime；逐项登记稳定修复是否已经包含，保留预览版本号、语言接口和 extra。发生冲突由主代理逐项解决，不整体覆盖或自动选一边。

```sh
git -C "$RD_PROJECT" rev-parse HEAD
git -C "$RD_PREVIEW" rev-parse HEAD
git -C "$RD_PROJECT" diff --stat v0.5.3 2b786cf22eecaed29327b9d8a453a00429875782 -- repo_doctor
/Users/kisara/.local/bin/repo-doctor --version
```

**Acceptance:** 来源与本计划一致，原资料无变化，所有候选命令使用独立绝对入口。来源变化先查明，不直接重置。

## J1：冻结支持矩阵并复核 7 条旧评分缺口

**Consumes:** 现有规格、真实源码、`esm.py`、旧评审。**Produces:** support-matrix 与 oracle-review；不修改原 oracle。

- [x] 每项能力记录 `feature_id`、`contract=current-supported/current-limited/proposed`、输入、预期结果、现有测试、事实来源与版本。
- [x] 对以下七条逐一核对 frozen commit、源码 hash、声明跨度、目标文件与已选择语言；比较旧 oracle 与当时合同。

| 历史 repo_id / p04 | 预期目标 | 首要复核维度 |
|---|---|---|
| mxmvshnvsk__i18n-unused | src/types/index.ts | 无后缀目录 index |
| sunanakgo__nais3 | src/main/db/index.ts | 无后缀目录 index |
| roseforljh__qoneagent | apps/desktop/src/components/assistant-ui/tool-call-display.ts | 无后缀文件 |
| smp46__pingvin-share-x | backend/src/constants.ts | 无后缀文件；多行声明 |
| duplicati__ngclient | projects/ngclient/src/app/core/openapi/index.ts | 无后缀目录 index |
| emircanagac__voxpery | apps/web/src/secureId.ts | 无后缀文件 |
| yu000jp__logseq-plugin-weekdays-and-weekends | src/lib.ts | 已使用 holdout；无后缀文件 |

- [x] 每条输出 `probe_id, repo_id, commit, old_review_path, source_sha256, specifier, expected_file, contract_at_old_version, classification, rationale, proposed_action`。
- [x] classification 只用 `oracle_scope_mismatch`、`confirmed_product_defect`、`confirmed_coverage_gap`、`insufficient_evidence`。同一条可用 proposed_action 登记未来覆盖价值，但不能改变历史得分。
- [x] 若 a5 对未支持输入造了错误边，仍是产品缺陷；“范围外”不能豁免误导输出或崩溃。

**Acceptance:** 七条均有可复核结论；不把修正评价口径当作实现无后缀/index 支持。旧报告入口：`RD_HISTORY/final-reports/reports/revision-003/report.md`，仍保留其原始结论。

## J2：准备正负例和源码参考

**Consumes:** J1 冻结合同与现有测试。**Produces:** 下表案例的 prepared 记录；补充真正缺失的 fixture/断言。

24 是能力案例 ID 数量，不是强制新增 24 个测试。先链接已有断言，避免重复或只检查实现内部步骤。

| ID | 输入/关注点 | 必须核验的外部结果 | 优先复用测试 |
|---|---|---|---|
| C01 | JS 具名函数、const 箭头/表达式 | 真实 ID、类型、起止行与原文 | test_js_ts |
| C02 | .mjs、async、default | 已承诺符号可找，匿名 default 命名明确 | test_js_ts |
| C03 | TS 重载及实现 | 签名与单一实现关联；声明不算运行函数 | test_js_ts |
| C04 | 显式本地 ESM 路径、导入别名 | 文件边声明行正确，绑定唯一 | test_esm |
| C05 | TS ./core.js → 唯一 core.ts | 已选择且唯一时连接 | test_esm |
| C06 | .ts/.js/.d.ts/.tsx 候选冲突 | 不猜实现，保留未知原因 | test_esm |
| C07 | import type / type-only export | 不形成运行调用；保留原声明类别 | test_esm |
| C08 | 顶层直接函数、别名直达导出 | 精确 caller/callee/line | test_esm |
| C09 | 参数/局部遮蔽、赋值改写 | 不误连同名函数 | test_esm |
| C10 | 方法、this、对象链、回调 | 符号与关系区分，调用未知不造边 | test_esm |
| C11 | 多跳 re-export、namespace、dynamic import | 不冒充已解析直接调用 | test_esm |
| C12 | ./core、./dir 的无后缀/index | a5 合同为未知，不新增猜测；另记覆盖缺口 | test_esm |
| C13 | bare package、@alias、node_modules | 不猜别名，不追踪外部依赖 | test_esm |
| C14 | .jsx/.tsx/.cjs/.mts/.cts/.d.ts | 不当作已分析实现文件；图范围说明准确 | test_languages |
| C15 | JS/TS 语法错误或坏 UTF-8 | 明确文件/行或读取错误；无部分伪证据 | test_js_ts |
| C16 | BOM、CRLF、中文和 emoji | 物理源码行、字节解码和引文正确 | test_languages |
| C17 | 默认 Python 与显式混合语言 | python_files 不混算，选择范围一致，无跨语言调用 | test_index/test_agent_tools |
| C18 | base 无 extra / 非法语言 CSV | 退出 2、可操作提示，不静默退回 Python | test_cli/安装验证器 |
| C19 | context 120 行及小预算截断 | target-first，实际行数不超预算，截断/省略可见 | test_context |
| C20 | include-symbol 及歧义 ID | 用真实搜索 ID；歧义不任意选中 | test_context/test_agent_tools |
| C21 | impact depth=2 与空结果 | 仅已解析反向边；逐跳证据正确；空结果有边界提示 | test_esm/test_agent_tools |
| C22 | JS/TS --snapshot-out | 退出 2，连父目录也不创建 | test_cli/安装验证器 |
| C23 | map 四件套、语言、200/500、搜索选择 | SVG 可解析，无悬空边，隐藏计数正确，选择及祖先保留 | test_repo_map/地图 JS 脚本 |
| C24 | ignore、软链接、选择后源码变化 | 不越界读取/写入；选择指纹变化符合合同 | test_languages/test_index |

- [x] cases.json 每行字段为 `case_id, contract, fixture_paths, expected_symbols, expected_imports, expected_calls, forbidden_calls, expected_exit, expected_limits, existing_assertions, preparation_status`。不适用字段用空列表，不能用空列表表示“已验证没有关系”。
- [x] 预期符号/边必须由主代理阅读 fixture 源码写出；不得从产品输出反填。
- [x] reference.jsonl 的事实包含 `case_id, file, start_line, end_line, quote, file_sha256, expected, reviewer`；每条 quote 与实际源码逐字节核对。
- [x] 无后缀/index 如需未来扩展，新增 `proposed` 案例，保留 C12 的 a5 合同。新语义要求：仓库内来源、歧义拒绝、类型与实现区分，以及“源码关联不等于运行时解析”的说明。

**Acceptance:** 24 类均能指向现有断言或具体补充项，正边有来源，负例明确，准备状态没有 passed 字段。缺失的新测试首次执行和红绿过程在 J5 记录。

## J3：准备真实仓库与调查问题

**Consumes:** 冻结 manifest 和 inventories。**Produces:** 12 仓库 cohort、36 题与独立参考。

- [x] 从 `RD_HARNESS/evaluation/benchmark200/manifest.jsonl` 的 80 个 JS/TS 仓库选择，不另克隆 200 仓库。字段使用实际 `primary_language,size_band,family_id,commit,source_inventory`。
- [x] 每语言 small/medium/large 各 2 个，共 JS 6、TS 6。已有各语言分层为 12/20/8，数量足够；同 family 优先只选一个。
- [x] 每个语言/大小层按 repo_id 排序，主代理源码检查后取两个符合层级且可提出真实调查题的仓库；第一个为 discovery，第二个为 confirmation。排除或替换须记录原因，不能因产品答错而替换。
- [x] 每语言的两组样本各至少 2 仓库具备当前合同内的可核对工作流；范围外仓库作为边界样本保留，不拿来虚增支持内分母。
- [x] cohort 记录 `repo_id,commit,tree,primary_language,size_band,family_id,original_split,cohort_role,source_inventory_sha256,already_seen=true,selection_rationale`。原 split 不改；confirmation 不称 blind holdout。
- [x] 每仓库提前写 3 题：Q1 项目组成/入口到核心符号；Q2 一个真实直接调用或明确未知的调用；Q3 指定函数改动的支持内影响及遗漏边界。共 36 题。
- [x] 每题记录 `question_id,repo_id,prompt,symbol_query,support_class,expected_facts,limitations,source_baseline_actions`。先做源码基线，再读工具输出；用相同问题比较，不事后换成容易回答的问题。
- [x] 为每题保存源码路径/行/引文/hash。允许 `answered/bounded/blocked` 三种结果，后两者不能算 answered；若没有支持内目标，明确原因而非杜撰函数。

**效益门槛：** 每语言至少 1 个支持内仓库的固定问题，比 rg/源码补读基线少至少一次定位或补读动作，同时事实不减损；每语言至少 2 个仓库完成支持内调查链。其余未知必须明示。没有观察到效益时先分析阻断，不凭 36 条命令成功宣称有实际收益。

## J4：准备运行合同与就绪检查

**Consumes:** J0–J3。**Produces:** test-plan/readiness 和可直接执行的命令清单；仍不运行。

- [x] test-plan.json 固定源提交、wheel/入口/hash、语言 CSV、样本 hash、case/question ID、超时、预算、每项证据路径和预期退出码。
- [x] 每条命令收据保存 `argv,cwd,exit_code,expected_exit,duration_seconds,stdout_file,stderr_file,product_sha256,source_sha256,attempt`。失败重试写新 attempt，不覆盖原输出。
- [x] 单仓库命令先采用已有 30 秒预算，context 120 行、impact depth 2；超时保留事实再定位，不无依据放宽预算。
- [x] 复用已有安装验证器，不新建用户 bench 命令。benchmark 的 validate-dataset/readiness 也会写状态；不要直接对 RD_HISTORY 运行这些命令。
- [x] 旧 harness 若用于新增评分，先核对 tools/benchmark200*.py 的现有输入合同，在新数据根使用独立复制材料和新来源；不得靠过滤旧锁、修改原分层、放宽数量检查拼成“新200”。小规模调查可用固定 argv 与现有 JSON 输出，初期不改 harness。
- [x] readiness.json 逐项列出来源、矩阵、24类案例、12仓库、36题、参考引文、输出位置、安装/CI命令；仅全部准备好且 missing=[] 时为 prepared-not-run。actual_tests_run=false、target_code_executed=false。
- [x] 主代理审核准备材料，确认没有“未运行=通过”，再开启 J5。

后续使用已装候选的命令形式：从 cohort.json 及其 checkout 收据取得实际根目录为 RD_TARGET，从冻结问题的 symbol_query 取得 RD_QUERY，从 symbols 输出取得实际 ID 为 RD_SYMBOL；RD_FRESH_MAP 取 test-plan 为该 repo_id/attempt 指定且不存在的输出目录。不得猜目标路径或符号 ID。

```sh
"$RD_EXISTING_CLI" overview "$RD_TARGET" --languages javascript,typescript --json
"$RD_EXISTING_CLI" symbols "$RD_TARGET" --query "$RD_QUERY" --languages javascript,typescript --json
"$RD_EXISTING_CLI" context "$RD_TARGET" "$RD_SYMBOL" --max-lines 120 --languages javascript,typescript --json
"$RD_EXISTING_CLI" impact "$RD_TARGET" "$RD_SYMBOL" --depth 2 --languages javascript,typescript --json
"$RD_EXISTING_CLI" map "$RD_TARGET" --languages javascript,typescript --out "$RD_FRESH_MAP" --json
```

**Acceptance:** 下一位执行者不依赖聊天记忆就能知道测试什么、输入从哪取、什么结果算正确、何时停止。准备材料就绪不等于产品通过。

## J5：定向测试、修复与候选冻结

**本阶段后续执行。Files:** J2 登记的缺失断言与 J5 定位的最小 runtime 文件；版本/验证器同步由主代理负责。

- [ ] 先运行现有 JS 契约；extra 环境不允许 skipped。新 fixture 或断言先检查引用，再运行得到真实结果，不为得到红灯人为破坏产品。
- [ ] 已确认 bug：先保留可复现失败和独立预期，再最小修复、原场景重跑；已有通过能力的验证只做差异涉及部分。
- [ ] 先 discovery 6 仓库调查并审阅；修复来源固定后再跑 confirmation 6 仓库。修复后的受影响 discovery 场景写新 attempt，不混计不同来源。
- [ ] P0：错误源码引用、无根据造边、数据损坏；P1：承诺能力不可用、有效输入崩溃、版本/安装/范围误导。上述已确认问题必须关闭，不以 accepted_limitation 绕过。
- [ ] 覆盖缺口单列。若无后缀/index 导入导致真实调查无法闭环，先提出最小来源关联设计，再写反例和实现；不得直接把它解释成完整 Node/TS 解析。
- [ ] JS/TS runtime 相对 a5 有变化则创建新的本地 0.6.0a6 来源、wheel 与收据，同时同步 `_version.py`、`validate_release_install.py::EXPECTED_VERSION`、`validate_js_ts_install.py::VERSION`；保留 a5。仅文档变化可复用 a5 runtime，但正式 0.6.0 仍单独构建。
- [ ] 变化涉及共享 index/context/map 时做 Python 兼容检查。只改 ESM 不重跑整套 200；需要分布性证据时扩到现有 80 个 JS/TS，使用新 run ID，不能把旧结果改挂新版本。

JS 契约命令：初始复用已验证 a5 extra 环境的解释器读取新工作树代码，禁止向旧环境安装或修改依赖；它不代替新候选的独立安装 gate。构建本轮 extra venv 后，用本轮解释器再执行受改动影响的同组契约。

```sh
cd "$RD_WORKTREE"
RD_JS_PY="${RD_JS_PY:-$RD_HISTORY/delivery/revision-001/candidates/0.6.0a5/venv/bin/python}"
PYTHONDONTWRITEBYTECODE=1 "$RD_JS_PY" - <<'PY'
import unittest
modules = ['tests.test_languages', 'tests.test_js_ts', 'tests.test_esm', 'tests.test_index', 'tests.test_context', 'tests.test_cli', 'tests.test_agent_tools', 'tests.test_repo_map', 'tests.test_js_ts_spike']
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(modules))
assert result.wasSuccessful() and not result.skipped
PY
```

候选修改和审查完成后先提交，只从真实冻结 SHA 构建；将 SHA 和版本写入 `RD_NEXT/candidate.json`，记录为 RD_CANDIDATE_SHA / RD_VERSION。source、wheels、venvs 路径须不存在；恢复已有尝试时核对身份后新建递增 attempt。主代理构建及安装，不委派依赖操作。

```sh
mkdir -p "$RD_NEXT/candidate/source"
git -C "$RD_WORKTREE" archive "$RD_CANDIDATE_SHA" -o "$RD_NEXT/candidate/source.tar"
tar -xf "$RD_NEXT/candidate/source.tar" -C "$RD_NEXT/candidate/source"
python3 -m pip wheel --no-deps --wheel-dir "$RD_NEXT/candidate/wheels" "$RD_NEXT/candidate/source"
RD_WHEEL="$RD_NEXT/candidate/wheels/ai_repo_doctor-${RD_VERSION}-py3-none-any.whl"
python3 -m venv "$RD_NEXT/venvs/base"
python3 -m venv "$RD_NEXT/venvs/js"
RD_BASE_PY="$RD_NEXT/venvs/base/bin/python"
RD_BASE_CLI="$RD_NEXT/venvs/base/bin/repo-doctor"
RD_JS_PY="$RD_NEXT/venvs/js/bin/python"
RD_JS_CLI="$RD_NEXT/venvs/js/bin/repo-doctor"
"$RD_BASE_PY" -m pip install --no-index "$RD_WHEEL"
"$RD_JS_PY" -m pip install "$RD_WHEEL[js]"
```

独立安装 gate 使用本轮冻结来源的现有验证器，输出目录必须新建；RD_BASE_PY/RD_BASE_CLI 和 RD_JS_PY/RD_JS_CLI 来自上述两个 venv。先核对 site-packages、metadata、后端固定版本和全部打包 runtime 与 source 字节一致；验证器版本常量也须与冻结版本一致。

```sh
"$RD_BASE_PY" "$RD_NEXT/candidate/source/tools/validate_js_ts_install.py" --mode base --python "$RD_BASE_PY" --cli "$RD_BASE_CLI" --out "$RD_NEXT/install-base/attempt-001"
"$RD_JS_PY" "$RD_NEXT/candidate/source/tools/validate_js_ts_install.py" --mode js --python "$RD_JS_PY" --cli "$RD_JS_CLI" --out "$RD_NEXT/install-js/attempt-001"
"$RD_JS_PY" "$RD_NEXT/candidate/source/tools/validate_release_install.py" --python "$RD_JS_PY" --cli "$RD_JS_CLI" --out "$RD_NEXT/install-python-lifecycle/attempt-001"
```

- [ ] base 9、extra 18、Python 生命周期 33 条是现有基线；若改验证器增加真实门槛，记录实际数量，不强行保持计数。预期负例退出码不能算失败。
- [ ] 每次候选必须获得精确来源 SHA 的 7 项 CI：Python 3.11/3.12/3.13；JS preview Python 3.11/3.12/3.13；Offline map interaction and SVG。
- [ ] JS job 必须实际安装 extra、契约无 skipped、独立 extra wheel 验证通过；地图 job 包含纯 Python 和混合地图 DOM/SVG、完整 ID 搜索。
- [ ] viewer 字节未变可引用既有实际地图交互证据，并注明其原版本；如改变 viewer，至少核验一个 JS 和一个 TS 实际 HTML，记录展开、搜索、聚焦、过滤、计数、SVG 导出。浏览器阻断时保留 blocked，不用 jsdom 冒充真人浏览器体验，也不扩 scope 排查 Chrome。

**Acceptance:** 24类合同中支持与负例断言均符合预期；所选正边/引用全部核验正确，负例无误边；样本调查/效益门槛达成；P0/P1 为零；安装和 7 项 CI 有精确来源记录。否则继续定位实际阻断，不开始 J6。

## J6：正式支持晋级与发布闭环

**目标版本：** 0.6.0 基础正式支持，不等于支持所有 JS/TS 语法、框架或运行时关系。独立 alpha 发行是可选中间结果，不能代替本节完成定义。

- [ ] 主代理审查实际支持边界及确认集，核对源码、wheel、CI、测试收据；release checklist 必须列出未支持 CommonJS、JSX/TSX、别名及方法/回调的实际范围，不能只有“支持 JS/TS”一句话。
- [ ] 版本提升为 0.6.0 时同步 `_version.py`、两个安装验证器常量、README/Skill安装说明；两类安装的 metadata 保留三个 extra 条件依赖，不能套用 0.5.3 的“Requires-Dist为空”断言。
- [ ] 选择实际合适的集成 base，检查稳定修复是否完整包含；不把 JS 分支强行合入 codex/python-stable。0.5.3 维护线继续保留；正式统一主线的选择由主代理记录。
- [ ] 正式合并 SHA 的 7 项 CI 通过后，从该 SHA 构建正式 wheel；独立 base/extra 安装与 Python 生命周期通过。
- [ ] 发布正确 tag 的 GitHub wheel 与 SHA256SUMS；匿名下载后核对包 hash、版本、runtime 和一个 JS/一个 TS 实际入口。公开包与验收包一致方可复用安装结果。
- [ ] 先在独立本机 JS/TS 环境交付，普通 Python 稳定入口仍为 0.5.3。需要将全局入口升级到 0.6.0 时，在该部署范围获授权后备份并切换，保留已验证的 0.5.3 回滚包；不能现在预先切换。
- [ ] 交付两种明确安装方式：基础 wheel 与同一 wheel 的 `[js]` extra；文档给出语言 CSV、Codex调用、地图、未知关系和当前支持矩阵。
- [ ] 最终保护哈希一致；completion 必需项 pending=[]；准备/执行/公开安装/本机状态分开记录。GraphFlow 增量索引实际变动文件。

**发布闭环：** 可安装 → 可从真实仓库找符号取证 → 可看关系图 → 未知明确 → Python兼容 → 包/源码/CI来源一致 → 旧版本可回滚。不能仅以发布成功宣布闭环。

## 5. 停止重复验证的规则

| 事实目标 | 所需证据 | 停止条件 |
|---|---|---|
| a5 已有本机记录 | 原候选安装/试用收据 | 不为准备计划重跑 |
| 合同正确、没有造边 | 24类正负例及独立源码核对 | 所选场景符合预期，不追求更多测试数量 |
| 真实调查有效 | 12仓库36题；分语言支持内分母；定位动作对照 | 达到 J3 门槛，或记录具体阻断 |
| Python 不受影响 | 共享差异检查、现有兼容测试及 CI | 无回归，不默认跑 Python 120 仓库 |
| 三版本可安装 | 精确 SHA 的 7-job CI、base/extra独立包 | 全通过，无 skipped 冒充 JS 验证 |
| 人可查图 | 既有交互证据+字节一致性，或修改后的实际地图 | 不反复连接失效 Chrome |
| 新版本广泛覆盖 | 仅有具体分布风险时扩展80 JS/TS | 新候选新记录，不追加无目标200再跑 |

## 6. 当前计划自查与下一动作

- [x] 已核对真实版本、工作树、CLI、支持代码、安装验证器、CI及历史问题入口。
- [x] 已区分准备/执行/发布和当前支持/未知/未来拓展。
- [x] 已明确旧 holdout 已使用，不能再当新盲测。
- [x] 已定义具体案例、样本分层、源码参考、效益门槛、错误分类及停止条件。
- [x] 已承接 Python 0.5.3 的保护和回滚要求；没有改历史评分或主产品接口。
- [x] J0–J4 准备材料已构建并核验；补充断言任务逐项写入 cases.json，实际编写和首次运行均留在 J5。
- [ ] J5 按冻结合同开始定向产品验证，不将准备结果计为通过。

依据：无后缀和目录 index 的解析依赖运行时/编译配置，不能统一冒充 Node ESM 行为。参见 [TypeScript 模块引用](https://www.typescriptlang.org/docs/handbook/modules/reference.html#extensionless-relative-paths) 与 [Node ESM 扩展要求](https://nodejs.org/api/esm.html#mandatory-file-extensions)。本产品未来可单独定义保守源码关联，但要保留歧义和未知说明。
