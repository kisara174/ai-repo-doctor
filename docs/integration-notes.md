# T0 统一基线记录

## 起点与保护范围

- GitHub 仓库：`kisara174/ai-repo-doctor`；实际默认分支为 `codex/repo-doctor-v1`，远端 SHA 为 `aa2a84243fe122a2b7a89b955598b039fcc62345`。
- V2 语义及旧评估分支：`codex/explicit-add-command-registration`，SHA `341c3ffa9cfe4c2a40a61e9ccf5b7139dd03b8cc`。
- V3 诊断分支：`codex/repo-doctor-v2-design`，PR #5 已合并，merge SHA `a61f6fb4dd28e342d3b6550ef257f64d6b402010`。
- 集成从默认分支创建于隔离 worktree `/Users/kisara/.codex/worktrees/post-v3-integration/AI Repo Doctor`，分支 `codex/post-v3-integration`。
- 两次整合提交：`830586ed995b23fce0e31fd85a603d03a84e78fd`（显式 Click 注册与评估）和 `ac263823ebee51e3b2ffff80d979b587f8f463a3`（V3 DeepSeek 诊断）。
- 原工作区保持未改写：`codex/repo-doctor-v2-design`，HEAD `ce0d6d7a61b64e03e11f9e9fce5c90ecf3cfa96d`；其中四个未跟踪 V3 计划/规格文件仍保留。未执行 reset、clean、强制 checkout 或 pull。

## 冲突处理

合并 `341c3ffa` 时，`docs/superpowers/specs/2026-09-24-repo-doctor-v2-design.md`、`repo_doctor/model.py`、`repo_doctor/parser.py`、`repo_doctor/semantics.py` 和 `tests/test_semantics.py` 有冲突。逐文件比较共同基线与引入分支，把可确认的新增字段、显式 `add_command` 注册解析及其测试合入；没有整文件选 ours/theirs。最终冲突结果保留两侧功能，且这五个文件与经过检查的引入版本一致。

合并 `a61f6fb4` 时仅 `README.md` 冲突。说明合并后同时保留 V2 的 schema v2、语义边、重导出、overload 与 Click 能力，以及 V3 的可选云端诊断、显式上传边界和人工复核限制，并链接 V2/V3 两份设计文档。

## 验证

- `python3 -m unittest discover -s tests -v`：155 项通过。
- `python3 -m compileall -q repo_doctor tools`：通过。
- `python3 -m repo_doctor --help` 与 `python3 -m repo_doctor diagnose --help`：通过。
- `python3 -m repo_doctor scan . --json`：输出 `schema_version: 2`，含 71 条语义边。
- `git diff --check` 与 `git diff --cached --check`：通过。
- Click、Requests、Flask 固定 checkout 分别为 `06b2a678741131fd577ce170e23e5ca0aeba0309`、`611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60`、`d73fa1cdcbd8b1465c151db8924ba58b1dd14e35`；三个目录均 clean。未运行目标仓库代码或安装其依赖。

## 五次冻结评估

三份结果都由集成提交 `ac263823ebee51e3b2ffff80d979b587f8f463a3` 产生，每个仓库五次扫描哈希一致；每条 probe 的预测和各仓库关系指标均与已提交历史报告相同。以下 FP/FN 均为零；这些定向样本不能推断未标注代码区域的整体精度。

| 清单 | 新结果（JSON / Markdown，`/tmp`） | 关系汇总 |
|---|---|---|
| `baseline-v1` | `/tmp/post-v3-integrated-baseline-t0.json` / `.md` | call 18 TP；command registration 5 TP；overload resolution 9 TP；overload signatures 18 TP；re-export 12 TP |
| `challenge-v1` | `/tmp/post-v3-integrated-challenge-v1-t0.json` / `.md` | call 2 TP；command registration 4 TP；overload resolution 3 TP；overload signatures 8 TP；re-export 2 TP |
| `challenge-v2` | `/tmp/post-v3-integrated-challenge-v2-t0.json` / `.md` | call 2 TP；command registration 4 TP；overload resolution 3 TP；overload signatures 8 TP；re-export 2 TP |

旧报告保持不变；运行时间和生成日期不要求匹配。T0 无未解释的指标退步。

## T1 官方来源核查

核查日期：2026-09-24。官方 README 当前展示 checkout v7 和 setup-python v7；远端 `v7` refs 解析为下列完整提交 SHA，并在各自 GitHub 提交页确认属于官方 action 仓库：

- `actions/checkout` v7：`3d3c42e5aac5ba805825da76410c181273ba90b1`（[提交](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1)）。
- `actions/setup-python` v7：`5fda3b95a4ea91299a34e894583c3862153e4b97`（[提交](https://github.com/actions/setup-python/commit/5fda3b95a4ea91299a34e894583c3862153e4b97)）。
- GitHub 的[安全使用指南](https://docs.github.com/en/actions/reference/security/secure-use)建议将 Actions 固定到完整 commit SHA；[workflow 权限文档](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)说明顶层 `permissions` 可缩小 `GITHUB_TOKEN` 范围，指定权限后未列出的权限设为 `none`。同一参考把 `timeout-minutes` 定义在 job 层级，因此配置于 `jobs.test`。
- 原始 action 文档：[checkout README](https://github.com/actions/checkout)，[setup-python README](https://github.com/actions/setup-python)。

以上提交用于计划中的只读 Python CI。实际 workflow 和本地验证结果在完成 T1 后记录。
