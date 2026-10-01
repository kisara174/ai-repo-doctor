# AI Repo Doctor 基础版产品收尾执行计划

> **2026-10-01 执行入口调整：** 用户已授权按[稳定基础版指导清单](2026-10-01-basic-product-optimization-guide.md)继续执行。本文保留 C1–C4 实施细节与历史证据；C5 的实际使用和 C6 的正式交付对应新清单的剩余工作。当前状态以 R1–R5 为准，已完成任务不重复执行。

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` task-by-task. 主代理负责设计、排错、风险和验收；仅将文中已锁定的机械步骤按 AGENTS 路由给有界执行器。每项完成后更新复选框和交付记录。

**Goal:** 交付一个版本与入口一致、Codex 能按需调用、人能搜索查看和导出结构关系图的 Python 基础版，并明确每一条使用流程是否已闭环。

**Architecture:** 保留现有 Python AST、CLI JSON、Skill、快照与报告机制。仅修复 HTML 目录导航，统一主目录/安装包/文档，再用固定真实仓库走完整使用流程。详细分析与修复仍由 Codex 完成，页面只呈现结构关系。

**Tech Stack:** Python >=3.11，标准库与 setuptools；内嵌 SVG/JavaScript；Node 和已有 JSDOM 仅用于开发验证，运行依赖保持 `[]`。

**Spec:** [已批准的 P1–P6 目标](2026-10-01-codex-tools-repo-map-goals.md)，以及 2026-10-01 用户批准执行的历史回顾建议。用户已要求写计划并执行，无需再次审批同一范围。

## 全局约束与完成定义

- 人的产物：项目结构关系 HTML/SVG。Codex 的产物：结构、上下文、来源证据及必要的调查记录。
- 主要流程无需 DeepSeek Key，扫描不执行被扫描仓库代码。
- 不新增继承图、外部依赖图、MCP、多语言、运行时追踪、新模型评估或自动补丁系统。
- 使用同一候选源码；每个发行包以 SHA256 标识。版本维持 0.5.0，全部交付门槛通过前明确为候选。
- 保留已有文件、历史、Key 和客户端配置，不使用 `git reset --hard`、`git clean` 或覆盖未保存文件。
- 浏览器此前明确拒绝 `file://`。不得用 HTTP 代理、其他浏览器工具或间接执行绕过拒绝。原生打开/下载必须通过允许的操作或用户实际操作取得证据；不可用 DOM 检查替代。
- 未收到人工核对结果不能推定通过。相关门槛待确认时，完成其余工作、保存候选与待办；不合并或发布稳定版。
- 验证只覆盖本次导航缺陷、使用入口、安装资源和真实用户流程。既有测试/CI 是回归门槛，不追加大规模盲测。

完成画面：在主目录或普通终端使用一致版本；Codex 获取概览和带源码行的影响结果；人打开图后能找到目标目录、看局部关系、保存并重开 SVG；所有条件确认后整合发布。需要修复时，Codex 修改，Repo Doctor 记录明确选择的检查。

## 旧计划制定时的基线（历史）

以下版本与分支是 C1 开始前的状态，当前工作位置、版本与剩余任务见新的指导清单。

- 实施工作树：`/Users/kisara/.codex/worktrees/diagnosis-evaluation/AI Repo Doctor`。
- 复用分支和 PR：`codex/codex-tools-repo-map`、GitHub PR #30。
- 用户主目录：`/Users/kisara/Documents/ChatGPT/AI Repo Doctor`；当前源码 0.1.0，旧分支 `codex/repo-doctor-v2-design`。
- 主目录镜像分支：创建 `codex/local-product-closure`，来自本轮计划提交；最后仅快进至验收后的同一功能提交。
- 安装环境：`/Users/kisara/.local/share/ai-repo-doctor/venv`；入口 `~/.local/bin/repo-doctor`。
- 当前候选 0.5.0：功能提交 `be8ea19`；文档提交 `e25d3ed`；401 项 Python 测试与 Python 3.11–3.13、地图 DOM CI 已通过。
- Node：`/Users/kisara/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`。
- 已有 JSDOM：`/private/tmp/ai-repo-doctor-v050-check/dom-deps/node_modules/jsdom`；不存在时由主代理按已锁定开发工具版本恢复，执行器不安装依赖。

