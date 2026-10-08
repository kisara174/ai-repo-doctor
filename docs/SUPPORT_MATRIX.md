# 1.0 平台与能力支持矩阵

<!-- repo-doctor-development-version: 1.0.0.dev1 -->

当前为 1.0.0.dev1 开发候选，公开版仍为 0.8.0。[安装指导](INSTALL.md) 与 [CLI 合同](CLI_CONTRACT.md) 规定新候选的使用方式。下表的新增远端组合等待精确提交 CI 回执；不能用本地 ARM Mac 结果代替其他系统/版本的运行证据。

## 平台门禁

| 系统/架构 | Python | Python-only 安装 | JS-extra 安装 | 证据状态 |
| --- | --- | --- | --- | --- |
| Ubuntu 24.04 / x86_64 | 3.11、3.12、3.13、3.14 | 各独立 venv，核心五步/绑定 Skill，保留旧生命周期门禁 | 各独立 venv，核心五步/绑定 Skill，原 JS 安装门禁 | 待本阶段远端 CI |
| macOS 15 / arm64 | 3.11、3.14 | 各独立 venv，核心五步/绑定 Skill | 各独立 venv，核心五步/绑定 Skill | 待本阶段远端 CI |
| 本地 macOS 27.0.1 / arm64 | 3.14.5 | 独立安装 11 条命令 | 独立安装 16 条命令 | V3 源码 `50a97b8` 已通过，不等于正式发行 |
| Windows、Intel Mac、其他 Linux 架构 | 未列入本轮 | 未验收 | 未验收 | 不承诺 |

CI 每个安装 runner 记录 uname、Python、实际平台/架构，并保留安装回执 artifact。macos-15 的默认架构依据 [GitHub 官方 runner 文档](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)选择，最终仍以实际 machine.json 为准。Python 矩阵使用 [setup-python](https://github.com/actions/setup-python) 获取对应版本。

最低 Python 为 3.11；包元数据的最低要求不等于所有未来 Python 或操作系统已经验收。JS-extra 固定 Tree-sitter 0.26.0、JavaScript grammar 0.25.0、TypeScript grammar 0.23.2；这些属于工具依赖，安装不会安装目标仓库依赖。

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
