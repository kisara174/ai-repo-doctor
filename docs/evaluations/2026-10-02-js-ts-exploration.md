# JS/TS 只读调查探索

执行日期：2026-10-02。当前阶段：A0–A2 完成；原型和去留门槛尚未验证。

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

## 未完成项

A3 AST 原型、夹具和六题调查；A4 五项去留门槛。只有 A4 go 后才实施产品接入和独立预览交付。
