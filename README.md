# AI Repo Doctor

<!-- repo-doctor-install-versions: 0.8.0 -->

为 Codex 提供 Python、JavaScript、TypeScript 仓库的静态源码证据，为人提供离线结构关系图。Codex 负责判断和修改代码。主要流程无需 API key、服务或 Node，不运行目标仓库代码。

**当前公开版本为 [0.8.0](https://github.com/kisara174/ai-repo-doctor/releases/tag/v0.8.0)**。1.0 正在完成交付验收，尚未发布；以下下载示例属于 0.8.0。1.0 候选的版本绑定 Skill、安装、升级和回滚见 [安装指南](docs/INSTALL.md)，进度见 [1.0 指导清单](docs/V1_TODO.md)。

## 安装固定版本

需要 Python 3.11+；[1.0 平台矩阵](docs/SUPPORT_MATRIX.md)明确实际验证的系统与解释器组合。选择尚不存在的虚拟环境目录，不修改系统 Python。

仅使用 Python：

```sh
python3 -m venv .venv-repo-doctor
.venv-repo-doctor/bin/python -m pip install 'https://github.com/kisara174/ai-repo-doctor/releases/download/v0.8.0/ai_repo_doctor-0.8.0-py3-none-any.whl'
.venv-repo-doctor/bin/repo-doctor --version
```

同时分析 JS/TS，改用独立环境及同一 wheel 的可选依赖：

```sh
python3 -m venv .venv-repo-doctor-js
.venv-repo-doctor-js/bin/python -m pip install 'ai-repo-doctor[js] @ https://github.com/kisara174/ai-repo-doctor/releases/download/v0.8.0/ai_repo_doctor-0.8.0-py3-none-any.whl'
.venv-repo-doctor-js/bin/repo-doctor --version
```

当前以 GitHub wheel 分发，没有 PyPI 发行。Python 基础安装无运行依赖；JS/TS extra 安装三个固定版本 Tree-sitter 包。安装后核心调查无需联网。

## 五步调查

`RD_CLI` 设置为刚安装的 CLI 绝对路径。`REPO` 是目标仓库；ID 必须来自本轮搜索结果；地图使用新目录。

```sh
RD_CLI="$PWD/.venv-repo-doctor/bin/repo-doctor"
REPO='/absolute/path/to/repository'
"$RD_CLI" overview "$REPO" --json
"$RD_CLI" symbols "$REPO" --query NAME --json
ID='ID_RETURNED_BY_SYMBOLS'
"$RD_CLI" context "$REPO" "$ID" --max-lines 120 --json
"$RD_CLI" impact "$REPO" "$ID" --depth 2 --json
"$RD_CLI" map "$REPO" --out NEW_MAP_DIRECTORY --json
```

默认只分析 Python。JS/TS 每条命令增加 `--languages javascript,typescript` 并选用安装 extra 的 CLI；混合仓库选择 `python,javascript,typescript`。缺 extra 会明确失败。使用 `--include-symbol REAL_ID` 加入相关源码，共享行预算。

打开地图目录中的 `map.html`：可以搜索、展开路径、切换结构/关系、筛选测试、聚焦与缩放，并导出当前视图 SVG。同目录的 `structure.svg`、`relations.svg` 可直接查看，`map.json` 可供工具读取。页面完全离线，只展示结构关系；详细结论交给 Codex。

## 接入 Codex

公开 0.8.0 可从选定环境导出原 Skill：

```sh
"$RD_CLI" skill export --out NEW_SKILL_DIRECTORY
```

导出目录必须不存在；保留已有自定义 Skill。1.0 候选应按 [安装指南](docs/INSTALL.md) 导出带 `--cli` 的 `repo-doctor-v1`，新会话核对 installation.json 和实际 `--version`。不要混用两套版本说明或默默回退到 PATH 中的旧 CLI。

## 支持与边界

- Python 支持结构、源码上下文和保守静态关系。JS/TS 实现后缀为 `.js .mjs .jsx .ts .tsx`，支持安全直接函数绑定与有限本地 ESM 源码关联。
- 关系存在只证明静态依据；空影响、未解析调用、零解析错误都不能证明无缺陷或无运行时影响。JS/TS 嵌套函数、对象方法、匿名回调、JSX 标签、动态调用和仓库外调用存在明确限制。
- context 可能截断，analysis 示例和限制列表也会省略；地图每视图上限为 200 节点/500 边，并显示隐藏数量。1.0 的文件、总量、时间和深度边界见 [资源说明](docs/RESOURCE_LIMITS.md)。
- JS/TS 不支持 snapshot、case/findings、诊断或自动修复。Python 的旧案件保存和可选接口保持兼容，见 [次级使用参考](docs/LEGACY_USAGE.md) 和 [调查教程](docs/CODEX_AND_MAP.md)。

## 文档入口

- [安装、绑定、升级和回滚](docs/INSTALL.md)
- [Codex 调查与地图教程](docs/CODEX_AND_MAP.md)
- [CLI/JSON 合同](docs/CLI_CONTRACT.md)、[兼容政策](docs/COMPATIBILITY.md)
- [JS/TS 支持范围](docs/JS_TS_SUPPORT.md)、[平台支持](docs/SUPPORT_MATRIX.md)
- [变化记录](CHANGELOG.md)、[问题反馈与维护](SUPPORT.md)
- [1.0 准备状态](docs/delivery/2026-10-08-v1-readiness.md)

许可尚待项目所有者确定；没有 LICENSE 不能解释为获得再分发或商用授权。1.0 正式发行前必须完成许可声明和实际 wheel 核验。
