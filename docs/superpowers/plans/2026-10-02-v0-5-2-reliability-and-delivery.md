# AI Repo Doctor v0.5.2 可靠性修复与产品交付计划

> **For agentic workers:** 使用 `executing-plans` 按阶段执行。主代理承担设计、调试、审查与发布。仅完全确定的机械小任务按用户 AGENTS.md 考虑 `luna_executor`，不要为每个阶段强行创建子代理。

**Goal:** 交付可 pip 安装、Mac 持久部署、Codex 可调用的稳定 Python 基础产品，修复三项已确认的记录缺陷，完成简洁的调查、地图、证据保存和复查流程。

**Architecture:** 保留现有离线 CLI、源绑定快照、case.json 和 HTML/SVG。回归证据按当前轮配对；正常 case 共用一个容量上限；历史超大 case 导出完整只读档案。版本采用唯一常量来源，旧公开命令保持可调用。

**Tech Stack:** Python 3.11+ 标准库、现有 setuptools、unittest、GitHub Actions、现有内嵌 HTML/SVG 资源。

**Spec:** 第 2 节为自包含设计合同，实施者先读第 1–4 节。审计原始证据位于 `/Users/kisara/.local/share/ai-repo-doctor/audits/2026-10-02-v0.5.1/`；其他机器没有该目录时，仍可按本文件复现和实施。

**状态：** 2026-10-02 编写。D0–D8 尚未实施。本轮只写计划，本文代码、命令、验收结果不得被当作已执行。

## Global Constraints

- Python 最低版本保持 `3.11`；已有 CI 保持 `3.11/3.12/3.13`，Mac 当前解释器另做安装核对。
- 运行依赖保持 `dependencies = []`，构建依赖保持 `setuptools>=77.0.3`。
- 主要路径离线、无需 API Key；此次交付不调用付费 API，不执行真实外部仓库代码。
- context 快照保持最多 `120` 行、`64 KiB` 源码，finding 输入保持 `1 MiB`。
- 普通 case 的 UTF-8 JSON 上限为 `8 * 1024 * 1024` 字节，恰好等于上限允许，超过拒绝。
- 救援读取上限为 `32 * 1024 * 1024` 字节，仅生成完整只读档案。
- 显式检查仍为 `1–300` 秒超时、默认 `120` 秒，输出最多 `16 KiB`。
- case schema 保持 `1`，新增复核字段可选；旧数据可读，读取不得重写原始记录。
- 人类页面只展示结构关系；诊断、方案和代码修改由 Codex 处理。
- 保留旧 CLI 命令、地图格式、Skill、Key 配置、历史报告、旧发行包和用户工作区改动。
- 不增加自动修复、MCP 服务、多语言、数据库、通用缓存或新 UI 框架。
- 完成声明必须有实际产物与新鲜验证，不能以测试数量、勾选框代替真实使用结果。

---

## 1. 基线和确认问题

### 1.1 当前现场

| 项目 | 编写计划时的值 |
| --- | --- |
| 主目录 | `/Users/kisara/Documents/ChatGPT/AI Repo Doctor` |
| 主分支 / HEAD | `codex/local-product-closure` / `0e96e45b7e4f5ea1fe11a313172aee414c57de5e` |
| 可复用干净 worktree | `/Users/kisara/.codex/worktrees/diagnosis-evaluation/AI Repo Doctor` |
| worktree 当前分支 | `codex/v0-5-1-delivery`，与主目录同 HEAD |
| 远端 | `https://github.com/kisara174/ai-repo-doctor.git` |
| 远端默认分支 | `codex/repo-doctor-v1`，实施前重新查询 |
| 正式版本 / 来源 | `v0.5.1` / `d35e52a474ed76835e663da9833306d05d037d78` |
| 持久 CLI | `/Users/kisara/.local/bin/repo-doctor` |
| 持久 venv | `/Users/kisara/.local/share/ai-repo-doctor/venv` |
| 0.5.1 wheel SHA256 | `be6ed5ae971b46f995f48c3674fa6aadac3a90e40f1db873b7ee2cf9dca12041` |

主目录以下四份用户改动必须保留，不能恢复、自动改写或混入新提交：

1. `docs/superpowers/plans/2026-09-24-post-v3-execution.md`
2. `docs/superpowers/plans/2026-09-24-post-v3-handoff.md`
3. `docs/superpowers/plans/2026-09-24-repo-doctor-v3.md`
4. `docs/superpowers/specs/2026-09-24-repo-doctor-v3-design.md`

保留 manifest：`/Users/kisara/.local/share/ai-repo-doctor/workspace-preservation/2026-10-01-product-closure/manifest.json`。逐文件 SHA256 以它为依据。

### 1.2 三项已复现缺陷

| 编号 | 位置 | 真实复现 | 影响 |
| --- | --- | --- | --- |
| F1 / P1 | `report.py::repair_state` | A before 失败 → A after 通过并关联 → B before 失败 → A after 通过；B 仍失败，报告再次显示修复证据 | 当前失败轮未闭合却给出闭合结论 |
| F2 / P1 | `case.py::save_case/load_case` | 每份 finding JSON 800,332 字节，六次导入成功；case 为 9,610,636 字节，重开被 8 MiB 上限拒绝 | 成功保存了工具无法继续处理的任务 |
| F3 / P2 | `case.py::TOOL_VERSION` | 安装 metadata 是 0.5.1，新报告却记录 0.5.0 | 来源版本不准确 |

