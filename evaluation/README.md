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
