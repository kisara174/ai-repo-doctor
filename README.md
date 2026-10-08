# AI Repo Doctor

为 Codex 提供本地 Python、JavaScript、TypeScript 仓库的结构、静态调用证据和有界源码上下文，并生成供人查看的离线交互 HTML 与 SVG 关系图。Codex 负责问题判断和代码修改；Repo Doctor 提供可核对的源码证据。主要流程无需 API Key，不运行目标仓库代码。

**0.8.0 支持范围**：Python 默认启用；JS/TS 通过可选 `[js]` 安装并显式选择语言。需要 Python 3.11+，JS/TS 分析不需要 Node。详细支持范围见 [支持矩阵](docs/JS_TS_SUPPORT.md)，验证证据见 [J5 报告](docs/evaluations/2026-10-07-js-ts-support-validation.md)。

支持 `.jsx` / `.tsx` 组件搜索、源码上下文、文件依赖和安全直接调用；`.ts` 与 `.tsx` 分别使用对应方言。JSX 标签、属性引用及匿名回调不建立推测函数边。修复匿名 MISSING 错误文件泄漏部分证据的问题。

保留无后缀/index 的唯一源码关联及实际导入来源输出，方便 Codex 继续调查。多候选、目录配置或不合格实现保持未知；关联不证明运行时模块解析。见 [设计与边界](docs/superpowers/specs/2026-10-07-js-ts-source-association-design.md)。

## 安装

发行方式为 [GitHub wheel](https://github.com/kisara174/ai-repo-doctor/releases/tag/v0.8.0)，目前没有 PyPI 发行。两种安装使用同一个 wheel。

仅使用 Python（没有无条件运行依赖）：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'https://github.com/kisara174/ai-repo-doctor/releases/download/v0.8.0/ai_repo_doctor-0.8.0-py3-none-any.whl'
.venv/bin/repo-doctor --version
```

同时使用 JS/TS（安装三个固定版本的 Tree-sitter 可选依赖）：

```sh
python3 -m venv .venv-js
.venv-js/bin/python -m pip install 'ai-repo-doctor[js] @ https://github.com/kisara174/ai-repo-doctor/releases/download/v0.8.0/ai_repo_doctor-0.8.0-py3-none-any.whl'
.venv-js/bin/repo-doctor --version
```

以下 `repo-doctor` 表示所选环境中的完整 CLI 路径，或已加入 PATH 的入口。默认扫描遵循目标仓库 ignore 规则；没有安装 extra 时，显式 JS/TS 选择会报错并提示安装方式。

本机原有全局 Python 入口继续使用 [0.5.3](https://github.com/kisara174/ai-repo-doctor/releases/tag/v0.5.3)，其维护线和回滚包保留。0.8.0 独立部署路径见 [交付记录](docs/delivery/2026-10-08-v0.8.0-source-association.md)。

## Codex 调查仓库

```sh
repo-doctor overview /path/to/repo --json
repo-doctor symbols /path/to/repo --query NAME --json
# 从搜索结果复制真实 ID，替换 REAL_ID
repo-doctor context /path/to/repo REAL_ID --max-lines 120 --json
repo-doctor impact /path/to/repo REAL_ID --depth 2 --json
repo-doctor map /path/to/repo --out ./new-repo-map
```

JS/TS 必须在每个命令中选择语言：

```sh
repo-doctor overview REPO --languages javascript,typescript --json
repo-doctor symbols REPO --query NAME --languages javascript,typescript --json
repo-doctor context REPO REAL_ID --max-lines 120 --languages javascript,typescript --json
repo-doctor impact REPO REAL_ID --depth 2 --languages javascript,typescript --json
repo-doctor map REPO --languages javascript,typescript --out NEW_MAP
```

JavaScript 覆盖 `.js .mjs .jsx`，TypeScript 覆盖 `.ts .tsx`；使用搜索返回的组件 ID 即可执行上述流程。JSX 表达式中的安全直接 `helper()` 调用可以返回证据，组件渲染和事件绑定仍需 Codex 查阅源码。

混合仓库可选 `--languages python,javascript,typescript`；默认仍仅 Python，不自动猜测语言。用 `--include-symbol REAL_ID` 补充上下文；行预算和截断标识始终有效。空影响结果只说明没有返回已解析的调用者，不能证明没有影响。

打开地图目录中的 `map.html`，可搜索、展开、筛选、聚焦和缩放；另有 `structure.svg`、`relations.svg`、`map.json`。页面可导出当前视图 SVG，无需服务或联网。地图只展示结构关系，详细问题由 Codex 解读。

## 安装 Codex Skill

```sh
repo-doctor skill export --out NEW_SKILL_DIRECTORY
```

导出目录必须尚不存在。选择并明确使用所需安装环境的 CLI；保留已有 Skill，新增 JS/TS Skill 可放到独立目录。不要用导出操作覆盖现有设置。已有 Python 调查方式继续适用。

## 按需保存 Python 调查

```sh
repo-doctor report create REPO --out NEW_CASE --json
repo-doctor context REPO REAL_ID --snapshot-out NEW_CONTEXT.json --json
repo-doctor findings import CASE --from FINDINGS.json --context NEW_CONTEXT.json --producer codex --json
repo-doctor report show CASE
```

此流程仅支持 Python。引用通过只说明出处正确，问题判断和修复结论仍需 Codex 分析和针对性检查。只有显式 `reproduce` / `verify` 才执行指定命令。

- [Codex 调查教程、JSON 格式与容量限制](docs/CODEX_AND_MAP.md)
- [JS/TS 支持范围及下一步](docs/JS_TS_SUPPORT.md)
- [产品目标与指导书](docs/PRODUCT_GUIDE.md)
- [历史与可选接口](docs/LEGACY_USAGE.md)

动态绑定、方法、回调和仓库外调用不构成完整运行时影响清单；解析失败、未知关系和省略数量均需结合源码复核。JS/TS 不支持 snapshot、case/findings、诊断或自动修复流程。
