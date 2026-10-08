# JS/TS 完善正式版设计

日期：2026-10-08。状态：按用户活跃 Goal 和会话中自主执行授权推进；主代理负责范围、实现、复核与发版。基线：0.7.0，源码 `4c3a709aac332da2ce238de1fcf8cfa60473f335`，发行提交 `552b23f7e26462b084b0ac3744a801e66ab26bad`。工作分支 `codex/js-ts-release-completion`。

## 目标与实际问题

交付 0.8.0：使 Codex 能用现有五个只读调查命令分析实际前端 JS/TS 源码，获取可核对的符号、文件依赖、已有安全直接调用和反向影响；人类仍只看离线结构关系图。安装、CI、公开 wheel 与本机独立部署必须闭环。

本轮不是重新宣布已发布的0.7.0完成，也不把“所有JS/TS运行时语义”作为静态工具能够兑现的承诺。必须落实下述真实缺口，明确未知，不以更多测试数量代替产品效果。

### 已验证事实

证据根目录：`/Users/kisara/.local/share/ai-repo-doctor/evaluations/js-ts-release-completion-v1`。

1. 干净基线相关合同110项通过；原项目14文件/65旧runtime/用户Skill摘要无变化。新增保护0.7.0目录2426个文件和8个符号链接。
2. 对原80个JS/TS固定仓库中130个后端排除文件逐文件复核：125 TS、5 JS，来自21仓库。37个 `root_node.has_error` 文件仍被 `extract` 返回部分证据。错误检查遍历 `named_children`，遗漏匿名 `MISSING` 标点。截断JS缺 `}`、TS调用缺 `)` 均有最小复现。37是本轮固定样本内的已见计数，不能推广到所有仓库。
3. 原80仓库inventory中23仓库有3332个前端文件（3250 TSX、82 JSX）。独立grammar可行性解析3291通过、41拒绝。尚未完成产品验证，不能写成新增成功分析3332文件。
4. 固定依赖已含JSX可用的JS grammar及单独 `language_tsx()`。上游PyPI当前TS grammar仍为0.23.2；不假设升级即可修复新TS语法。

## 方案比较与选择

- **选择：** 保留三个固定依赖，修复全部错误token隔离，按扩展选择TS/TSX grammar，新增.jsx/.tsx实现覆盖。已有模型、CLI、ESM和地图管线复用，收益能在固定源码复核。
- 仅修错误隔离：必要但不能满足真实前端调查覆盖的完善目标。
- 换后端或自建grammar：当前缺乏已发布替代收益证据，新增构建与兼容风险，不作为此次发行路径。

## 设计合同

### D1：完整错误隔离

错误token检查覆盖 named 和 anonymous children。`ERROR` 或 `is_missing` 存在时，整文件不得返回 symbols、esm_imports、esm_exports、calls、identifier_uses、top_level_symbols、unsafe_bindings 或 class_header_spans。返回现有 ParseError 格式及按UTF-8字节计算的最早物理行；避免访问已知不稳定的native Point.column。

无错误树仍沿用已有命名节点提取逻辑，不改变Python、不启用语法恢复或改写目标源码。解析拒绝不能说明目标源码无效。先修错误隔离，才新增方言覆盖。

### D2：JSX/TSX 文件选择与方言

语言枚举不变：python、javascript、typescript。默认仍python。

- javascript实现扩展：`.js .mjs .jsx`。
- typescript实现扩展：`.ts .tsx`。
- `.ts`使用TypeScript grammar，`.tsx`使用独立TSX grammar，绝不在失败后自动换方言。`.jsx`使用现有JavaScript grammar。
- `.d.ts`、`.d.mts`、`.d.cts`声明实现，`.mts/.cts/.cjs`以及CommonJS解析仍不属于本次新增范围。
- `parse_tree(source, language, *, tsx=False)`保留原调用，新增显式TSX选项；`extract(... file=..., language=...)`从受支持file后缀选择。private `_parser(language, *, tsx=False)`缓存三个有效parser；javascript+tsx=True拒绝。
- 扫描与read_source的ignore、node_modules、链接、根身份和UTF-8约束完全复用。

