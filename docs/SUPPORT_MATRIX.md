# 1.0 平台与能力支持矩阵

<!-- repo-doctor-development-version: 1.0.1 -->

当前源版本为 1.0.1，继承已验证 rc2 的源码物理行修复及独立 JSX grammar 后端。正式发行的精确提交及公开下载验收见 [1.0.1 交付记录](delivery/2026-10-09-v1.0.1-release.md)。[安装指导](INSTALL.md) 与 [CLI 合同](CLI_CONTRACT.md) 规定使用方式。下表属于既有 1.0.0 及其前置候选的证据，1.0.1rc2 的独立证据列于下方候选小节；正式提交 CI 与产物身份见 [交付记录](delivery/2026-10-08-v1.0.0-product-closure.md)。不能用本地 ARM Mac 结果代替其他系统/版本的运行证据。

## 平台门禁

| 系统/架构 | Python | Python-only 安装 | JS-extra 安装 | 证据状态 |
| --- | --- | --- | --- | --- |
| Ubuntu 24.04 / x86_64 | 3.11、3.12、3.13、3.14 | 各独立 venv，核心五步/绑定 Skill，保留旧生命周期门禁 | 各独立 venv，核心五步/绑定 Skill，原 JS 安装门禁 | `88392c1` 远端安装通过 |
| macOS 15 / arm64 | 3.11、3.14 | 各独立 venv，核心五步/绑定 Skill | 各独立 venv，核心五步/绑定 Skill | `88392c1` 远端安装通过 |
| 本地 macOS 27.0.1 / arm64 | 3.14.5 | 独立安装 11 条命令 | 独立安装 16 条命令 | V3 源码 `50a97b8` 已通过，不等于正式发行 |
| Windows、Intel Mac、其他 Linux 架构 | 未列入本轮 | 未验收 | 未验收 | 不承诺 |

CI 每个安装 runner 记录 uname、Python、实际平台/架构，并保留安装回执 artifact。macos-15 的默认架构依据 [GitHub 官方 runner 文档](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)选择，最终仍以实际 machine.json 为准。Python 矩阵使用 [setup-python](https://github.com/actions/setup-python) 获取对应版本。

最低 Python 为 3.11；包元数据的最低要求不等于所有未来 Python 或操作系统已经验收。JS-extra 固定 Tree-sitter 0.26.0、JavaScript grammar 0.25.0、TypeScript grammar 0.23.2；这些属于工具依赖，安装不会安装目标仓库依赖。

上句为正式 1.0.0 的依赖身份。1.0.1rc2 开发候选改为 Tree-sitter 0.26.0、独立 companion 0.1.0（JS/TSX）与官方 TypeScript grammar 0.23.2；companion 使用 CPython 3.11 abi3，JS 语言 ABI 15、TSX 语言 ABI 14。候选平台验证记录单独归档，不能将本表的旧结果自动转标。Windows、Intel Mac、Linux ARM/musl 和 free-threaded Python 不属于本次承诺。

## 功能门禁

| 能力 | Python | JavaScript/JSX、TypeScript/TSX |
| --- | --- | --- |
| overview / symbols / context / impact / map | 默认启用 | 需 js extra，每次显式选择语言 |
| 离线 HTML / structure.svg / relations.svg / map.json | 支持 | 混合语言支持 |
| 直接调用与导入来源证据 | 保守静态解析 | 保守静态 ESM/具名绑定；不是 Node/bundler 等价模拟 |
| snapshot / 案件 / findings 保存 | 保留原 Python 合同 | 不支持，显式拒绝 |
| 自动诊断/修复 | 不属于核心五步目标；历史参考见 [兼容使用](LEGACY_USAGE.md) | 不支持 |

细节见 [JS/TS 支持范围](JS_TS_SUPPORT.md)、[源码/时间/深度边界](RESOURCE_LIMITS.md)。空影响不是没有影响；未知、语法隔离、歧义和截断必须保留。

地图 viewer/search/真实 DOM 与 SVG 的既有门禁保留。Node 24 / jsdom 30.1.1 只用于开发验证；用户运行 Python、JS/TS 分析或打开 HTML 不需要 Node。DOM 自动验证不代替 V5 实际浏览器查看。

## 当前候选证据归属

V3 精确构建 `50a97b84327860c86a33d4456285838e770bb399`：35 个 runtime 文件源码/wheel/两套安装一致，119 项冻结相关回归和 40 条自有规模查询通过。阶段新增 CI 和之后 RC/正式版须记录各自精确 SHA，历史 200 仓库结果不重标为当前候选全量验收。

V4 平台门禁：[push 运行](https://github.com/kisara174/ai-repo-doctor/actions/runs/37771770415)与[PR 运行](https://github.com/kisara174/ai-repo-doctor/actions/runs/37771840654)均指向 `88392c131818c1d5e90cad9b859a70f1223bf69a`，各 11 个任务全部成功。下载并核对 push 的 10 份 runner artifacts，包含 12 份独立 base/js 安装 summary、162 条实际/预期退出码一致的命令（36 条预期拒绝）。Linux 实际 x86_64/glibc2.39，macOS 实际 15.7.9/arm64。既有生命周期和地图 DOM/SVG job 保留并通过。

## 1.0.1rc2 原生 grammar 候选门禁

本候选独立验证，未改变上面旧版证据归属；详见 [候选交付](delivery/2026-10-09-jsx-grammar-repair.md)。发行件构建来源为 `a41a5c1e4208a7ba2d644b52019a9f7b3bedc765`，两轮CI各15任务成功；后续 `aa20a7e` 的两轮15任务增加安装指导原样执行验收，也已通过。

| 实际运行环境 | Python | 安装结果 |
| --- | --- | --- |
| Ubuntu24.04 / x86_64 / glibc2.39 | 3.11、3.12、3.13、3.14 | base独立安装、同提交manylinux companion + JS-extra独立安装均通过 |
| macOS15.7.9 / arm64 | 3.11、3.14 | base与macosx_11_0_arm64 companion + JS-extra独立安装均通过 |
| 本地macOS27 / arm64 | 3.14.5 | 四文件候选安装指导原样执行通过，原R051五命令闭环通过 |

两平台companion严格abi3审计通过；Mac 11.0 tag仅为二进制最低目标，不作Mac11实机验收声明。用户不需要Node或编译器；不支持的平台在仅本地匹配wheel时拒绝。候选尚未正式发布，正式1.0.0仍为原安装入口。

1.0.1 正式源需要自己的 exact-head CI 和公开发行件安装回执；不能重标上面的 rc2 产物。详见正式交付记录及 Release 的 release-receipt.json。
