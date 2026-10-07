# JS/TS J5 定向验证结果（2026-10-07）

状态：J5 已接受，正式 0.6.0 发布尚待 J6。冻结源码 `135f02fac084f4259f63c018b9bb27ff8a2116b5`，runtime 为 0.6.0a5。

## 实际结果

- 补充八项断言；97 项定向契约无跳过通过。首次执行已通过，没有人为制造红灯，也没有新增分析器实现。
- 12 个固定仓库、36 题，71 条命令：32 题 answered、4 题 bounded、0 blocked。JS、TS 各 5 仓库完成支持内调查链，两阶段各语言均至少 2 仓库达标。
- 与固定源码核对 863 行 context、50 条唯一 context/impact 调用证据；12 份地图通过四件套、SVG、投影上限和端点检查。未对所有完整地图关系评分。
- 相同问题的源码定位/补读基线 96 次；工具回答加必要源码补读及地图共 72 次，减少 24 次。本结论仅适用于这批已见样本，不代表盲测、速度、token 成本或总体准确率。
- 独立冻结源码 wheel：base 9、extra 18、Python 生命周期 33 条安装验收通过；34 个打包 runtime 文件与源码及两个安装逐字节一致。
- 精确 SHA 的 7 项 CI 通过：[候选 CI](https://github.com/kisara174/ai-repo-doctor/actions/runs/37632523935)。Python 3.11/3.12/3.13 基础环境各收集 474 项，其中缺少可选后端的 36 项按设计跳过；三个独立 JS job 的 97 项契约全部无跳过通过。
- 保留检查：14 个原文件、150789 份历史文件、65 个原 runtime 文件、已安装 Skill 无变化；全局仍为 0.5.3。

## 边界与审查

两个 bounded 仓库分别涉及脚本顶层调用与无后缀 TS 导入；源码可见使用点已经补读，但不能将空 impact 当作没有影响。未支持能力没有计为 answered。

若干其他文件被 Tree-sitter 拒绝，已记录准确位置并排除整文件证据；没有独立证明它们都是无效目标语法。本轮所选证据没有确认的 P0/P1；后续应单独研究 grammar 覆盖，不能以此改写本次口径。

地图 viewer 相对已验收 a5 完全相同，保留原 a5 实际浏览器交互证据的版本归属。本轮没有新增浏览器交互，没有排查 Chrome。

原 prepared-not-run 材料与历史 200 仓库评估均保持原归属；本结果不构成新候选的新 200 仓库全量通过。

## 可复核入口

本机独立证据根：`/Users/kisara/.local/share/ai-repo-doctor/evaluations/js-ts-support-v1`。

- `execution-completion-j5.json`：门槛与计数。
- `candidate.json` / `candidate/build.json`：冻结、构建来源及 wheel 哈希。
- `reviews/{discovery,confirmation}/attempt-002/primary-review.json`：逐题中文回答、来源、限制与效益动作。
- `installation-gates/summary.json`、`install-base`、`install-js`、`install-python-lifecycle`：安装证据。
- `ci/candidate/run.json` / `run.log`：七项远端结果及完整日志。
- `protection-j5.json`：保护检查。

## 下一步

只做 J6：同步 0.6.0 版本与安装说明，选择现有统一主线，正式合并 SHA 七项 CI；从该 SHA 构建并验收包，公开发布后匿名下载比对、验证 JS/TS 入口，最后独立部署并再次核对保护。Python 0.5.3 维护线与入口保留。
