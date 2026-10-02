# JS/TS 只读调查探索

执行起始：2026-10-02；收尾：2026-10-03（Asia/Shanghai）。文件名保留计划日期。当前阶段：A0–A3 完成；A4 等待最终去留核对。

稳定产品仍是 Python v0.5.2。实验在 `codex/js-ts-readonly-preview` worktree 进行，未改产品源码、稳定入口、已安装 Skill 或 Key。

## 固定来源与六个问题

| 来源 | 固定提交 | 调查问题 |
| --- | --- | --- |
| np | `591e003bfc57371cfb8236694e8d784ae5d6fe5f` | J1：CLI 到核心；J2：发布参数函数与关系；J3：入口、核心、发布文件的结构图 |
| ts-extras | `323908522c9f90f07f99378b43891da742f2319f` | T1：包入口与源码出口；T2：assertError 实现与影响边界；T3：源码入口与局部文件关系图 |

先冻结问题，再获取这两个提交。没有安装或执行样本代码。Git 下载曾遇到 TLS 错误，同一固定提交重试后成功。GraphFlow 读取样本时生成的未跟踪缓存已保留到评估目录的 `graphflow-artifacts/`，没有修改样本源文件；两个样本工作区重新核对为干净。

## 独立源码参考

- np 的 `source/cli.js` 是命令入口，使用动态 import 进入 `cli-implementation.js`。动态路径不应变成静态 ESM 导入边。实现文件中的 `getOptions` 位于 145–250 行，核心 `np` 位于 `source/index.js:71–350`。
- np 的发布参数函数 `getPackagePublishArguments` 位于 `source/npm/publish.js:6–26`；`runPublish` 位于 49–111 行。该文件的 `./util.js` 指向 `source/npm/util.js`，不能与根层 `source/util.js` 混淆。嵌套函数、回调和接收者方法需要明确保留未知关系。
- ts-extras 包 exports 指向 `distribution`，固定源码中没有构建产物。`source/index.ts` 通过 `.js` 路径 re-export `.ts` 实现。这是源码文件关系，不能宣称包入口可直接运行。
- `isDefined` 实现位于 `source/is-defined.ts:16–18`；`assertError` 位于 `source/assert-error.ts:53–60`，其中 `describeValue` 的源码调用在第 59 行。JSDoc 例子中的 import/调用不是代码关系。
- `objectMapValues` 有重载签名，其唯一实现位于 146–169 行；`objectEntries` 是现有对象方法的类型断言别名，不应伪装成具名函数定义。类型导入需要保留 type-only 信息。

这些参考由固定源码手工建立，包含逐段引文、整文件 SHA256、行范围和固定提交 URL；没有从后续 parser 输出反推。

## 实际记录与计数方法

证据根：`/Users/kisara/.local/share/ai-repo-doctor/evaluations/js-ts-readonly-preview`。

`questions.json` 冻结问题；`sources.json` 固定来源；`oracle.json` 保存六题参考；`baseline/` 保存真实源码读取和搜索命令；`compat/` 保存稳定 CLI 的实际输出。`tools/js_ts_trial.py check-sources` 和 `check-oracle` 均通过。

每题新增源码读取/定位动作分别为 J1=6、J2=2、J3=3、T1=3、T2=1、T3=3。已有材料复用单独记录、不重复计数。该计数仅描述本次观测工作流，前期选样阅读不计入，也不代表人类耗时或普遍效率。

稳定 CLI 的两个 overview 和两个 symbols 均退出 0；没有返回 JS/TS 符号 ID，所以没有虚构 ID 调用 context/impact。兼容命令不计入上述源码基线。

## A2 解析器核对

在仓库外独立 venv 安装 tree-sitter 0.26.0、JavaScript grammar 0.25.0、TypeScript grammar 0.23.2，使用 binary wheels；当前 Python 3.14.5 / Mac arm64。实际安装退出 0，pip-report.json 保留三包分发 URL 和 SHA256。两种语言的 Unicode/emoji、CRLF、BOM、无末尾换行和错误语法共 10 项检查通过。详情见 dependency-check.json；没有安装另一套后端或运行 Node。

