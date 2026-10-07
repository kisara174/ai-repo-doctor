# AI Repo Doctor 正式发布与 Mac 交付闭环执行计划

> **For agentic workers:** 使用 `executing-plans` 按任务顺序执行。主代理负责版本、CI、Git、打包、审查、发布、部署和验收。用户 AGENTS.md 的执行器路由规则优先；仅满足全部条件的机械小任务才考虑 `luna_executor`，不强制委派。

**Goal:** 将已验收的 Python 0.5.3rc3 交付为可公开下载、可 pip 安装、Mac 普通终端可持续调用且可回滚的 Python 0.5.3 稳定版；保留 JS/TS 0.6.0a5 的独立预览交付。

**Architecture:** 延续现有 GitHub wheel 发行、独立 venv 安装和持久 Mac venv。使用现有 CI 和安装验证器验证正式来源提交，复用已完成的调查与地图证据；发布、下载、安装和报告通过同一版本与文件哈希关联。

**Tech Stack:** Python 3.11+、setuptools、unittest、现有 Node 地图检查、GitHub Actions、GitHub CLI、现有 HTML/SVG 资源。

**Spec:** `docs/delivery/2026-10-06-v0.5.3rc3-local-candidate.md`；预览工作树的 `docs/delivery/2026-10-06-v0.6.0a5-local-candidate.md`；`/Users/kisara/.local/share/ai-repo-doctor/evaluations/benchmark200-v1/delivery/revision-001/delivery-report.md`；沿用 `docs/superpowers/plans/2026-10-02-v0-5-2-reliability-and-delivery.md` 的发行与部署要求。

**计划状态：** 2026-10-07，用户已授权完整执行并建立 Goal。S0–S7 稳定交付已完成；正式 tag `v0.5.3`、公开下载安装与 Mac 0.5.3 均通过，最终证据见新交付说明及 releases/v0.5.3/completion.json。J1 保持独立待选。

## Global Constraints

- Python 最低版本保持 `3.11`；现有 CI 保持 `3.11/3.12/3.13`。
- Python 稳定包 `dependencies = []`，沿用 `GitHub wheel` 发行方式；本轮不迁移到 PyPI。
- JS/TS 保持 `0.6.0a5` 预览，显式安装 `js` extra；不混入 Python 稳定版。
- 产品主流程：Codex 调用 overview/symbols/context/impact；人查看离线 HTML/SVG 结构关系；按需保存可复查的调查线索。
- 动态调用、仓库外调用与未解析关系仍有边界；空影响清单不能解释为没有影响。
- 图的节点 `200`、边 `500` 上限不变；不得为发版放宽测试或容量限制。
- 正常 case 上限 `8 MiB`；旧记录保留原来源版本，版本升级不重写历史 case。
- 保留交接中的 14 个既有未提交文件、原评估资料、候选 wheel、候选安装环境和 Skill；不得读取、打印或重写 Key。
- 原 0.5.3rc2/0.6.0a4 的 200 仓库与 20 地图证据保留原归属。新候选未完成新的全量 200 再跑，不得改写为全量通过。
- Chrome 连接异常暂不处理；此前已完成的实际地图验收不重新归零，也不补造浏览器证据。
- 2026-10-06 仅编写计划；2026-10-07 用户授权执行 S0–S7，包括推送、PR/合并、稳定发行与 Mac 安装切换。按既有授权推进，不反复询问。
- Git 不使用 force push，不移动已公开 tag，不用 reset/clean/stash 清除用户改动，不整体 `git add .`。

---

## 1. 已完成的起点

| 项目 | 已确认状态 | 本轮处理 |
|---|---|---|
| Python 本地集成 | `codex/local-product-closure`，HEAD `619cb55cd63b5cdb36420aa41a91ecb791b68b0f` | 作为稳定版准备起点 |
| Python 候选包源码 | `fd80763fb0c6991d170d49ef10d1689ae2dee582`，0.5.3rc3 | 保留；正式版生成独立源码和 wheel |
| JS/TS 本地集成 | `codex/js-ts-readonly-preview`，HEAD `2b786cf22eecaed29327b9d8a453a00429875782` | 独立保留 |
| JS/TS 候选包源码 | `4c001259a0e498643c32f9d26b49670e63229da8`，0.6.0a5 | 不自动升为稳定版 |
| 本机候选单元测试 | Python 431；预览 466 | 复用已有记录，不为开工重复跑 |
| 安装生命周期 | 两候选各 33 条；预览 base 9、extra 18 | 正式 wheel 与实际部署分别验证 |
| 新仓库及受控地图 | 4 图、24 动作、16 投影状态已验收 | viewer 字节不变时复用 |
| 历史完整评估 | 996 命令成功；199 工作流通过；1 个符号歧义失败 | 保留原候选与失败说明 |
| 当前 Mac 全局入口 | `/Users/kisara/.local/bin/repo-doctor`，0.5.2 | S6 成功后切为 0.5.3 |
| 远端默认分支 | 当前为 `codex/repo-doctor-v1` | S0 再查询；不得假设是 main |
| 远端版本矩阵 | 新候选尚未运行 | S3 必须取得正式来源的结果 |

