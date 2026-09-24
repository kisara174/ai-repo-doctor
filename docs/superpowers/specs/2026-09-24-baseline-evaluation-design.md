# AI Repo Doctor 可复现基础评估设计

## 目标

建立一个仅供开发和发布检查使用的评估集与 runner，用固定版本的公开 Python 仓库测量当前 Repo Doctor 静态关系分析的抽样 precision、recall 和 CLI 扫描耗时。评估属于离线开发工具，不改变 Repo Doctor 的运行时依赖、扫描行为或只读边界。

评估结果必须让另一位开发者能够取回同一份目标源码、核验人工标注，并复跑得到同样的关系计数。耗时结果保留原始样本和环境信息；它用于同一环境下的后续比较，不宣称跨机器绝对性能。

## 现状与评估样本

V2 计划以真实源码关系验收，并明确指出 unresolved-call 总数不能当作准确率或召回率。目前已有 Click、Requests 的固定快照回归，但没有可复用的 gold probe 数据集或统一报告格式。

初始基线固定以下三个公开仓库快照：

| 数据集 | 仓库 | Commit | 选择理由 |
| --- | --- | --- | --- |
| Click | `pallets/click` | `06b2a678741131fd577ce170e23e5ca0aeba0309` | 覆盖明确的包重导出、Click 组注册与 overload。 |
| Requests | `psf/requests` | `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60` | 提供独立的 HTTP 客户端调用与重导出样例。 |
| Flask | `pallets/flask` | `d73fa1cdcbd8b1465c151db8924ba58b1dd14e35` | 第三个不同规模的 Python 框架快照；使用 `src/` 布局并包含包 API 重导出和 overload。 |

