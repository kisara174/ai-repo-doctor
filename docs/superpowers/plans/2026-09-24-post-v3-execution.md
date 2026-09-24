# AI Repo Doctor：V3 合并后的完整执行计划

> For agentic workers: Use executing-plans to execute one checked task at a time. 本文是一份待执行的计划，不代表任何新增功能已经实现。主代理负责判断；简单模型只能领取已明确边界的任务。不要默认创建子代理。

**Goal:** 将已有代码统一为可回归验证的基线，建立真实 DeepSeek 诊断评估，得到可审计的质量报告，再依据证据决定下一轮功能。

**Architecture:** 保留本地扫描、上下文与证据校验；复用现有 DeepSeek 客户端。新增独立评估工具，分为离线 prepare、显式联网 run、离线人工复核与 score 四步。CI 只运行离线测试。

**Tech Stack:** Python 3.11+、标准库 unittest/urllib/json/hashlib、Git、GitHub Actions；不增加运行时依赖。

**Spec:** 既有 docs/superpowers/specs/2026-09-24-repo-doctor-v3-design.md；新增需求以本文“固定设计和数据契约”为准。本次用户授权编写计划；实施、上传源码、付费调用和发布的授权分别按下文记录。

## 0. 执行者先读：实际状态与范围

核查日期：2026-09-24。以下是核查时的事实，执行时要重新读取远端：

| 内容 | 已知位置 / 提交 | 注意事项 |
|---|---|---|
| GitHub | kisara174/ai-repo-doctor | 已有公开仓库，不新建仓库 |
| 默认分支 | codex/repo-doctor-v1，aa2a84243fe122a2b7a89b955598b039fcc62345 | 名字叫 v1，但已经含 V2 合并 |
| V3 合并结果 | codex/repo-doctor-v2-design，a61f6fb4dd28e342d3b6550ef257f64d6b402010 | PR #5 已合并，但不在默认分支 |
| 已有评估与显式 Click 注册 | codex/explicit-add-command-registration，341c3ffa9cfe4c2a40a61e9ccf5b7139dd03b8cc | 含 baseline/challenge 清单、工具和回归测试 |
| 原始工作目录 | /Users/kisara/Documents/ChatGPT/AI Repo Doctor | 本地基线仍旧；有未跟踪的 V3 计划和规格，不能直接 pull 覆盖 |
| V3 工作目录 | /Users/kisara/.codex/worktrees/repo-doctor-v3/AI Repo Doctor | V3 实现曾通过 93 项测试；不代表包含此前所有评估功能 |
| CI | PR #5 未报告 checks | 不能把“无 checks”写成 CI 通过 |
| 模型诊断效果 | 尚未进行真实 API 评估 | mock 测试只证明程序流程，不证明诊断质量 |

**本轮终点：** 统一基线、离线 CI、冻结诊断样本、可复现评估工具、获授权后的真实实验、人工复核报告和下一轮决策。UI、自动补丁、多 provider、大批量扫描不在这轮实施范围内。

**不要将所有任务交给受限 Luna executor。** 按 AGENTS.md，合并冲突、网络、密钥、依赖、工作流权限、真实缺陷判断、指标解释、发布均由主代理或人工负责。简单模型可作为受监督的执行者；它不自动获得 Luna/Harness 被禁止的权限。可委派任务仍须先读取 weekly quota，再按 AGENTS.md 路由。

## 1. 固定设计和数据契约

### 1.1 全局约束

- 一个任务一个提交；完成任务后必须检查真实 diff 和新鲜验收结果。
- 以最终统一分支的完整测试集为基线，不把 93 当作未来的固定总数。
- 保留 scan schema_version=2 的 V2 语义关系；diagnose 结果继续使用现有 schema_version=1。不得用复制旧 cli.py 的方式集成。
- 不修改或覆盖 evaluation/baseline-v1.json、challenge-v1.json、challenge-v2.json 和既有历史报告。
- 固定 endpoint、120 行、64 KiB 源码、60 秒 timeout、4096 max_tokens、不重试等 V3 约束继续适用。
- 目标仓库只读；不安装其依赖，不运行其代码或测试。测试只使用自己写的最小 fixture。
- API Key 仅从环境变量读取；不索要用户把密钥贴进聊天；不读其它项目的密钥文件。
- 评估工具允许显式保存所选公开上下文及 findings，这是独立工具的新行为；原 diagnose 命令仍不自动落盘。仅在已审核上传材料目录中保存，默认不提交 Git。
- 测试/CI 不使用真实 API；联网模式必须有显式开关和一次性执行授权。授权给定模型、样本、次数/费用范围后，不重复询问同一动作。
- 模型 ID 与价格属于执行时外部事实。必须由主代理核对官方文档，记录来源和日期，不把当前默认 deepseek-flash 当成永久可用保证。
- 不伪造真实缺陷、SHA、价格、测试通过、人工审核或 live 结果。缺失值写 null 或 pending，并停止依赖它的步骤。

### 1.2 工作流和文件布局

执行顺序：T0 统一基线 → T1 CI → T2 样本冻结 → T3 prepare → T4 客户端 usage → T5 run → T6 review/score → T7 联网实验 → T8 报告与交付。
T6 的合成评分测试可在 T5 后离线完成；T7 必须等 T2–T6 全部通过。