Python 与 JS/TS 候选均可通过已有候选 CLI 使用。稳定版发布完成不以 JS/TS 预览升级为条件。

## 2. 顺序与完成定义

`S0 锁定和保护 → S1 形成正式版改动 → S2 审查与提交 → S3 远端 CI/集成 → S4 正式包验收 → S5 公开发行 → S6 Mac 部署 → S7 交付归档`

| 阶段 | 独立产出 | 进入下一阶段的条件 |
|---|---|---|
| S0 | baseline.json、保护清单、远端实际状态 | 起点与交接一致，工作区隔离 |
| S1 | 正式版本及发行说明改动 | 0.5.3 版本一致，稳定包无新增依赖 |
| S2 | 已审查的准备提交 | diff 在允许范围内，保护文件无变化 |
| S3 | PR、精确 SHA 的 CI 记录、正式来源 SHA | 三版本及地图 job 均成功，合并来源明确 |
| S4 | 正式 wheel、SHA256SUMS、安装 receipt | metadata/CLI/新报告一致，安装流程通过 |
| S5 | v0.5.3 release、公开下载收据 | 下载包与验收包哈希一致 |
| S6 | 持久安装与回滚资料 | 普通登录 shell 调用 0.5.3，安装后流程通过 |
| S7 | 中文交付、状态记录、最终保护核验 | 必需待办归零，预览待办独立记录 |

**稳定版闭环：** 公开安装链接有效 → 干净安装可用 → 普通 Mac 终端可用 → Codex 调查与关系图可用 → 旧记录可重开 → 发行与安装来源一致 → 有可用的 0.5.2 回滚包。

## 3. 文件与证据目录

### 执行时允许修改

- 发布隔离工作树内：`repo_doctor/_version.py`、`tools/validate_release_install.py`、`README.md`。
- 创建：`docs/delivery/2026-10-07-v0.5.3-release.md`；如果实际交付跨日，使用实际日期且只创建一份最终记录。
- `.github/workflows/ci.yml` 只在 S3 出现明确的实际 CI 缺陷时修复，不预先重写。
- 新缺陷需要涉及其他代码时，主代理先记录失败证据和必要的最小修改范围，再修复并重新冻结来源；不得静默扩大范围。
- 主目录当前脏文件不在允许修改范围。产品指导书已有未提交内容，本轮在新增交付说明中承接状态，不覆盖它。

### 执行时创建的证据

固定发布根目录：`/Users/kisara/.local/share/ai-repo-doctor/releases/v0.5.3/`。

- `baseline.json`：两候选 SHA、版本、保护清单、默认分支与授权范围。
- `protection-before.json` / `preservation.json`：原 14 个文件及原证据的路径和 SHA-256。
- `source.json`：准备提交、PR head、合并 SHA、正式来源 SHA、核心文件一致性。
- `ci.json`：正式来源 SHA、run URL、job 名称、结果、日志引用。
- `source/`、`wheels/`、`SHA256SUMS`：从正式 SHA 导出的构建源码与包。
- `release-notes.md`、`pr-body.md`：实际用于发布/PR 的说明。
- `formal-install/`：正式 wheel 的独立安装环境和 33 命令验收。
- `public-download/`、`public-install/`：公开资产及干净安装核验。
- `publication.json`：远端 tag 指向、发行 URL、公开下载包哈希。
- `mac-install/`、`rollback-test/`：持久环境验收与旧包独立安装核验。
- `completion.json`：逐阶段状态，实际失败与未完成项。

原 `delivery/revision-001` 不写入。上述目录若已存在，读取其状态后恢复执行；只为新的尝试创建 `attempt-002` 等递增子目录，禁止覆盖旧收据。

执行 shell 的公共变量：

