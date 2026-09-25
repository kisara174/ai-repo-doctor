# AI Repo Doctor 后续工作与 Luna Max 任务包

> For agentic workers: 本文是规划交付物，不是现在开始执行的授权。未来执行时，主代理先核对状态，一次只发一个满足范围限制的任务包；使用 subagent-driven-development / executing-plans 的适用流程，并在接受结果前使用 verification-before-completion。Luna 不负责选择下一项工作。

**Goal:** 收尾并发布现有诊断评估基础设施，补齐失败可解释性与结果可追溯性，最终取得可人工复核的真实诊断结果。

**Architecture:** 保留本地静态分析、受限上下文、云端诊断、证据校验、人工标注和离线评分的现有分层。先修复证据与交付缺口，再进行有预算的在线实验。不更换提供商、不扩建平台。

**Tech Stack:** Python 3.11–3.13；标准库；unittest；Git/GitHub Actions；现有 DeepSeek HTTP 客户端。

**Spec:** 已有 `docs/superpowers/plans/2026-09-24-post-v3-execution.md`、`docs/execution-status.md`、`docs/evaluations/2026-09-25-diagnosis-v1.md` 及当前实现。本文新增条目是后续计划，不代表已经实施或验证。

## Global Constraints

- 本次仅新增本文；不执行以下命令、不修改产品代码、不运行测试、不调用 API、不提交或推送、不创建子代理。
- 执行工作目录固定为 `/Users/kisara/.codex/worktrees/diagnosis-evaluation/AI Repo Doctor`。原目录 `/Users/kisara/Documents/ChatGPT/AI Repo Doctor` 不是本计划的修改目标。
- 所有下文相对路径均相对于上述工作目录；新建文件会明确标注。
- 主代理负责事实判断、设计、故障定位、安全边界、人工标注、审查、验收与发布。本文以 M 标识这些任务。
- L 标识可以机械执行的任务。只有这些完整任务包可交给 `luna_executor`，其模型为 Luna、推理级别为 max。一次最多一个，不让它接收整个项目后自行规划。
- 开始每次委派前读取最新核心周额度：`usedPercent > 90` 时，仅符合条件的机械工作按 `delegating-to-dsh-executor` 技能转给规定的 Harness；否则或周额度不可读时使用 Luna。不得把五小时额度当周额度。本文编写时不需要查询额度。
- Harness 必须使用规定的 `dsh-executor` 路径；写入必须由主代理审查任务包并明确传 `--mode bounded-write --approve-write`。仍不得处理秘密、网络、依赖、安全决策或发布。
- 不泄露 key，不读取/打印完整环境变量，不把 `.local` 请求/响应或凭据提交到 Git。
- 现有 key 报错即跳过的指令持续有效：不自动重试、不循环探测、不把离线测试变成真实请求。
- 保留历史 manifest、历史结果、已有本地改动。不得通过改 ground truth、放宽证据校验、删除失败记录让结果变好。
- 每项 L 任务失败后最多一次范围内的明确修正；仍失败就交还主代理。不要自行扩文件范围。

## 1. 当前事实与尚未完成的目标

### 1.1 已有功能：不要重复建设

1. Python 仓库静态扫描、符号与调用关系提取、有限框架语义支持。
2. 按目标符号生成受限源码上下文与调用证据。
3. DeepSeek JSON 诊断入口、输出结构与证据校验。
4. 固定样本准备、请求计划与哈希校验、顺序执行、失败停止。
5. 人工复核模板、确定性评分、JSON/Markdown 报告。
6. 离线基线与 challenge 数据集及重复扫描评估。

“已有”不等于“真实模型效果已验证”。

### 1.2 本次只读核对的状态

| 项目 | 事实 | 后续含义 |
| --- | --- | --- |
| 分支 | `codex/diagnosis-evaluation` | 本地尚无 upstream |
| HEAD | `fba3d86a1304923898e89e57404f827b0c67e695` | 执行前重新核对，不能假定永远不变 |
| 历史 PR | #6 已合并；head `3492deb7c9971c06da48477f2dff6a8836cf2226` | 不重建、不重复合并 #6 |
| 默认分支历史记录 | `codex/repo-doctor-v1` | 发布时重新读取远端默认分支 |
| 历史本地验证 | 合并后 229 tests；DeepSeek 15 tests | 本轮没有重跑，不是本轮通过证明 |
| #6 CI | Python 3.11/3.12/3.13，共六个成功 job | 覆盖 #6，不代表评估分支通过 CI |
| 真实诊断 | 计划 10 个样本，首个 provider_error，另外 9 个未发送 | 无有效响应，无质量结论 |
| 人工复核 | 当前模板零行 | 不得虚构 TP、FP 或召回率 |
| 失败请求费用 | usage 缺失 | 未知，不能写零费用 |