新增文件：

~~~text
evaluation/diagnosis/manifest-v1.json          冻结样本、来源、标签、行指纹
evaluation/diagnosis/README.md                 数据来源与执行说明
tools/diagnosis_data.py                        manifest 校验与上下文准备
tools/diagnosis_runner.py                      授权、配额、单次请求、结果落盘
tools/diagnosis_score.py                       人工复核表校验与纯函数计分
tools/evaluate_diagnosis.py                    四个子命令的薄 CLI
tests/test_diagnosis_data.py
tests/test_diagnosis_runner.py
tests/test_diagnosis_score.py
tests/test_diagnosis_evaluation_cli.py
.github/workflows/ci.yml
.local/diagnosis/<run-id>/                     被忽略的计划、记录、复核和报告
~~~

修改范围：repo_doctor/deepseek.py、tests/test_deepseek.py（仅 usage）；.gitignore；README.md；各任务明确列出的文档。不要重构既有扫描器、graph.py、parser.py 或旧评估器。

### 1.3 Manifest 契约

顶层：schema_version=1，dataset_id="diagnosis-v1"，cases 数组。
每个 case：

| 字段 | 类型 / 约束 |
|---|---|
| id | 唯一非空字符串，只允许 ASCII 字母数字、下划线和连字符 |
| pair_id | bug/fixed 共用 ID，普通对照为 null |
| repository_url | 审阅过的公开 HTTPS GitHub 仓库地址 |
| checkout_id | 安全目录名；每个不同 commit 使用独立 checkout，不允许路径分隔符 |
| commit | 完整 40 位 Git SHA |
| symbol | 实際扫描确定的 file.py::qualified.name |
| label | bug / fixed / control |
| issue_id | bug/fixed 使用同一个问题 ID；control 为 null |
| source | file、start_line、end_line、sha256；相对路径，行数正整数，end>=start |
| ground_truth | 解释触发条件、观察到的失败、修复语义、可接受的命中描述与不计命中的描述 |
| references | issue/修复 PR/提交的永久链接数组 |
| annotation | reviewer 非空、reviewed_at ISO 时间、status="approved" |

source.sha256 的唯一算法：用 tokenize.open 读取文件，splitlines 后取包含端点的行，使用 LF 连接、末尾不加换行，再编码 UTF-8 求 SHA-256。与已有 source_fingerprint 对照，不另外发明算法。

校验时拒绝布尔值冒充整数、重复 ID、未知 label、空理由、缺失 reviewer、路径逃逸、符号歧义、错误 SHA。真实清单不允许示例 SHA。测试数据可使用构造的固定 SHA，但必须创建对应 fixture 或 mock Git 检查。

### 1.4 Prepared plan / 请求隔离

prepare 输出到一个不存在的目录，包含 plan.json 和以 case ID 命名的 context JSON 文件。
plan.json 顶层：schema_version=1、dataset_id、manifest_sha256、analyzer_commit、python_version、requested_model、max_lines、cases。
每个 prepared case：id、repository_url、commit、symbol、context_file、context_sha256、source_lines、source_bytes。

context_file 只包含 build_diagnosis_prompts 的 user JSON 中实际允许的字段：symbol、blocks、call_evidence。它不能包含 label、issue_id、ground_truth、references 或 reviewer。system prompt 固定复用 V3，不加入真实标签。

context_sha256 = sha256(json.dumps(context_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))。
请求指纹还应覆盖 system_prompt、user_prompt、requested_model、max_tokens=4096、stream=false、response_format，以同一 JSON 规范化算法计算。

离线 plan/review 输出允许标签与元数据；模型请求仅能看到 allowlist 字段。prepare 不读取密钥、不联网、不执行目标项目。

### 1.5 Run record 契约

每次实际调用生成单独 JSON：case_id、repeat_index（从 1 开始）、request_sha256、context_sha256、analyzer_commit、target_commit、requested_model、response_model、started_at、elapsed_seconds、status、usage、accepted、rejected、error。

status 为 success / provider_error / invalid_response；error 只用工具自定义的短错误类别，不保存原始异常、Authorization、环境变量或 HTTP body。usage 只允许 prompt_tokens、completion_tokens、total_tokens，缺失或非法值记 null。服务方未返回有效 usage 时，不猜数值、不把 null 当零费用。

延迟用 time.perf_counter 测量调用，不包含 clone/扫描。运行记录可保留 findings，不能保留完整原始 provider envelope。离线错误记录不等于 provider 调用成功。

实验目录必须包含 run.json：schema_version=1、dataset_id、manifest_sha256、plan_sha256、analyzer_commit、requested_model、repeats、max_calls、planned_calls、attempted_calls、completed_calls、state 和 record_files。state 为 running / complete / partial，record_files 只允许本目录内相对路径。评分从这里读取记录；不得扫描任意外部目录。run_cases 返回同样的 summary 字典。

同一输出目录不得重用；不得默默 resume。崩溃留下 partial 状态，主代理根据已有调用记录决定是否另开实验；不能自动重发可能已经计费的请求。