来源链接：[Click commit](https://github.com/pallets/click/tree/06b2a678741131fd577ce170e23e5ca0aeba0309)、[Requests commit](https://github.com/psf/requests/tree/611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60)、[Flask commit](https://github.com/pallets/flask/tree/d73fa1cdcbd8b1465c151db8924ba58b1dd14e35)。Flask 仓库由 Pallets 维护，是 Python WSGI 应用框架；其官方项目说明和配置可见 [README](https://github.com/pallets/flask/blob/d73fa1cdcbd8b1465c151db8924ba58b1dd14e35/README.md) 与 [pyproject.toml](https://github.com/pallets/flask/blob/d73fa1cdcbd8b1465c151db8924ba58b1dd14e35/pyproject.toml)。

## 方案选择

1. **固定源码探针集（采用）**：针对少量有源码依据的关系和应保持未解析的样例逐条标注，计算这些已审阅探针上的指标。它成本可控、能捕捉误连，也不会把部分人工标注误报成全仓库真值。
2. **整仓库全量关系标注**：对每个 Python 调用和语义关系都建立完整真值。对首轮基线过于昂贵，漏标会让 precision 看起来虚高或虚低，并难以持续维护。
3. **仅使用合成夹具**：适合验证指标计算与边界规则，但无法说明扫描器在真实项目中的表现；它作为 runner 单测保留，不作为唯一评估集。

## 标注数据契约

新增 `evaluation/baseline-v1.json`，使用标准 JSON，不引入 YAML 或第三方运行时依赖。数据集记录 schema 版本、仓库 ID、官方 HTTPS URL、不可变 commit SHA 和每个仓库的 probe 列表。Probe 按四类组织：

- `call`: 普通调用点及其预期规范目标，或预期 unresolved。
- `reexport`: 显式导出绑定及其预期本地符号目标，或预期不产生符号边。
- `command_registration`: Click 父组到回调的边，或预期没有注册边。
- `overload`: 同名 overload 组是否应归并到唯一实现，以及其完整有序签名集合；负例标注为 ambiguous。

每条 probe 保存稳定 ID、仓库相对文件路径、1-based 起止行、必要的符号/表达式选择器、预期目标或预期 unresolved 原因，以及标注理由。来源内容不复制进 manifest；保存所选行按 UTF-8 解码、`splitlines()` 后以单个 `\n` 重连所得文本的 SHA-256。runner 重新计算指纹并在不匹配时失败。commit、行范围、表达式和理由共同提供可审计出处，同时避免 vendoring 仓库源码。

初始覆盖量目标如下：

- 每个仓库至少 6 个正向普通调用探针和 2 个有依据的 unresolved 探针。
- 每个仓库至少 4 个正向显式重导出探针；可证实的冲突或不支持情况作为负向探针单独标注。
- Click 快照覆盖 `examples/repo/repo.py::cli` 中五个已验证的回调注册，以及至少五个不应形成父组注册边的候选点。
- 每个仓库至少 3 个正向 overload 归并探针。若该仓库有可证明的 overload-only 或多实现歧义样例，则纳入负例；否则通过本地合成夹具测试负向分类，不伪称该仓库提供了负样本。

普通调用 probe 由 `file`、`caller`、`line`、`expression` 唯一标识。当前 `call_edges` 不携带表达式，因此 manifest 只能选择该 `(caller, line)` 下恰有一个 `calls[]` 记录的行；runner 必须验证唯一性，不能把同一行的另一个调用边算给目标表达式。重导出 probe 还以导出名区分同一行的多个 import 名。注册 probe 使用 kind、证据文件/行和父组/回调符号。Overload probe 使用符号 ID、期望状态和签名集合。

## 指标与报告

Runner 将 scanner 输出和标注转换成按 probe 限定的规范关系集合。对每种关系分别计算：

```text
TP = predicted ∩ expected
FP = predicted - expected
FN = expected - predicted
precision = TP / (TP + FP)
recall = TP / (TP + FN)
```

每个集合元素同时带有 probe ID，避免同一预测被不同标注重复计数。普通调用以 probe 对应的唯一 `(caller, line)` 过滤 `call_edges`；重导出按 `kind/evidence_file/line/exported_name` 过滤；注册按 `kind/evidence_file/line/target_symbol` 过滤后比较完整父组与回调端点。错误目标同时产生一条 FP 和一条 FN。期望无边的负向 probe 上，任何匹配该候选绑定的预测边都是 FP。

Overload 用两个互不混合的关系类型评分：

- `overload_resolution`：对预期成功的 probe，期望关系为 `group_symbol_id -> implementation_symbol_id`。实际 symbol 不在 `ambiguous_symbols` 且出现在 `symbols[]` 时生成同样形式的预测关系；预期 ambiguous 的 probe 期望空集合，因此被错误保留为唯一符号会成为 FP。
- `overload_signature`：期望和实际关系是 `(implementation_symbol_id, signature_text)`。这样既能发现 overload 组未归并造成的 FN，也能发现多余或错误签名造成的 FP/FN。

分母为零时输出 JSON `null`，不伪造 0% 或 100%。报告逐仓库、按关系类型合并统计正例/负例数和指标，不把不同类别混成单一总分。

报告只声称“已标注 probe 集”上的 precision/recall。所有未标注的全图预测都排除在指标之外；仓库总 unresolved 调用数、扫描文件行数和边总数只作为规模上下文，不作为精度指标。某仓库没有某类 probe 时标为 `not_sampled`。

耗时测量执行真实用户命令 `python -m repo_doctor scan <checkout> --json`，通过同一 Python 解释器启动独立进程，使用单调时钟计时完整进程墙钟时间。默认每个仓库运行 5 次，记录所有单次耗时以及中位数、最小值、最大值；不声称清空操作系统文件缓存或模拟冷启动。比较报告包含运行 UTC 时间、Repo Doctor commit、Python 版本、操作系统/架构、repo commit 和运行次数。对每次 JSON 结果做规范化摘要哈希；同一运行组出现不同摘要则报告失败，不生成可信的指标报告。

输出包括机器可读 JSON 和人类可读 Markdown。JSON 保存每个 probe 的预测、真值和 TP/FP/FN，便于核查汇总；Markdown 显示每个仓库、每类关系的计数、precision/recall、耗时分布和限制。固定初始报告保存在 `evaluation/results/`，不覆盖原始人工标注。

## Runner、输入校验与安全边界

新增 `tools/evaluate_baseline.py`，仅用 Python 标准库和仓库现有 CLI。调用形式：

```bash
python3 tools/evaluate_baseline.py \
  --repos-root /path/to/pinned-checkouts \
  --runs 5 \
  --json-out evaluation/results/v2-baseline.json \
  --markdown-out evaluation/results/v2-baseline.md
```

`repos-root` 下固定使用 `click/`、`requests/`、`flask/` 子目录。Runner 在开始前检查每个 checkout 的 `HEAD` 与 manifest SHA 一致、Git 工作区无 tracked/untracked 改动、证据行哈希正确；随后调用扫描 CLI，并校验 schema 版本为 2。任何输入校验失败、CLI 非零退出、输出摘要不稳定或 probe 不唯一时都以非零退出，不写部分成功报告。

评估 runner 不 clone/fetch、不访问网络、不 import 或执行目标仓库代码、不写入目标 checkout，也不安装目标依赖。网络只在开发者依照 `evaluation/README.md` 中的命令取回固定 Git commits 时使用。Runner 使用 `subprocess` 的参数数组，不经过 shell，并在报告中记录真正运行的 Repo Doctor Git commit。

## 测试策略

- 通过纯函数测试规范关系集合的 TP/FP/FN 计算：完全匹配、遗漏、错误目标、预期无边却预测出边，以及空分母。
- 用临时小型 Git 仓库测试 commit/干净工作区检查；通过改动证据行验证指纹不匹配会被拒绝。
- 用含有同一调用者同一行多个调用表达式的 fixture 验证 manifest 唯一性校验会拒绝含糊 probe。
- 验证 overload 唯一实现、overload-only 和多实现三种标签的正负结果。
- 在三份固定真实快照上手工审阅 probe 预测，确认采样指标和 CLI 耗时报告均生成。目标仓库扫描是人工运行的评估命令，不进入常规网络依赖单测。

## 非目标和限制

- 该结果不是全仓库完整图准确率，也不测模型是否能提出真实缺陷或 finding validator 的诊断质量。
- 不执行测试、benchmark target code、运行插件或启动服务。
- 不新增 Repo Doctor 运行时网络、依赖、数据库或用户数据上传。
- 本轮只测当前 V2 的行为，不做 V1 对比，也不增加 CI 门禁；后续若要跨 commit 比较，复用同一 manifest 和环境字段即可。

## 验收标准

1. 三个 repo URL、commit 和 checkout 布局固定；Runner 会拒绝错误 SHA、dirty checkout 和失效证据指纹。
2. 所有 probe 都有可审计的源码定位、选择器、预期关系或预期无关系原因。
3. 普通调用、重导出、Click 注册和 overload 分别提供采样的 precision/recall 或明确标记未采样；错误目标产生 FP 与 FN，空分母为 null。
4. 同行多调用不会发生调用边错配；同一 JSON 扫描重复运行的内容摘要一致。
5. 五次 CLI 耗时都被记录，报告给出中位数、范围和运行环境。
6. 单元测试不联网、不安装外部依赖、不执行评估目标代码；真实快照评估可按文档命令离线复跑。
