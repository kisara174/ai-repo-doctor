# JS/TS 基础支持与源码关联矩阵

调用脚本和 Codex 的公共返回约定见 [CLI / JSON 合同](CLI_CONTRACT.md)；分析限制与运行时结论必须区分。

0.8.0 新增 JSX/TSX 实现分析与完整 ERROR/MISSING 整文件隔离；0.7.0 增加下述保守源码关联。旧版 0.6.0 仍沿用明确扩展路径合同；正式发行身份和验收结果见 [0.8.0交付记录](delivery/2026-10-08-v0.8.0-js-ts-completion.md)；[0.7.0历史](delivery/2026-10-08-v0.7.0-source-association.md)保留。

## 支持范围

| 能力 | 本分支行为 |
|---|---|
| 文件选择 | 显式选择 javascript / typescript；实现文件 `.js`、`.mjs`、`.jsx`、`.ts`、`.tsx`；TS/TSX 使用不同 grammar；遵循 ignore、不追踪 node_modules |
| 符号 | 具名函数、顶层 const 函数/箭头、类/方法位置；async、default；TS 重载与实现区分 |
| 文件依赖 | 明确本地 ESM 路径及旧 TS `.js` 替换；新增无后缀文件/index 的唯一可见实现源码关联；先判断歧义再检查语言选择与解析状态 |
| 调用 | 唯一、未遮蔽、未改写的直接函数绑定和直接 ESM 导出；每条提供 caller/callee/文件/物理行，导入调用另提供实际 `via_esm_import` 来源 |
| 类型引用 | import type / type-only export 不形成运行调用；声明记录与运行关系区分 |
| context | 目标优先、真实源码行、可选 include-symbol、预算和截断标识；歧义 ID 拒绝 |
| impact | 已解析反向直接调用的有界遍历；depth=2 可核对逐跳证据；空结果不代表无影响 |
| map | 离线 HTML、两份 SVG、JSON；混合语言可查看；每视图至多 200 节点/500 边，显示隐藏数量 |
| 错误/限制 | 不可读或解析失败文件排除证据；analysis limits 最多显示 50 条并保留省略计数 |

符号存在不等于能解析其调用。静态源码关联不证明运行时执行，也不证明问题存在。JS/TS analysis 提供 `esm_source_resolution.runtime_resolution: false`。context/impact 的调用来源包含导入文件、声明行段、specifier、绑定和关联种类；impact 文件依赖另提供 `esm_source_association`。

JS/TS 元数据 `source_extensions` 明确所选语言的实现后缀；实际 JSX 节点产生 `jsx-render` 限制说明。错误树包含匿名 MISSING 标点时同样整文件排除，不返回恢复树的部分符号或关系。

## 新增路径的保守边界

文件与目录 index 同时进入候选并集，不选择扩展或文件优先级。`.ts` 与 `.d.ts`、`.js` 与 `.ts`、文件与 index 等多个可见候选都拒绝，即使其中一个不参加实现分析也不先删去。只有唯一候选、已选择语言、受支持实现扩展且成功解析时才连接。

候选后缀为 `.ts .js .mjs .tsx .jsx .d.ts .mts .cts .cjs .d.mts .d.cts .json .node`，并检查无扩展 exact 文件；不受支持的后缀只参与拒绝歧义，不获得实现支持。该有限集合不覆盖自定义加载器。目录 package.json 可见时拒绝新增关联，不读取配置。URL 特殊字符、尾随斜杠、转义、外部来源保留未知。关联仍只覆盖扫描器可见、安全、仓库内文件。

类型导入、namespace 和再导出可建立文件依赖；只有现有安全直接调用规则通过才有函数边。桶文件多跳调用仍不解析。源码行段引用不额外塞入源码引文，context blocks 仍按 max-lines 预算提供内容。

## 明确未知或未支持

- 无后缀/index 的歧义或不合格候选、路径别名、外部 package；不模拟 tsconfig、bundler 或 Node 的完整解析。
- CommonJS、`.cjs/.mts/.cts`、`.d.ts` 声明实现分析。
- JSX 标签、props/事件引用不作为函数调用；包装匿名组件不猜测符号。实际 JSX 表达式内安全直接 helper 调用可解析。
- 对象/实例/this 方法、匿名回调、动态 import 调用、多跳 re-export 调用、运行时替换和仓库外调用。
- Tree-sitter 对部分较新或复杂 TS 语法的覆盖有限。解析错误说明当前后端拒绝了文件，不能据此直接断言目标代码无效。
- JS/TS snapshot、case/findings、诊断和自动修复。源码判断与修改由 Codex 完成。

当关系未解析时，Codex 应补读 import 声明和使用点，并明确区分源码可见关系与工具已解析边。不得用同名目标猜测连接。

## 验证结论和下一步

[J5 固定样本报告](evaluations/2026-10-07-js-ts-support-validation.md)：12 个已见仓库、36 题，32 answered、4 bounded；没有将范围外题计为回答成功，也没有新的 200 仓库全量或盲测结论。地图 viewer 沿用 a5 实际交互证据，本次新地图仅做产物检查。

无后缀/index 的量化研究、设计及实施出口见 [研究报告](evaluations/2026-10-07-extensionless-source-survey.md) 与 [实施清单](superpowers/plans/2026-10-07-js-ts-source-association.md)。新的定向结果不能回写旧评分或称为新一轮完整 200 回归。后续可研究已记录的 TS grammar 拒绝文件，但需单独来源与反例。本轮不增加新命令或自动修复。

## 0.8.0 定向前端验证

[固定题与执行器](../evaluation/js-ts-release-completion/README.md) 覆盖一个 JSX、两个 TSX 已见仓库，题目来源在产品运行前手工核对并固定 commit/tree/SHA。组件上下文按120行预算，两个 helper 调用及反向影响核对实际 import 来源，地图核对 SVG 与 JSON 投影。它不是新一轮200仓库回归或盲测；正式安装和公开发行结论以交付记录为准。