### 1.6 人工复核与指标

prepare-review 为每个 success record 的 accepted 和 rejected finding 生成一行：case_id、repeat_index、bucket、finding_index、verdict、matched_issue_id、rationale、reviewer。verdict 初始 pending；人工填写 tp / fp / uncertain / duplicate。额外 duplicate 必须指定其 canonical finding，不能指向另一个 duplicate。

必须复核所有 finding。匹配以根因、触发条件和结果为依据，不能用标题相似度或模型自己判断代替人工。grounded 不等于正确。fixed/control 只表示已知问题修复或未标注，不代表没有其它缺陷；发现额外真实问题先标 uncertain，由主代理裁决并新建数据集版本，不能倒改本轮标签提高分数。

评分输出约定：顶层 schema_version=1、dataset_id、manifest_sha256、by_repeat、totals、limitations。每个 by_repeat 元素包含 repeat_index、counts、metrics。counts 的字段为 accepted_tp、accepted_fp、uncertain、duplicate、accepted_count、rejected_count、detected_known_bug_cases、successful_bug_cases、all_requested_bug_cases、successful_control_cases_with_accepted_fp、successful_fixed_and_control_cases、failed_calls、rejected_true_positive。metrics 使用下面公式中的五个名称。totals 仅汇总请求/资源数量，不把多轮结果冒充独立 case。

核心指标：

~~~python
def ratio(numerator, denominator):
    return numerator / denominator if denominator else None

# 以下统计在人工复核完成后计算；pending 会使 score 退出 2。
precision = ratio(accepted_tp, accepted_tp + accepted_fp)
recall = ratio(detected_known_bug_cases, successful_bug_cases)
end_to_end_detection = ratio(detected_known_bug_cases, all_requested_bug_cases)
grounding_rate = ratio(accepted_count, accepted_count + rejected_count)
control_false_alarm_rate = ratio(successful_control_cases_with_accepted_fp,
                                 successful_fixed_and_control_cases)
~~~

- 同一个 case/repeat/issue 的多个发现只能命中一次；额外 finding 单列 duplicate。
- uncertain 不计入 TP/FP，但必须展示数量及其占比；precision 必须标注“排除 uncertain/duplicate 后”。
- provider_error/invalid_response 不算“没有缺陷”，显示调用失败率；条件 recall 和端到端检出率同时报告。
- rejected findings 即使人工认为根因正确，也不能算 accepted_tp；单列 rejected_true_positive 诊断证据门禁损失。
- 每次 repeat 分别报告；重复请求不是新增独立样本。bug/fixed 配对也不是独立随机抽样。
- 10 个定向样本只做探索性评估，不声称总体质量达标，不推导商业可靠性。

## 2. 任务 T0：统一基线（主代理执行）

**允许修改：** 新集成 worktree 中的合并冲突文件、docs/integration-notes.md。原工作目录及旧评估报告不得修改。
**目标：** 默认分支来源、V2 语义、旧评估、V3 diagnose 同时存在。

- [x] 在原目录执行以下只读检查，保存当前 SHA、未提交状态和 worktree 列表：

~~~bash
git status --short --branch
git worktree list
git ls-remote --heads origin
gh repo view --json defaultBranchRef
gh pr view 5 --json state,mergeCommit,baseRefName
~~~

- [x] git fetch origin 后核对第 0 节三个固定 SHA 都存在。若远端增加了新提交，先记录变更，由主代理决定新起点；简单模型不得自动 reset 或覆盖。
- [x] 用原生 worktree 工具从核查后的默认分支建立隔离目录，分支名 codex/post-v3-integration；工具不可用时使用下列命令。目标目录必须不存在：

~~~bash
git worktree add -b codex/post-v3-integration ../AI-Repo-Doctor-post-v3 aa2a84243fe122a2b7a89b955598b039fcc62345
cd ../AI-Repo-Doctor-post-v3
git merge --no-ff 341c3ffa9cfe4c2a40a61e9ccf5b7139dd03b8cc
git merge --no-ff a61f6fb4dd28e342d3b6550ef257f64d6b402010
~~~

新 worktree 不会自动包含原目录未跟踪的本计划。进入新 worktree 后，将原目录中 2026-09-24-post-v3-execution.md 和 2026-09-24-post-v3-handoff.md 复制到相同相对目录；源文件保留。目的文件若存在，先比较 SHA-256，相同则复用，不同则交主代理处理，不覆盖。将两份计划作为集成说明文档提交。

每个 merge 单独执行并检查返回码；有冲突立即交主代理，不能继续下一条命令。不得整文件选 ours/theirs。重点保留 CLI 的 V2 semantic 输出与 V3 diagnose dispatch。**已完成：** 两个冲突集均由主代理逐项审阅并整合，结果见 `docs/integration-notes.md`。

- [x] 全量测试和语法检查：

~~~bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q repo_doctor tools
python3 -m repo_doctor --help
python3 -m repo_doctor scan . --json > /tmp/repo-doctor-integrated-scan.json
python3 -c 'import json; d=json.load(open("/tmp/repo-doctor-integrated-scan.json")); assert d["schema_version"] == 2'
python3 -m repo_doctor diagnose --help
git diff --check
~~~