四个已有未提交文件必须保留：

- `docs/evaluations/2026-09-25-diagnosis-v1.md`
- `docs/execution-status.md`
- `docs/integration-notes.md`
- `docs/superpowers/plans/2026-09-24-post-v3-execution.md`

历史实验 analyzer：`5044a94b37631f19b8547ba568b235b4fa9e695f`。manifest SHA-256：`f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`。新 HEAD 不应直接复用旧计划重跑；新实验需重新冻结和审查。

### 1.3 具体缺口与代码依据

- README 仍称真实结果“待授权运行”，与已失败一次的事实不一致。
- `tools/diagnosis_runner.py::_client_error_status` 依赖错误字符串，runner 持久化通用错误，无法区分连接、超时、HTTP、响应格式问题。
- `repo_doctor/deepseek.py::complete_json` 使用无上限 `response.read()`；请求有 256 KiB 上限，但 wire payload 检查目前在客户端内部。
- `tools/diagnosis_data.py::_analyzer_commit` 仅取 HEAD；`tools/evaluate_baseline.py` 报告也未充分保证源码工作区干净。未提交实现可能被标为某个正式 commit。
- `tools/diagnosis_score.py::render_report` 没有醒目的“零成功响应”提示；耗时同时包含失败请求，当前 Latency 标签容易被理解为成功推理耗时。
- 同 checkout 的多个 case 重复 `build_index`，值得测量，但没有证据表明必须立刻缓存。
- `pyproject.toml` 仅打包 `repo_doctor*`。`tools.evaluate_diagnosis` 属于源码树工具，不能向 wheel 用户承诺安装后可直接使用。

## 2. 顺序、依赖与交付物

本计划共 **14 项：10 项主代理任务，4 项 Luna 机械任务**。P0 是收尾与正确性；P1 是可解释性与实验；P2 是测量后优化。

| ID | 优先级 / 执行者 | 工作 | 依赖 | 完成证据 |
| --- | --- | --- | --- | --- |
| M00 | P0 / 主代理 | 状态审计与建立交接基线 | 无 | 实际 HEAD、差异清单、历史证据归属 |
| L01 | P0 / Luna | README 状态和使用范围同步 | M00 | 仅 README diff + 文本验证 |
| L02 | P0 / Luna | 追加 CI 证据范围更正 | M00 | 三份文档追加相同事实块 |
| L03 | P1 / Luna | 评分边界测试 | M00 | 三个新增测试通过 |
| L04 | P1 / Luna | 报告提示与耗时标签 | L03 | 展示测试 + 原评分测试通过 |
| M01 | P0 / 主代理 | 评估分支独立验证与 PR 收尾 | L01–L04 | 该 PR 实际 head 的 CI |
| M02 | P1 / 主代理 | 结构化安全错误信息 | M01，或主代理建立独立基线 | 兼容测试、无原始错误泄露 |
| M03 | P1 / 主代理 | 请求预检与响应字节上限 | M02 | 边界测试、零调用预检证据 |
| M04 | P0 / 主代理 | 分析器版本与工作区一致性 | M01，或主代理建立独立基线 | dirty/HEAD 变更拒绝测试 |
| M05 | P1 / 主代理 | 新版本离线回归与发行候选 | M02–M04 | 新 SHA 下测试、静态评估、CI |
| M06 | 条件 / 主代理 | 单次真实诊断连通性实验 | M05、明确的当次网络授权 | 1 次调用结果，失败即停止 |
| M07 | 条件 / 主代理 | 冻结真实评估并人工评分 | M06 成功、评估授权 | 新计划、逐条复核、评分报告 |
| M08 | P2 / 主代理 | 测量准备阶段性能 | M05；不依赖 API 成功 | 耗时拆分、优化或不优化的决定 |
| M09 | P2 / 主代理 | 下一轮数据与产品规划 | M07，或明确记录其阻塞 | 有证据的优先级决策文档 |

推荐分批：A=M00/L01–L04/M01；B=M02–M05；C=M06–M07；D=M08–M09。C 被 key 阻塞时仍可完成 D 的离线测量与问题整理，不伪造真实评估结论。

## 3. 主代理任务定义

### M00 — 状态审计与交接基线

**目标：** 避免在错误 worktree、过期 HEAD 或未知改动上机械执行。

**读取范围：** Git 状态、上述四个文档、README、本文、适用 AGENTS.md。不读取 key 内容。

**步骤：**

