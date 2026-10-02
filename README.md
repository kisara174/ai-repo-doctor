# AI Repo Doctor

为 Codex 提供本地 Python 仓库的结构、调用证据和有界源码上下文，并生成供人查看的离线交互 HTML 与 SVG 关系图。Codex 负责问题判断和代码修改；Repo Doctor 校验来源、保存发现和显式检查记录。主要流程无需 API Key。

需要 Python 3.11+。扫描、调查和地图生成不运行目标仓库代码；只有显式 reproduce/verify 才执行指定命令。

[v0.5.2 稳定版](https://github.com/kisara174/ai-repo-doctor/releases/tag/v0.5.2) 已发布并部署到这台 Mac。普通终端直接运行 `repo-doctor --version`，无需激活环境。三项可靠性修复与安装证据见 [交付记录](docs/delivery/2026-10-02-v0.5.2-reliability.md)。

## 安装

从公开发行 wheel 安装 v0.5.2：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'https://github.com/kisara174/ai-repo-doctor/releases/download/v0.5.2/ai_repo_doctor-0.5.2-py3-none-any.whl'
export PATH="$PWD/.venv/bin:$PATH"
repo-doctor --version
repo-doctor skill export --out ~/.agents/skills/repo-doctor
```

Skill 导出目录必须尚不存在；已有 Skill 可继续使用。在 Codex 中显式使用 `$repo-doctor`。安装包无需运行依赖；安装 Git 后扫描遵循目标仓库的 ignore 规则。发行方式为 GitHub wheel。

## 阅读仓库与查看关系图

```sh
repo-doctor overview /path/to/python-repo --json
repo-doctor symbols /path/to/python-repo --query run_pending --json
# 从上一步复制真实符号 ID，再获取上下文与影响
repo-doctor context /path/to/python-repo 'FILE.py::SYMBOL' --json
repo-doctor impact /path/to/python-repo 'FILE.py::SYMBOL' --depth 2 --json
repo-doctor map /path/to/python-repo --out ./new-repo-map
```

打开 `new-repo-map/map.html`：可搜索、展开、筛选、聚焦和缩放。一起生成 `structure.svg`、`relations.svg`、`map.json`；页面还可导出当前视图 SVG。地图无需服务或联网，只展示结构关系。

## 按需保存调查

```sh
repo-doctor report create REPO --out NEW_CASE --json
repo-doctor context REPO 'REAL_SYMBOL_ID' --snapshot-out NEW_CONTEXT.json --json
repo-doctor findings import CASE --from FINDINGS.json --context CONTEXT.json --producer codex --json
repo-doctor report show CASE
```

完整 finding JSON、可复制的离线样例、修复前后检查、容量上限和旧任务救援见 [Codex 调查教程](docs/CODEX_AND_MAP.md)。引用通过只说明出处正确；问题判断和修复结论仍需 Codex 分析和针对性检查。

## 能力边界与后续工作

工具记录已解析的静态关系，保留解析失败、未解析和省略数量；动态绑定、仓库外调用与运行时行为不能当作完整影响清单。普通 case 上限 8 MiB，超限操作拒绝并保留上一次任务；历史超大任务可导出只读档案。切换回归命令需要重新确认关联。

- [产品目标与指导书](docs/PRODUCT_GUIDE.md)
- [v0.5.2 执行计划 D0–D8](docs/superpowers/plans/2026-10-02-v0-5-2-reliability-and-delivery.md)
- [历史与可选接口：scan、validate、DeepSeek、开发验证](docs/LEGACY_USAGE.md)