```sh
RD_PROJECT='/Users/kisara/Documents/ChatGPT/AI Repo Doctor'
RD_PREVIEW='/Users/kisara/.codex/worktrees/dom-preview-delivery/AI Repo Doctor'
RD_DELIVERY='/Users/kisara/.local/share/ai-repo-doctor/evaluations/benchmark200-v1/delivery/revision-001'
RD_RELEASE='/Users/kisara/.local/share/ai-repo-doctor/releases/v0.5.3'
RD_REPO='kisara174/ai-repo-doctor'
RD_BRANCH='codex/release-v0.5.3'
```

不要将变量设为 `$HOME`、`$home` 或 `$CODEX_HOME`。发布工作树路径 `RD_WORKTREE` 使用原生 worktree 工具的实际返回值；PR URL、run ID、正式 SHA 都从真实结果取得并写收据，不能猜测。

---

## S0：锁定起点与保护已有工作

**Owner:** 主代理。**Files:** 只读现有源码、交付证据；创建 baseline 与保护记录。

**Consumes:** 两个本地 HEAD、`completion.json`、`products.json`、`main-preservation-before.json`。**Produces:** 可复核的起点与隔离执行目录。

- [x] 读取交付报告和完成记录；确认两候选本地 HEAD、wheel hash、CLI 与 0.5.2 全局入口。
- [x] 根据 `main-preservation-before.json` 的真实路径结构取出 14 个受保护文件，比较当前 SHA-256；将本计划新增文件单独记录，不计为原文件变化。
- [x] 核验 `completion.json.receipt_files` 中每份文件的 SHA-256；保留历史证据清单，对原有证据条目做执行前快照，执行结束仅核验这些条目。
- [x] 查询远端默认分支、现有 PR、v0.5.3 tag/release 和账号可用性。`gh auth status` 不打印 token；不使用 `gh auth token`。

```sh
git -C "$RD_PROJECT" status --short --branch
git -C "$RD_PROJECT" rev-parse HEAD
git -C "$RD_PREVIEW" rev-parse HEAD
/Users/kisara/.local/bin/repo-doctor --version
gh repo view "$RD_REPO" --json url,defaultBranchRef
gh pr list --repo "$RD_REPO" --state open --json url,headRefName,baseRefName,title
gh release list --repo "$RD_REPO" --limit 10 --json tagName,isDraft,isPrerelease,name
git -C "$RD_PROJECT" ls-remote --tags origin refs/tags/v0.5.3 'refs/tags/v0.5.3^{}'
```

- [x] 使用 `using-git-worktrees` 先检查已有附件；优先复用合适的干净工作树，否则从 `619cb55cd63b5cdb36420aa41a91ecb791b68b0f` 创建隔离工作树。发行分支使用 `codex/release-v0.5.3`；同名分支存在时读取来源和状态，禁止覆盖。
- [x] 原生 worktree 若返回 detached HEAD，在确认发行分支不存在后执行 `git -C "$RD_WORKTREE" switch -c "$RD_BRANCH"`。确认 `git -C "$RD_WORKTREE" branch --show-current` 返回实际发行分支。
- [x] 在 baseline.json 写清后续授权范围。本轮编写计划不视为执行发布的授权。

**Acceptance:** 来源与交接一致；受保护文件未变化；不存在未知 tag 冲突；执行目录没有用户脏文件。

**Stop:** 来源漂移、保护 hash 不符或远端已有不同来源的 v0.5.3 时先核查差异；不自行重置。GitHub 登录失败只暂停远端阶段，本地准备可以继续。

## S1：形成 Python 0.5.3 正式版准备改动

**Files:** 修改隔离工作树的 `_version.py`、安装验证器、README；创建稳定版交付说明和 release-notes 草稿。

**Consumes:** S0 已保护的 0.5.3rc3 来源。**Produces:** 可审查的 0.5.3 发布改动。

- [x] 将 `repo_doctor/_version.py::__version__` 从 `0.5.3rc3` 改为 `0.5.3`。
- [x] 将 `tools/validate_release_install.py::EXPECTED_VERSION` 从 `0.5.3rc3` 改为 `0.5.3`。`pyproject.toml` 使用动态版本，不添加第二份版本常量。
- [x] 搜索当前 runtime/测试/验证器内的候选版本硬编码，检查每个命中。历史交付记录保持候选版本；动态读取版本的 `tests/test_product_cli.py` 无需机械改写。

```sh
cd "$RD_WORKTREE"
rg -n '0\.5\.3rc3|EXPECTED_VERSION|__version__' repo_doctor tools tests
```