1. 在指定 worktree 执行 `git status --short`、`git branch --show-current`、`git rev-parse HEAD`、`git diff --stat`、`git diff --check`。
2. 阅读四个现有 diff，逐项识别作者已有改动；不 restore、不 stash 覆盖、不 `git add .`。
3. 若 HEAD 与本文不同，主代理先重新确认 L 任务的旧文本和接口仍存在。机械任务不自行猜测迁移。
4. 保存交接记录到新建 `docs/evaluations/2026-09-25-handoff-audit.md`：实际 SHA、改动文件、历史验证时间/范围、未验证项、下一任务。
5. 把四份已有文档改动纳入主代理审核；不把未知改动自动视为通过。

**验收：** 文件范围明确，未丢失已有改动，历史 229 tests 与未来新验证分别记录，PR #6 CI 不被拿来替代本分支 CI。

### M01 — 当前评估分支交付与 CI

**范围：** 分支已有评估代码、四份已有文档、L 任务输出；必要时 `.github/workflows/ci.yml`。CI 属于主代理范围，不委派 Luna 修改 workflow。

**执行：**

1. 审阅实际 diff，确认没有 `.local`、秘密、目标仓库源码或响应日志被暂存。
2. 运行全量 unittest、compileall、两个 CLI 主入口 help，以及 `prepare`、`run`、`prepare-review`、`score` 的 help。只运行 help，不能去掉 `--help` 调用 `run`。
3. 当前 CI 已有 Python 3.11/3.12/3.13。只在缺少评估 CLI help 覆盖时补充这四条 smoke 命令；保持 action pins、权限、矩阵和依赖不变。
4. 逐个明确路径暂存并提交。读取实际远端默认分支与现有开放 PR；如已经有评估 PR，更新它而非重复创建。
5. 在当时有效授权范围内发布 PR；多行正文写入本地文件再用 `--body-file`。正文包含本地验证、在线失败限制、没有质量结论。创建后调用 attach_artifact。
6. 等待**新评估 PR 实际 head** 的 CI。记录 URL、head SHA、矩阵结果。若 merge/rebase 改变 head，旧 CI 不能冒充新 head 的验证。
7. 合并只有在当时授权覆盖时进行；本计划本身不执行发布。可继续离线 B 批，不为了等网络状态反复轮询。

**验收：** 评估代码在自己的 commit 上有可追溯验证；T8 的历史报告保留，新增交付状态与真实诊断状态分别描述。

### M02 — 安全且可解释的客户端失败

**范围：** `repo_doctor/deepseek.py`、`tools/diagnosis_runner.py`、必要的 `tools/diagnosis_score.py` / `tools/evaluate_diagnosis.py` 记录校验，以及对应现有测试文件。主代理先定位真实接口后确认修改范围。

**固定设计方向：**

- `DeepSeekError` 增加受控错误码和可选 HTTP status；兼容现有 `DeepSeekError("message")`，默认类别 unknown。
- 类别覆盖 timeout、connection、http、invalid_response、request_too_large、response_too_large、unknown；HTTP 状态保留整数，不从响应体推断余额或账户状态。
- 顶层 record.status 继续使用已有 success/provider_error/invalid_response。旧 schema1 文件继续可读；新增可选诊断字段只能存错误码、HTTP status。主代理明确 schema 兼容策略并给测试，不能依赖报错全文字符串分类。
- 不持久化 exception repr、URL/proxy 信息、headers、key、HTTP body 或任意提供商原文。
- 不改变失败停止、无自动重试语义；不把网络错误当成模型错答。

**测试矩阵：** 模拟 timeout、URLError、HTTP 401/429/500、响应非 JSON、缺 choices、length 截断、空 content、旧式 exception、自定义 unknown。验证分类、旧记录加载、首错停止及秘密哨兵不出现在输出/记录中。只用 mock。

**验收：** 可以判断故障类别，但不能从缺少证据的 401/429 等结果断言“key 一定错了”或“余额不足”。旧实验仍可离线评分。

### M03 — 有界传输与发送前预检

**范围：** `repo_doctor/deepseek.py`、`tools/diagnosis_data.py`、`tools/diagnosis_runner.py` 及对应测试。涉及安全边界，必须主代理实施。

**契约：**

1. 将实际 wire payload 的标准序列化形成单一内部实现；预检与真正发送使用相同字节构造，不要独立复制两份计算。
2. 保持现有 256 KiB 请求上限；UTF-8 字节数不是字符数。超过上限离线拒绝，不能先写“已尝试网络请求”再失败。
3. 增加 **2 MiB 响应体上限**，这是本项目提议的保护上限，不是对提供商规格的声明。按 limit+1 最多读取，超过则拒绝并关闭响应；不解析截断部分。
4. 冻结计划若必须改变 request hash 定义或新增强制字段，明确升级版本，拒绝混用；不能无声改变旧 schema1 的哈希含义。
5. 客户端仍保留自身上限检查，避免独立 diagnose 入口绕过保护。

