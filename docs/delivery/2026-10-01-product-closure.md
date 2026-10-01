# 基础版产品收尾记录

日期：2026-10-01。当前指导清单：[R1–R5](../superpowers/plans/2026-10-01-basic-product-optimization-guide.md)；前轮实施细节：[C1–C6 历史计划](../superpowers/plans/2026-10-01-product-closure-execution.md)。

## 1. 当前交付状态

**0.5.0 收尾候选版已部署到 Mac。** 主目录与安装入口统一；目录搜索缺陷已修复；固定真实仓库的问题调查、HTML/SVG 生成、同一 wheel 的干净安装均已完成。公开稳定版仍为 0.4.1。用户已分别确认新会话完整 Skill 调用及原生 HTML/SVG 操作通过，当前执行正式发布；稳定交付以随后 R4/R5 记录为准。

| 环节 | 实际结果 |
| --- | --- |
| C1 主目录与版本 | 主目录分支 `codex/local-product-closure` 已同步；四份用户原文保留并按 SHA256 核对 |
| C2 目录导航 | 纯投影与实际生成页面均取得 RED→GREEN，包含搜索展开、高亮、定位和大量文件下的目标保留 |
| C3 真实用途 | 已用 schedule 回答定时检查到执行的源码路径，保存命令、JSON 与三份最终地图 |
| C4 安装 | 同一候选 wheel 在干净环境及 Mac 安装；资源、版本和无运行依赖已核对 |
| C5 人的使用 / 新会话 | 用户确认新会话四步调用，以及原生 HTML 目录导航、当前 SVG 导出重开均通过 |
| C6 正式交付 | 实际使用门槛已齐，执行 PR #30 正式整合、构建、发布与安装 |

当前产品的基本用途：让 Codex 先获取小而有来源的仓库概览，再按目标取源码、调用与影响证据；给人一个只展示结构和关系的离线地图。Codex 负责详细分析和修改。有明确发现时，工具可校验证据、保存 issue，并记录明确选择的复现与修复复查。结构问题本身无需制造 issue。

## 2. 目录导航修复与保护措施

旧目录搜索会打开全部目录，随后走普通选择逻辑再次收起目标。修复使用独立 `reveal` 操作：打开目标及祖先、收起无关目录、清除关系焦点，并高亮及定位选中结构节点。

200 个节点、500 条边的单视图上限保留。目标路径及直接子节点先纳入预算，避免目标被靠前的大量文件挤掉，再恢复结构顺序。普通展开、文件聚合调用焦点、符号调用邻域和测试筛选保持可用。

- Luna Max 只在指定测试文件插入锁定的断言；主代理检查实际 diff 并重新运行 RED，再负责实现、复核和部署。
- 纯投影旧实现失败于缺少 reveal；旧 HTML 失败于目标目录子文件不可见。
- 修改后纯投影、DOM 与当前 SVG 序列化通过；250 个靠前根文件下仍保留目标及祖先、子文件，边无悬空端点。
- 401 项 Python 回归于代码冻结后一次通过，耗时 18.939 秒。未重新进行模型盲测。
- 四份原文备份及哈希保存在 `~/.local/share/ai-repo-doctor/workspace-preservation/2026-10-01-product-closure/manifest.json`。原文复制回主目录，作为本地修改保留，不提交到功能分支。

## 3. 真实问题：schedule 的任务执行路径

仓库：`dbader/schedule`，本地路径 `~/.local/share/ai-repo-doctor/evaluations/2026-09-30-schedule/repo`。

固定修订：`82a43db1b938d8fdf60103bd41f329e06c8d3651`。操作前后 Git 状态相同；未执行或修改该仓库代码。

问题：**定时任务检查从哪里进入，Scheduler.run_pending 如何推进到实际任务执行，改动它可能影响哪些已解析调用？**

### 入口与执行

