# 无后缀与目录 index 源码关联调查

日期：2026-10-07。状态：研究完成，产品实现尚未开始。

## 决策摘要

建议下一阶段增加保守的源码关联：在可见文件集合中同时检查文件与目录 index 候选，只有一个候选且其实现源码已被选择、成功解析时才连接。来源必须可追溯；关联不构成运行时模块解析证明。

当前正式版 0.6.0 明确将这类路径留作未知。这是新增覆盖范围，不是把历史不支持的案例追认成已修复 bug。

## 方法和证据

研究基线源码：`c41f9ec4e1a264ef8d7366bccce298335181715e`；其分析器与正式版 `f750c68b728e67cdce7ca9d1bce79466a8c3515a` 相同。

使用已有 benchmark200 固定集合中的 80 个 JS/TS 仓库（主语言各 40 个），全部已经看过，不是盲测。读取固定源码，直接用既有 Tree-sitter 后端检查顶层静态 import/export 声明；没有运行 Repo Doctor 产品命令、目标代码或目标依赖安装。

研究证据目录：`/Users/kisara/.local/share/ai-repo-doctor/evaluations/js-ts-source-association-v1/attempt-002/`。

- `survey-script.py`：实际研究脚本；Tree-sitter 0.26.0、JavaScript grammar 0.25.0、TypeScript grammar 0.23.2。
- `inputs.json`：原 manifest 和 80 个 inventory JSON 文件的字节摘要。
- `declarations.jsonl`：逐条仓库、提交、来源摘要、声明行段、原文、候选及研究分类。
- `repositories.json`、`parser-exclusions.json`、`summary.json`：分仓库计数、整文件排除、总计。
- `stdout.log`、`execution-receipt.json`：运行记录。回执在进程完成后补记；stderr 未单独捕获。
- `validate-survey.py`、`validation.json`：独立重计、输入摘要、来源逐字检查及旧 oracle 对照。

实际读取 17,751 个受支持扩展文件，17,621 个通过整文件解析，130 个被后端排除。解析失败不能直接说明目标源码本身有错误。共找到 68,871 条顶层静态模块声明，其中相对路径 30,350 条。

有限候选规则：规范化相对路径 stem，检查 exact stem，以及 stem 和 stem/index 加以下后缀的并集：`.ts .js .mjs .tsx .jsx .d.ts .mts .cts .cjs .d.mts .d.cts .json .node`。候选先包含不受支持的可见文件，再检查唯一性与解析状态。stem 目录存在 package.json 时拒绝关联；本集合没有触发此分支。排除反斜杠、URL 特殊字符、尾随斜杠和具有后缀的声明。此规则不是完整加载器模型。

## 结果

| 分类（单位：静态模块声明） | 数量 | 含义 |
|---|---:|---|
| 唯一、实现扩展受支持且已解析 | 9,706 | 潜在源码关联，尚未通过产品验证 |
| 唯一，但实现不合格 | 521 | 441 条不支持的源码种类；80 条目标整文件解析失败 |
| 无候选 | 48 | 保持未知 |
| 多候选 | 4 | 必须拒绝连接 |
| 总计 | 10,279 | 不按 named binding 数量重复计数 |

潜在关联中，9,205 条为文件路径，501 条为目录 index；9,490 条指向 `.ts`，216 条指向 `.js`。样本没有验证无后缀 `.mjs` 关联，需合成合同用例覆盖。

| 仓库主语言 | 仓库总数 | 出现这类声明的仓库 | 潜在关联声明 |
|---|---:|---:|---:|
| JavaScript | 40 | 7 | 2,720 |
| TypeScript | 40 | 32 | 6,986 |

合计 39/80 个仓库可能受益。dembrane/echo 与 orkas-ai/orkas 合计占 4,791/9,706 条，结果受大仓库集中影响，不能据此推断任意 GitHub 仓库的收益。这里按仓库主语言分组，不等于各源码文件的语言分类。

## 必须保留的拒绝案例