**测试：** ASCII/多字节边界；上限与上限+1；mock response 检查 read 使用有限长度；超限响应被关闭；无 JSON decode；预检失败 transport 调用次数 0、无 inflight/attempt 记录；正常载荷保持行为。

**验收：** 不产生无限读；超限本地输入不占用网络尝试计数；旧计划兼容性有明确结果。测试 fixture 不分配异常巨量内存。

### M04 — 分析器 provenance 一致性

**范围：** `tools/diagnosis_data.py`、`tools/evaluate_baseline.py` 及对应测试；若需共用 helper，主代理先明确新文件名与接口，禁止执行者自行扩模块。

**主代理已确定的共享接口：** `tools/analyzer_provenance.py` 提供 `analyzer_snapshot(root: Path) -> tuple[str, bool]` 与 `require_clean_analyzer(root: Path, expected_commit: str | None = None) -> str`。前者返回完整 HEAD 和 dirty 状态，后者要求工作树 clean，并可校验预期 SHA。`tools/diagnosis_runner.py` 复用同一快照实现，避免 prepare、baseline、run 分别维护不同的 Git 状态规则。

**契约：**

- 正式 prepare/baseline 在生成前确认分析器 HEAD 与工作树状态可归因；未提交 tracked 修改和未忽略 untracked 源码导致拒绝。忽略目录 `.local` 不因此被清空或提交。
- 生成完成、发布正式文件前再次核对 HEAD/状态，防止生成途中切换版本。新输出失败时不得留下貌似有效的正式报告，不覆盖旧报告。
- 这只是对实验可追溯性的检查，不宣称能抵抗恶意并发修改。
- 不添加默认忽略 dirty 的开关；不把 dirty 源码伪装成某个 commit。
- 使用已有 runner 的检查模式时核对实际差异，不机械复制并造成三套互不一致规则。

**验证：** 临时 Git 仓库 fixture 覆盖 clean、tracked dirty、untracked source、ignored artifact、生成途中 HEAD 变化；确认失败发生在正式报告发布前。测试自身不能改实际项目 HEAD。

**验收：** clean commit 能复现；dirty 不会输出带干净 SHA 身份的正式结果。

### M05 — 新版本离线发行候选

**输入：** M02–M04 的审阅后 clean commit。

**步骤：**

1. 运行受影响定向测试，再运行一次全量 unittest、compileall、CLI help、diff-check。失败由主代理定位，不让 Luna 随机改实现。
2. 使用已有固定 baseline/challenge，各做 5 次扫描，产物置于新的 ignored 目录，不覆盖历史目录；命令参数以当前 `tools.evaluate_baseline --help` 与已有 runbook 为准，先在本地主代理记录实际完整命令。
3. 比较每个 probe 的 expected/predicted、TP/FP/FN、扫描统计和哈希稳定性。耗时单列；不要把 JSON hash 变化自动判定为语义回归，也不能忽略实际证据变化。
4. 对冻结诊断 manifest 做离线 prepare，并审查每份上下文。输出新计划，记录 analyzer/manifest/context/request 哈希。
5. 新建 `docs/evaluations/2026-09-25-hardening-offline.md`，记录命令、SHA、结果路径、差异与未完成在线项；发布代码时按 M01 的实际 head CI 规则。

**验收：** 原语义无未解释回归；新计划来自 clean commit；测试数使用真实结果，不能继续照抄 229。

### M06 — 最小真实连通性实验（有条件）

**只能主代理进行。** 本文不包含 key，也不安排 Luna 执行网络命令。

1. 先只检查 key 是否存在，不输出值。必要账户/账单核查由有权限者进行；已有 generic provider_error 不足以定位原因。
2. 执行前刷新官方接口、所选模型、价格信息；不要复制历史价格当现价。
3. 主代理选一个已有公开样本符号，生成并审查实际发送内容，固定模型、字节/源码/输出 token 限制、timeout 和单次调用预算。
4. 用普通 `diagnose` 做一次独立 smoke；它不是十样本评估结果。真实请求须有当次范围授权；若没有，任务标记待网络实验，继续离线任务。
5. 不把十样本 runner 的 `max_calls=1` 当作“只执行第一个”：现有预算校验可能拒绝整个计划。不得删除样本或破坏 bug/fixed 配对来绕过约束。
6. 调用一次；失败按受控类别记录并停止，不自动换模型/endpoint/代理/key。成功检查结构和证据，成功不等于诊断正确。

**验收：** 0 或 1 次实际发送数有记录；费用未知时写未知；失败不阻塞离线收尾；没有实际成功时不进入 M07 的批量请求。

### M07 — 新冻结计划、人工复核与真实质量报告

**输入：** M06 成功、M05 clean SHA、新请求计划、当次预算与网络授权。

