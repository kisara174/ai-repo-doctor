# AI Repo Doctor

为 Codex 提供本地 Python 仓库结构、上下文和证据的 CLI，并生成供人查看的离线结构关系图。Codex 负责问题判断、方案和代码修改；Repo Doctor 保存调查记录并校验来源。主要流程不需要 API Key。扫描和地图生成不会运行目标仓库代码；只有显式调用 `reproduce` 或 `verify -- <命令>` 才会运行检查。

[v0.5.0 稳定版](https://github.com/kisara174/ai-repo-doctor/releases/tag/v0.5.0) 已交付 Codex 接入与离线关系图，并部署到这台 Mac；发行包和安装入口见下方。完整用法见 [Codex 与仓库地图](docs/CODEX_AND_MAP.md)，实际发布证据见 [交付记录](docs/delivery/2026-10-01-product-closure.md)。

当前目标、剩余工作和完成标准统一见[稳定基础版指导清单](docs/superpowers/plans/2026-10-01-basic-product-optimization-guide.md)，实际产物与使用确认见[收尾交付记录](docs/delivery/2026-10-01-product-closure.md)。此前的模型评估和阶段计划保留为历史。

## 安装与快速开始

需要 Python 3.11+；安装 Git 后扫描会遵循目标仓库的 ignore 规则。安装 v0.5.0 发行 wheel：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install 'https://github.com/kisara174/ai-repo-doctor/releases/download/v0.5.0/ai_repo_doctor-0.5.0-py3-none-any.whl'
export PATH="$PWD/.venv/bin:$PATH"
repo-doctor --help
```

本项目在这台 Mac 上已安装，普通终端直接使用 `repo-doctor`，无需激活环境或重新加载 Key。当前主目录也已同步到 0.5.0；从源码运行 `python3 -m repo_doctor` 时请确认所在 checkout 的 `pyproject.toml` 版本。

如需保留历史版本 **v0.4.1**，请安装到另一个环境。该旧版本支持报告与检查记录，不含下方 0.5.0 的 `overview`、`map`、`skill` 和 `findings import` 新命令：

```bash
python3 -m venv .venv-v041
.venv-v041/bin/python -m pip install 'git+https://github.com/kisara174/ai-repo-doctor.git@v0.4.1'
```

### 让 Codex 调用，并查看项目结构

```bash
repo-doctor overview /path/to/python-repo --json
repo-doctor map /path/to/python-repo --out ./repo-map
repo-doctor skill export --out ~/.agents/skills/repo-doctor
```

打开 `repo-map/map.html`，搜索文件与符号、切换结构树和静态关系图；`structure.svg` 与 `relations.svg` 同时生成，也可在页面导出当前视图。页面只呈现项目结构。地图的数据与资源都在本地，不需要启动服务。分析边界和隐藏数量会保留在图中。

Skill 导出会保留已有目录；若目录已存在，请先查看其内容并选择新的导出位置。Skill 被 Codex 加载后可以使用 `$repo-doctor` 显式调用；按描述匹配任务的隐式调用不是必然触发。工具不修改 Codex 全局配置和 AGENTS 规则。

### 五分钟走完一条离线闭环

发行包自带受控小样例。`demo create` 会生成一个**故意有语法错误**的 Python 仓库，以及检查 `answer() == 42` 的回归测试。以下命令只处理这个样例；任务目录保存到样例仓库外。

```bash
RD=.venv/bin/repo-doctor
$RD demo create --out ./demo-repo
$RD report create ./demo-repo --out ./demo-case
$RD report show ./demo-case
$RD issue ./demo-case S-001

# 修改前：预期退出码 1，结果写入 demo-case/case.json 和 report.md
$RD verify ./demo-case S-001 --phase before -- python3 -m unittest -q test_regression

# 模拟人工修复样例源码
python3 - <<'PY'
from pathlib import Path
Path('demo-repo/app.py').write_text('def answer():\n    return 42\n', encoding='utf-8')
PY

# 修改后：对同一个 issue 使用完全相同的命令
$RD verify ./demo-case S-001 --phase after -- python3 -m unittest -q test_regression
$RD issue ./demo-case S-001 --status resolved --note '语法已修复，回归测试与此问题相关' --related-test
$RD report show ./demo-case
```

最终报告会区分静态事实、人工判断和修复证据。`verify` 不自动修改源码；上例中的编辑由用户明确完成。实际仓库中先用 `symbols REPO --query NAME` 搜索可复制的符号 ID，再用 `context` 和 `impact` 检查选定目标。可将目标直接纳入任务：

```bash
$RD report create /path/to/python-repo --out ./my-case --symbol 'app.py::target'
$RD symbols /path/to/python-repo --query target
$RD context /path/to/python-repo 'app.py::target'
$RD impact /path/to/python-repo 'app.py::target'
```

`report create` 写入权限受限的 `case.json` 与 `report.md`；`report show` 不需重新扫描，就能读取已有任务。`case.json` 是原始记录，Markdown 是可阅读视图。已存在的非空任务目录不会被覆盖。报告可能含源码引文与回归输出，请按本地敏感文件保存。发行包提供 `repo-doctor` 和 `repo_doctor`，但不包含源码仓库中的 `tools.evaluate_diagnosis` 评估脚本。
若选定路径下没有可扫描的 Python 文件，`report create` 会返回错误；该路径可能受上级 Git 仓库的 ignore 规则影响。

`v0.3.0` 新建的任务报告含“建议先检查”：先列影响扫描完整性的语法解析失败，再列有证据行的局部导入环，最后列至多五个被至少三个不同生产代码符号、且分布在至少两个其他文件中直接调用的函数或方法。每项都有检查理由、下一步和文件行号；跨文件调用目标是改动影响入口，不是缺陷判断。旧版任务文件仍可打开；这一顺序不是缺陷严重度或模型分数。

新建任务还会给出“静态架构摘要”：最多列五个被至少两个其他生产代码文件依赖的本地模块，展示不同依赖文件数、导入者数、跨文件调用者数与具体导入/调用边。排序只用于浏览已解析的依赖，不是代码质量分数；测试文件、外部包、动态导入和未解析调用不参与。指定 `--symbol` 后，报告把反向调用分为直接和间接影响，并列出每一跳的调用行、目标模块的直接导入行。旧任务照旧可打开，但需新建任务才能保存这些新增的扫描摘要。

`scan`、`symbols`、`report`、`context`、`impact`、`validate`、`demo` 和默认 `doctor` 都离线运行；只有显式 `diagnose` 或 `doctor --deepseek` 会联网。只有显式 `reproduce` 或 `verify` 会执行用户给出的目标仓库命令。两者使用参数数组执行，不经隐式 shell；工作目录是任务中的仓库路径。它们仅传递必要环境变量并移除 `DEEPSEEK_API_KEY`，默认 120 秒超时（可在 1–300 秒范围内调整），保存最多 16 KiB 输出。它们**不提供操作系统级隔离**，应只对愿意自行运行测试的仓库使用。

超时同时限制进程退出与输出等待；到期后会结束原进程组并停止读取输出。命令主动创建新会话的后台进程需要自行管理，它们不在原进程组的清理范围内。

任务状态分三层：静态事实或引文是否得到来源校验；人工状态 `unreviewed`、`confirmed`、`rejected`、`resolved`；回归命令的 `before`/`after` 记录。只有同一命令在修改前失败、Python 源码指纹变化、最新一轮修改后检查通过、两次执行期间源码都未变，并且用户用 `--related-test` 确认关联时，报告才写“有修复证据”。开始新的 `before` 检查后，报告显示“仍需复核”，直到这一轮的 `after` 检查也满足上述条件。未满足时显示“仍需复核”或“复查未通过”。这仍不等于整仓无缺陷。

| 记录 | 含义 |
| --- | --- |
| `static_fact` | 本地解析器观察到的语法错误或导入环；导入环本身不等于缺陷。 |
| `quote_verified` | AI 引文与已发送的源码匹配；推理和影响仍待人工确认。 |
| 诊断 `accepted` / `partial` / `empty` / `rejected` | 分别为有引文通过的发现、通过与拒绝并存、无发现、所有发现被证据校验拒绝。 |
| 诊断 `invalid_json` / `invalid_response` / `connection_failure` / `provider_failure` / `source_changed` | 请求失败的分类；不形成已验证 issue。 |
| 人工 `unreviewed` / `confirmed` / `rejected` / `resolved` | 尚未审阅、认为相关、驳回、已处理；每次更改保留时间与备注。 |
| 回归 `passed` / `failed` / `timeout` / `command_error` | 所选命令退出 0、退出非 0、超时、无法启动。 |

`scan` 文本输出会给出示例符号 ID；`symbols --query` 可按名称、限定名或 ID 检索，找不到精确匹配时显示候选而不替用户选定。完整索引在 `scan --json` 输出中，包括文件、符号、导入声明、调用点、局部导入边、已解析调用边、语义关系、导入环和解析错误。

各命令独立声明 `schema_version`；完整扫描和现有上下文等使用版本 2，概览、快照与地图使用版本 1。`call_edges` 只表示普通静态调用；`semantic_edges` 单独记录显式本地重导出和 Click 命令注册。符号包含装饰器和 overload 签名元数据，调用边通过 `via_reexports` 保留重导出链。`context` 会为命令组和回调标出注册关系，`impact` 将语义关系与普通调用影响分开列出。

## 让 ChatGPT 诊断一个函数

```bash
python3 -m repo_doctor context /path/to/python-repo 'app/services/user.py::UserService.create' --max-lines 120 > context.txt
```

如果目标行为依赖另一个已知符号，可重复添加 `--include-symbol 'app/policies.py::AccessPolicy'`。额外符号按给定顺序排在目标及其所属类声明之后，与自动找到的相关代码共用行数预算；过长片段会标为截断。若显式选择的就是目标所属类，原本简短的类声明会展开为该类源码。未指定该选项时，选取结果不变。它只表示你主动选入了源码，不表示工具已证明两个符号之间存在调用或继承关系。

把 `context.txt` 内容交给 ChatGPT。它要求返回一个 finding 对象、finding 数组，或 `[]`。将模型返回的纯 JSON 保存为 `findings.json`，再运行：

```bash
python3 -m repo_doctor validate /path/to/python-repo findings.json
```

finding 结构：

```json
{
  "title": "可能的资源泄漏",
  "category": "reliability",
  "confidence": 0.8,
  "evidence": [
    {
      "file": "app/database.py",
      "start_line": 17,
      "end_line": 20,
      "quote": "session = SessionLocal()",
      "symbol": "app/database.py::get_db"
    }
  ],
  "reasoning": "说明为什么这些代码可能导致问题",
  "impact": "说明受影响的路径",
  "suggested_fix": "说明建议的修改"
}
```

`validate` 对有拒绝项的文件返回退出码 1；参数、路径或 JSON 无法读取时返回 2。通过校验只说明引文真实且定位正确，**不代表诊断结论一定成立**；仍需人工审查推理和实际运行验证。

## 检查运行环境

```bash
repo-doctor doctor /path/to/python-repo
repo-doctor doctor /path/to/python-repo --json
repo-doctor doctor /path/to/python-repo --deepseek
```

`doctor` 默认检查 Python 版本、Git 可用性、仓库可解析的 Python 文件数、语法解析错误数，以及 `DEEPSEEK_API_KEY` 是否存在；省略路径时检查当前目录。它不会运行目标代码，也不会联网。Git 不可用时扫描器会退回目录遍历；语法错误或没有 Python 文件会使检查返回退出码 1。

只有加 `--deepseek` 才会发出一次不含仓库源码的 `GET /models` 请求，检查 Key 与所选模型。模型选择顺序是 `--model`、`DEEPSEEK_MODEL`、默认 `deepseek-flash`。连接失败时 JSON 输出给出安全的类别和下一步提示，包括认证、余额、限流、DNS、TLS、代理、超时和服务端故障；不会输出 Key 或原始服务端错误正文。检查成功返回 0，未就绪返回 1，路径或参数错误返回 2。这项检查不运行诊断，也不能证明诊断质量或账号余额足以完成后续调用。

如果 `doctor --deepseek` 报告 `tls`，检查当前 Python 的可信 CA 证书配置。对 python.org 安装的 macOS Python，运行与当前解释器版本匹配的 `Install Certificates.command`（例如 `/Applications/Python 3.14/Install Certificates.command`），再运行 `doctor --deepseek`；这是 [Python 官方安装步骤](https://docs.python.org/3.14/using/mac.html)。若需要临时指定证书，先确认 `/etc/ssl/cert.pem` 存在且来源可信，再运行 `SSL_CERT_FILE=/etc/ssl/cert.pem repo-doctor doctor --deepseek`。保持 TLS 证书验证开启。

## 使用 DeepSeek 云端诊断（可选）

配置 DeepSeek API Key。模型可通过 `DEEPSEEK_MODEL` 指定；默认使用 `deepseek-flash`。

```bash
export DEEPSEEK_API_KEY="your-key"
# 可选：export DEEPSEEK_MODEL="deepseek-flash"

# 先检查将要分析的本地上下文
python3 -m repo_doctor context /path/to/python-repo 'app/services/user.py::UserService.create' --max-lines 120

# 可选：离线预览精确的 JSON 请求体；SHA-256 显示在标准错误中
$RD diagnose /path/to/python-repo 'app/services/user.py::UserService.create' --preview --case ./my-case

# 复制预览输出中的 SHA-256，再显式发起云端诊断
REQUEST_SHA256='paste-the-64-character-digest-here'
$RD diagnose /path/to/python-repo 'app/services/user.py::UserService.create' --expect-request-sha256 "$REQUEST_SHA256" --case ./my-case
# 若有引文通过的发现，按输出中的实际 issue ID 查看并人工判断
$RD issue ./my-case A-001
$RD issue ./my-case A-001 --status confirmed --note '复核后认为与预期行为相关'

# 可选：使用 DeepSeek Responses API 的 JSON Schema 输出路径
python3 -m repo_doctor diagnose /path/to/python-repo 'app/services/user.py::UserService.create' --response-format json-schema
```

普通 `diagnose` 只发送所选的、有上限的源码片段，以及仓库相对路径、行号、关系标签和静态调用证据。片段可能包含本地类父级定义、类方法所属的类声明和被引用的模块级导入行；预算不足时会截断或省略排在后面的片段。普通请求不会发送整个仓库、绝对仓库路径或未选中的源码；显式使用 `--reproduction` 时还会发送命令参数和捕获的输出，它们可能自带绝对路径或敏感信息。每次请求最多包含 120 行和 64 KiB 源码文本，完整序列化后的 HTTP 请求体另有 256 KiB 上限，超出会在联网前失败。客户端拒绝所有重定向，只连接固定的 DeepSeek endpoint。发出请求前，命令会在标准错误中显示将发送的文件、行范围、源码大小、请求体字节数和 SHA-256，不会在提示中重复源码。

`--preview` 只输出将要发送的 JSON 请求体，不需要 API Key，也不联网；其内容含所选源码，请仅保存到受保护的位置。把标准错误中显示的 64 位 SHA-256 赋给 `REQUEST_SHA256` 后使用 `--expect-request-sha256`。若源码、模型、输出格式或提示内容使请求体变化，正式诊断会在联网前拒绝发送。命令还会在请求前和收到响应后核对已选源码行；若核对时与构造请求时不同，就丢弃返回的 finding。`--preview` 输出的是 HTTP 请求体，不含 Key 或请求头；`--json` 在预览模式下仍输出这个原始请求体。

`diagnose` 也支持重复使用 `--include-symbol`。预览和正式发送时须提供相同的额外符号及顺序，否则预览 SHA-256 不会匹配。额外符号同样受 120 行、64 KiB 源码和 256 KiB 请求体限制，并会列在发送前显示的文件与行号中；请一并检查是否含有敏感内容。

### 可选：把实际失败记录绑定到诊断（v0.4.0）

当你已经有一个针对目标行为的回归命令时，可以先明确运行并保存结果，再决定是否将它发给 DeepSeek。`reproduce` 可以在 AI issue 出现之前使用；命令退出非零时返回码 1，并保存 `R-001` 等稳定 ID。

```bash
$RD report create /path/to/python-repo --out ./my-case
$RD reproduce ./my-case -- python -m pytest -q tests/test_specific.py
$RD diagnose /path/to/python-repo 'app.py::target' --case ./my-case --reproduction R-001 --preview > request.json
# 检查 request.json 中的源码、命令和输出；复制标准错误显示的 SHA-256
REQUEST_SHA256='paste-the-64-character-digest-here'
$RD diagnose /path/to/python-repo 'app.py::target' --case ./my-case --reproduction R-001 --expect-request-sha256 "$REQUEST_SHA256"
# 若产生 issue，按实际 ID 查看；修改源码后仍需显式运行同一回归命令
$RD verify ./my-case A-001 --phase after -- python -m pytest -q tests/test_specific.py
$RD issue ./my-case A-001 --status resolved --note '确认该测试覆盖此问题' --related-test
$RD report show ./my-case
```

只有同一命令的最新记录为失败、输出未被 16 KiB 截断、运行中 Python 源码未改变且当前源码指纹相同时，`--reproduction` 才可用于诊断。正式发送必须带预览哈希；这会把所选命令、退出码和已捕获的输出一起发送。输出可能含密钥或个人信息，请先检查完整预览；不想上传时直接停在本地报告。源码指纹只覆盖扫描到的 Python 文件，其他文件的变化无法由此检查发现。通过引文校验的 AI 结果仍是待人工复核的假设；一次失败命令不能自动证明任何 issue。之前的症状提示实验有误报，这条新流程尚无独立的诊断准确率结论。

源码片段可能含有密钥或其他敏感内容。调用前请用 `context` 查看实际选中的代码；发现不应上传的内容时，不要运行 `diagnose`。不带 `--case` 的普通 `diagnose` 不保存请求或结果。带 `--case` 时仅保存请求及上下文哈希、经证据校验的 finding、被拒发现的标题与原因、调用状态和失败类别；不保存完整请求体或原始服务端正文。报告中的 finding 含源码引文。API Key 仅从 `DEEPSEEK_API_KEY` 读取，不作为命令参数，也不会写入任务。

文本输出完整显示 finding 标题、相对文件与行号、引文、推理、影响和建议，并将通过本地源码及已发送上下文校验的 finding 标为 `QUOTE-VERIFIED`；JSON 输出仍使用 `accepted` 字段以保持兼容。`--case` 将它们作为稳定 ID 的 issue 保存，后续诊断不会覆盖此前人工判断。空发现、引文拒绝、无效 JSON 和连接失败也留在诊断历史。引文匹配不证明推理正确。请人工复核结论，并使用显式 `verify` 记录所选择的回归检查。

`v0.3.0` 的默认 `chat-json` 路径显式关闭 thinking，以在 4,096 token 输出上限内给 JSON 留出空间。它的预览请求 SHA-256 与 `v0.2.0` 不同，升级后请重新预览再发送。这不能保证所有请求都可解析，也不代表诊断质量达标：[M1 六样本盲测](docs/evaluations/2026-09-29-m1-holdout-v2.md)出现一次无效 JSON、未命中三个已知缺陷，并有一次修复后误报。`--response-format json-schema` 是显式选择的实验性路径：它在相同的本地上下文与证据校验规则下调用 DeepSeek Responses API，请求结构化输出并关闭 thinking。两种路径都不会自动重试。[最初的单样本格式对照](docs/evaluations/2026-09-28-structured-output.md)之后，结构化路径完成了一轮[十样本诊断基线](docs/evaluations/2026-09-28-schema-ten-case-baseline.md)：十次请求均可解析，但经主代理复核只命中四个已知缺陷中的一个，且有较多误报和待确认发现。该定向小样本也不足以证明未来成功率。

## 影响分析

```bash
python3 -m repo_doctor impact /path/to/python-repo 'app/services/user.py::UserService.create' --depth 2
```

它沿已解析的反向调用边显示直接与间接调用者、每一跳的调用文件与行号，并列出目标文件的局部导入者及导入行。`--json` 可用于工具集成；新增 `call_path_evidence` 字段不改变原有符号、距离和路径字段。这些是静态参考，不代表运行时调用或测试覆盖。

## 当前精度边界

- 只解析当前 Python 解释器支持的语法。解析失败的文件会出现在错误列表中，其他文件继续分析。
- 显式本地重导出只沿可唯一解析的模块级导入绑定处理；此处的“重导出”表示静态可解析的绑定，不推断作者是否打算公开该名称。经过重导出的调用会指向规范实现，并附带每段导出证据。
- `typing.overload` 声明在同名唯一具体实现下作为签名元数据保留，不会成为额外的可执行符号或普通调用目标；缺少唯一实现时继续标记为歧义。
- Click 支持通过未遮蔽的显式 `click` 导入识别 `group`、`command` 装饰器，以及同一模块中唯一命令组的 `.command()` / `.group()` 注册关系（包括嵌套组）。这些注册边保留装饰器行号，但不计入普通调用统计或 impact 调用深度。
- Git 仓库采用 Git 标准 ignore 规则；非 Git 目录使用常见生成目录排除规则，不解释 `.gitignore`。
- 调用图只连向静态可定位的局部目标。对局部变量，只解析调用前唯一且无条件的简单本地类构造绑定（例如 `client = Client()`）；`with ... as client` 还要求对应的 `__enter__` / `__aenter__` 能直接证明返回 `self`、无需额外必填参数，并且类上存在匹配的 `__exit__` / `__aexit__`。复杂工厂、重绑定和多态分派仍可能无法解析。重名的条件定义会标为歧义；函数内部 import 的别名、动态 import、反射、猴子补丁、别名传播和外部包调用也可能无法解析。关联测试仅表示静态引用，不等于测试覆盖率。
- 上下文预算以源码行数计算；片段被截断时会标记。每次命令重新扫描当前工作树，不保留旧索引。
- 自动生成或应用补丁、自动运行目标仓库测试，以及跨多个目标符号的整体审查不在当前范围内。`reproduce` 和 `verify` 只执行用户明确输入的单条命令。

## 诊断评估

离线评估基础设施、固定十例样本，以及独立的 Flask、Werkzeug 和
Click 对照样本已完成。原始 Chat 十例在线运行曾因首个请求报错而停止；
后续 JSON Schema 十例运行已完整结束，经主代理复核命中 4 个已知缺陷
中的 1 个。

Flask 基线未命中 3 个已知缺陷，3 个修复后样本均出现误报；预先登记的
提示词对照因首例无效 JSON 而未完成，正式提示词已恢复。Werkzeug 六例
运行完整，命中 3 个已知缺陷中的 1 个，2 个修复后样本出现明确误报。
最新的 Click 显式上下文对照完成 8/8 次调用，但两个已知缺陷在两组
上下文中都未命中；四条引文通过校验的发现经主代理复核均为误报，
其中两条来自修复后样本。

详见[当前进度](docs/execution-status.md)、
[十例基线](docs/evaluations/2026-09-28-schema-ten-case-baseline.md)、
[Flask 对照报告](docs/evaluations/2026-09-28-flask-holdout.md)、
[Werkzeug 基线](docs/evaluations/2026-09-29-werkzeug-holdout.md)和
[Click 对照报告](docs/evaluations/2026-09-29-click-explicit-context.md)。
这些都是定向小样本及主代理复核，云端诊断仍属实验性能力，不能据此
推断总体准确率。

评估命令 `tools.evaluate_diagnosis` 需要在本项目源码目录中执行；当前发行包仅包含 `repo_doctor`，不包含 `tools`。

数据保存范围按命令区分：不带 `--case` 的 `diagnose` 不保存请求或结果；带 `--case` 的产品流程仅保存前述调查数据；评估工具另会把经审查的公开样本上下文、运行记录和评分产物写入指定本地输出目录。实验产物使用被 Git 忽略的 `.local` 目录，不是普通诊断命令的默认行为。

详细设计见 [V2 设计文档](docs/superpowers/specs/2026-09-24-repo-doctor-v2-design.md) 和 [V3 设计文档](docs/superpowers/specs/2026-09-24-repo-doctor-v3-design.md)。

## 开发验证

需要 Python 3.11 或更高版本。在仓库根目录运行：

```bash
python -m unittest discover -s tests -v
python -m compileall -q repo_doctor tools
python -m repo_doctor --help
python -m repo_doctor diagnose --help
```

GitHub Actions 会在 Python 3.11、3.12 和 3.13 上运行相同命令；该工作流只读仓库内容，不安装项目依赖，也不运行固定评估集。