- [x] 依 evaluation/README.md 准备 Click、Requests、Flask 的固定 checkout。确认公开源码克隆获当前会话授权；不执行源码。旧三套评估输出写 /tmp 下新文件，不能覆盖历史结果：

~~~bash
export BASELINE_CHECKOUTS=/tmp/ai-repo-doctor-checkouts
python3 tools/evaluate_baseline.py --repos-root "$BASELINE_CHECKOUTS" --manifest evaluation/baseline-v1.json --runs 5 --json-out /tmp/post-v3-baseline.json --markdown-out /tmp/post-v3-baseline.md
python3 tools/evaluate_baseline.py --repos-root "$BASELINE_CHECKOUTS" --manifest evaluation/challenge-v1.json --runs 5 --json-out /tmp/post-v3-challenge-v1.json --markdown-out /tmp/post-v3-challenge-v1.md
python3 tools/evaluate_baseline.py --repos-root "$BASELINE_CHECKOUTS" --manifest evaluation/challenge-v2.json --runs 5 --json-out /tmp/post-v3-challenge-v2.json --markdown-out /tmp/post-v3-challenge-v2.md
~~~

- [x] 检查退出码、每个探针预测、哈希重复一致性和旧指标。耗时/机器字段不要求相等；预测变差必须调查，不能重写历史预期。
- [x] 写 integration-notes：来源 SHA、冲突决策、测试总数、三份新结果位置、与旧结果的差异。

**验收：** 两套功能的测试同时存在且通过；三个固定评估无无法解释的退步。
**停止：** 冲突无法判定、旧评估快照无法取到、测试语义矛盾。禁止简单模型“修预期值”过关。
**交付：** 统一分支及针对实际默认分支的集成 PR。发布/合并按当前授权执行，不更改 GitHub 默认分支名称。后续任务从该统一提交起步，不能返回旧 V3 分支。

## 3. 任务 T1：建立离线 CI（主代理审核权限与 action）

**文件：** 新建 .github/workflows/ci.yml；修改 README.md 的开发验证说明。
**选择：** Ubuntu，Python 3.11、3.12、3.13，三个版本跑相同命令。仅 pull_request、push、workflow_dispatch；无 secrets，无 pull_request_target。

- [x] 执行者查阅 GitHub 官方 actions/checkout、actions/setup-python README，选择兼容版本并记录 tag 对应的完整提交 SHA。主代理批准后将 workflow uses 固定为这些 SHA；不能填臆造 SHA。网络失败时停止这一任务。2026-09-24 核验的 v7 pins：checkout `3d3c42e5aac5ba805825da76410c181273ba90b1`，setup-python `5fda3b95a4ea91299a34e894583c3862153e4b97`；来源见 `docs/integration-notes.md`。
- [x] workflow 顶层 `permissions: contents: read`；job `timeout-minutes: 10`；`strategy.fail-fast: false`；matrix Python `['3.11', '3.12', '3.13']`。GitHub workflow schema 将 `timeout-minutes` 定义为 job 属性，因此放在 `jobs.test`，不能放 workflow root。
- [x] checkout 设置 persist-credentials: false；setup-python 使用 matrix.python；不安装目标仓库依赖，不运行 live 评估。步骤执行以下实际命令：

~~~bash
python -m unittest discover -s tests -v
python -m compileall -q repo_doctor tools
python -m repo_doctor --help
python -m repo_doctor diagnose --help
~~~

- [x] 在功能分支提交 ci 文件，推送当前已获授权的 PR；若无推送授权，交付本地 diff 待主代理发布。提交 `8457984` 已进入 PR #6，base 为 `codex/repo-doctor-v1`。
- [x] 使用 gh pr checks 检查三项真实结果，记录各 job URL。不可用本机单版本通过替代矩阵通过。失败由主代理分类，不盲目降级版本或跳测试。push 和 pull_request 两个 run 的 3.11–3.13 jobs 均通过；job URLs 见 `docs/integration-notes.md`。

**验收：** 三个版本的 GitHub job 均通过，无密钥配置。暂不自动修改分支保护。
**提交：** ci: run offline tests on supported Python versions。

## 4. 任务 T2：冻结 10 个真实诊断样本（主代理/人工标注）

**文件：** evaluation/diagnosis/manifest-v1.json、README.md；不修改旧 baseline/challenge。
**任务性质：** 外部事实和缺陷判断，不委派受限执行器。