| 步骤 | 源码位置（schedule/__init__.py） | 观察 |
| --- | --- | --- |
| 公开便利入口 | 850–854 | 模块级 `run_pending()` 调用 `default_scheduler.run_pending()` |
| 检查待执行任务 | 89–101 | `Scheduler.run_pending` 从 `self.jobs` 选择 `job.should_run` 的任务，排序后逐一调用 `_run_job` |
| 执行及取消 | 172–175 | `_run_job` 调用 `job.run()`；返回 `CancelJob` 类或实例时调用 `cancel_job` |
| 实际回调及重排 | 674–698 | `Job.run` 先检查截止时间，691 行调用 `self.job_func()`，692–693 行更新 `last_run` 并安排下一次执行 |

89–101 行的说明明确：漏掉多个调度周期后，`run_pending` 不会为所有错过的周期逐次补跑。改动这一方法应保护该行为、到期任务筛选、排序和 `_run_job` 的执行入口。以上是基于源码的行为解释，不是运行结果或新缺陷判断。

**图边与解释分开：** 工具确认的静态边包含 `Scheduler.run_pending → Scheduler._run_job`（101 行）。模块便利函数对实例的方法调用、`job.run()` 的参数对象调用以及动态 `job_func()` 未被这次返回的边全部解析。`Job.run` 和模块入口是 Codex 通过真实符号搜索后显式补入的源码；正常 Job 对象沿上述路径执行是基于源码和类型标注的解释，不能把这些补充关系冒充工具已经证明的调用边。

### 已解析改动影响

`impact --depth 2` 返回一个直接调用方：`test_schedule.py::SchedulerTests.test_misconfigured_job_wont_break_scheduler`，调用位于 `test_schedule.py:1599`。没有返回额外的二跳调用方。另有该测试模块在 13、14 行导入 schedule 的证据。

这个结果只是已解析集合。模块级便利入口、其他实例调用和仓库外使用者可能受到行为变化影响；动态解析缺口使工具无法给出完整反向影响清单。没有边不能解读为没有使用者，未解析数量也不应解读为 bug 数量。

### 实际调用与预算

安装后的 CLI 按 Skill 顺序运行：

```sh
repo-doctor overview REPO --json
repo-doctor symbols REPO --query run_pending --json
repo-doctor context REPO 'schedule/__init__.py::Scheduler.run_pending' --max-lines 120 --json
repo-doctor impact REPO 'schedule/__init__.py::Scheduler.run_pending' --depth 2 --json
repo-doctor symbols REPO --query Job.run --json
repo-doctor context REPO 'schedule/__init__.py::Scheduler.run_pending' \
  --include-symbol 'schedule/__init__.py::Job.run' \
  --include-symbol 'schedule/__init__.py::run_pending' --max-lines 120 --json
```

`REPO` 为上述固定本地路径。符号 ID 从实际 `symbols` 结果选择。基础上下文 28 行、5 块；补充后 59 行、8 块，上限 120 行，均无截断、无省略符号/导入。概览为 4 个 Python 文件、170 个符号、482 个已解析调用、563 个未解析调用、0 个解析错误。

全部命令退出 0。命令参数、输出大小、原始 JSON、仓库前后状态保存在 `releases/v0.5.0-closure-candidate/usage/`。只记录实际预算与观察，不声称节省某比例时间或 token。

## 4. 安装产物与地图

- 功能及安装文档提交：`19dd92ae8bfb77d534761cfb916eb8dd8e83eaac`。
- wheel：`~/.local/share/ai-repo-doctor/releases/v0.5.0-closure-candidate/ai_repo_doctor-0.5.0-py3-none-any.whl`。
- SHA256：`9f5491da5b76a75922803ec2b1baa770d122a049f6689884a0ff474a2a007129`。
- 包内 Skill、HTML、JavaScript、CSS 与该功能提交一致；`Requires-Dist` 为空。
- 干净安装实际从 site-packages 导入；已安装 Skill 与包内字节相同，未改全局配置或 Key。
- Mac 入口：`/Users/kisara/.local/bin/repo-doctor`，无需激活环境；同一包生成的受控页面通过本轮 DOM 导航及 SVG 检查。
- 旧候选、0.4.1 wheel 和部署历史保留。本轮部署收据另存，避免覆盖旧记录。

最终地图根目录：`~/.local/share/ai-repo-doctor/maps/2026-10-01-product-closure/`。

| 子目录 | 内容 |
| --- | --- |
| `self/` | 本项目结构；快照来源功能提交 19dd92a |
| `schedule/` | 固定 schedule 仓库的结构和文件关系 |
| `schedule-run-pending/` | 指定 Scheduler.run_pending 的一跳静态关系 |

