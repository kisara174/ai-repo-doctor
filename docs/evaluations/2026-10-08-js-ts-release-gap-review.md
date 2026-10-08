# JS/TS 完善发布缺口复核

日期：2026-10-08。基线0.7.0。此报告为真实来源研究与范围决策，不是0.8.0产品验收。

## 当前已经闭环的能力

0.7.0的Python默认、JS/TS显式选择、五个只读调查命令、有限ESM关联、来源证据和离线HTML/SVG已正式交付。现有release与安装记录仍保留原身份。新Goal要求在其基础上完善，不能再次用0.7.0已有结果当作新版本完成。

## 本轮可重现研究

证据根：`/Users/kisara/.local/share/ai-repo-doctor/evaluations/js-ts-release-completion-v1`。

- `baseline-contracts.log`：110项现有合同通过，无skip。
- `protection-before.json`：原14文件/65旧runtime/用户Skill核对通过，另保护0.7.0目录2426文件及8符号链接。
- `research/rejections.json`、summary.json、repositories.json：原研究中的130个拒绝文件，21个固定仓库，125 TS/5 JS；逐文件source SHA、仓库commit/tree和干净Git状态核对。
- `research/frontend-inventory.json`、frontend-parse-files.json、frontend-parse-summary.json：23个已见仓库，3332前端文件，逐文件摘要核对。grammar可行性3291 parsed、41 rejected；不是产品通过率或盲测。
- 研究脚本与stdout保留同目录。未运行目标代码、未安装目标依赖。

## 缺口与处理决定

| 缺口 | 实际证据 | 决定与产品收益 |
|---|---|---|
| 匿名MISSING错误未隔离 | 130个has_error文件中37个extract未返回error，部分仍返回符号；最小JS缺`}`、TS缺`)`可复现 | 必修。修复完整错误token检查，避免不可靠局部树进入上下文、调用和影响结果 |
| JSX/TSX实现完全排除 | 23仓库有3332个文件，其中现有grammar完整解析3291 | 增强。五个现有命令覆盖实际前端组件、结构与安全helper调用 |
| JSX隐含渲染/事件可能被误读为调用 | 语言语义与原静态调用模型不同 | 显式jsx-render限制，标签、props引用、匿名事件回调不虚构函数边；表达式中实际直接调用按原护栏判断 |
| TS grammar拒绝较新/复杂语法 | 原130样本含类型import/泛型等；不能直接判目标源码无效 | 本轮保留未知并隔离。上游现成PyPI仍0.23.2，没有证据支持简单升级即可修复；不修改源码来绕过解析 |
| 用户Skill/全局安装仍是Python维护线 | 全局0.5.3有明确保护；0.7.0独立环境已存在 | 完善新独立安装教程、包内Skill和导出验证，给出可直接调用路径，保留既有入口 |
| CommonJS、alias、方法/回调、多跳导出等 | 当前支持矩阵明确未知；未为其建立已批准的可靠绑定模型 | 列为后续独立语义目标，不能以猜测增加本轮覆盖，也不宣称0.8.0完整支持运行时 |

### 错误隔离说明

Tree-sitter的MISSING可能是匿名terminal。现有提取只遍历named_children寻找错误，遗漏缺括号/大括号等恢复节点；这是产品对自己“错误文件排除”的合同违反。37个漏报既包含截断测试夹具，也可能包含合法源码被旧grammar恢复的情况。修复目的为隔离不可信树，不能据此判断这37个目标文件无效。

最小复现：

```javascript
export function target() { return 1; }
export function broken() {
  return target();
```

0.7.0 tree.has_error为true，extract.error为空且返回target、broken。新合同要求最早错误物理行3、证据集合为空。

### 覆盖统计的限制

3250 TSX、82 JSX来自既有80 JS/TS仓库的冻结inventory，并非另取3332个随机样本。3291仅代表已安装grammar接受整文件；实际提取的符号、导入、调用及影响必须按新实施清单验证。41拒绝保持错误/未知，不采用fallback或局部树。

## 官方依据与实现出口

- [Tree-sitter错误节点](https://tree-sitter.github.io/tree-sitter/using-parsers/queries/1-syntax.html)：ERROR与MISSING都需要检测，匿名token是树节点。
- [上游TS/TSX grammar说明](https://github.com/tree-sitter/tree-sitter-typescript/blob/master/README.md)：两种方言分开选择。
- [上游PyPI版本](https://pypi.org/project/tree-sitter-typescript/)：查询时当前0.23.2；沿用固定依赖。

执行出口：[设计](../superpowers/specs/2026-10-08-js-ts-release-completion-design.md)与[实施清单](../superpowers/plans/2026-10-08-js-ts-release-completion.md)。本轮0.8.0的新增核心是可靠错误隔离和前端源码调查，完成定义同时包含安装、真实使用、正式发行与独立部署。