- [x] 在已有公开 Click、Requests、Flask 中优先寻找 4 个有明确修复提交和公开讨论的普通逻辑缺陷；不足再选其它公开 Python 项目，记录选择理由。不选需要运行外部服务才能理解或依赖秘密数据的问题。已确认 Click #3084/#3152、Click #1921/#2006、Requests #6628/#6629、Requests #7432/#7433；四项均可从源码和上游 issue/PR 静态理解，未运行外部服务。
- [x] 每个缺陷收集修复前、修复后两个快照，构成 8 个 case；另选 2 个有明确契约、未标注目标缺陷的 control。至少覆盖 2 个仓库；不要凭空制造“已知缺陷”。Click 与 Requests 各贡献两个真实 bug/fixed 对；另有 IntRange clamp 与 HTTPBasicAuth 两个有文档/源码契约的 control。
- [x] 每个案例必须能在 120 行/64 KiB 内呈现理解根因所需的上下文。符号和必要语义无法包含时更换案例，不放宽 V3 限额。AI Repo Doctor 静态 scanner 在全部 10 个案例唯一解析目标符号，parse_errors=0；目标块均覆盖指纹范围，准备上下文不超过 120 行、5,132 bytes。
- [x] 所有样本由主代理先读源码和上游修复说明，再写 ground_truth。**冻结标签后才看模型结果。** 找不到足够可确认案例时交付候选清单并停止，不让简单模型补造。完成逐项源码、上游 issue/PR 和回归测试复核；没有查看模型结果或发起 live 请求。
- [x] 单独 checkout 每个 commit；只读源码，记录完整 SHA、许可证标识、永久链接和 fingerprint。README 记录样本是定向选择、可能存在公开数据记忆偏差。8 个不同 SHA 各有独立干净 checkout；Click 为 BSD-3-Clause、Requests 为 Apache-2.0；逐 case 写入精确代码 permalink 与经独立复核的 source fingerprint。
- [x] 文件冻结后记录 manifest 文件字节 SHA-256；版本后续改变必须成为 manifest-v2.json，不能覆盖 v1。`evaluation/diagnosis/manifest-v1.json` 为 17,139 bytes，SHA-256 `f76bbe7a4daa4933b0be2db0552a740a7147ddc8923ed7ed91bc04bdfc78f31f`，并记入数据集 README 和执行状态。

**验收：** 10 个唯一 case，4 对 bug/fixed、2 个 control；每个 case 审核状态 approved，路径/指纹/符号可验证。
**交付前 gate：** 主代理审完真实标签；较简单模型只可按已批准表格机械录入，不能自行定性。
**提交：** eval: freeze diagnosis sample manifest。

## 5. 任务 T3：离线校验和上下文准备

**文件：** tools/diagnosis_data.py、tools/evaluate_diagnosis.py、tests/test_diagnosis_data.py、tests/test_diagnosis_evaluation_cli.py、.gitignore。
**接口：** validate_manifest(data: dict) -> None；prepare_cases(manifest: dict, repos_root: Path, model: str, max_lines: int) -> dict。后者返回 {plan: dict, contexts: dict[str, dict]}，自己不写文件。CLI 原子发布完整准备目录。

- [x] 写 fixture：app.py 中 def broken(): return 1 / 0，再写一个不会加入上下文的 unrelated 函数；临时 Git 仓库 commit；manifest 标注只在本地 fixture 内存在。首轮定向测试因缺少 T3 模块而失败，随后实现并通过。
- [x] 写并运行以下行为测试，确认因缺少实现失败：合法 fixture 成功；HEAD 错误、dirty/untracked、指纹错误、重复 ID、../、绝对路径、symlink 逃逸均拒绝；未知/歧义符号拒绝；超过预算拒绝。20 项 T3 定向测试通过。代码审查后补充 malformed URL 和 bug/fixed pair 一致性校验，并加入回归测试。
- [x] 请求隔离：fixture ground_truth 使用 GROUND_TRUTH_SENTINEL；prepared context 仅含 symbol、blocks、call_evidence；urlopen mock 未被调用。
- [ ] 请求隔离测试示例：

~~~python
prepared = prepare_cases(manifest, repos_root, "test-model", 120)
context = prepared["contexts"]["bug-01"]
wire = json.dumps(context, ensure_ascii=False)
self.assertNotIn("GROUND_TRUTH_SENTINEL", wire)
self.assertEqual(set(context), {"symbol", "blocks", "call_evidence"})
~~~

manifest 的 ground_truth 写入 GROUND_TRUTH_SENTINEL；测试 case id 使用 bug-01。导入 unittest.mock.patch 拦截 urllib.request.urlopen，assert_not_called，证明 prepare 没有发请求。

- [x] 复用已有 build_index、build_context、validate_context_budget、build_diagnosis_prompts；使用其 JSON allowlist 生成 context。读取源码复用安全读取机制；不要只靠字符串前缀判断路径。
- [x] CLI 加 prepare，支持 --manifest、--repos-root、--model（必填非空）、--max-lines（默认 120）、--out-dir。输出目录已存在退出 2；错误不留下看似成功的 plan。
- [x] .gitignore 新增 /.local/diagnosis/，不要忽略整个 evaluation 目录。
- [x] 运行：

~~~bash
python3 -m unittest tests.test_diagnosis_data tests.test_diagnosis_evaluation_cli -v
python3 -m tools.evaluate_diagnosis prepare --help
python3 -m unittest discover -s tests -q
git diff --check
~~~

**验收：** 不需要 API Key 即可准备；所有无效输入在网络前失败；标签不进入请求；计划与上下文有稳定哈希。真实冻结清单已离线准备 10 个上下文，最大 120 行 / 5,132 字节，原始 manifest SHA-256 与冻结值一致；没有请求 API。
**提交：** eval: prepare bounded diagnosis contexts offline。

## 6. 任务 T4：只增加可选 token 用量元数据