- [x] README 的默认安装示例指向 `v0.5.3/ai_repo_doctor-0.5.3-py3-none-any.whl`；准备阶段标明发行待完成，最终完成态在 S7 更新。
- [x] release-notes 包含：搜索选择/结构树修复、安装版本验证同步、核心分析器来源一致性、真实测试范围、原符号歧义与静态分析边界、安装和回滚方法。
- [x] 新稳定版说明链接原交付报告；公开说明避免把个人 Mac 绝对路径作为其他用户的安装步骤。人类主界面仍只展示结构关系图。
- [x] 保持 Python 稳定包无运行依赖；不引入 JS extra、自动修复、Web 服务或新 CLI 接口。

**Acceptance:** 正式版本唯一且一致；正文没有“新版本全量 200 通过”的错误陈述；runtime 预期只有 `_version.py` 与 rc3 不同，viewer 不变。

## S2：审查差异并冻结准备提交

**Files:** S1 文件；创建 source.json 初始记录和 pr-body.md。

**Consumes:** S1 diff。**Produces:** 经主代理审查的准备提交及可提交 PR 说明。

- [x] 检查实际 diff、文件列表和受保护 hash；确认只修改 S1 允许范围。
- [x] 做版本改动的最小本地核验及既有地图脚本核验，记录输出。无需为仅版本提升新增镜像测试。

```sh
cd "$RD_WORKTREE"
git diff --check
git diff --stat
python3 -m unittest tests.test_product_cli -v
node tests/test_map_search.js
```

- [x] 审查重点：新 case 使用 0.5.3；旧 case 保留旧版本；版本验证器同步；README 未承诺不存在的能力。
- [x] 仅显式暂存允许文件并提交；提交前审查 staged diff。使用 `git add repo_doctor/_version.py tools/validate_release_install.py README.md docs/delivery/2026-10-07-v0.5.3-release.md`，不暂存主目录既有改动。
- [x] 记录准备提交 SHA。PR 说明写明稳定范围、候选证据、远端验证待完成、JS/TS 独立保留、200 回归归属及保护方式。

**Acceptance:** 准备提交可独立审阅，本地目标核验通过；没有无关 staged 文件。

## S3：远端 CI 与正式源码集成

**Owner:** 主代理；这是需要远端执行授权的阶段。**Files:** 默认不改 CI；必要修复限制在已定位的故障。

**Consumes:** S2 准备提交与实际默认分支。**Produces:** PR URL、完整 CI 结果、正式来源 SHA。

- [x] 推送发行分支，目标为 `kisara174/ai-repo-doctor`；执行发现默认分支已包含JS/TS0.6.0a1；从已发布v0.5.2 tag创建 `codex/python-stable` 作为独立稳定维护分支并设为 PR base。已有同一分支 PR 时更新该 PR，不创建重复 PR。

```sh
git -C "$RD_WORKTREE" push --set-upstream origin "$RD_BRANCH"
RD_BASE='codex/python-stable'
gh pr create --repo "$RD_REPO" --base "$RD_BASE" --head "$RD_BRANCH" \
  --title 'Release Python 0.5.3 stable CLI' --body-file "$RD_RELEASE/pr-body.md"
```

- [x] 创建 PR 成功后调用 Codex `attach_artifact` 附加实际 URL；若后续继续处理已有 PR，也附加它。
- [x] 查询 PR 的 `headRefOid`；按这个 SHA 获取 CI 记录。不要用旧候选、本地 3.14 或另一个 PR 的绿色结果代替。
- [x] 核对全部预期 job：`Python 3.11`、`Python 3.12`、`Python 3.13`、`Offline map interaction and SVG`，共 4 个。
- [x] 每个 Python job 的 wheel 安装及生命周期验证必须实际执行；地图 job 必须包含 `test_map_search.js` 和 DOM/SVG 检查。缺失、跳过、取消或仍 pending 都不算通过。

```sh
gh pr view "$RD_PR_URL" --repo "$RD_REPO" --json headRefOid,baseRefName,mergeable,url
gh pr checks "$RD_PR_URL" --repo "$RD_REPO" --json name,state,bucket,link
gh run list --repo "$RD_REPO" --commit "$RD_PR_HEAD" --workflow ci.yml \
  --json databaseId,headSha,status,conclusion,url
gh run view "$RD_RUN_ID" --repo "$RD_REPO" --json headSha,status,conclusion,jobs,url
```

`RD_PR_URL`、`RD_PR_HEAD`、`RD_RUN_ID` 均来自本阶段实际返回值。等待每次最长 60 秒并保持有意义的进度更新，不增加多余的手动 CI dispatch。

