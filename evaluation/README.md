# V2 固定快照基础评估

`baseline-v1.json` 是逐条审阅的源码关系探针集。每条记录包含固定 commit、源码行范围、选择器、预期关系、理由和源码指纹。评估器先检查三个 Git checkout 的 commit、干净状态与全部指纹，再启动扫描。目标代码不会被导入或执行；运行评估不需要安装目标项目的依赖。

## 准备固定源码

需要 Python 3.11+ 和 Git。下面的克隆命令是一次性准备步骤，需要网络；评估器本身不执行克隆或网络请求。

```bash
BASELINE_CHECKOUTS=/tmp/ai-repo-doctor-checkouts
mkdir -p "$BASELINE_CHECKOUTS"
git clone https://github.com/pallets/click.git "$BASELINE_CHECKOUTS/click"
git -C "$BASELINE_CHECKOUTS/click" checkout --detach 06b2a678741131fd577ce170e23e5ca0aeba0309
git clone https://github.com/psf/requests.git "$BASELINE_CHECKOUTS/requests"
git -C "$BASELINE_CHECKOUTS/requests" checkout --detach 611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60
git clone https://github.com/pallets/flask.git "$BASELINE_CHECKOUTS/flask"
git -C "$BASELINE_CHECKOUTS/flask" checkout --detach d73fa1cdcbd8b1465c151db8924ba58b1dd14e35
```

目录名固定为 `click/`、`requests/`、`flask/`。不要在这些 checkout 中安装依赖或生成文件；评估器会拒绝任何 tracked 或 untracked 改动。

## 运行

从 AI Repo Doctor 仓库根目录执行：

```bash
python3 tools/evaluate_baseline.py \
  --repos-root "$BASELINE_CHECKOUTS" \
  --runs 5 \
  --json-out evaluation/results/v2-baseline.json \
  --markdown-out evaluation/results/v2-baseline.md
```

默认 manifest 是 `evaluation/baseline-v1.json`，默认重复次数为 5。也可用 `--manifest` 指定该文件的位置。失败时退出码为 2，已有报告保持原样。每次重复运行会保存独立进程的耗时和完整扫描 JSON 的规范化哈希；同一仓库的哈希不同则拒绝生成报告。

## 解释结果

Precision 与 recall **只适用于这里人工标注的 probe**，不能推断为整个仓库调用图的准确率。正向调用和重导出候选来自固定快照的扫描清单，再逐条核对源码；它们偏向扫描器已识别的关系。负向调用与 Click 注册候选也经源码核对。首版没有对全部调用做随机抽样或完整标注，因此 100% 的采样指标不代表未标注区域没有遗漏或误报。

报告按调用、重导出、命令注册、overload 归并、overload 签名分别计数。JSON 保留每个 probe 的预期、预测和 TP/FP/FN；Markdown 展示汇总和不匹配 ID。`stats` 中的 unresolved 数量仅为规模背景，不进入准确率分母。没有探针的类别显示 `not_sampled`，零分母显示 `null`。

耗时是同一 Python 解释器启动真实 `repo_doctor scan --json` 命令的完整墙钟时间。报告记录五次原始耗时、中位数、最小值、最大值、Python 与平台信息，适合在同一环境中做后续比较；没有控制操作系统文件缓存，不应跨机器直接比较绝对耗时。

## 独立挑战集 challenge-v1

challenge-v1 的案例先依据固定 commit 的源码结构审阅和选择，再检查 Repo Doctor 的预测。它是独立且刻意更难的挑战集，共 15 个 probe，覆盖调用、重导出、命令注册和 overload。`baseline-v1` 及其指标和报告仍是历史基线；不得与 challenge-v1 的指标合并。

动态导入、运行时属性查找，以及接收者驱动的嵌套调用标为 unresolved，因为当前的单目标关系形式无法声称存在唯一的本地被调用目标。

从仓库根目录复用前文准备好的固定 checkout 目录运行：

```bash
python3 tools/evaluate_baseline.py \
  --manifest evaluation/challenge-v1.json \
  --repos-root "$BASELINE_CHECKOUTS" \
  --runs 5 \
  --json-out evaluation/results/challenge-v1.json \
  --markdown-out evaluation/results/challenge-v1.md
```

结果只属于 `challenge-v1`，应逐条根据其源码证据解释。

本轮在加入显式 `add_command` 解析后，三仓库各运行五次，每个仓库的五个规范化扫描哈希一致。此前发现的两条源码确认关系现均匹配：Click 的 `examples/completion/completion.py:56` 通过 `cli.add_command(group)` 将子组加入 `cli`；Flask 的 `src/flask/cli.py:594` 通过 `self.add_command(run_command)` 将命令加入 `FlaskGroup`。Click 的三个命令注册探针与 Flask 的一个命令注册探针全部匹配，未出现采样误报或漏报；其余挑战探针也全部匹配。`baseline-v1` 的五次评估另写入临时文件，其逐仓库关系指标与冻结报告一致；原始 baseline manifest 与报告文件保持不变。精确数据与重复运行哈希见 `results/challenge-v1.json` 和 `results/challenge-v1.md`。

## 显式注册边界集 challenge-v2

`challenge-v2` 保留 challenge-v1 的 15 个探针，并增加四个来自相同固定源码快照的负向注册探针：Click 内部装饰器中运行时创建的 `cmd`，Flask 插件入口动态加载命令时的多参数调用，以及 Flask 教程中无法静态解析的 `app.cli` 接收者。负向探针只记录调用位置、理由和未解析说明，不要求标注不存在的父/回调符号。challenge-v1 的清单和报告保留原样。

从仓库根目录运行：

```bash
python3 tools/evaluate_baseline.py \
  --manifest evaluation/challenge-v2.json \
  --repos-root "$BASELINE_CHECKOUTS" \
  --runs 5 \
  --json-out evaluation/results/challenge-v2.json \
  --markdown-out evaluation/results/challenge-v2.md
```

本轮五次评估中，19 个探针全部匹配，每个仓库的五个规范化扫描哈希一致。Click 的三个注册正例与 Flask 的一个注册正例均命中；新增四个动态或属性接收者负例均未产生误报。challenge-v1 的既有报告未覆盖写，五次复评的指标和扫描哈希与已提交结果一致。另行运行的 baseline-v1 指标与冻结报告一致；冻结文件保持不变。详细结果见 `results/challenge-v2.json` 和 `results/challenge-v2.md`。