1. 保留 `diagnosis-v1` 原始 manifest/标签；新建独立 plan/run 输出目录。主代理审查全部哈希和载荷，确认 ground truth 未送进模型。
2. 首轮 repeats=1，现有十样本最多十请求，失败即停；重复实验另行决策，不由循环脚本默认追加。
3. `prepare-review` 生成模板；主代理逐条依据目标版本源码与已验证 ground truth 标 TP/FP/uncertain/duplicate，不让 Luna 或同一模型自动充当事实裁判。
4. 用当前 CLI 的离线 score 命令重算 JSON/Markdown；缺失标注按现有校验拒绝或明确 partial，不补造标签。
5. 报告必须包含分子/分母、成功/失败/未尝试、grounding 与 correctness 区别、usage 缺失、实际请求耗时，以及配对/非随机样本/公开 issue 污染等局限。
6. 任何 prompt 修改用独立版本与新计划；不覆盖原结果，不把挑选的最好结果当全体结果。

**验收：** 每条结论能追到样本 commit、请求、有效响应、证据、人工标签；十个样本不支持“通用准确率”营销结论。

### M08 — 准备阶段性能测量与优化决定

**只先测量，不默认实施缓存。** 新建 `docs/evaluations/2026-09-25-preparation-performance.md`。

- 同环境、同 clean SHA、同样本集测 5 次；分别记录 checkout 验证、build_index、context 构造和总耗时，说明缓存冷热状态及计时方法。
- 优先调查同 checkout 多 case 重复 `build_index`，其次同文件邻居块重复读取。检查是否会改变每 case 的 fingerprint、路径限制、源码一致性。
- 只有测得明显占比且可保持正确性，才由主代理提出“单次 prepare 内按 checkout+commit 复用 index”的下一份设计；不做进程间或磁盘缓存。
- 候选优化必须满足相同输入的上下文/request hashes 与 probe 语义不变，或由主代理解释并审查每一变化。不能先承诺加速百分比。

**验收：** 输出“实施某项优化”或“不值得优化”的有数据决定；实现属于后续独立任务，不交给 Luna 自行选择缓存键。

### M09 — 下一轮样本与产品规划

**新建文档：** `docs/superpowers/specs/2026-09-25-next-iteration-candidates.md`。

- 基于 M07 真正出现的 FP/FN/uncertain 与 M08 数据排序；无真实响应时明确证据不足。
- 新外部仓库选择、许可证、修复 commit 与缺陷真实性由主代理调查。先提出最多两组新 bug/fixed pair 的候选，不自动纳入正式数据集。
- 对每个候选写来源、冻结方式、可执行验收、预计成本、是否需要 schema 变化；只在设计明确后形成新的机械任务包。
- 暂不建设 Web UI、多提供商路由、自动修复 PR、向量库、长期缓存、模型自动评分或依赖升级。用户新需求可改变范围，不能由执行者扩张。

**验收：** 排序依据是已观察问题；优化项没有被伪装成已经批准实现的需求。

## 4. 可直接交给 Luna Max 的机械任务包

以下代码只作为未来修改指令，本次不会运行。每次委派仅复制一个包；主代理另外附实际基线 SHA 与允许目录绝对路径。它不是让 Luna 解释需求的邀请。

### L01 — README 状态与源码工具说明

#### Objective

准确描述已失败的真实实验，以及源码评估工具的使用边界。

#### Allowed changes

仅 `README.md`。

#### Forbidden changes

其他文件、安装配置、API 参数、源码实现、历史评估结果、Git 提交/推送、任何网络或凭据操作。

#### Exact steps

1. 找到包含“该报告当前记录离线基础设施完成、真实模型结果待授权运行。”的句子，只把这句话替换为：

   `离线评估基础设施已完成；一次获批的真实运行在首个请求发生 provider_error 后停止，其余九个请求未发送。当前没有有效模型响应，因此尚不能得出诊断质量结论；失败请求的费用未知。`

2. 在“诊断评估”说明段后追加下面两段，不改命令示例：

   `评估命令 tools.evaluate_diagnosis 需要在本项目源码目录中执行；当前发行包仅包含 repo_doctor，不包含 tools。`

   `数据保存范围按命令区分：普通 diagnose 命令不保存请求、源码或模型响应；评估工具会把经审查的公开样本上下文、运行记录和评分产物写入指定的本地输出目录。实验产物使用被 Git 忽略的 .local 目录，不能把这些产物当作普通诊断命令的默认行为。`

3. 旧句不存在、出现多处，或 README 已表达更新事实时停止，由主代理判断是否已完成，不重复插入。

#### Validation