- [x] 如失败，按 `systematic-debugging` 提取首个失败和最小原因；只修复可复现的兼容性、安装或工作流问题。不得删除门槛、允许跳过或随意延长超时掩盖失败。
- [x] 修复改变实际 runtime 时，生成新的候选来源和对应验证记录；旧 rc3 证据保持不变。没有 runtime 改动时不重跑 200 仓库。
- [x] CI 成功、审查通过且合并授权有效时合并 PR；记录合并 SHA，核验源码变化与已审查 diff 一致。
- [x] 仓库允许 merge commit 时使用下列命令；若仓库策略要求 squash/rebase/merge queue，主代理根据真实策略选择，不能使用 `--admin` 绕过门槛。合并命令返回成功后仍查询实际合并状态，排队不等于合并完成。

```sh
gh pr merge "$RD_PR_URL" --repo "$RD_REPO" --merge --match-head-commit "$RD_PR_HEAD"
gh pr view "$RD_PR_URL" --repo "$RD_REPO" --json state,mergedAt,mergeCommit,url
```

- [x] 等待稳定维护分支上合并提交的 4 个 CI job 完成；使用该合并 SHA 作为 `RD_FORMAL_SHA`。PR merge-ref 的结果不能直接冒充最终源码 SHA 的结果。
- [x] 通过 `gh pr view "$RD_PR_URL" --repo "$RD_REPO" --json mergeCommit --jq '.mergeCommit.oid'` 取得 `RD_FORMAL_SHA`，写入 source.json；执行 `git -C "$RD_WORKTREE" fetch origin "$RD_BASE"` 取回该对象，并确认它在实际远端 base 历史中。

**Acceptance:** 正式来源明确，最终 SHA 上 4 个 job 全部成功，ci.json 保存实际链接与结果。

**Stop:** 缺少远端授权、登录/服务故障或 CI 失败时暂停相应阶段；不得先打正式 tag 再修正证据。

## S4：从正式 SHA 构建并验收 wheel

**Files:** 新建发布 source、wheels、正式安装与 hash 记录；读取现有候选。

**Consumes:** `RD_FORMAL_SHA`。**Produces:** 唯一正式 wheel 与 33 命令验收 receipt。

- [x] 将真实 `RD_FORMAL_SHA` 写入 source.json；从该 SHA 导出源码，排除工作树未提交文件。

```sh
mkdir "$RD_RELEASE/source"
git -C "$RD_WORKTREE" archive --format=tar "$RD_FORMAL_SHA" -o "$RD_RELEASE/source.tar"
tar -xf "$RD_RELEASE/source.tar" -C "$RD_RELEASE/source"
python3 -m pip wheel --no-deps --wheel-dir "$RD_RELEASE/wheels" "$RD_RELEASE/source"
```

- [x] 预期唯一包 `ai_repo_doctor-0.5.3-py3-none-any.whl`；读取 ZIP 内 metadata，确认版本、Python >=3.11、无 Requires-Dist 及 CLI 入口。
- [x] 生成 SHA256SUMS，记录实际 build interpreter、构建来源与包 hash；不要求新 wheel 与 rc3 整包 hash 相同。
- [x] 与 rc3 wheel 比较 `repo_doctor/` 内全部 runtime 资源：预期仅 `_version.py` 不同；viewer、分析器、CLI 和 Skill 字节相同。如有其他差异，定位原因并确定必要验证后继续。
- [x] 安装正式 wheel 到新 venv，复制正式源码的验证器到仓库外，执行现有生命周期验证。

```sh
python3 -m venv "$RD_RELEASE/formal-install/venv"
RD_FORMAL_WHEEL="$RD_RELEASE/wheels/ai_repo_doctor-0.5.3-py3-none-any.whl"
"$RD_RELEASE/formal-install/venv/bin/python" -m pip install --no-index "$RD_FORMAL_WHEEL"
cp "$RD_RELEASE/source/tools/validate_release_install.py" "$RD_RELEASE/formal-install/validate_release_install.py"
cd /private/tmp
"$RD_RELEASE/formal-install/venv/bin/python" "$RD_RELEASE/formal-install/validate_release_install.py" \
  --python "$RD_RELEASE/formal-install/venv/bin/python" \
  --cli "$RD_RELEASE/formal-install/venv/bin/repo-doctor" \
  --out "$RD_RELEASE/formal-install/evidence"
```

- [x] receipt 的 `version` 为 0.5.3，33 条受控命令符合预期退出码；导入来自 site-packages。验证器内预期失败的回归步骤不能误记为产品失败。
- [x] viewer 字节一致时，引用已有 4 地图交互证据，并写出一致性理由；不修复 Chrome、不追加随机地图验收。