---

## C1：统一主目录，保留原有文档

**责任：** 主代理。涉及 Git 状态与用户文件，不委派执行器。

**范围：** 主目录 Git 分支；四份冲突文档的备份；外部保存目录 `~/.local/share/ai-repo-doctor/workspace-preservation/2026-10-01-product-closure/`。

- [x] 1. 提交本执行计划到复用的功能分支。检查主目录无已跟踪文件修改；若发现修改，先判断来源，不覆盖。
- [x] 2. 用 `git ls-files --others --exclude-standard -z` 与 `git ls-tree -r --name-only -z codex/codex-tools-repo-map` 求交集。当前交集为以下四份文档：
  - `docs/superpowers/plans/2026-09-24-post-v3-execution.md`
  - `docs/superpowers/plans/2026-09-24-post-v3-handoff.md`
  - `docs/superpowers/plans/2026-09-24-repo-doctor-v3.md`
  - `docs/superpowers/specs/2026-09-24-repo-doctor-v3-design.md`
- [x] 3. 为上述文件保存路径、字节数、SHA256、旧分支与旧 HEAD 的 `manifest.json`，将文件移动到外部保存目录的 `files/<相对路径>`；目标必须不存在。逐个核对哈希。任何失败停止切换并恢复已移动文件。
- [x] 4. 主目录执行 `git switch -c codex/local-product-closure codex/codex-tools-repo-map`。不要切换到已被另一工作树占用的同名分支，不使用强制选项。
- [x] 5. 从备份将四份原文复制回原位置，保留其内容；与新分支不同的内容作为用户本地修改保留，不加入本轮功能提交。`.graphflow-cache` 和 `graphflow-out` 不移动、不清理。
- [x] 6. 核对每份原文与备份的 SHA256 相等；在主目录运行 `python3 -B -m repo_doctor overview . --json`，再通过安装环境的 console script 读取同一仓库。二者应成功并具有相同源码指纹；`pyproject.toml` 和安装元数据均为 0.5.0。

**完成结果：** 主目录启动新命令，原文内容不丢失，旧分支和备份可恢复。Python 的当前目录优先加载规则保持正常，版本一致消除误用。

## C2：修复目录搜索、展开与定位

**Files:**
- Modify: `repo_doctor/resources/map/viewer.js`
- Modify: `tests/test_map_viewer.js`
- Modify: `tests/test_map_dom.js`
- Modify: `tests/make_map_fixture.py`

**接口约定：**
- 新增纯函数 `reveal(data, state, nodeId) -> newState`，在 `RepoMap` 开发检查接口导出。
- `state.target` 继续用于关系邻域；新增 `state.selected` 用于结构视图选中节点。
- `reveal` 打开目标目录和全部祖先，仅保留这条路径的展开状态；无关目录保持收起；关系 target 清空。
- `project` 限制仍为 200 节点/500 边。结构选中节点、祖先与目标的直接子节点先纳入预算，再填充其他节点并恢复层级顺序。
- 选中目录应高亮，并在渲染后将相机移到它的结构位置；目录搜索不能再次 toggle 将目标收起。重置清除选中状态。
- 文件和符号搜索仍进入现有关系邻域，保持文件聚合调用、符号真实调用和测试筛选行为。

- [x] 1. 先添加纯投影回归：嵌套目标目录展开、无关目录不展开；250 个根文件挤占视图时目标、祖先及直接子节点仍可见。使用真正的 `RepoMap` 函数，不能以模拟实现替代。
- [x] 2. 执行 Node 检查，确认在当前实现上失败；首先断言 `typeof scope.RepoMap.reveal === 'function'`，预期错误为目录 reveal 缺失。记录失败后再写生产代码。
- [x] 3. 主代理实现最小 reveal 和预算优先次序。例如：