审计还通过了概览、搜索、context、impact、四份地图产物、正常同命令修复记录及过期快照拒绝。正式包的 29 个运行文件与源码一致，正式 CI 通过。本轮沿现有产品修补，不重建产品。

## 2. 设计合同：实施时不得自行改换规则

### 2.1 当前回归轮和命令关联

1. `verification` 数组追加顺序是顺序依据，不用秒级时间戳猜轮次。
2. 当前轮从数组最新一条 `phase == 'before'` 开始，不能跳过它去找更早、恰好 argv 相同的 before。
3. 最后一条必须是 after，且位于该 before 之后；两者 argv 数组逐项完全相等，才存在当前配对。
4. before 必须 `failed`、after 必须 `passed`，两次执行期间 Python 指纹各自未变，两次之间 Python 指纹确实不同。
5. issue 为 resolved，最后一条复核记录明确关联当前命令，才显示“有修复证据”。actor 为 codex 时仍显示 Codex 确认。
6. 最后 after 不通过时显示“复查未通过”；其他缺配对或缺关联的情形显示“仍需复核”。
7. B before 后，A after 通过不能闭合 B。B 真正 after 通过，也需要针对 B 的关联。
8. 同一 argv 的新轮可以沿用这个命令的已有关联；不同 argv 不能沿用。

**新增可选字段：** 新 `human_history` 记录在 `--related-test` 时保存 `related_test_argv: list[str]`，复制最新已记录检查的 argv。没有已记录命令时，该参数返回操作错误，不能凭空建立关联；单独标记 resolved 仍允许，但修复证据保持待复核。检查发生在修改 issue 之前。

**旧记录兼容：** 最后复核没有新字段时，若所有 verification 只出现一个唯一 argv，可把旧关联解释为这个命令；多个不同 argv 则关联不明确，保持待复核，提示使用现有 issue 命令重新确认。不猜时间，不批量改写历史。

### 2.2 普通 case 读写一致性

- 定义唯一 `MAX_CASE_BYTES = 8 * 1024 * 1024`，普通读写都引用。
- 大小为最终 JSON 加换行的 UTF-8 字节数，不是字符数或输入 finding 大小。
- 保存先构造候选 updated_at，校验可加载结构，生成 JSON/Markdown，再检查大小；容量和结构拒绝发生在任何写入之前。
- 超限抛 `ValueError('case.json exceeds 8 MiB; create a new case for further findings')`，CLI 返回 2，原 case.json/report.md 字节均不变。
- 不静默删 issue、截断推理或扩大限制。保留旧 finding 字段及原数据格式。
- 正常写入沿用现有逐文件原子替换和权限，不宣称提供双文件事务；本任务不增加通用事务系统。
- 普通读取改为 `read(MAX_CASE_BYTES + 1)` 有界字节读取，不能只 stat 后无界 read_text。
- 提取原 load_case 结构检查为 `_validate_case(case: object) -> dict`，供普通读取、保存前和救援共享。保留旧可选字段与容错，不新增无依据的格式限制。

### 2.3 超大历史 case 的完整只读救援

新增随 wheel 安装的独立模块 `repo_doctor.case_recovery`，不新增一级 CLI 命令：

```sh
/Users/kisara/.local/share/ai-repo-doctor/venv/bin/python -m repo_doctor.case_recovery CASE_DIRECTORY --out NEW_ARCHIVE_DIRECTORY
```

| 产物 | 合同 |
| --- | --- |
| `original-case.json` | 原始读取字节，完整保留全部 issue、finding、历史、版本 |
| `recovered-report.md` | 当前渲染器生成的完整报告，前置只读档案说明 |
| `recovery.json` | schema_version 1、status `read-only-archive`、原路径、source_bytes、source_sha256、source_tool_version、export_tool_version、生成时间、前两份产物的 SHA256 |

具体规则：

- 原 case.json/report.md 完全不修改，不运行目标代码，不联网。
- 一次读取原 JSON：`read(MAX_RECOVERY_BYTES + 1)`；所有输出基于这一次字节，避免混合来源。
- 原目录与 case.json 的链接检查沿用现有规则。输出不能是原目录或其子目录；已有输出或链接拒绝。
- 校验输入并准备输出内容后才创建新目录；目录 0700、文件 0600，独占创建，receipt 最后写。
- 成功返回 0；输入、容量、输出冲突、写入错误返回 2，短错误不带 traceback。写入途中失败说明产物不完整，不能声称成功或自动删除已有文件。
- 超过 32 MiB 仍拒绝，普通 load_case 保持 8 MiB。
- 档案不是可续写 case，不能宣传为 report show 已恢复加载。后续调查新建普通 case；档案供 Codex 查阅完整历史。
- 原 tool_version 原样保留，receipt 单独记录导出工具为 0.5.2。

选择“完整只读档案 + 新任务继续”，避免拆分 issue、重编号或改变证据语义。

### 2.4 统一版本

- `_version.py` 唯一声明 `__version__ = '0.5.2'`。
- pyproject 使用 setuptools dynamic attr，不增加版本插件或构建依赖。
- case 保留 TOOL_VERSION 名称作为别名，值来自该常量。
- `repo-doctor --version` 输出 `repo-doctor 0.5.2`，退出 0，不扫描、读 Key 或联网。
- 新 case 与包 metadata 一致；旧 case 的版本不因读取更新。
- 从仓库外查询安装 metadata，排除源码和遗留 egg-info 干扰。