**Acceptance:** 正式 SHA、包、metadata、CLI、新 case 与导出版本一致，安装 receipt 通过。

## S5：发布 GitHub wheel 并核验公开安装

**Owner:** 主代理；执行前核对发布授权。**Files:** release-notes、远端 tag/release、public-download 与 publication.json。

**Consumes:** S3 CI、S4 wheel 与安装 receipt。**Produces:** 可公开下载的 v0.5.3 稳定发行。

- [x] 完成 release-notes；实际审核文件、包与 SHA256SUMS 后再执行发布。
- [x] 再查 v0.5.3 tag/release。未存在才创建 tag，明确指向 `RD_FORMAL_SHA`；已有匹配来源则恢复原发行工作，来源不一致则停止，绝不覆盖。

```sh
git -C "$RD_WORKTREE" tag -a v0.5.3 "$RD_FORMAL_SHA" -m 'AI Repo Doctor 0.5.3'
git -C "$RD_WORKTREE" push origin refs/tags/v0.5.3
gh release create v0.5.3 --repo "$RD_REPO" --verify-tag \
  --title 'AI Repo Doctor 0.5.3' --notes-file "$RD_RELEASE/release-notes.md" \
  "$RD_FORMAL_WHEEL" "$RD_RELEASE/SHA256SUMS"
```

- [x] Python 发行不带 `--prerelease`；不要发布未经验证的额外源码包或随意上传本地评估资料。
- [x] 下载公开资产到新目录，并比较公开 wheel 与 S4 wheel 的 SHA-256、metadata，以及远端 tag 解引用后的正式 SHA。

```sh
gh release download v0.5.3 --repo "$RD_REPO" \
  --pattern 'ai_repo_doctor-0.5.3-py3-none-any.whl' --pattern SHA256SUMS \
  --dir "$RD_RELEASE/public-download"
python3 -m venv "$RD_RELEASE/public-install/venv"
"$RD_RELEASE/public-install/venv/bin/python" -m pip install --no-index \
  "$RD_RELEASE/public-download/ai_repo_doctor-0.5.3-py3-none-any.whl"
```

- [x] 从 /private/tmp 验证公开安装的 `--version`、site-packages metadata 和一个 overview；使用 S4 验证器生成的受控 Python repo。公开包与正式验收包完全相同且 site-packages 资源一致时，引用 S4 的 33 命令结果，不重复完整流程。
- [x] publication.json 记录发布链接、tag/正式来源、公开包 hash、安装证据与时间。资产下载或安装失败，状态记为失败并修复，不写“发布已验收”。

**Acceptance:** 用户能从 `https://github.com/kisara174/ai-repo-doctor/releases/download/v0.5.3/ai_repo_doctor-0.5.3-py3-none-any.whl` 安装同一正式包。

## S6：升级 Mac 持久安装并验证回滚资料

**Owner:** 主代理；执行前核对安装切换授权。**Files:** 持久 venv、独立备份目录、新部署收据。

**Consumes:** S5 已验证的公开 wheel。**Produces:** 普通终端入口为 0.5.3、可恢复的 0.5.2 安装资料。

- [x] 保存当前 deployment.json、deployment-v0.5.2.json、INSTALLATION.md、CLI 入口文件/链接信息、Skill hash 和旧 wheel 信息至新的升级前目录。Key 不读取，不搬移。
- [x] 确认旧公开下载 wheel 存在且 SHA-256 为 `aa43f2ff3967b7584cb26f1ffe50a1866b964c9558c9aed9a7b78db30f0ced03`。
- [x] 旧 wheel 在独立 rollback-test venv 安装并验证 0.5.2；不要为测试回滚在持久环境先降级再升级。
- [x] 使用公开下载的同一正式 wheel 升级持久 venv，保留原 `/Users/kisara/.local/bin/repo-doctor` 入口和 Skill。

```sh
/Users/kisara/.local/share/ai-repo-doctor/venv/bin/python -m pip install --no-index \
  "$RD_RELEASE/public-download/ai_repo_doctor-0.5.3-py3-none-any.whl"
zsh -lc 'command -v repo-doctor'
zsh -lc 'repo-doctor --version'
```

- [x] 在仓库外核验持久安装 metadata、site-packages、全部 runtime hash；登录 shell 解析到 `/Users/kisara/.local/bin/repo-doctor` 且输出 0.5.3。
- [x] 用持久解释器/CLI 执行 S4 仓库外验证器到新的 `mac-install/evidence`，验证该实际部署环境的 33 命令生命周期。
- [x] 重开既有 Python 调查 A-001，确认来源引用仍可读、旧版本与未评审状态保留；读取前后 case/report hash 不变。具体路径从 `fresh-trials/summary.json` 取得，不猜测案件目录。
- [x] 升级或验收失败，使用保留的 0.5.2 wheel 恢复持久环境，再核对版本/入口/旧记录；记录失败和恢复结果，部署状态不得标为成功。