```sh
python3 - <<'PY'
from pathlib import Path
s = Path('README.md').read_text(encoding='utf-8')
assert '真实模型结果待授权运行' not in s
assert s.count('一次获批的真实运行在首个请求发生 provider_error 后停止') == 1
assert s.count('当前发行包仅包含 repo_doctor，不包含 tools') == 1
assert '失败请求的费用未知' in s
PY
git diff --check -- README.md
```

#### Expected result

仅 README 有预定文字改动；回传 diff 与验证退出码。不报告任何新 API 结果。

#### Stop conditions

定位不唯一、原文已变、需要改其他文件、验证修正一次仍失败。

### L02 — 补充 CI 证据范围

#### Objective

保留历史记录，同时消除“PR #6 成功等于评估分支成功”的歧义。

#### Allowed changes

仅 `docs/execution-status.md`、`docs/integration-notes.md`、`docs/superpowers/plans/2026-09-24-post-v3-execution.md`，均只在文件末尾追加。

#### Forbidden changes

改写既有段落、删除用户修改、改复选框状态、宣称新 CI 成功、运行 gh、修改报告或代码。

#### Exact steps

给每个允许文件追加一次相同块：

```markdown
## 2026-09-25 CI evidence scope clarification

PR #6 CI applies to PR head `3492deb7c9971c06da48477f2dff6a8836cf2226`. It does not validate the unpublished diagnosis-evaluation changes. The integrated evaluation branch has a historical local result of 229 passing tests; that result is not a fresh CI result. Before publishing or merging the evaluation changes, record the actual evaluation PR head SHA and its own Python 3.11/3.12/3.13 CI results. This clarification does not change the stopped live run or establish model quality.
```

若该标题已存在，停止并报告已存在，不增加第二份。不得把本文创建日期解释成 CI 已运行日期。

#### Validation

```sh
python3 - <<'PY'
from pathlib import Path
names = ['docs/execution-status.md', 'docs/integration-notes.md',
         'docs/superpowers/plans/2026-09-24-post-v3-execution.md']
for name in names:
    s = Path(name).read_text(encoding='utf-8')
    assert s.count('## 2026-09-25 CI evidence scope clarification') == 1, name
    assert 'It does not validate the unpublished diagnosis-evaluation changes.' in s, name
PY
git diff --check -- docs/execution-status.md docs/integration-notes.md docs/superpowers/plans/2026-09-24-post-v3-execution.md
```

#### Expected result

相对本任务起点，三个文件仅增加规定块；原有未提交 diff 完整保留。

#### Stop conditions

出现较新的实际评估 CI 记录、标题已存在、不能保证只追加、需要判断历史真伪。交给主代理更新任务，不自行改事实。

### L03 — 评分数学边界测试

#### Objective

补充全拒绝、仅 uncertain 和返回值独立性测试，不改变评分定义。

#### Allowed changes

仅 `tests/test_diagnosis_score_math.py`。

#### Forbidden changes

生产代码、指标公式、已有测试、依赖、网络、其他文件。

#### Exact steps

在现有 `DiagnosisScoreMathTests` 类中、文件末尾 `if __name__` 之前插入以下三个方法。沿用已有 imports 与 `make_counts`，不要新增 helper。

```python
    def test_all_rejected_findings_keep_precision_undefined(self):
        counts = dict.fromkeys(make_counts(), 0)
        counts.update(rejected_count=2, successful_bug_cases=1,
                      all_requested_bug_cases=1)
        metrics = calculate_repeat_metrics(counts)['metrics']
        self.assertIsNone(metrics['precision'])
        self.assertEqual(metrics['recall'], 0.0)
        self.assertEqual(metrics['end_to_end_detection'], 0.0)
        self.assertEqual(metrics['grounding_rate'], 0.0)
        self.assertEqual(metrics['uncertain_rate'], 0.0)
        self.assertEqual(metrics['duplicate_rate'], 0.0)
        self.assertIsNone(metrics['control_false_alarm_rate'])

    def test_uncertain_only_is_not_counted_as_false_positive(self):
        counts = dict.fromkeys(make_counts(), 0)
        counts.update(accepted_count=2, uncertain=2,
                      successful_bug_cases=1, all_requested_bug_cases=1)
        result = calculate_repeat_metrics(counts)
        self.assertIsNone(result['metrics']['precision'])
        self.assertEqual(result['metrics']['grounding_rate'], 1.0)
        self.assertEqual(result['metrics']['uncertain_rate'], 1.0)
        self.assertEqual(result['metrics']['recall'], 0.0)
        self.assertEqual(result['counts']['accepted_fp'], 0)

    def test_returned_counts_do_not_alias_caller_counts(self):
        counts = make_counts()
        result = calculate_repeat_metrics(counts)
        result['counts']['accepted_tp'] = 99
        self.assertEqual(counts['accepted_tp'], 1)
        counts['accepted_fp'] = 88
        self.assertEqual(result['counts']['accepted_fp'], 1)
```