```js
function reveal(data, state, nodeId) {
  const lookup=new Map(data.nodes.map(n=>[n.id,n]));
  if(!lookup.has(nodeId)) return state;
  const open=new Set(), expanded=[];
  for(let id=nodeId; lookup.has(id); id=lookup.get(id).parent) {
    const node=lookup.get(id);
    if(node.kind==='directory') open.add(id); else expanded.push(id);
  }
  return {...state, mode:'structure', target:null, selected:nodeId, expanded,
    closed:data.nodes.filter(n=>n.kind==='directory'&&!open.has(n.id)).map(n=>n.id)};
}
```

- [x] 4. 搜索目录采用 `reveal`，普通展开操作继续 toggle。用 `state.selected` 设置结构节点高亮；选中目录的相机 y 值根据节点位置和可见高度计算，原生渲染仍使用当前 SVG。
- [x] 5. 在 DOM 受控材料中加入 `pkg/deep/README.md` 和 `other/README.md`。它们是非 Python 文件，不改变现有文件关系测试。先添加目录搜索行为断言，确认旧页面失败；生成新页面后确认：选中 deep、显示其子文件、other 的子文件未出现、选中高亮、相机定位、导出 SVG 与当前图一致。
- [x] 6. 执行下列针对性检查，检查实际 diff 后提交修复：

```sh
NODE=/Users/kisara/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
"$NODE" tests/test_map_viewer.js
python3 -B tests/make_map_fixture.py /private/tmp/repo-doctor-closure-check/fixture
python3 -B -m repo_doctor map /private/tmp/repo-doctor-closure-check/fixture --out /private/tmp/repo-doctor-closure-check/dom-map
"$NODE" tests/test_map_dom.js /private/tmp/repo-doctor-closure-check/dom-map/map.html /private/tmp/ai-repo-doctor-v050-check/dom-deps/node_modules/jsdom
```

所有输出目录必须是新的；恢复执行时使用新目录名，不能为了重跑清空用户目录。

## C3：用真实用户问题确认实际用途

**范围：** 固定 `dbader/schedule` 仓库，只读源码；创建 `docs/delivery/2026-10-01-product-closure.md` 和外部使用记录。不得执行或修改目标仓库。

**材料：** `~/.local/share/ai-repo-doctor/evaluations/2026-09-30-schedule/repo`，修订 `82a43db1b938d8fdf60103bd41f329e06c8d3651`。

- [x] 1. 核对修订和目标仓库未修改。用户问题固定为：“定时任务检查从哪里进入，`Scheduler.run_pending` 如何推进到实际任务执行，改动它可能影响哪些已解析调用？”
- [x] 2. 使用已安装 Skill 的顺序，运行 `overview --json`、`symbols --query run_pending --json`，从真实搜索结果选择类方法 ID，再运行 `context --max-lines 120 --json`、`impact --depth 2 --json`。
- [x] 3. 如预算不足，只为回答该问题补充已返回或实际源码中的 `_run_job`、`Job.run`，保留每段路径/行号、被省略内容、无法解析的边；不凭名称补画调用关系。
- [x] 4. 写中文结论：入口、执行链、已解析影响、动态回调/外部调用的边界。记录用了哪些命令和内容预算，不声称节省某比例 token、时间或发现新 bug。
- [x] 5. 用最终安装包生成自身、schedule 总览，以及指定 `Scheduler.run_pending` 的局部图。保存到 `~/.local/share/ai-repo-doctor/maps/2026-10-01-product-closure/` 下的新子目录。

**完成结果：** 一次真实结构问题有可追溯答案和给人阅读的地图。问题不涉及缺陷时无需生成 issue；原有受控发现/修复记录作为记录机制证据，不重复模型评估。

## C4：安装与操作入口一致

