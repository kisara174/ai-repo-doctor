# AI Repo Doctor 1.0 交付准备状态

日期：2026-10-08。公开版本仍为 0.8.0，候选为 1.0.0rc1；本文件不是正式发行或完整验收声明。

## 最终目标核对

| 目标 | 已取得证据 | 尚未完成 |
| --- | --- | --- |
| A1 可独立安装、明确实际版本 | V2/V3 冻结源码、wheel、base/js 独立安装；35 个 runtime 一致 | RC 和正式下载件的新环境安装 |
| A2 Codex 证据调查链 | 三个新仓库及真实源码核对；已解析路径与未知分开 | V5 第二次独立会话 295.53 秒成功并经主代理复核；正式安装的核心链仍待 V8 |
| A3 离线 HTML/SVG | V4 DOM/搜索门禁，V5 三份原生 Chrome 交互、当前 SVG 精确投影 | RC/正式产物地图门禁 |
| A4 Python/JS/TS 和公共接口 | CLI 合同、明确 JS/TS 边界、精确提交 11 项 CI | 正式提交的同样 CI 与合同复核 |
| A5 规模与超限清楚 | V3 文件/字节/Git/协作时间/深度门禁；100/1000 文件参考样本 | 正式安装资源拒绝复核，不扩写为所有仓库性能承诺 |
| A6 升级回滚可完成 | 安装、Skill 绑定及回滚文档，旧入口/Skill 保留 | 实际全局切换、旧版查询和恢复新版演练 |
| A7 公开产物可下载并使用 | 0.8.0 既有公开发行；1.0 技术准备 | 1.0 发布、匿名下载 SHA、安装下载件并走通核心链 |
| A8 许可、反馈和维护 | 本轮补齐 metadata URL、CHANGELOG/SUPPORT/兼容政策/问题模板 | MIT / kisara174 已确定；c767c98 wheel 标准许可及字段已通过，正式版本仍待复核 |

## 发布阻塞

1. 用户已在 2026-10-08 明确选择 MIT，版权署名 kisara174；标准文本和包字段已加入，c767c98 实际 wheel 核验通过；此许可阻塞已关闭。
2. V7 的 RC 精确源码安装、全量针对发行的门禁、最终评审尚未执行。
3. V8/V9 的正式公开下载后安装、本机升级回滚和最终保护审计尚未执行。

JS 嵌套 helper 调用解析、方法/匿名回调/动态关系/外部消费者等属于公开支持边界，不作为已完成的运行时能力。pretty-ms 本题已明确记录影响图收益不足，定位与上下文可用；没有把空影响伪装为无影响。

## 已解决的验收事项

V5 独立消费者首轮在 420 秒外层时限结束，保留为失败；第二次限定核心命令、产物链接和简短回答，295.53 秒正常结束、进程退出 0。主代理核对 binding、同一 CLI、先搜索后用 ID、源码行与 7 个影响结论，接受该次会话。没有把首轮报告冒充正常完成。

## 证据与继续点

实施分支 `codex/v1-product-closure`；[草稿 PR #43](https://github.com/kisara174/ai-repo-doctor/pull/43)。V3 runtime 源码 `50a97b84327860c86a33d4456285838e770bb399`，V4 CI 实施 `88392c131818c1d5e90cad9b859a70f1223bf69a`；它们不是正式 1.0 tag。

本机证据根为 `~/.local/share/ai-repo-doctor/evaluations/v1-product-closure-v1/`：V3 completion/products/scale，V4 verified-ci/completion，V5 各调查/source-verification/browser/consumer。历史 200 仓库证据不改候选归属，不声称新 1.0 全量评估。

按 [指导清单](../V1_TODO.md) 和 [执行计划](../superpowers/plans/2026-10-08-v1-product-closure.md) 推进。V6 已完成，现进入 RC 精确产物门禁；Goal 仅在 A1–A8 和正式交付全部完成时关闭。

## 本轮包核验与提前准备

V6 技术文档提交 `80f25ec8e26b1ff8be93eab630689c08f65e5e2e` 已从精确 archive 构建新 dev1 wheel：Name、Version、Summary、Requires-Python、4 个 Project-URL 和 3 个可选依赖字段匹配；35 个 runtime 文件与 V3 安装一致。License-Expression 为空、License-File 为空，门禁实际返回 2，明确不是发行准备成功。回执位于 v6/metadata/summary.json。

V7.3 仅提前补齐旧生命周期回执的 expected_exit_code，最小负向检查修复前缺字段、修复后通过；现有 installed dev1 的 33 条生命周期命令实际/预期退出码逐条匹配，预期失败未改成 0。它不代替 RC 的全套精确提交验收。

安装文档另发现并修复 zsh 对未加花括号的 wheel extra 变量展开问题：改用 `"${RD_WHEEL}[js]"`。实际 zsh 复现旧命令丢参，文档门禁新增回归（红→绿，现 8 项）；随后直接提取文档 shell 块，在新虚拟环境安装上述精确 dev1 wheel，核对版本、导出新绑定 Skill、完成自建源码概览。bash/zsh 的带空格参数也分别核对。证据在 v6/zsh-expansion、zsh-doc-red/green、zsh-install；无目标程序执行。

最新许可核验：v6/license-approved/wheel-validation/summary.json，MIT / LICENSE 字段和实际许可文件逐字节通过；旧 v6/metadata 失败记录属于此前无许可候选，原样保留。