四条歧义均来自 sunanakgo/nais3：导入 preload/index 时同时存在 `src/preload/index.ts` 与 `src/preload/index.d.ts`。来源分别是：

1. `src/renderer/src/browser/install-browser-api.ts:1`。
2. `tests/i18n-renderer.test.ts:9`。
3. `tests/layout-store.test.ts:3`。
4. `tests/quick-generation-controls.test.ts:5`。

这四条均为 type-only 导入。不能因为 `.d.ts` 不参加实现分析就先删去它，再选 `.ts`；也不能构造运行时调用。

## 可直接用于下一阶段的真实案例

旧的七条 oracle 范围误配均对应唯一、已解析的实现文件（逐条摘要与路径已核对）：

| 仓库 | 声明文件与起始行 | 唯一候选 |
|---|---|---|
| mxmvshnvsk/i18n-unused | src/core/action.ts:1 | src/types/index.ts |
| sunanakgo/nais3 | src/main/backup/repo.ts:3 | src/main/db/index.ts |
| roseforljh/qoneagent | apps/desktop/src/components/assistant-ui/tool-timeline-state.ts:2 | 同目录 tool-call-display.ts |
| smp46/pingvin-share-x | backend/src/main.ts:12 | backend/src/constants.ts |
| duplicati/ngclient | projects/ngclient/src/app/backup/general/general.component.ts:21 | projects/ngclient/src/app/core/openapi/index.ts |
| emircanagac/voxpery | apps/web/src/stores/toast.ts:2 | apps/web/src/secureId.ts |
| yu000jp/logseq-plugin-weekdays-and-weekends | src/rendering.ts:3 | src/lib.ts |

它们首先验证文件关联，不能一律要求函数调用边，尤其是类型导入和桶文件再导出。旧评分、旧 split 和旧未知合同保持原归属。

另有真实调查闭环案例 dembrane/echo，提交 `d5cb0a61cab5abac4b784c57d16a4a826cede15e`：

- `dembrane/platform/packages/tenancy/src/usage.ts:2` 从 `./numbers` 导入 pyRound。
- 唯一候选 `dembrane/platform/packages/tenancy/src/numbers.ts`，pyRound 定义在 6–22 行。
- withCapSignals 在 usage.ts 70–82 行，76 行直接调用 pyRound。
- 下一阶段应验证该安全直接调用及反向影响，并返回第 2 行导入来源。成功标准是减少这一次调查的手工补读，而非声称所有调用均可解析。

## 官方规则与产品边界

TypeScript 的无后缀路径及目录模块解析取决于解析模式和运行环境；目录中的 package.json 还可能改变入口。[TypeScript 模块引用](https://www.typescriptlang.org/docs/handbook/modules/reference.html#extensionless-relative-paths)

Node ESM 要求相对导入明确扩展，并明确目录 index 文件名。[Node ESM](https://nodejs.org/api/esm.html#mandatory-file-extensions)

因此产品应使用“保守源码关联”名称，并提供 `runtime_resolution: false`，不能将它写成完整 Node、TypeScript 或 bundler 解析。

## 研究过程的纠正记录

首次研究脚本误将 checkout receipt 的 canonical inventory 摘要与 inventory JSON 文件字节摘要比较，已按原 collector 的算法纠正；失败保存在 attempt-001。未改变输入或放宽验证。

首次独立引文校验将 CRLF 拆成规范化行，却拿它与保留 CRLF 的原引文比较；已改为只按 LF 分行并保留 CR 字节。`validation-attempt-001.json` 保留原因。修正后的验证核对 81 个输入摘要、80 个固定提交且干净的仓库、4,108 个声明来源文件、全部 10,279 条引文和七条旧 oracle。

未重跑完整 200 仓库产品回归，未修改历史评分、全局安装、用户 Skill 或目标源码。

## 下一阶段出口

参见 [设计](../superpowers/specs/2026-10-07-js-ts-source-association-design.md) 与 [执行清单草案](../superpowers/plans/2026-10-07-js-ts-source-association.md)。先批准新增语义，再实施合同用例、最小解析、调用来源、真实定向调查和候选安装验收。