**文件：** repo_doctor/deepseek.py、tests/test_deepseek.py。
**接口：** DeepSeekResult 保持前两个位置参数 model、payload，末尾新增 usage: dict[str, int | None] | None = None。旧 DeepSeekResult(model, payload) 构造必须继续有效；不改变 diagnose JSON 顶层字段。

- [ ] 先写测试：有效 usage 原样提取三个允许字段；缺失 usage 为 None；负数、bool、字符串值分别转为 null；额外字段不透传。未给 usage 的既有成功测试仍通过。
- [ ] 最小解析：只从 API envelope 的 usage 字典提取白名单字段；合法值必须 type(value) is int 且 value>=0。不增加 raw envelope 保存。
- [ ] 全部 transport 测试必须 mock URL；检查原 timeout、错误脱敏、单次请求等测试继续通过。

~~~bash
python3 -m unittest tests.test_deepseek tests.test_cli -v
python3 -m unittest discover -s tests -q
~~~

**停止：** 发现需要改 API endpoint、默认模型、结果 schema 或添加依赖；转交主代理重新决定。
**提交：** feat: expose optional DeepSeek token usage internally。

## 7. 任务 T5：受控单次请求执行器（主代理负责 API 边界）

**文件：** tools/diagnosis_runner.py、tools/evaluate_diagnosis.py、tests/test_diagnosis_runner.py、tests/test_diagnosis_evaluation_cli.py。
**接口：** run_cases(plan: dict, contexts: dict[str, dict], repos_root: Path, *, repeats: int, max_calls: int, api_key: str, client: Callable, output_dir: Path) -> dict。client 使用 complete_json 的签名；API Key 由入口从 env 读取且仅传给 client，不放入 plan。

CLI：run --plan-dir --manifest --repos-root --out-dir --repeats --max-calls --allow-network。repeats 只允许 1–3；max-calls 正整数，cases*repeats 超限时整个运行拒绝，而不是跑前几个。--allow-network 缺省时返回 2，不调用 client。

- [ ] 先写离线 mock 测试：缺开关、缺 key、预算不够、上下文哈希改变、manifest/analysis SHA 改变、目标 dirty/HEAD 不匹配、输出目录存在，全部 assert_not_called。
- [ ] 调用前重新校验 manifest、每个 checkout、分析器干净状态/commit、context 哈希与请求指纹；有效负载只来自冻结 context，不从标签拼 prompt。
- [ ] 顺序执行，最多一个请求在途，不重试。一次 provider 或响应格式失败则写失败记录并停止余下任务；结果明确 partial，CLI 返回 2。accepted/rejected 都是有效实验结果，不因为 evidence rejection 中断下一 case。
- [ ] 在发请求前创建整个实验的锁定目录与状态文件；每次请求前写 started，完成后临时文件+replace 写记录。保留中断状态，不自动再次发送 started 未完成的请求。
- [ ] 通过 validate_diagnosis_payload 校验证据；将 accepted/rejected 与 token usage、延迟、模型名写入记录。保存的源码来自已审核公开 context，避免保存 HTTP envelope/环境变量。
- [ ] 两个 case、repeats=1、max_calls=2 的 mock 成功测试应恰好调用两次并生成两份记录；首次 401/timeout/无效 JSON 时只有一次调用。扫描所有记录，不得出现测试密钥 TEST_SECRET_SENTINEL。
- [ ] 退出码：0=计划内全部请求成功并形成记录（允许 finding 被拒绝）；2=配置/输入错误或 partial。不要复制 diagnose 的 rejected=1 到 runner。

~~~bash
python3 -m unittest tests.test_diagnosis_runner tests.test_diagnosis_evaluation_cli -v
python3 -m unittest discover -s tests -q
~~~

**验收：** 预算校验在第一请求之前、失败不重试、记录可追踪、密钥不落盘、全部测试离线。
**提交：** eval: run explicitly authorized diagnosis requests。

## 8. 任务 T6：离线复核模板与评分

**文件：** tools/diagnosis_score.py、tools/evaluate_diagnosis.py、tests/test_diagnosis_score.py。
**接口：** make_review_template(records: list[dict]) -> dict；score_records(manifest: dict, records: list[dict], review: dict) -> dict；render_report(report: dict) -> str。纯函数，不读 env、不发网络、不执行源码。

CLI 增加 prepare-review --run-dir --out-file，以及 score --manifest --run-dir --review --json-out --markdown-out。prepare-review 可以生成 pending；score 遇到 pending/缺行/重复行/未知 finding index/manifest 哈希不匹配时返回 2，保持旧报告原样。

- [ ] 写手算 fixture：3 个 bug case 中 2 个 success（仅一个命中）、1 个 provider_error；2 个 control success（一个有 FP）；accepted 共 1 TP、1 FP、1 uncertain、1 duplicate；另有 1 个 rejected finding。
- [ ] 断言：precision=1/2；条件 recall=1/2；端到端检出率=1/3；grounding_rate=4/5；control_false_alarm_rate=1/2；uncertain=1、duplicate=1、failed_calls=1。为无 findings/无正例/全失败分别断言相关比率为 null，不能写成 100%。
- [ ] 实现第 1.6 节定义的计算；报告同时展示原始分子分母、样本 ID、版本/哈希、每轮结果、token 缺失数、延迟原值与中位数，避免仅有一个总分。
- [ ] rejected TP 单列；模糊问题不强塞 TP。输出中的 reviewer/rationale 缺失同样拒绝 score。
- [ ] 原子写 JSON/Markdown，路径相同或覆盖已有报告需要显式新文件名；失败不部分覆盖旧结果。