#### Validation

```sh
python3 -m unittest discover -s tests -p 'test_diagnosis_score_math.py' -v
git diff --check -- tests/test_diagnosis_score_math.py
```

#### Expected result

新增 3 项测试通过；原有 4 项保持通过。若起点已新增其他测试，以实际清单为准，不删测试来凑 7。

#### Stop conditions

接口不匹配、重复测试名、任何断言失败且不是插入/缩进错误。不得修改公式让测试通过。

### L04 — 零成功响应提示与耗时说明

#### Objective

仅优化 Markdown 报告的解释文字，不改 JSON、评分或执行语义。

#### Allowed changes

`tools/diagnosis_score.py` 中 `render_report`；新建 `tests/test_diagnosis_report_presentation.py`。

#### Forbidden changes

其他函数/文件、记录 schema、评分计算、网络、实际实验结果、CLI 参数。

#### Exact steps

1. 在 `render_report` 的初始 `lines = [...]` 结束后、`labels = {...}` 前插入：

```python
    summary = report['totals']
    if summary['completed_calls'] - summary['failed_calls'] == 0:
        lines.extend([
            'No successful model response was recorded; quality conclusions are unavailable.',
            '',
        ])
    elif report['run_state'] != 'complete':
        lines.extend([
            'This run is partial; unattempted requests are reported separately.',
            '',
        ])
```

2. 仅在此函数里把两个 `Latency median:` 文本替换为 `Request elapsed median (including failed calls):`。不改字段名与数值。
3. 新建测试文件，内容如下。它构造展示层 fixture，不声称是实际运行报告。

```python
import copy
import unittest

from tools.diagnosis_score import render_report


def presentation_fixture(completed, failed, state):
    keys = ('precision', 'recall', 'end_to_end_detection', 'grounding_rate',
            'control_false_alarm_rate', 'uncertain_rate', 'duplicate_rate')
    repeat = {
        'repeat_index': 1,
        'metrics': dict.fromkeys(keys, None),
        'metric_inputs': {k: {'numerator': 0, 'denominator': 0} for k in keys},
        'counts': dict.fromkeys(('accepted_count', 'rejected_count', 'uncertain',
                                'duplicate', 'rejected_true_positive'), 0),
        'samples': {'requested_bug_case_ids': [], 'detected_bug_case_ids': []},
        'latency_median_seconds': 2.0 if completed else None,
        'latency_values_seconds': [2.0] * completed,
        'missing_usage_records': completed,
        'observed_token_totals': {},
        'request_details': [],
    }
    repeat['counts']['failed_calls'] = failed
    return {
        'schema_version': 1, 'dataset_id': 'presentation-fixture',
        'manifest_sha256': 'a' * 64, 'plan_sha256': 'b' * 64,
        'analyzer_commit': 'c' * 40, 'requested_model': 'fixture',
        'response_models': ['fixture'] if completed > failed else [],
        'case_count': 2, 'case_ids': ['one', 'two'], 'repeats': 1,
        'run_state': state, 'by_repeat': [repeat], 'limitations': ['Fixture only.'],
        'totals': {
            'planned_calls': 2, 'attempted_calls': completed,
            'completed_calls': completed, 'failed_calls': failed,
            'unresolved_calls': 0, 'not_attempted_calls': 2 - completed,
            'call_failure_rate': failed / completed if completed else None,
            'call_failure_rate_inputs': {'numerator': failed, 'denominator': completed},
            'missing_usage_records': completed, 'observed_token_totals': {},
            'latency_median_seconds': 2.0 if completed else None,
        },
    }


class DiagnosisReportPresentationTests(unittest.TestCase):
    def test_no_success_is_explicit_for_unattempted_and_failed_runs(self):
        for completed, failed in ((0, 0), (1, 1), (2, 2)):
            with self.subTest(completed=completed):
                report = presentation_fixture(completed, failed, 'partial')
                text = render_report(report)
                self.assertIn('No successful model response was recorded; '
                              'quality conclusions are unavailable.', text)

    def test_partial_success_is_distinguished_from_no_success(self):
        text = render_report(presentation_fixture(1, 0, 'partial'))
        self.assertIn('This run is partial; unattempted requests are reported separately.', text)
        self.assertNotIn('No successful model response', text)

    def test_complete_success_has_no_partial_or_failure_banner(self):
        text = render_report(presentation_fixture(2, 0, 'complete'))
        self.assertNotIn('No successful model response', text)
        self.assertNotIn('This run is partial;', text)

    def test_elapsed_label_covers_repeat_and_totals_without_mutating_report(self):
        report = presentation_fixture(1, 1, 'partial')
        before = copy.deepcopy(report)
        text = render_report(report)
        self.assertEqual(text.count('Request elapsed median (including failed calls): 2.0000'), 2)
        self.assertNotIn('Latency median:', text)
        self.assertEqual(report, before)


if __name__ == '__main__':
    unittest.main()
```