JS/TS analysis新增 `source_extensions`（按requested JS/TS语言列出支持后缀），不向默认Python JSON追加字段。移除jsx/tsx的旧unsupported-source-kind提示；仍未选择的语言不能因为扩展支持就被读取。

### D3：关系、证据与未知

ESM有限候选并集已含jsx/tsx；只在已选择且完整解析的唯一实现上建立文件边，歧义和目录配置拒绝规则不变。TSX来源的 `.js` specifier使用现有TypeScript唯一替换候选规则；不新增自定义优先级。

JSX元素名、属性引用、事件handler引用不是普通调用；不得虚构 `<Card />` → Card 或 `onClick={handler}` 的函数调用。实际JSX表达式内 `helper()` 可按原安全直接调用规则返回证据；事件内匿名回调、对象方法、包/alias、多跳re-export和运行时替换仍未知。

具名组件函数、顶层const箭头、类/方法位置复用现有符号合同。memo/forwardRef等包装的匿名组件不新建推测符号。JS/TS元数据明确 `jsx-render` 范围限制（实际出现JSX节点时记录有行号的limit），并继续 `runtime_resolution:false`。

context/impact保留 `via_esm_import` 实际绑定证据；源码行预算、截断、符号歧义拒绝都保持。地图展示实际结构与已有证据，200节点/500边限制保持，无新viewer交互或自动诊断/修复。

### D4：验证与交付

- 错误隔离：最小named/anonymous MISSING正反合同；原130个拒绝文件均不得泄漏证据（按同一固定源码检查）。
- 前端：JSX/TSX函数与精确位置、Unicode/BOM/CRLF、TS独有尖括号类型断言不被TSX误替代、默认Python不读前端、不合格/歧义目标拒绝。
- 关系：真实直接调用、JSX标签/props无假边、匿名callback无假边、TSX的.js替换、相对无后缀/index、context/impact来源和地图/SVG一致。
- 真实调查：从固定已见集合冻结至少一个JSX、两个TSX仓库的问题和source hash，覆盖组件搜索/上下文、实际导入、实际直接helper调用及影响；若某题无直接调用，明确作为结构题，不伪造要求。
- 不把原研究可行性、旧200评分或旧浏览器动作重新归属为本轮产品验收。新地图检查以产物/DOM性质记录，不声称新浏览器验收。
- 一次完整本地单元＋受影响相关合同；每次修改仅重跑实际受影响门槛。正式安装base、js-extra、Python生命周期均按预期退出码验收，保留负例非零记录。
- 新候选0.8.0a1及正式0.8.0分别冻结；正式来源通过精确SHA七项CI、独立wheel/source/installed runtime字节一致和真实调查。合并、公开GitHub wheel、SHA256SUMS、匿名下载身份和独立CLI部署完成后才闭环。

### D5：保护与部署

全局0.5.3及安装用户Skill保持；从正式wheel导出新的Skill到本次交付目录，验证导出内容与包内内容一致。发布文档给出完整独立CLI路径与五步调查命令；不自动覆盖用户现有设置。

沿用原0.5.3保护manifest，并补充本轮protection-before.json对0.7.0的保护。最后完整核对原14文件、150789证据、65runtime、用户Skill以及0.7.0文件/链接；新增证据全部在新目录。目标仓库代码与依赖均不执行、不安装；无DeepSeek调用。

## 官方依据

- [Tree-sitter ERROR/MISSING与匿名节点](https://tree-sitter.github.io/tree-sitter/using-parsers/queries/1-syntax.html)：两种错误节点需要完整覆盖。
- [官方TypeScript/TSX grammar](https://github.com/tree-sitter/tree-sitter-typescript/blob/master/README.md)：两个方言使用不同grammar。
- [PyPI TS grammar当前发行](https://pypi.org/project/tree-sitter-typescript/)：本轮查询为0.23.2。

## 完成条件

D1–D5均有对应实施与验收证据；新增前端调查有真实收益、未引入猜测关系；已知阻塞全部处理；正式包公开可下载，独立部署及五步流程可用；原状态保护通过。完整Goal保持到正式交付完成。