**Files:** `README.md`、`docs/CODEX_AND_MAP.md`、`docs/PRODUCT_GUIDE.md`、本计划及交付记录；Mac 外部安装和保存目录。Python 版本仍为 0.5.0。

- [x] 1. README 首先说明新功能对应的 0.5.0 候选安装方式；将旧稳定 0.4.1 安装单独标为旧版本，不让用户装旧版后使用新命令。
- [x] 2. Mac 已部署用户的入口写为 `repo-doctor`；不要求重新配置 Key 或手动激活环境。说明从源码执行时使用当前主目录，避免在旧 checkout 构建旧包。
- [x] 3. 在中立目录完成候选 wheel 构建/安装。新包保存于 `~/.local/share/ai-repo-doctor/releases/v0.5.0-closure-candidate/`；旧候选原样保留。核对版本、包内 Skill/HTML/JS/CSS、无运行依赖和 SHA256。
- [x] 4. 新建干净验证环境安装同一 wheel，确认 import 来自 site-packages；通过安装入口读取真实仓库并生成地图。已有 Skill 未变时只核对一致性，不能覆盖其他 Skill 或配置。
- [x] 5. 更新 Mac 安装说明和本轮部署记录；记录新 wheel 路径/哈希、源码修订、Skill 路径、最终地图与尚待确认条件。旧稳定部署记录保留。
- [x] 6. 功能代码冻结后运行一次 Python 全套回归；重跑 Node/实际打包页面检查只为确认同一包具有本轮修复。之后仅为具体失败追加检查。

## C5：完成人的地图使用与新会话调用

- [ ] 1. 在允许的原生浏览器操作中打开最终 `map.html`，沿用户问题查看目录、选中路径和局部关系，保存当前 SVG，并重开下载文件。
- [x] 2. 浏览器限制仍存在时，将最终文件链接和具体操作一次性提供给用户，说明限制来源；等待其实际结果，同时推进不依赖该结果的 CI、文档和版本同步。不请求重复代码审阅。
- [ ] 3. 新 Codex 会话显式使用 `$repo-doctor` 完成同一结构问题；记是否按需调用工具。用户未明确要求新建聊天时不自行创建用户任务；提供可直接使用的简短提示。
- [ ] 4. 分别记录“Skill 已加载”“当前会话能调用”“新会话完整流程”“隐式匹配”四种证据。隐式匹配不是必然条件，不能把当前会话的手动工具调用算作全新会话验证。

**完成结果：** 人实际看图、导出重开；新会话可以重复调用。没有实际证据时保持相应步骤未勾选。

## C6：CI、源码同步与正式交付

**责任：** 主代理。提交、推送、整合与发布不委派执行器。

- [ ] 1. 检查 diff 仅含已授权修复、测试与本计划文档；提交并更新 PR #30，核对当前提交的 Python 3.11–3.13 和地图 CI。
- [ ] 2. 主目录执行 `git merge --ff-only codex/codex-tools-repo-map`，再次核对四份用户原文哈希和主目录/安装的版本及 CLI 结果；保留用户本地文档修改。
- [ ] 3. 刷新主目录 GraphFlow 索引并检查实际 root；若 MCP 仍忽略 root 不声称刷新成功，不为此修改无关服务器配置。
- [ ] 4. 当 C1–C5 必需条件全部通过：将 PR 转为可整合状态，核对基线与当前 CI，合并到实际默认分支 `codex/repo-doctor-v1`，取得实际合并提交，按该提交构建正式包并发布 v0.5.0。版本标签必须指向正式源码，不能直接使用未经核对的旧候选。
- [ ] 5. 下载/安装正式发行 wheel，核对资源与版本、打开已有报告，再同步主目录到正式提交；更新稳定版安装指令与交付状态。
- [ ] 6. C5 外部条件未确认时：完成步骤 1–3 和发布准备；保留草稿 PR，不标稳定、不创建稳定标签。最终明确列出已完成与剩余条件，不能以“所有测试通过”代替闭环结论。