回滚命令：

```sh
/Users/kisara/.local/share/ai-repo-doctor/venv/bin/python -m pip install --no-index \
  /Users/kisara/.local/share/ai-repo-doctor/releases/v0.5.2/public-download/ai_repo_doctor-0.5.2-py3-none-any.whl
zsh -lc 'repo-doctor --version'
```

**Acceptance:** Mac 正常终端可持续调用稳定版，完整安装验收成立，原记录和 Skill 未变化，旧包具备独立安装成功证据。

## S7：文档整合与最终闭环核验

**Files:** 新稳定交付记录、README 完成态、新部署收据与 INSTALLATION.md；原脏指导书仍不覆盖。

**Consumes:** S0–S6 收据。**Produces:** 中文交付、实际部署状态与清楚的剩余方向。

- [x] 创建 `/Users/kisara/.local/share/ai-repo-doctor/deployment-v0.5.3.json`，通过它更新 deployment.json 和 INSTALLATION.md；原 0.5.2 收据与升级前备份保留。
- [x] 更新 README 的稳定版完成态；提交独立文档改动。正式 tag 保持 S5 来源，记录后续文档 HEAD，不移动 tag。
- [x] 如果合并文档到主目录，先核对 runtime 和所有受保护文件；无法安全快进时保留主目录现状，在已集成的发行分支交付，记录实际 checkout 状态，不强制合并脏文件。
- [x] 核验 protection-before 的全部原条目；原 14 个文件和旧评估 hash 均不变，新增的正式发行文件单独列出。
- [x] completion.json 的必需项包括：正式版本、精确 SHA 的 CI、wheel/install、公开下载、Mac、回滚资料、旧资料保护、中文说明。全部有证据才 `pending=[]`。
- [x] GraphFlow 仅增量索引实际修改的项目文件；自动图谱状态不代替 CI 和部署收据。
- [x] 中文交付报告说明实际版本、安装链接、普通终端命令、Codex 调查方式、地图位置、支持边界与回滚方法。

**Acceptance:** 用户无需阅读历史长对话即可安装、调用、查阅图、保存/重开调查和回退旧版；所有必需阶段已闭合。

---

## 4. JS/TS 独立预览交付清单 J1（不阻塞 S0–S7）

**起点：** 0.6.0a5 已有本地候选、安装和真实地图证据。仅用户要求公开预览时执行本节；不替换 Mac 稳定入口，不升级为 0.6.0 正式版。

- [ ] 核对预览 HEAD `2b786cf22eecaed29327b9d8a453a00429875782` 与包源码 `4c001259a0e498643c32f9d26b49670e63229da8`，检查当前远端同名分支是否漂移。
- [ ] 获得远端执行授权后推送独立预览分支，取得当前精确 SHA 的 CI：3 个 Python 基础 job、3 个 JS preview job、1 个地图 job，共 7 个。
- [ ] JS preview 必须实际安装 extra；指定模块契约无 skipped；base 9 条与 extra 18 条安装验收实际执行，缺失依赖不能被当作通过。
- [ ] 审核现有 wheel 与当前预览源码的 runtime 一致性；CI 没有引入 runtime 改动时复用现有 0.6.0a5 wheel。若需修复 runtime，另定新 alpha 来源和版本，禁止覆盖已公开包。
- [ ] 用 `v0.6.0a5` 独立 tag 和 GitHub `--prerelease` 发行，使用 `--verify-tag`；先确认 tag 不存在冲突。不设为默认稳定安装版本。
- [ ] 公开安装说明必须采用 wheel 的 `[js]` extra，明确 `--languages javascript,typescript`，支持 overview/symbols/context/impact/map。
- [ ] 文档明确：JS/TS 无快照、案件/findings和自动修复能力；回调、方法、模块解析存在限制；上下文截断可见；影响结果为空不能证明无影响。
- [ ] 下载公开预览 wheel 到独立目录，hash 与来源一致；公开发行、预览环境与 Mac 稳定安装状态分别写收据。

**终点：** 需要 JS/TS 的用户可以明确选择预览包，Python 用户继续使用 0.5.3 稳定入口。

## 5. 发布后的优化方向（先收集明确任务，再另写功能计划）