配置依据：[setuptools dynamic metadata](https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html#dynamic-metadata)、[argparse version action](https://docs.python.org/3.11/library/argparse.html#action)、[JSON 序列化](https://docs.python.org/3.11/library/json.html#json.dumps)。

### 2.5 精简产品入口

README 第一条主流程：安装 → Codex overview/symbols/context/impact → 人查看 map → 有发现才建 case/快照并导入 → 必要时显式检查 → 重开结果。

| 类别 | 命令 | 本轮处理 |
| --- | --- | --- |
| 核心 | overview、symbols、context、impact、map | 主教程前置 |
| 记录 | report、findings、issue、reproduce、verify | 按需接续 |
| 辅助 | skill、doctor、demo | 安装和演示入口 |
| 高级/兼容 | scan、validate、diagnose | 文档后移，旧命令参数保持 |

不重建 argparse 子命令体系；帮助只改善说明。图保持结构展示，不增加诊断面板或重做布局。

## 3. 允许文件与职责

| 文件 | 职责 |
| --- | --- |
| `repo_doctor/report.py` | 当前轮配对、命令关联解释、旧关联提示 |
| `repo_doctor/case.py` | 新关联记录、容量、共享校验、保存前检查、版本引用 |
| `repo_doctor/case_recovery.py`（新） | 有界只读救援、独立模块入口 |
| `repo_doctor/_version.py`（新） | 唯一版本常量 |
| `repo_doctor/cli.py` | --version、准确帮助，保留现有主流程 |
| `pyproject.toml` | dynamic version，依赖和 package-data 保留 |
| `tests/test_repair_state.py`（新） | 回归轮与旧关联状态 |
| `tests/test_product_verify.py` | 实际 CLI 跨轮与既有兼容 |
| `tests/test_product_case.py` | 保存边界、字节计量、原文件保留 |
| `tests/test_case_recovery.py`（新） | 救援完整性、边界、拒绝 |
| `tests/test_product_cli.py` | 版本入口、写入版本、超限状态 |
| `tools/validate_release_install.py`（新） | 仓库外安装后完整流程校验，只用标准库 |
| `.github/workflows/ci.yml` | 现有 wheel 步骤接入校验，保留原矩阵和地图门槛 |
| README、CODEX_AND_MAP、PRODUCT_GUIDE | 当前流程、容量、兼容和救援说明 |
| `docs/LEGACY_USAGE.md`（新） | 旧云端、完整扫描、独立校验、历史教程 |
| `docs/delivery/2026-10-02-v0.5.2-reliability.md`（新） | 唯一交付记录，正文写实际执行日期 |
| 本计划 | 状态与证据索引 |

若实际需要改图算法、解析器、传输、Skill 或地图资源，主代理先记录阻塞并更新计划。执行者不能自行扩展。

## 4. 执行、分工与状态

### 4.1 主代理与执行者

主代理负责 D0–D8 全部设计、调试、验收、依赖、Git 和发布。无预设必须委派的编码任务。Luna 仅用于已确定且协调成本合算的机械复制，事先给完整 Objective、Allowed changes、Forbidden changes、Exact steps、Validation、Expected result、Stop conditions。

委派前读取新鲜核心周限额，剩余严格低于 10% 才按用户规则考虑合格 Harness 包装器；否则合格机械任务用 luna_executor。无合格任务就直接做，不为展示子代理而造任务。返回后主代理检查实际 diff 和独立验证。

### 4.2 顺序与停止条件

```text
D0 现场 → D1 回归轮 → D2 保存 → D3 救援 → D4 版本
        → D5 教程 → D6 安装验收/冻结 → D7 正式发布 → D8 Mac 交付
```

- 每阶段先最小失败案例，再最小实现和相关验证；RED 必须说明所缺行为，不能以无关 import 错误替代缺陷复现。
- 一次针对性修正仍不通过，由主代理查根因；不能放宽规则或权限换绿色。
- 提交只列明确文件；禁止 git add .、reset --hard、clean、force push、覆盖旧标签或旧报告。
- 全套测试在代码冻结后跑一次；改源码才重跑有关门槛，文档改动只复核相关内容及当前提交 CI。
- 每份证据记录 argv/cwd/版本/退出码/关键输出/hash，不保存环境变量全集和 Key。

### 4.3 状态表

| 阶段 | 用户成果 | 状态 |
| --- | --- | --- |
| D0 | 可追溯基线与隔离位置 | 待执行 |
| D1 | 当前失败轮不误报闭合 | 待执行 |
| D2 | 超限保留原件，成功保存可重开 | 待执行 |
| D3 | 超大历史完整可查阅 | 待执行 |
| D4 | 包、CLI、新报告版本一致 | 待执行 |
| D5 | 一条当前产品教程 | 待执行 |
| D6 | 安装后真实流程及冻结证据 | 待执行 |
| D7 | 公开 wheel 与正式来源一致 | 待执行 |
| D8 | 普通终端可用及中文交付 | 待执行 |

---
## D0：核对现场和确定隔离位置

**Files:** 不改业务源码。本地证据写入 `/Users/kisara/.local/share/ai-repo-doctor/evaluations/v0.5.2-reliability/`；开始填写交付文档。

**Consumes:** 第 1 节、审计、保留 manifest。

**Produces:** baseline.json：真实 HEAD/分支、四份用户文件 hash、旧 wheel、CLI/Skill、旧报告 hash、worktree 状态。

- [ ] 查询主目录、现有 worktree 与远端默认分支。

```sh
git -C '/Users/kisara/Documents/ChatGPT/AI Repo Doctor' status --short
git -C '/Users/kisara/.codex/worktrees/diagnosis-evaluation/AI Repo Doctor' status --short
gh repo view kisara174/ai-repo-doctor --json defaultBranchRef
```

- [ ] 按 manifest 核对四份用户文件；保存旧 schedule case、Skill、部署收据、0.5.1 wheel hash。不得读取 Key 文件。
- [ ] 优先复用干净 worktree，从当前 HEAD 新建 `codex/v0-5-2-reliability`。分支已有则核对来源后接续，不能覆盖。先让执行 worktree 包含本计划最新版；主目录文档尚未提交时，只复制本计划和本次 PRODUCT_GUIDE 入口，不复制四份用户历史改动。
- [ ] 执行 worktree 先 GraphFlow context，再登记执行 DAG，回答全部设计与范围工作项。
- [ ] 写 baseline.json 和交付记录，D0 完成必须附实际证据，其他阶段仍待执行。

**Validation:** 主目录原四份改动保留，hash 与 manifest 一致；执行 worktree 没有未知改动；从 `/private/tmp` 查询安装 metadata 为 0.5.1。

**Stop:** 未知源码改动、不同来源或保留 hash 不符，先查清来源，不清空工作区。

## D1：修复当前轮配对与命令关联

**Files:** report.py、case.py；新 tests/test_repair_state.py；tests/test_product_verify.py。

**Interfaces:** 保持 repair_state(issue: dict) -> str、update_issue 的现有参数；新 related_test_argv 是可选历史字段。

- [ ] 新测试文件建立如下完整夹具，不调用云端。

```python
import copy
import unittest
from repo_doctor.report import repair_state

def record(phase, argv, status, source):
    return {'phase': phase, 'argv': argv, 'status': status,
            'source_fingerprint': source, 'source_fingerprint_after': source}

class RepairStateTests(unittest.TestCase):
    def make_issue(self):
        return {'human_status': 'resolved',
                'human_history': [{'status': 'resolved', 'related_test': True,
                                   'actor': 'codex', 'related_test_argv': ['check-a']}],
                'verification': [record('before', ['check-a'], 'failed', 'one'),
                                 record('after', ['check-a'], 'passed', 'two')]}

    def test_after_cannot_skip_latest_before_with_another_command(self):
        issue = self.make_issue()
        issue['verification'] += [record('before', ['check-b'], 'failed', 'three'),
                                  record('after', ['check-a'], 'passed', 'three')]
        self.assertEqual(repair_state(issue), '仍需复核')

    def test_changed_command_requires_its_own_related_confirmation(self):
        issue = self.make_issue()
        issue['verification'] += [record('before', ['check-b'], 'failed', 'three'),
                                  record('after', ['check-b'], 'passed', 'four')]
        self.assertEqual(repair_state(issue), '仍需复核')
        issue['human_history'].append({'status': 'resolved', 'related_test': True,
                                      'actor': 'codex', 'related_test_argv': ['check-b']})
        self.assertIn('有修复证据', repair_state(issue))

    def test_legacy_single_command_does_not_rewrite_issue(self):
        issue = self.make_issue()
        del issue['human_history'][-1]['related_test_argv']
        original = copy.deepcopy(issue)
        self.assertIn('有修复证据', repair_state(issue))
        self.assertEqual(issue, original)
```

- [ ] 跑新文件，记录 F1 真实 RED；增加没有 before、最后只有 before、argv 不同、after 失败、运行变源、同 argv 新轮、旧多 argv 关联不明确七种断言。
具体输入与断言如下，均以 make_issue() 为初始夹具并分别独立执行：

| 补充案例 | 修改夹具 | 预期 |
| --- | --- | --- |
| 无 before | verification 只留原 after | 仍需复核 |
| 最新只有 before | 末尾追加 A before failed/source three | 仍需复核 |
| 不同 argv | 原 after 的 argv 改为 check-b | 仍需复核 |
| after 失败 | 原 after status 改为 failed | 复查未通过 |
| 运行变源 | 原 after source_fingerprint_after 改为 three | 仍需复核 |
| 同 argv 新轮 | 追加 A before failed/three、A after passed/four | 有修复证据，沿用 A 关联 |
| 旧多命令 | 删除关联 argv 字段，再追加 B before/after，维持 resolved/related_test | 仍需复核，不改对象 |

- [ ] 替换原 matching argv 搜索，仅寻找最新 before，随后比较命令。

```python
history = issue.get('verification', [])
after = history[-1] if history and history[-1]['phase'] == 'after' else None
before = next((item for item in reversed(history[:-1])
               if item['phase'] == 'before'), None) if after else None
if before is not None and before['argv'] != after['argv']:
    before = None
```

- [ ] 实现关联解释：新字段比较 argv；旧字段只有唯一 argv 才回退；修复证据同时检查 §2.1 的状态与指纹条件。
- [ ] update_issue 在修改对象前检查已有检查 argv，复制入新记录；无命令时抛 ValueError。只标 resolved 不附 --related-test 仍允许。
- [ ] 添加实际 CLI 跨轮测试：自建语法错误 app 和 S-001；A 的 unittest before 失败，修复后 A after 通过并关联；增加 B 检查的未修复行为，B before 失败，再跑 A after。报告仍待复核，B 失败记录存在。
- [ ] B 真修复并 B after 通过仍待关联；用 actor codex 关联 B 后才显示 Codex 修复证据。全部执行仅限自建目录。

```sh
python3 -B -m unittest discover -s tests -p 'test_repair_state.py' -v
python3 -B -m unittest discover -s tests -p 'test_product_verify.py' -v
python3 -B -m unittest discover -s tests -p 'test_reproduction.py' -v
```

**Acceptance:** A 不跨 B 配对；不同命令不复用关联；旧单命令正常可读，旧多命令保守待复核；actor 不混淆，读取不改历史。

**Commit:** `fix: bind repair evidence to current regression cycle`，只提交本阶段文件。

## D2：保存前容量检查和有界读取

**Files:** case.py、tests/test_product_case.py、tests/test_product_cli.py。

**Interfaces:** MAX_CASE_BYTES；_validate_case(case: object) -> dict；save_case/load_case 的现有签名保持。

- [ ] 在 ProductCaseTests 添加以下行为 RED：

```python
def test_oversize_save_preserves_both_existing_files(self):
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        repo = base / 'repo'
        repo.mkdir()
        (repo / 'app.py').write_text('def value():\n    return 1\n', encoding='utf-8')
        out = base / 'case'
        case = create_case(build_index(repo), out)
        before = {name: (out / name).read_bytes() for name in ('case.json', 'report.md')}
        case['padding'] = '中' * 5000
        with patch('repo_doctor.case.MAX_CASE_BYTES', 8192, create=True):
            with self.assertRaisesRegex(ValueError, 'exceeds'):
                save_case(out, case)
        self.assertEqual(before, {name: (out / name).read_bytes() for name in before})
        self.assertEqual(load_case(out)['issues'], [])
```

- [ ] 记录 RED：目标是未拒绝或原文件被改变，不能把无关错误计为成功复现。
- [ ] 提取原结构检查为 _validate_case；普通 load 改为有界读取、json.loads、校验。
- [ ] 保存按以下顺序准备候选，再调用原原子写入。正常两份文件写完后才同步传入对象的 updated_at。

```python
candidate = {**case, 'updated_at': timestamp()}
_validate_case(candidate)
case_text = json.dumps(candidate, ensure_ascii=False, indent=2) + '\n'
report_text = render_report(candidate)
if len(case_text.encode('utf-8')) > MAX_CASE_BYTES:
    raise ValueError('case.json exceeds 8 MiB; create a new case for further findings')
# 通过全部检查后，沿用现有 _atomic_write 写两份内容。
```

- [ ] 边界测试固定 timestamp，计算真实 byte_count；patch 限制为 byte_count 成功，为 byte_count-1 拒绝且双文件不变。中文 padding 证明按字节而非字符计量。
- [ ] CLI 再现六次 800 KiB finding：前五次成功，第六次返回 2；保存前后双 hash 一致，前五次任务能 report show 和 issue 读取。
- [ ] 输入结构缺项也在写入前拒绝，旧文件不变。不能改为删除字段、截断内容或提高上限。

```sh
python3 -B -m unittest discover -s tests -p 'test_product_case.py' -v
python3 -B -m unittest discover -s tests -p 'test_product_cli.py' -v
python3 -B -m unittest discover -s tests -p 'test_agent_tools.py' -v
```

**Acceptance:** 成功保存可加载；比较为 UTF-8 字节和 `>`；容量/结构拒绝保留双文件；读写上限一致。

**Commit:** `fix: enforce readable case size before persistence`。

## D3：历史超大任务只读救援

**Files:** 新 case_recovery.py、tests/test_case_recovery.py。

**Interfaces:** MAX_RECOVERY_BYTES；export_archive(source: Path, destination: Path) -> dict；main(argv: list[str] | None = None) -> int；模块入口。

- [ ] 新测试创建合法 case，再添加 padding 超过正常容量。建立完整输出合同测试，原 schema 和 issue 字段完整。未实现时记录缺少功能；实现后必须以实际档案字节证明成功。

```python
source_bytes = (source / 'case.json').read_bytes()
old_report = (source / 'report.md').read_bytes()
result = export_archive(source, destination)
assert result['status'] == 'read-only-archive'
assert (destination / 'original-case.json').read_bytes() == source_bytes
assert (source / 'case.json').read_bytes() == source_bytes
assert (source / 'report.md').read_bytes() == old_report
assert 'A-001' in (destination / 'recovered-report.md').read_text(encoding='utf-8')
receipt = json.loads((destination / 'recovery.json').read_text())
assert receipt['source_sha256'] == hashlib.sha256(source_bytes).hexdigest()
```

- [ ] 检查输出冲突、源目录/链接、输出路径关系；一次有界读取原字节，超限抛 ValueError；共享 _validate_case 校验。
- [ ] render_report 生成完整报告，前置只读说明；receipt 记录 §2.3 字段。复制原字节，不调用 save_case。
- [ ] 输入全部有效后创建新目录，权限独占写入，receipt 最后写。输入错误不得创建输出。
- [ ] 模块捕获 ValueError/OSError/UnicodeError/JSONDecodeError，错误返回 2；成功打印 JSON receipt，返回 0。
- [ ] 验证超 32 MiB、已有输出、源链接、输出在源内、畸形 JSON、合法旧 schema、中文、旧多命令、途中写入失败。每个拒绝核对原 hash；途中失败不得写成功 receipt。

```sh
python3 -B -m unittest discover -s tests -p 'test_case_recovery.py' -v
python3 -B -m repo_doctor.case_recovery --help
```

**Acceptance:** 原审计 9,610,636 字节 case 导出全部六个 issue；原件 hash 不变；普通 load 仍拒绝超限；不把档案称为可续写任务。

**Commit:** `feat: export oversized cases as bounded read-only archives`。

## D4：版本单一来源

**Files:** 新 _version.py；pyproject.toml、case.py、cli.py、tests/test_product_cli.py。

**Interfaces:** __version__: str；TOOL_VERSION 别名；全局 --version。

- [ ] 新测试捕获 main(['--version']) 的 SystemExit 0，断言输出；patch build_index 为会抛错的 mock，证明未扫描。
- [ ] 新 case 断言 0.5.2，旧 0.5.0 case 的 report show 不改其字段和字节。
- [ ] 添加字面量常量，删除 project 内静态 version 行，加入以下 dynamic 配置，其他元数据保留：

```python
# repo_doctor/_version.py
__version__ = '0.5.2'
```

```toml
# 添加到现有 [project] 内
dynamic = ['version']

[tool.setuptools.dynamic]
version = {attr = 'repo_doctor._version.__version__'}
```

```python
from ._version import __version__
# case.py
TOOL_VERSION = __version__
# cli.py，在 add_subparsers 前加入
parser.add_argument('--version', action='version', version=f'repo-doctor {__version__}')
```

- [ ] 常量模块没有 Git 查询或 metadata 导入；构建不依赖遗留 egg-info。

```sh
python3 -B -m unittest discover -s tests -p 'test_product_cli.py' -v
python3 -B -m repo_doctor --version
```

**Acceptance:** 源码 CLI 和新报告为 0.5.2，旧数据不更新。D6 还须验证真实 wheel metadata，不能在本阶段提前宣称发行版本一致。

**Commit:** `fix: use one version source for package and reports`。

## D5：收拢当前产品教程

**Files:** README、CODEX_AND_MAP、PRODUCT_GUIDE；新 LEGACY_USAGE；计划和交付记录。

**Consumes:** D1–D4 实际行为与退出码。**Produces:** 一条主教程，旧能力直接链接。

- [ ] README 第一屏只说明目标、Python 3.11+、安装、Skill、结构图。当前安装 URL 改为 0.5.2，并明确 D7 发布后才可用。
- [ ] 主教程准确覆盖 overview → symbols → context/impact → map → 按需 report/快照/import → 检查/重开；提供完整 findings JSON。SYMBOL 来自搜索，引用必须在快照内。
- [ ] 旧版安装、完整 scan、独立 validate、云端诊断/Key、旧教程移至 LEGACY_USAGE；保留参数和边界，主文档用直接链接承接。
- [ ] 说明换命令重新关联、旧多命令待复核、超限保留旧数据、救援只读及新任务继续。
- [ ] 救援使用已安装环境 Python，不要求克隆源码。人类页面仍只看图。
- [ ] PRODUCT_GUIDE 当前路线指向 D0–D8，旧 T0–T8、R1–R5 仍已完成；此时 0.5.2 状态写待发布部署。
- [ ] 主代理逐条比对文档命令、wheel 文件名、版本、退出码；历史版本数字不批量替换。

**Acceptance:** 按一条主教程能走当前目标，无 Key 要求；旧能力可找到，图不混入详细诊断。

**Commit:** `docs: center the offline Codex investigation workflow`。

## D6：安装后真实验收、CI 和代码冻结

**Files:** 新 tools/validate_release_install.py；必要修改已有 CI；计划和交付记录。

**Interfaces:** 校验器参数 `--python ABS_PYTHON --cli ABS_CLI --out NEW_EVIDENCE_DIRECTORY`。输出目录必须不存在。仅通过指定安装后的解释器/CLI 工作，使用自建仓库和标准库。

### D6.1 独立校验器

- [ ] 用 argparse/subprocess/tempfile/json/hashlib/Path 编写；每条命令保存 argv、cwd、exit_code、stdout、stderr。任一断言失败返回非零，不能只保存错误继续宣布成功。
- [ ] 子进程 cwd 为证据目录或 /private/tmp，去除 PYTHONPATH；metadata 查询必须 version 为 0.5.2，import_path 在 site-packages。
- [ ] 在自建仓库使用以下源码并准备两条检查，所有 target code 执行仅限这里：

```python
# app.py 初始内容
def value():
    return 1

def entry():
    return value()
```

```python
command_a = [installed_python, '-B', '-c', 'import app; assert app.value() == 2']
command_b = [installed_python, '-B', '-c', 'import app; assert app.entry() == 2']
```

- [ ] 调 overview、symbols 取得 app.py::value，再 context snapshot、impact、map、report create。impact 必须含 app.py::entry，四份地图必须存在，两张 SVG 可 XML 解析。
- [ ] 写完整 finding，引用 value 第 2 行 return 1，导入保存为 A-001。A before 返回 1；改 value 返回 2，A after 返回 0；actor codex 关联后重开报告含修复证据。
- [ ] 将 entry 改为 return 0，B before 返回 1；A after 通过仍待复核。改 entry 返回 2，B after 通过仍待关联；显式关联 B 后闭合。确认报告中的命令与当前轮相符。
- [ ] 用新快照/新 case 写 reasoning 长度 800000 的合法 finding（单份 JSON 小于 1 MiB）；前五次导入成功，第六次返回 2。第六次前后 case.json/report.md 双 hash 均不变，前五次正常任务可重开。
- [ ] 手动生成仅供复现的超大历史 case，使用已安装 Python 的 case_recovery 模块导出；核对原字节、原文件 hash、完整六个 issue 和 receipt。新 save_case 不负责写这个超限原件。
- [ ] 旧单命令 case 的读取不改字节；过期 snapshot 导入返回 2且正常任务不变。核对 --version/new case/package metadata 三者一致。
- [ ] 最终 receipt 至少如下，任一 false、缺项或 map_files 不为 4 都失败：

```json
{
  "version": "0.5.2",
  "site_packages_import": true,
  "report_version_matches": true,
  "normal_offline_flow": true,
  "current_cycle_guard": true,
  "related_command_guard": true,
  "oversize_write_preserved_case": true,
  "oversize_write_preserved_report": true,
  "saved_case_reopened": true,
  "read_only_recovery_complete": true,
  "old_case_unchanged": true,
  "stale_snapshot_rejected": true,
  "map_files": 4
}
```

### D6.2 候选 wheel 与 CI

- [ ] 从明确的候选源码 Git archive 构建 wheel，安装到新临时 venv，沿用现有 build 工具，不增加运行依赖。候选 SHA、wheel hash 和运行文件清单写 receipt。
- [ ] 校验器复制到仓库外，用候选环境调用。禁止源码 import 冒充安装后检验。

```sh
"$RD_TEST_PYTHON" "$RD_VALIDATOR" --python "$RD_TEST_PYTHON" --cli "$RD_TEST_CLI" --out "$RD_NEW_EVIDENCE"
```

RD_TEST_PYTHON、RD_TEST_CLI、RD_VALIDATOR、RD_NEW_EVIDENCE 在运行前设置为实际新建 venv、仓库外校验器副本和证据目录的绝对路径；不能使用旧持久安装通过候选门槛。

- [ ] 在 CI 的已有 wheel 安装步骤追加校验，指定 RUNNER_TEMP 内已安装 Python/CLI。保留原 smoke、Python 矩阵和地图交互门槛。
- [ ] 代码冻结后跑一次全套离线测试，记录真实数量和输出，不硬编码必须恰好某个数量。

```sh
python3 -B -m unittest discover -s tests -q
```

- [ ] 主代理审查最终 diff：允许文件、边界、旧兼容、无新网络依赖、没有把失败证据改成成功；记录 freeze SHA 和源码 hash。
- [ ] 用临时 body 文件创建正式 PR，附 F1–F3 前后结果、旧关联变化、救援定位和安装 receipt。创建后必须 Codex attach_artifact。
- [ ] 等 PR 当前 head 的完整 CI。旧 SHA 的绿色不能验收最新代码；源码改变重跑相关门槛。

**Acceptance:** 同一候选 wheel 在仓库外通过全部 receipt 项，全套离线门槛和当前 head CI 通过，冻结与审查证据已保存。

**Commit:** `test: gate installed release on case reliability workflow`。

## D7：正式发布 v0.5.2

**Owner:** 主代理；Git、构建、公开发布不交给 Luna/Harness。

**Artifacts:** 正式来源 SHA、tag、wheel、SHA256SUMS、release-notes、build/publication receipt，目录 `/Users/kisara/.local/share/ai-repo-doctor/releases/v0.5.2/`。

- [ ] 确认执行时的发布授权仍适用。用户仅授权写计划的本轮不得执行此阶段；后续明确开始完整计划且历史发布授权仍有效时，继续已授权工作，不反复索要相同确认。
- [ ] 合并已审查且当前 head CI 通过的 PR，查询合并后真实 SHA 和 CI，设为 formal source。不得把 0.5.1 来源构建成 0.5.2。
- [ ] 从 formal source 的 Git archive 构建正式 wheel；build-receipt 记录源码 SHA、全部 repo_doctor 模块和资源 hash、版本、Requires-Python/Dist、wheel SHA256。
- [ ] 正式 wheel 在干净 venv 跑 D6。任何失败先解决并形成新来源提交，不能先发布后补证据。
- [ ] release-notes 明确三项修复、旧多命令关联变化、只读救援、安装方法、静态边界；不承诺整仓无缺陷。
- [ ] 创建 v0.5.2 tag 指向 formal source，正常稳定 release 附 wheel、SHA256SUMS。若已有 tag/release，查询实际来源，绝不覆盖。
- [ ] 从公开资产重新下载到新目录，比较 SHA256、wheel metadata、tag SHA；公开包在仓库外安装后再过 D6。
- [ ] 写 publication.json。公开下载、来源和安装均验证后，才记录已发布。保留 0.5.1 与全部旧收据。

**Acceptance:** 用户可从公开 URL pip 安装 0.5.2；formal source、tag、包 metadata、新报告版本一致；公开下载校验成功。

## D8：Mac 升级、回滚保障和交付闭环

**Owner:** 主代理。**Consumes:** D7 验证后的公开 wheel 与正式 hash 清单。

- [ ] 保存旧 deployment.json/INSTALLATION.md 副本和旧 wheel 路径。用同一已验证 wheel 升级持久 venv，不从可变分支安装。
- [ ] 保留现有 CLI 入口、Skill 和 Key，使用持久 Python -m pip 安装；失败则从保留的 0.5.1 wheel 恢复，不先删环境再重建。
- [ ] 从 /private/tmp 查询 metadata、site-packages 导入、--version，逐文件比对正式运行 hash。
- [ ] 新登录 zsh 执行 command -v repo-doctor 与 --version，不能仅靠激活的临时 shell 验收。
- [ ] 持久 CLI 执行 D6。重开已有 schedule 报告并核对原字节；schedule 仅作 overview/context/impact/map 静态调查，不执行其代码。
- [ ] 用持久救援模块导出原审计超大受控 case 到新目录，保存完整报告和档案链接，原 audit 不变。
- [ ] fast-forward 主目录；之前之后核对四份用户改动 hash。未知变更阻止快进时由主代理保留并解决，不能 reset。
- [ ] 单独文档提交记录交付；不移动正式 tag。清楚区分 formal source SHA 和后续 documentation HEAD。
- [ ] 更新 deployment-v0.5.2.json、deployment.json、INSTALLATION.md：真实来源、包 hash、CLI、安装 receipt、旧数据保留、D0–D8 状态与 pending。必需事项全部完成才 pending=[]。
- [ ] 项目更新后 GraphFlow incremental index，最终对齐产品目标；历史 workbench 自动状态不代替正式交付状态。
- [ ] 中文交付包含版本、公开安装链接、普通终端入口、正常报告、地图、救援档案、三个缺陷的结果与静态边界。

**Acceptance:** 普通终端使用 0.5.2，正常调查/图/记录/复查成立，三个审计缺陷不再重现，旧数据和用户改动保留，公开包与安装匹配，必需待办归零。

---

## 5. 目标完成定义与需求追踪

| 承诺 | 阶段 | 实际证据 |
| --- | --- | --- |
| 当前失败轮不误报闭合 | D1/D6/D8 | B before/A after 仍待复核，失败记录保留 |
| 测试关联有明确对象 | D1/D6 | 新字段、不同命令拒绝复用、旧多命令提示 |
| 成功保存可重开 | D2/D6 | 超限双 hash 不变，已保存任务可读 |
| 超限历史不丢失 | D3/D8 | 原始字节完整档案、完整 Markdown |
| 版本真实 | D4/D7/D8 | metadata/--version/新 case 一致，旧版原样 |
| 一条教程完成使用 | D5/D6 | 主流程真实执行，无 Key |
| 完整发布与 Mac 部署 | D7/D8 | formal SHA、公开包 hash、干净与持久 receipt |
| 产品保持精简 | 全程 | 无解析/云端/UI/依赖扩张，兼容能力只收拢呈现 |

**D8 全部满足即完成本轮稳定基础产品。** 代码完成但没有公开安装、Mac 验证或旧记录保留证据，仍不能标为完成。V1/V2 是之后的方向，不阻塞补丁交付，不用追加目标无限延长本轮。

## 6. 之后的实际效益工作

### V1：两类真实仓库、六个调查问题

**启动条件：** D8 完成。先写问题，再选符合问题的公开 Python 仓库；一类多模块库、一类带命令注册的 CLI。实施时查询官方源码、固定 commit/本地路径，不执行其代码，不调用诊断 API。

- [ ] 每仓库三个问题：真实入口如何到核心逻辑、修改某实际函数影响谁、图如何定位相关文件/局部关系。
- [ ] 每题保存四步真实命令、真实 symbol ID、源码行证据、Codex 补读。需要图时生成新目录 HTML/SVG。
- [ ] 记录工具已回答、需补读、误边/漏边、完成步骤与耗时；未解析调用数量不作为准确率。
- [ ] 有具体阻断才做最小源码夹具，限定一种可保守解析的关系。没有缺口就结束，不造新特性。

**产物：** `docs/evaluations/2026-10-02-v0.5.2-investigation-value.md`，正文记录真实执行日期，六题逐条“回答完整/边界明确/阻断”并附来源。选出最多一个收益明确的继续点，或建议保持当前版本。

### V2：只做证据最强的一项优化

- 重复扫描确实慢：先测同仓库四步耗时，再单独设计来源一致的复用；修改、增删、ignore、工具版本变化必须正确失效。
- 一种漏边阻断答案：单独制定有范围的白名单，未知对象保持未知，不靠同名猜边。
- 图定位困难：只改已复现动作，保留隐藏数与静态边界。
- 没有实际阻断则不启动。V2 需要独立小计划，不能扩大本轮允许文件。

**收益标准：** 同一调查的补读或步骤减少，证据未变弱。模块、命令、测试、模型数量增加不算收益。

## 7. 下一会话可直接复制

```text
请继续 AI Repo Doctor，先读用户 AGENTS.md 规则、GraphFlow context 和
 docs/superpowers/plans/2026-10-02-v0-5-2-reliability-and-delivery.md。
目标完成 D0–D8，交付并部署可 pip 安装的 v0.5.2 稳定 Python CLI。
从首个未完成阶段推进，先核对源码、worktree 和证据，不重复已完成项。
按计划修复回归轮、容量与版本，提供完整只读救援，收拢教程，完成干净安装、公开发布核对、Mac 部署和中文交付。
主代理承担设计、debug、审查和发布；Luna 仅用于合格机械任务。
保留四份用户文档改动、Skill、Key、旧报告和旧发行包。主要流程离线，不执行外部仓库代码。
测试只对应实际风险和已有门槛。新阻塞由主代理定位并更新计划，保持产品精简。
本段供用户决定开始实施后使用；当前写计划本身不代表代码、发布或部署已完成。
```

## 8. 计划编写自审

- [x] 三项缺陷都有复现、规则、文件、接口与验收。
- [x] 新关联和旧数据回退明确，不用时间戳猜轮次。
- [x] 超限写入与历史救援分开，不冒充可续写恢复。
- [x] 版本配置有官方依据，安装版本在仓库外核对。
- [x] D0–D8 包含公开下载、正式来源、Mac、保留和回滚，终点明确。
- [x] 教程收拢有产物，旧接口不删，人类图不混入诊断。
- [x] 执行阶段均未完成，计划示例不称为实现。
- [x] V1/V2 有触发条件和收益标准，不无限扩张补丁范围。