## 已执行的有界执行器任务包：C2 的纯回归材料

以下任务包保留为历史。reveal 已实现，其 RED 合同只适用于修改前源码，后续不要重复派发。

### Objective

仅将主代理给出的固定目录导航断言插入 `tests/test_map_viewer.js`，取得预期失败证据；不实现功能。

### Allowed changes

只允许 `/Users/kisara/.codex/worktrees/diagnosis-evaluation/AI Repo Doctor/tests/test_map_viewer.js`。

### Forbidden changes

禁止生产代码、其他测试、依赖、Git 状态操作、发布、网络、配置、权限和其他目录；不得创建子代理。执行器不是独自在代码库中工作，不得回退其他人的修改。

### Exact steps

1. 在该文件最后的 `console.log` 之前插入主代理任务消息中给出的完整固定块。
2. 保留已有断言；不更名接口，不改变输入数据契约。
3. 运行下列 Validation 命令，返回 diff 与预期失败；实现由主代理接手。

### Validation

`/Users/kisara/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tests/test_map_viewer.js`，cwd 为实施工作树。当前生产代码未实现 reveal，期望退出 1，且断言消息为 `Directory search must expose the reveal operation`。该预期失败是材料的输出合同，不应由执行器修复生产代码。

### Expected result

只有指定测试文件变化；现有检查先通过，新目录检查按合同失败。主代理检查实际 diff 并重新运行后，才接受材料。

### Stop conditions

遇到歧义、文件范围外需求、非预期失败、兼容性/安全问题即停止。一次机械纠正仍无法得到输出合同则返回主代理，不扩大范围。

## 执行状态与证据

C 项复选框记录本次收尾的已发生步骤；当前总状态以新指导清单 R1–R5 和 `docs/delivery/2026-10-01-product-closure.md` 为准。新增真实问题先定位，只修复与目标流程有关的阻塞；已满足条件的部分不重复实施。

### 2026-10-01 C1/C2 实施记录

- 计划提交 `25d60eb`；主目录已切换至 `codex/local-product-closure`。四份原文复制回原位置，外部 `workspace-preservation/2026-10-01-product-closure/manifest.json` 保存旧分支、修订及 SHA256，核对一致。
- 主目录源码与安装入口 `overview` 结果相同，源码指纹 `21789fdc6f80213d110c3f98a4cc4ef7be8dd35fc6ce39d17b64126eea6da057`；源码版本 0.5.0，中立目录核对安装元数据为 0.5.0。
- Luna Max 仅插入既定纯回归块；主代理检查实际 diff 并重新运行，得到预期 reveal 缺失断言。DOM 旧页面也失败于“Directory search must open the selected directory”。
- 最小修复后纯投影与实际页面 DOM 均通过，包含 250 个根文件挤占预算、目录展开/高亮/定位、原有文件调用焦点与当前 SVG 序列化。RED/GREEN 输出保存于 `/private/tmp/repo-doctor-closure-check/`。

### C3/C4 实施记录

- 功能提交 `19dd92a`；代码冻结后 401 项 Python 回归一次通过。候选 wheel SHA256 `9f5491da5b76a75922803ec2b1baa770d122a049f6689884a0ff474a2a007129`；包资源及无运行依赖核对完成，同包在干净环境和 Mac 安装，实际打包页面 DOM/SVG 检查通过。
- schedule 修订 `82a43db1b938d8fdf60103bd41f329e06c8d3651`，结构问题输出与三份地图已保存。基础上下文 28 行，补充 Job.run 与模块入口后 59 行，均未耗尽 120 行预算。操作前后仓库状态相同。
- C5 已提供最终文件与明确步骤，等待用户实际结果；未绕过浏览器工具拒绝，未自行创建新会话。
- GraphFlow 增量索引返回 144 个文件、1824 个符号、2901 个引用；随后诊断确认 root 为主目录，索引缓存非过期。