[Tree-sitter 官方接口](https://github.com/tree-sitter/py-tree-sitter)满足本轮语法节点与行号提取；[TypeScript Compiler API](https://github.com/microsoft/TypeScript/wiki/Using-the-Compiler-API)还提供 Program 与类型检查器，并采用 npm/Node 工具链，本轮只比较资料，没有安装。本产品的唯一候选规则比[TypeScript 扩展替换](https://www.typescriptlang.org/docs/handbook/modules/reference.html#file-extension-substitution)更保守，不能冒充编译器语义。

## A3 原型与六题结果

原型位于 `experiments/js_ts/spike.py`，独立运行 overview、symbols、context、impact、map。它记录具名函数、const 箭头、类/方法、重载与 ESM 文件关系；普通调用只保存位置。impact 的空列表同时返回 `status=not-supported`，不表示没有影响。关系图是现有渲染器的实验适配，正式 viewer 未改。

一个 Luna Max 执行者只复制了 12 个预先冻结的静态夹具；主代理检查实际内容并重新验证。12 项聚焦原型测试通过，没有重复 Python 完整套件。普通环境跳过这些可选实验测试；隔离解析器环境必须全部实际运行，没有跳过。

### 真实故障与修正

第一次 np 运行 exit 139。自写 300 函数的受控遍历中，读取 Point 属性 exit -11，读取字节偏移 exit 0。原型改为依据 UTF-8 换行字节表计算行号/列；同一崩溃回归随后通过，版本和支持范围未扩大。这与[上游 Point.column 问题](https://github.com/tree-sitter/py-tree-sitter/issues/487)表现相关，但没有确认其底层根因。原始崩溃、受控比较和修正后的验证均保留。

另有一次外部验证脚本因模块搜索路径失败，使用显式 runpy 调用后通过；第一次输出保留。trial 草稿的相对路径也被校验拒绝，随后统一为证据根内绝对路径，未改回答或动作数。

### 六题结果与观察到的动作

| 题目 | 结果 | 源码基线 | 原型加补读 | 实际回答与限制 |
| --- | --- | ---: | ---: | --- |
| J1 | bounded | 6 | 9 | 找到核心和选项函数；120 行上下文截断，动态 bootstrap、package 和剩余源码需补读 |
| J2 | answered | 2 | 2 | 发布参数函数 6–26 和 runPublish 49–111 源码完整；文件关系有行依据，普通影响不支持 |
| J3 | answered | 3 | 5 | CLI 实现→核心→发布/发布辅助文件边正确；动态入口缺边，聚焦符号图没有普通调用边 |
| T1 | bounded | 3 | 5 | 定位 isDefined 16–18；源码 re-export 与 distribution 构建入口分开，package 信息需补读 |
| T2 | answered | 1 | 3 | assertError 53–60 与 describeValue 3–17 源码完整；第 59 行调用由源码解释，未冒充已解析边 |
| T3 | answered | 3 | 6 | 源码 barrel 和多个实现文件关系正确；objectMapValues 唯一实现 146–169，类型依赖不等于运行调用 |

answered 表示支持范围内的回答完成；bounded 表示工具本身只覆盖问题的一部分，补读事实单独保存。4/6 题在支持范围内完成，两仓库各 2 题；六题均有真实记录。

计数仍使用 A1 冻结的问题与源码基线。新增命令或独立源码/图读取算一次，跨题复用已标明、不再计数；oracle 验收与环境准备另列，没有算作试验动作。合计基线 18 次、试验 30 次。两边并非盲测，主代理先建立参考，已有阅读知识不能消除；这个小样本结果不能外推到所有仓库或人类效率。

保存 23 次成功原型命令，无 stdout/stderr 截断；最慢约 0.21 秒，仅代表本机。两仓库分别生成总览和聚焦地图，共 4 份 HTML/JSON、8 份 SVG。11 条符号参考、18 条正文件关系参考、6 条负例逐条通过核对（包含跨题复用，数量不是唯一对象数）；6 份 context 合计 263 行引文核对一致，各自不超过 120 行。动态图入口、接收者调用与回调没有伪造边。

原始材料：`trial.json`、`trial-commands/`、`supplements/`、`maps/`、`oracle-comparison.json`、`oracle-comparison-command-002.json`。当前代码随后补充了不支持源码扩展的限制提示，并修正解构参数默认值的绑定提取、对未知绑定保守标记限制；已保存的原始命令和图保持原样，该变更不改变已选符号、文件边或动作计数。最终原型源码与夹具另存 SHA256。

## 待完成的去留核对

A4 核对五项门槛并保存 gate.json。只有全部通过才实施 B1–B4 产品接入和独立预览交付；不能用“解析器可运行”替代实际调查收益。
