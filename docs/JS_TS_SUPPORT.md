# 0.6.0 JS/TS 基础支持矩阵

## 支持范围

| 能力 | 0.6.0 行为 |
|---|---|
| 文件选择 | 显式选择 javascript / typescript；实现文件 `.js`、`.mjs`、`.ts`；遵循 ignore、不追踪 node_modules |
| 符号 | 具名函数、顶层 const 函数/箭头、类/方法位置；async、default；TS 重载与实现区分 |
| 文件依赖 | 明确本地 ESM 路径；TS 的显式 `.js` 路径仅在已选实现唯一时可关联 `.ts`；歧义保留未知 |
| 调用 | 唯一、未遮蔽、未改写的直接函数绑定和直接 ESM 导出；每条提供 caller/callee/文件/物理行 |
| 类型引用 | import type / type-only export 不形成运行调用；声明记录与运行关系区分 |
| context | 目标优先、真实源码行、可选 include-symbol、预算和截断标识；歧义 ID 拒绝 |
| impact | 已解析反向直接调用的有界遍历；depth=2 可核对逐跳证据；空结果不代表无影响 |
| map | 离线 HTML、两份 SVG、JSON；混合语言可查看；每视图至多 200 节点/500 边，显示隐藏数量 |
| 错误/限制 | 不可读或解析失败文件排除证据；analysis limits 最多显示 50 条并保留省略计数 |

符号存在不等于能解析其调用。静态源码关联不证明运行时执行，也不证明问题存在。

## 明确未知或未支持

- 无后缀导入（`./core`）、目录 index、路径别名、外部 package；不模拟 tsconfig、bundler 或 Node 的完整解析。
- CommonJS、JSX/TSX、`.cjs/.mts/.cts`、`.d.ts` 声明实现分析。
- 对象/实例/this 方法、匿名回调、动态 import 调用、多跳 re-export 调用、运行时替换和仓库外调用。
- Tree-sitter 对部分较新或复杂 TS 语法的覆盖有限。解析错误说明当前后端拒绝了文件，不能据此直接断言目标代码无效。
- JS/TS snapshot、case/findings、诊断和自动修复。源码判断与修改由 Codex 完成。

当关系未解析时，Codex 应补读 import 声明和使用点，并明确区分源码可见关系与工具已解析边。不得用同名目标猜测连接。

## 验证结论和下一步

[J5 固定样本报告](evaluations/2026-10-07-js-ts-support-validation.md)：12 个已见仓库、36 题，32 answered、4 bounded；没有将范围外题计为回答成功，也没有新的 200 仓库全量或盲测结论。地图 viewer 沿用 a5 实际交互证据，本次新地图仅做产物检查。

下一阶段优先量化无后缀/目录 index 对实际调查的影响，再定义保守源码关联；随后研究已记录的 TS grammar 拒绝文件。两项都需独立来源与反例，不能直接扩成完整运行时解析。本版不增加新用户接口或自动修复。