~~~bash
python3 -m unittest tests.test_diagnosis_score tests.test_diagnosis_evaluation_cli -v
python3 -m unittest discover -s tests -q
~~~

**验收：** 合成数据指标等于手算；人工判断无法被默认值绕过；离线可反复生成同样的计数。
**提交：** eval: score human-reviewed diagnosis results。

## 9. 任务 T7：真实实验运行手册（主代理/人工）

**前提：** T0–T6 已验收，代码提交干净，模型可用性核查完成。下面命令调用新建工具；在 T3–T6 实现前不存在，不要提前运行。

- [ ] 新终端中由用户配置 DEEPSEEK_API_KEY；执行者只检查是否非空，不打印或写入文件。
- [ ] 主代理读官方文档，记录模型 ID、查询日期、价格单位和相关链接于本地实验 notes。模型 ID 通过 --model 传递；计费额度与输出 token 上限一并告知用户。
- [ ] 冻结配置：每次 120 行、1 次重复、10 个 case，最多 10 个请求；不自动扩大模型列表或案例数。先 prepare，审查所有实际上传 context 后，再申请这 10 次请求的上传/付费授权。已有同范围授权有效，不重复确认。

~~~bash
export DIAGNOSIS_CHECKOUTS=/tmp/ai-repo-doctor-diagnosis-checkouts
# DEEPSEEK_MODEL 由主代理核查后在当前环境设定，不能留空。
python3 -m tools.evaluate_diagnosis prepare --manifest evaluation/diagnosis/manifest-v1.json --repos-root "$DIAGNOSIS_CHECKOUTS" --model "$DEEPSEEK_MODEL" --max-lines 120 --out-dir .local/diagnosis/plan-v1
~~~

- [ ] 用户授权后执行一次首轮。以下命令逐条执行并检查返回码；run 返回 2 时停止，交主代理处理 partial，不能接着把它按完整实验评分：

~~~bash
python3 -m tools.evaluate_diagnosis run --plan-dir .local/diagnosis/plan-v1 --manifest evaluation/diagnosis/manifest-v1.json --repos-root "$DIAGNOSIS_CHECKOUTS" --out-dir .local/diagnosis/run-v1-r1 --repeats 1 --max-calls 10 --allow-network
python3 -m tools.evaluate_diagnosis prepare-review --run-dir .local/diagnosis/run-v1-r1 --out-file .local/diagnosis/run-v1-r1/review.json
~~~

- [ ] 请求失败时保留 partial 记录，主代理调查账户/模型/响应格式问题。禁止循环重跑整个实验。没有密钥或授权时，只完成离线交付，不写“真实评估通过”。
- [ ] 由主代理/人工逐条填写 review.json，引用上游材料和已有上下文解释。发现真实但未标注问题时标 uncertain，不改本轮 frozen manifest。
- [ ] 评分：

~~~bash
python3 -m tools.evaluate_diagnosis score --manifest evaluation/diagnosis/manifest-v1.json --run-dir .local/diagnosis/run-v1-r1 --review .local/diagnosis/run-v1-r1/review.json --json-out .local/diagnosis/run-v1-r1/report.json --markdown-out .local/diagnosis/run-v1-r1/report.md
~~~

- [ ] 如需测随机波动，另授权额外 20 次，使用新的目录 run-v1-r2-r3、--repeats 2、--max-calls 20；不要把这两轮称作 20 个新样本。只进行主代理明确批准的追加实验。
- [ ] token 费用只按执行时核实的计费规则估计；缓存/思考 token 等信息不足时把价格估计设为 null，以服务方账单为准。请求数量上限不是精确金额硬上限。

**验收：** 每个请求可对应到冻结源码/上下文/模型/人工复核，结果可离线复算；报告明确真实成功、失败和未运行数。

## 10. 任务 T8：结果交付、缺陷修复和后续分支

**文件：** docs/evaluations/2026-09-24-diagnosis-v1.md（若实际执行日期不同，使用实际日期）；README.md。完整 run 数据默认留在 .local，公开报告需主代理检查源码许可、引用范围和敏感信息。

- [ ] 报告写清：实际执行日期、分析器提交、数据集哈希、模型响应名、样本/请求数、各项分子分母、错误/uncertain/duplicate 数、token/耗时、两个代表性案例和限制。
- [ ] 加上离线复算命令；不能承诺再调用云端会生成逐字相同答案。未获 live 授权时，交付“基础设施完成，真实结果待运行”的状态报告。
- [ ] 根据下面的固定规则选择下一步，不让简单模型自行扩展产品：

