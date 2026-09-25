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
- `actions/setup-python` v7.0.0：`5fda3b95a4ea91299a34e894583c3862153e4b97`（[v7.0.0 release](https://github.com/actions/setup-python/releases/tag/v7.0.0)，[提交](https://github.com/actions/setup-python/commit/5fda3b95a4ea91299a34e894583c3862153e4b97)）。
- GitHub 的[安全使用指南](https://docs.github.com/en/actions/reference/security/secure-use)建议将 Actions 固定到完整 commit SHA；[workflow 权限文档](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)说明顶层 `permissions` 可缩小 `GITHUB_TOKEN` 范围，指定权限后未列出的权限设为 `none`。同一参考把 `timeout-minutes` 定义在 job 层级，因此配置于 `jobs.test`。
- 原始 action 文档：[checkout README](https://github.com/actions/checkout)，[setup-python README](https://github.com/actions/setup-python)。

以上提交用于只读 Python CI。工作流及本地验证在提交 `8457984` 中，read-only review 无 findings。分支 `codex/post-v3-integration` 已推送；PR [#6](https://github.com/kisara174/ai-repo-doctor/pull/6) 目标为实际默认分支 `codex/repo-doctor-v1`。

GitHub Actions 在被检查的 head `dd34f2cb1a74379ccbfb275cd1daf6bae73dd240` 上通过。push run `36006602740` 的三项 job URL：

- Python 3.11：[job 107656247231](https://github.com/kisara174/ai-repo-doctor/actions/runs/36006602740/job/107656247231)
- Python 3.12：[job 107656247589](https://github.com/kisara174/ai-repo-doctor/actions/runs/36006602740/job/107656247589)
- Python 3.13：[job 107656248817](https://github.com/kisara174/ai-repo-doctor/actions/runs/36006602740/job/107656248817)

`gh pr checks 6` 还确认了 pull_request run `36006656104` 的三个版本均通过。没有配置 secrets；测试和评估均未发起 DeepSeek 请求。当时 PR 尚未合并；后续状态见下节。


## PR #6 final integration update

Checked after merge: GitHub reports PR #6 `MERGED` at `2026-09-24T17:56:34Z`. The PR head was `3492deb7c9971c06da48477f2dff6a8836cf2226`; the merge commit is `ec5041d3b98e07dc42532336e36ebe9ac2e82f12` on `codex/repo-doctor-v1`. The merge tree (`6a441892287e3e1c6aeb79f8f8a0107cd7851d0e`) is identical to the tested PR head tree.

Both CI runs for the final PR head passed on all supported Python versions:

- Push run `36037698415`: [Python 3.11](https://github.com/kisara174/ai-repo-doctor/actions/runs/36037698415/job/107761795588), [Python 3.12](https://github.com/kisara174/ai-repo-doctor/actions/runs/36037698415/job/107761795645), [Python 3.13](https://github.com/kisara174/ai-repo-doctor/actions/runs/36037698415/job/107761795529).
- Pull-request run `36037704725`: [Python 3.11](https://github.com/kisara174/ai-repo-doctor/actions/runs/36037704725/job/107761817293), [Python 3.12](https://github.com/kisara174/ai-repo-doctor/actions/runs/36037704725/job/107761817011), [Python 3.13](https://github.com/kisara174/ai-repo-doctor/actions/runs/36037704725/job/107761817440).

After merging the base locally into `codex/diagnosis-evaluation`, the combined branch passed 229 tests, including 23 targeted data/CLI offline tests and 15 DeepSeek transport tests. The live diagnosis run remains partial (`provider_error` on its first request); this merge and evaluation made no additional provider calls. The evaluation branch and its report remain local and have not been published.

## 2026-09-25 CI evidence scope clarification

PR #6 CI applies to PR head `3492deb7c9971c06da48477f2dff6a8836cf2226`. It does not validate the unpublished diagnosis-evaluation changes. The integrated evaluation branch has a historical local result of 229 passing tests; that result is not a fresh CI result. Before publishing or merging the evaluation changes, record the actual evaluation PR head SHA and its own Python 3.11/3.12/3.13 CI results. This clarification does not change the stopped live run or establish model quality.