#### Validation

```sh
python3 -m unittest discover -s tests -p 'test_diagnosis_report_presentation.py' -v
python3 -m unittest discover -s tests -p 'test_diagnosis_score*.py' -v
git diff --check -- tools/diagnosis_score.py tests/test_diagnosis_report_presentation.py
```

#### Expected result

展示测试 4 项通过；原评分测试通过；只有指定函数文字和新测试改变；输入报告不被修改。

#### Stop conditions

字段/函数已变化、测试文件已存在、需要改计算或 schema、任何非插入错误导致测试失败。不得自动更新 snapshot 掩盖差异。

## 5. 优化清单：哪些现在做、哪些等证据

| 方向 | 当前安排 | 明确收益 | 边界 |
| --- | --- | --- | --- |
| 文档状态一致 | L01/L02 | 不把失败说成未运行，不混用 CI | 不新增质量宣称 |
| 评分边界覆盖 | L03 | 防止 uncertain / rejected 被误解 | 不改指标数学 |
| 结果可理解性 | L04 | 清楚显示零成功与失败耗时 | JSON 保持兼容 |
| 故障可定位 | M02 | 区分受控错误类别 | 不保存敏感原文 |
| 资源有界 | M03 | 避免无限响应读取；提前拒绝超限请求 | 无自动分片/自动重试 |
| 可复现性 | M04 | SHA 对应实际分析代码 | 不把 dirty 状态隐藏 |
| 准备速度 | M08 | 测量重复索引成本 | 测量后才决定缓存 |
| 数据广度 | M09 | 降低只熟悉少数仓库的问题 | 真实标签由主代理判断 |
| Prompt 质量 | M07/M09 后 | 针对已观察 FP/FN 单变量比较 | 不凭感觉大改 prompt |
| 安装体验 | L01 先说明实际范围 | 避免 wheel 用户找不到 tools | 是否打包 tools 另做设计 |

不设未经测量的性能指标，不把“测试更多”当成果，不安排简单模型自行选择架构。

## 6. 执行记录、验收与交接规则

### 6.1 每个任务的完成记录

主代理将记录追加到 M00 的 handoff-audit 文档；Luna 不被授权修改它。

- Task ID / 开始和结束时间。
- 实际 executor（主代理、Luna Max 或符合额度规则的 Harness）。
- 起点 HEAD、允许路径、已有 dirty 文件。
- 实际改动路径及 diff 摘要。
- 完整验证命令、退出码、真实测试数量与失败信息。
- 主代理重新检查实际 diff、重新运行独立 validator 的结果。
- 状态：未开始 / 进行中 / 待主代理复核 / 完成 / 阻塞。
- 阻塞原因及下一个可独立执行任务。

不以代理说“完成”代替验证；不以旧测试结果代替新增代码测试。

### 6.2 发给后续主代理的启动指令

> 读取本计划、适用 AGENTS.md 和当前 Git 状态。只从 M00 开始，不重建项目。你负责决策、调试、验收和发布。L01–L04 一次只委派一个完整任务包，使用额度规则选择执行器，Luna 使用 luna_executor（Max）。不得把 M 任务交给 Luna。保留四个已有文档改动与历史实验。每项通过实际 diff 和新验证后才更新状态。key/API 失败立即停止在线部分并继续独立离线工作；不自动重试、换提供商或伪造质量结论。发布和在线实验按当时有效授权执行。

### 6.3 阶段完成标准

**A 完成：** 文档真实；新增测试与展示改动审阅通过；评估分支有自身 CI 或明确记录尚待远端验证，不能假称已发布。

**B 完成：** 受控错误、字节限制、provenance 检查均有 mock/本地测试；新 clean SHA 下离线回归可复现；所有实际回归已解决或明确阻塞。

**C 完成：** 有有效响应、人工复核、可追溯报告才称“真实评估完成”。若仍 provider_error，称“在线实验阻塞；离线设施完成”，不是项目质量已达标。

**D 完成：** 有性能数据与下一轮候选决策；无需为了完成 D 强行实现缓存或增加样本。

### 6.4 本文自查范围

本文针对读取到的代码与本地状态编写。只有 L01–L04 是可直接机械实施的固定任务；M02–M04 等涉及安全与兼容性的任务有明确验收契约，但仍由主代理负责细化内部实现。没有把尚需工程判断的事项包装成 Luna 可盲做的工作。本文中的测试代码和命令尚未运行，未来执行必须验证。