| 观察 | 下一步 |
|---|---|
| 调用失败或格式失败 | 修客户端/协议；先 mock 回归，再审批最小复测 |
| 真问题被证据门禁拒绝 | 主代理检查原文、范围、换行和符号；不能直接放松门禁 |
| 上下文缺少必要条件 | 重新审查样本资格或设计下一版本上下文策略；保留本轮结果 |
| 有依据但推理误报 | 记录 FP，提出单一提示变更；用独立留出样本复测 |
| 漏报 | 先区分上下文不足与模型推理不足；不凭一例换模型或扩大预算 |
| 小样本表现稳定 | 收集新的独立公开样本再扩样；暂不宣称总体质量达标 |

- [ ] 修复任何新代码缺陷：先写可复现失败测试、最小修复、定向测试、全量测试、单独提交。不得为提高分数更改本轮标签。
- [ ] 最终离线测试和 CI 矩阵通过，主代理读最终 diff、报告和具体失败样本。PR 标题围绕最终交付，不写聊天过程。
- [ ] 已授权推送则更新对应 PR；合并按当时有效授权执行。这个计划不授予未来 PR 无条件合并权限。

**候选后续方向（本轮不自动实施）：** 扩大独立样本；按评估结果改进上下文；有明确需求再做批量诊断、交互界面或自动修复。自动补丁涉及新的执行边界，必须另行设计。

## 11. 提交与交付批次

| 批次 | 任务 | 产物与 PR 范围 | 前置门禁 |
|---|---|---|---|
| A | T0–T1 | 统一已有功能 + 离线 CI；基于实际默认分支的集成 PR | 合并冲突已审、既有评估无不明退步、CI 全绿 |
| B | T2–T6 | 样本、离线 prepare/run/score 工具、mock 测试 | 标签审核、数据契约与上传边界审查 |
| C | T7–T8 | 真实实验及经审查的公开报告；不把整个本地记录目录提交 | 上传/费用授权、人工 finding 复核 |

批次 B 分支命名 codex/diagnosis-evaluation，从 A 最终提交创建；A 尚未合并时允许基于该提交继续离线工作，明确记录 PR 依赖。发布 B 前应核对实际默认分支包含 A，否则主代理处理依赖，不让简单模型修改 PR base 猜测历史。C 使用 codex/diagnosis-evaluation-report，来源为 B 验收后的提交。

每批内部仍按任务独立提交；不要把真实运行过程中的每一个结果都推到公开仓库。预计工作量以半天至数天计，T0 冲突程度和 T2 样本调查是主要不确定项；这不是时间承诺。达到门禁即继续下一独立任务，无需每个小步骤重复向用户确认。

## 12. 每个小任务的统一执行与交接

每个任务循环：读指定文件 → 写行为测试并观察合理失败 → 最小实现 → 定向验证 → 主代理审 diff → 全量门禁 → 显式路径 git add → 单独 commit → 更新进度。纯文档/标注录入不写镜像测试，用 schema 校验和实际 diff 审查。

若委派给 Luna/Harness，主代理必须先把已定案步骤写成下列完整任务包。不是把整份计划扔给 executor：

~~~text
Objective: 本次唯一可验收目标。
Allowed changes: 列出此次实际可改路径，禁止“等”。
Forbidden changes: 网络、凭证、权限、依赖、发布及未列出的文件。
Exact steps: 按本计划已定案的顺序列出机械操作，不让执行者选架构。
Validation: 给出可直接运行的命令及预期结果。
Expected result: 文件、接口、输出与 diff 边界。
Stop conditions: 歧义、范围外文件、兼容风险、验证失败且一次定向修正无效时停下。
~~~

例：T6 中 ratio 的纯函数与手算测试可以在主代理提供完整固定输入后委派；T0 合并、T1 工作流、T2 真实标签、T4/T5 凭证与 API、T7 联网、T8 结论不交受限 executor。

每次上下文结束，更新 docs/execution-status.md：

~~~text
Plan: docs/superpowers/plans/2026-09-24-post-v3-execution.md
Branch / worktree:
Current HEAD:
Completed task IDs:
Current task and last completed step:
Changed files:
Validation commands and actual outcomes:
Known failures / blockers:
Next exact action:
Live authorization scope and requests consumed:
Open PR URL and base branch:
~~~

空字段必须明确写 none / not started，不捏造值。下一个模型先读状态、git status 和本计划，不重做已完成步骤。

## 13. 最终验收表

- [ ] 单一集成基线同时包含 V2 语义、旧 baseline/challenge、V3 诊断。
- [ ] 原目录未提交文件、旧 worktree 和冻结报告全部保留。
- [ ] GitHub Actions 在三个 Python 版本执行离线测试。
- [ ] 真实样本先于模型输出冻结，证据来源可核查。
- [ ] prepare 零联网；请求不含标签；上下文与请求指纹可复现。
- [ ] mock 测试证明预算前置、失败不重试、不会泄露 key。
- [ ] 人工复核无法被默认跳过；grounding 与实际正确性分开计数。
- [ ] live 已授权执行并有记录，或明确标注尚未执行。
- [ ] 公开报告与原始数据一致，未把小样本/重复请求当总体质量证明。
- [ ] 用户收到具体产物路径、PR、已完成范围及仍需人工判断的事项。