各目录均含 `map.html`、`structure.svg`、`relations.svg`、`map.json`。HTML 只呈现结构与关系；详细解释保存在这份记录和 Codex 对话中。SVG 默认文件与页面导出的当前视图是不同用途；当前视图导出需在真实浏览器重开确认。

## 5. 已确认的实际使用路径

1. Safari/Chrome 打开 `self/map.html`，搜索 `repo_doctor/resources/map` 并选择目录 `map`，确认子文件可见、目标高亮和定位。
2. 导出当前 SVG，并在浏览器重开下载文件。
3. 新 Codex 会话显式使用 `$repo-doctor` 完成第 3 节同一问题，确认实际调用 overview、symbols、context 和 impact。

浏览器工具此前因安全限制拒绝本地 file URL；不使用其他路由绕过拒绝。新用户会话未经用户要求不自行创建。上述两条使用路径已分别收到用户确认；没有将 DOM 检查当作原生浏览器证据。

| Skill 证据 | 状态 |
| --- | --- |
| 已安装、当前技能目录已加载 | 已确认 |
| 当前会话按 Skill 运行命令 | 已确认，原始输出保存 |
| 新会话完整显式调用 | 用户回传确认通过：Skill 已加载，4/4 步，退出码均为 0 |
| 隐式匹配 | 待确认；不是必然触发，也不是本版必需门槛 |

所有必需门槛通过后，继续使用 PR #30 整合到实际默认分支，再从正式合并提交构建及发布 v0.5.0、同步主目录和安装。确认未齐时，维持候选状态；现阶段不扩展新图类型或新模型评估。

## 6. R1/R3 本轮收拢结果

当前总入口已统一至 R1–R5 指导清单；README、Codex 用法、产品指导书与旧执行计划指向同一份状态。文档提交 `3a75d2d` 的 Python 3.11–3.13 和地图 CI 全部通过；本轮没有生产代码、依赖或测试改动。

主目录快进同步后，四份用户原文及指导清单初稿哈希保留。安装包与主目录 29 个运行资源字节一致，安装 CLI 与源码模块启动的 overview 输出一致，源码指纹为 `62acffe9211a9022e63b609226d3be0a1462cfb08066fb0a551767362c55b026`。当前仍安装同一功能提交 19dd92a 的候选 wheel；文档提交与构建源码分别记录。

实际同步记录：`releases/v0.5.0-closure-candidate/closure-synchronization-3a75d2d.json`；最新 head/CI 记录见 `deployment-closure-candidate-0.5.0.json` 和 PR #30。GraphFlow root 已确认为主目录，索引缓存非过期。

R1、R2 与 R3 已完成；两项实际使用分别由用户确认。继续 R4 稳定发布与 R5 最终交付，没有用测试通过代替人的实际操作结果。

## 7. R2-2 用户回传确认

用户在新 Codex 会话重新完成调查，确认 Skill 已加载，overview、symbols、context、impact 四步退出码均为 0。概览统计与固定仓库一致；context 补入搜索取得的 Job.should_run、Job.__lt__、Job.run、Job.do 及模块入口，120 行预算未耗尽且无截断。回答解释了到期判断、排序、回调绑定与执行，并保留静态解析边界。

确认来源是用户回传的实际操作报告，未收到原始 JSON；没有将本会话重复调用算作新会话证据。外部记录：`releases/v0.5.0-closure-candidate/r2-new-session-confirmation.json`。用户同时确认未改源码、未执行目标仓库代码、未调用 DeepSeek；这项是静态调查流程确认，不是运行时验证。

R2-1 随后也收到用户确认，见下方记录。

## 8. R2-1 用户确认原生地图

用户对最终 self/map.html 的原生打开、目录搜索展开/高亮/定位、当前 SVG 导出及下载文件重开回复“确认”。确认来源是用户反馈，未收到原始截图或 SVG 文件；未绕过浏览器工具限制。外部记录：`releases/v0.5.0-closure-candidate/r2-native-map-confirmation.json`。两项必需使用门槛均已通过，执行正式发布。