| 优先级 | 方向 | 开始条件 | 可判定目标 |
|---|---|---|---|
| P1 | 安装/版本兼容缺陷 | S3–S6 实际出现失败 | 固定失败输入或环境；最小修复后原场景通过 |
| P1 | 真实 Codex 调查闭环缺陷 | 用户不能搜索、取证、定位图或重开调查 | 固定目标、符号与预期结果，修复阻断步骤 |
| P2 | JS/TS 相对导入源码关联覆盖 | 固定场景确实需要无后缀/index 关联 | 明确源码推断范围、歧义规则与未知说明；不伪称运行时解析 |
| P2 | 方法/回调关系表达 | 调查问题有可验证的具体缺口 | 在不会制造错误边的前提下改善已定义场景 |
| P3 | 性能与超大仓库可用性 | 有超时/预算耗尽的真实证据 | 在固定仓库、固定提交和相同环境比较时间/内存及结果 |

既有 7 条 JS/TS 评分缺口涉及 oracle 支持范围误配，不能直接全部归类为当前产品 bug。优化必须重新定义目标并保留原 oracle/评分，不事后改历史数据。

本轮不启动新语言、自动诊断/修复、服务化 UI、常驻服务器、API 平台迁移或更多随机仓库试用。S7 成功即可完成稳定交付，不用新增功能无限延长本轮。

## 6. 有目标的验证与停止规则

| 需要证明的事情 | 对应验证 | 复用/停止条件 |
|---|---|---|
| 原候选本机可用 | revision-001 已有测试/安装/地图收据 | 已完成，不重复开工回归 |
| Python 3.11–3.13 兼容 | 正式来源 CI 4 个 job | 全部成功后不额外 dispatch |
| 正式版本包可安装 | S4 独立 wheel + 33 命令 | 正式包发生变化才重做 |
| 公开发行的是同一包 | S5 hash + metadata + 干净安装核验 | 与正式包字节相同可复用 S4 生命周期 |
| Mac 实际部署可用 | S6 登录 shell + 持久安装 33 命令 | 成功即停止安装测试 |
| 新图行为未漂移 | viewer 字节一致 + 原 4 图证据 + CI 地图 job | 未改变 viewer 不重跑 20 图 |
| 原评估与用户改动保留 | S0/S7 原路径与 hash | 保护核验不执行目标代码 |

- 功能、CLI schema、核心分析器或 viewer 出现实际变化时，由主代理据差异选择必要回归；重新计算证据归属。
- 分析器字节不变时不启动完整 200 仓库再跑；若将来需要新全量评估，必须另立新候选协议和证据目录。
- 无目标的测试扩容、重复构建、重复浏览器连接重试不属于本计划任务。

## 7. 执行器边界和检查点

- S0–S7 与 J1 的版本、Git、外部事实、依赖、发布、部署和风险判断由主代理执行，不交给 Luna/Harness。
- 后续若出现确定的纯文档机械同步，先检查委派成本与最新周额度，再按 AGENTS.md 路由；任务包必须包含 Objective、Allowed changes、Forbidden changes、Exact steps、Validation、Expected result、Stop conditions。
- 任何执行器不得自行发布、改依赖、改权限、扩充文件范围或创建其他子代理；主代理必须审查真实 diff 和新鲜验证后接纳。
- 每阶段结束更新本计划 checkbox 与 completion 状态；失败保留输出，说明精确未完成项，不为了继续下一阶段强行标通过。

## 8. 依据与计划自查

- 正式版本 `0.5.3` 与 `0.5.3rc3` 的区别采用 [Python Packaging 版本规范](https://packaging.python.org/en/latest/specifications/version-specifiers/#pre-releases)。
- PR 状态及 pending/fail/skipping 的区分采用 [GitHub CLI checks 文档](https://cli.github.com/manual/gh_pr_checks)。
- 发布使用已存在的正确远端 tag，并通过 `--verify-tag` 防止自动从错误默认分支创建 tag，依据 [GitHub CLI release 文档](https://cli.github.com/manual/gh_release_create)。
- [x] 计划覆盖正式源码、CI、包、公开下载、Mac、回滚、旧数据与中文交付的全部必要环节。
- [x] 计划使用实际仓库路径、分支、现有验证器及真实默认分支，没有假设 main。
- [x] 已区分稳定版必要任务与独立 JS/TS 预览任务。
- [x] 已区分历史证据、新候选试用、正式包验收及公开安装证据。
- [x] 没有把 Chrome 故障或新的 200 仓库评估加入稳定交付门槛。
- [x] 原计划编写时未实施；2026-10-07 开始按授权执行。
