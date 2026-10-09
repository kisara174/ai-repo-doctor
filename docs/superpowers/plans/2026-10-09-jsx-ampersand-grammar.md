# JSX 属性原生 grammar 修复执行清单

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Follow the project's primary-planner policy; native dependencies, debugging, acceptance and release stay with the primary agent. Do not delegate this entire plan to Luna.

**Goal:** 恢复原始 JSX/TSX 属性 URL 的完整静态分析，交付可安装、可回滚并经过既有平台门禁的 1.0.1 修复候选。

**Architecture:** 主产品保持纯 Python wheel；独立 `ai-repo-doctor-grammars` 提供补丁后的 JavaScript/TSX capsule。官方普通 TypeScript grammar 保持不变；GitHub Release 同时提供 companion wheel 压缩包，通过本地离线安装 companion 解决 PyPI 未发布问题。

**Tech Stack:** Python 3.11+、tree-sitter 0.26.0、C11、setuptools 84.0.0、tree-sitter-cli 0.25.10、Node 26.11.0、abi3audit 0.0.26、cibuildwheel 4.3.0、auditwheel 6.8.2。后三个打包工具的实际平台运行仍属 T5 门禁，已查询版本不等于已经验收。

**Spec:** [设计说明](../specs/2026-10-09-jsx-ampersand-grammar-design.md)。先读规格再执行。

## 全局约束与起点

- 产品候选起点：`adcb178c4641cc2f8dd01721c74fffe8a3f706f0` / 1.0.1rc1，包含已验证的 CF-001 行号修复。
- 工作树：`/Users/kisara/.codex/worktrees/js-ts-support-closure/AI Repo Doctor`。设计分支：`codex/jsx-ampersand-grammar-design`；实施创建 `codex/jsx-ampersand-grammar`，从设计提交开始。
- 主目录 `/Users/kisara/Documents/ChatGPT/AI Repo Doctor` 的 15 个既有改动、历史评估、1.0.0 安装与 Skill 全部保留。不得在主目录 checkout/reset/pull。
- 新证据使用 `/Users/kisara/.local/share/ai-repo-doctor/evaluations/v1-0-1-jsx-grammar-delivery-v1`，目录已存在则先检查，不覆盖或清空。
- 原型目录为 `.../evaluations/v1-0-1-jsx-url-v1`。其中 `.dylib`、ctypes capsule、0.0.0.dev0 wheel 都不是产品交付件，不可复制成正式包冒充验收。
- 原源 UTF-8 字节直接交给 parser；不替换 `&`、不放行 ERROR/MISSING、不把 JS 切换到 TSX、不增加 Flow 或 JSX 正文 scanner 支持。
- 主产品拟升级 1.0.1rc2；companion 首个候选使用精确 0.1.0。元数据和真实运行时必须一致。
- 有依赖关系的步骤串行执行。每个出口通过才进入下一步；不可用文档标勾代替实际命令回执。

## T0 — 原因与可行性冻结（本轮已完成）

- [x] 原 R051 的 DownloadModal.js 及最小属性值在固定官方 JS/TSX 后端复现失败。
- [x] 核对三个上游源提交及 TSX 的 JS 0.23.1 基底。
- [x] 在隔离目录生成补丁后的 JS ABI 15、TSX ABI 14 parser，直接编译原生库。
- [x] 上游 JS corpus 116/116、TS/TSX corpus 112/112；52 个合法组合通过，6 个坏文件继续排除。
- [x] 原 R051 错误 2→0、符号 42→45、85 行引用无错位，旧符号对象不变；只做进程内原型验证。
- [x] 试验 companion wheel 在独立 venv 安装并从 site-packages 加载；严格 abi3audit 通过。它仅为 Mac 27 / Python 3.14 可行性证据，不是支持矩阵验收。

证据：原型目录的 `baseline.json`、`reproduction.json`、`dialect-probe.json`、`spike/*.patch`、`spike/*-corpus.txt`、`spike/probe.json`、`spike/native-installed-probe.json`、`spike/abi3audit.json`。

## T1 — 固定源码、补丁及可重生成的 companion 源包

**允许文件：** 新建 `backends/jsx-grammars/`；新增维护脚本 `tools/check_grammar_provenance.py`；`.gitattributes` 仅允许补丁文件保留 unified diff 必需的空白上下文。此步不改产品 parser。

**产物布局：**

```text
backends/jsx-grammars/
  pyproject.toml
  setup.py
  MANIFEST.in
  README.md
  provenance.json
  licenses/JAVASCRIPT-LICENSE
  licenses/TYPESCRIPT-LICENSE
  src/ai_repo_doctor_grammars/__init__.py
  src/ai_repo_doctor_grammars/binding.c
  vendor/javascript/{grammar.js,tree-sitter.json,src/**}
  vendor/javascript-tsx-base/grammar.js
  vendor/typescript/{tree-sitter.json,common/**,tsx/grammar.js,tsx/src/**}
  patches/javascript.patch
  patches/javascript-tsx-base.patch
  tools/regenerate.py
  tools/package-lock.json
  tests/test_native.py
```

只纳入编译、生成和来源核对所需文件；不提交 `.git`、`node_modules`、编译产物、缓存、绝对 symlink。完整上游 corpus 可由固定 commit 的临时 checkout 运行，不必把整个上游仓库复制进产品。

- [x] 记录主树、安装、历史证据和真实目标 baseline；核对本轮 T0 原型 SHA 清单。
- [x] 从规格中的三个 commit 获取源码，逐个验证 `git rev-parse HEAD`，保存上游 license；禁止直接复制原型 build 目录。
- [x] 在 JS 0.25.0 与 JS 0.23.1 两个 grammar 源应用规格第 3 节的四处改动；保存补丁。TSX common grammar 不做语义修改。
- [x] `provenance.json` 固定每个输入/生成文件 SHA256、三上游 commit、补丁 SHA、CLI/Node 版本、语言 ABI、包版本和许可证来源。
- [x] 实现 `regenerate.py --check`：在新临时目录放置固定输入；为 TSX 的 require 创建仅指向临时 JS 0.23.1 基底的本地链接；运行下列两条生成命令；与提交的输出逐字节比较；差异退出 1，不覆盖源码。

```sh
tree-sitter generate --abi 15  # 临时 JavaScript grammar 根目录
tree-sitter generate --abi 14  # 临时 TypeScript 的 tsx 目录
```

- [x] `check_grammar_provenance.py --root backends/jsx-grammars`：检查所有受控文件、SHA、版本、生成 ABI、许可证和包内范围；篡改任一临时副本文件时必须退出 1。

**验证：**

```sh
python tools/check_grammar_provenance.py --root backends/jsx-grammars
python backends/jsx-grammars/tools/regenerate.py --check
```

出口：两条命令退出 0，固定临时篡改反例退出 1；普通 TS parser 未纳入或修改。提交消息：`build: vendor reproducible patched JSX grammars`。

## T2 — 构建 companion wheel，先测原生合同

**文件：** T1 包中的 `pyproject.toml`、`setup.py`、`MANIFEST.in`、`src/**`、`tests/test_native.py`。

**接口：** `language_javascript()`、`language_tsx()` 返回名称为 `tree_sitter.Language` 的 capsule。模块不依赖 Node，不下载数据，不导入目标仓库。

- [x] 在未修补上游 grammar 上运行合法裸 & 反例，确认是解析断言失败而不是依赖缺失；保存红灯。
- [x] 两个函数按上游 Python capsule binding 的方式实现，分别调用 `tree_sitter_javascript()`、`tree_sitter_tsx()`。编译宏与 wheel tag 必须一致：

```python
Extension(
    'ai_repo_doctor_grammars._binding',
    sources=[
        'src/ai_repo_doctor_grammars/binding.c',
        'vendor/javascript/src/parser.c', 'vendor/javascript/src/scanner.c',
        'vendor/typescript/tsx/src/parser.c', 'vendor/typescript/tsx/src/scanner.c',
    ],
    include_dirs=['vendor/javascript/src', 'vendor/typescript/tsx/src'],
    define_macros=[('Py_LIMITED_API', '0x030B0000'),
                   ('PY_SSIZE_T_CLEAN', None), ('TREE_SITTER_HIDE_SYMBOLS', None)],
    extra_compile_args=['-std=c11', '-fvisibility=hidden'],
    py_limited_api=True,
)
# setuptools 的 bdist_wheel 配置：py_limited_api = cp311。
```

- [x] 包版本为 0.1.0，`requires-python >=3.11`；companion 编译失败必须构建失败，不可产出没有 extension 的“成功包”。sdist 必须包含本地编译需要的所有 headers、scanner、原生源和 licenses。
- [x] companion 的 `build-system.requires` 固定 `setuptools==84.0.0`；这是本地试验 wheel 的实际 Generator。主产品原有 setuptools 下限不因本次更改。`package-lock.json` 同时固定 tree-sitter-cli 0.25.10 与 integrity，不能只在描述里固定而 manifest 使用浮动范围。
- [x] 原生测试逐个运行单双引号及 `?a=1&b=2`、`&`、`a&b`、`a& b`、`a&1`、实体、多行、中文 emoji、反斜杠。原型中的 52 组合可作为明确输入集合。

```python
raw = b'export const View = () => <img src="?a=1&b=2" />;'
tree = Parser(Language(language_javascript())).parse(raw)
assert not tree.root_node.has_error
assert tree.root_node.end_byte == len(raw)
```

- [x] 检查实体仍有 html_character_reference 节点，先前成功输入的 CST 与基线一致；检查 JS ABI 15 / TSX ABI 14。
- [x] 未闭合引号、未闭合函数体、坏调用仍 `has_error`；这些是不能以“修复更多”而修改期望的反例。
- [x] 构建 wheel 与 sdist，清洁目录中独立安装 wheel；从 sdist 另编译一次并核对 parser/provenance 内容。不能只在源码目录导入。
- [x] 严格审计：

```sh
python -m pip wheel --no-deps --wheel-dir "$RD_EVIDENCE/native-wheelhouse" backends/jsx-grammars
python -m unittest discover -s backends/jsx-grammars/tests -v
abi3audit --strict --report --output "$RD_EVIDENCE/native-abi3.json" "$RD_NATIVE_WHEEL"
```

`RD_EVIDENCE` 为全局约束中的新证据目录；`RD_NATIVE_WHEEL` 是刚构建的唯一目标 wheel 绝对路径。出口：原生测试无 skip，ABI 零违规，运行模块位于新 venv/site-packages，两个许可证在 wheel 中。提交：`build: package the patched JSX native backend`。

## T3 — 接入产品及回归，保留坏文件零证据

**修改：** `pyproject.toml`、`repo_doctor/js_ts.py`、`tests/test_js_ts.py`、`tests/test_js_ts_spike.py`、`tests/test_v1_contract.py`。**新增：** `tests/test_jsx_ampersand.py`。不改 context 取行算法。

- [x] 先在现有 1.0.1rc1 后端运行新测试，至少有一个合法 URL 的 symbol 断言失败；保存真实红灯。
- [x] 新测试覆盖 `.js/.jsx/.tsx`，具体合同：返回 `View`/helper 的真实符号 ID；span/引用等于手工物理行；直接 helper 调用可解析，组件标签和回调不新增虚假调用；错误文件整文件排除且消费它的文件不获得伪造导入或调用边。
- [x] `_parser` 依赖与分支改为：

```python
pins = (('tree-sitter', '0.26.0'),
        ('ai-repo-doctor-grammars', '0.1.0'),
        ('tree-sitter-typescript', '0.23.2'))
# 先核对所有 pin；缺失和不符均转成现有可控输入错误。
if language == 'javascript':
    from ai_repo_doctor_grammars import language_javascript
    capsule = language_javascript()
elif tsx:
    from ai_repo_doctor_grammars import language_tsx
    capsule = language_tsx()
else:
    import tree_sitter_typescript
    capsule = tree_sitter_typescript.language_typescript()
```

- [x] 移除上游 JS grammar 的 extra 依赖；更新三个测试文件的可选模块检测为 `tree_sitter, ai_repo_doctor_grammars, tree_sitter_typescript`。检测不得吞掉 JS CI 的缺后端问题；native gate 仍要求零 skip。
- [x] 缺 companion、版本不符时明确拒绝，不 silently fallback。错误提示指向本版安装指导，因为本地 companion 不保证存在于公共索引。
- [x] 原有 `extract` 的 ERROR/MISSING 排除分支完整保留；不产生临时字符串，不增加“包含 & 放行”逻辑。

**定向验证：**

```sh
python -B -m unittest tests.test_jsx_ampersand tests.test_js_ts_dialects tests.test_source_lines tests.test_js_ts_spike -v
python -B -m unittest discover -s tests -v
```

先安装 T2 companion 和本项目 extra 后运行。出口：新用例由红转绿、native 环境无 skip，既有 CF-001、TS/TSX 分流和错误树边界通过。提交：`fix: parse original JSX attribute ampersands`。

## T4 — 独立安装合同、版本及真实仓库闭环

**修改：** `tools/validate_js_ts_install.py`、`tools/validate_v1_install.py`、`repo_doctor/_version.py`、`CHANGELOG.md`、`docs/SUPPORT_MATRIX.md`。**新增：** `tools/validate_jsx_grammar_install.py`、`evaluation/jsx-ampersand/{cases.json,README.md}`。既有 `validate_release_install.py` 直接复用。

- [x] 候选升级 1.0.1rc2，支持矩阵只写实际证据，不把旧 CI/500 组当作新候选证明。
- [x] 两个安装验证器检查新可选模块及精确 metadata；base 模式没有 native，JS 模式真实存在 native。保留纯 Python import 懒加载断言。
- [x] 新安装验证器参数合同：`--python ABS --cli ABS --repo ABS --expected-version VERSION --out NEW_ABS`；禁止 import 源码 repo_doctor，只 subprocess 调用传入 CLI；所有真实源只读。
- [x] `cases.json` 固定 R051 commit/tree/源码 SHA、DownloadModal 符号 ID 与声明/URL物理行；先从原 manifest 和人工源码证据取得，不从候选结果反推预期。
- [x] 验证器顺序：version/metadata→overview→symbols→context(120行)→impact(depth2)→map；保存每条命令、实际/预期退出码和输出。符号 ID 必须经 symbols 确认。
- [x] 必须断言两个特定 parse_errors 消失、45 个符号、原有 42 符号记录不变、DownloadModal 从原源码引用、所有上下文行逐行匹配、SVG/JSON 投影一致。空 impact 保留“不证明无影响”，不用数量增加当正确率。
- [x] 另造自有坏文件 fixture，安装 CLI 验证零符号/边泄漏；相同源码只变化属性内容时保留调用证据位置。运行前后核对真实仓库全部 tracked 源 SHA 和 git 状态。
- [x] base/js 分开新 venv，安装路径和 cwd 都不能指向源码产品。运行以下出口：

```sh
python tools/validate_release_install.py --python "$RD_JS_PY" --cli "$RD_JS_CLI" --expected-version 1.0.1rc2 --out "$RD_EVIDENCE/lifecycle"
python tools/validate_js_ts_install.py --mode base --python "$RD_BASE_PY" --cli "$RD_BASE_CLI" --expected-version 1.0.1rc2 --out "$RD_EVIDENCE/base"
python tools/validate_js_ts_install.py --mode js --python "$RD_JS_PY" --cli "$RD_JS_CLI" --expected-version 1.0.1rc2 --out "$RD_EVIDENCE/js"
python tools/validate_v1_install.py --mode base --python "$RD_BASE_PY" --cli "$RD_BASE_CLI" --expected-version 1.0.1rc2 --out "$RD_EVIDENCE/v1-base"
python tools/validate_v1_install.py --mode js --python "$RD_JS_PY" --cli "$RD_JS_CLI" --expected-version 1.0.1rc2 --out "$RD_EVIDENCE/v1-js"
python tools/validate_jsx_grammar_install.py --python "$RD_JS_PY" --cli "$RD_JS_CLI" --repo "$RD_R051" --expected-version 1.0.1rc2 --out "$RD_EVIDENCE/real-r051"
python tools/check_public_docs.py --root .
```

各变量记录为本轮新 venv/真实 R051 绝对路径，不使用 PATH 的旧全局 CLI。summary 必须带 exact product/native SHA 与所有布尔校验，失败退出非零。出口：独立安装而非注入 capsule 通过、主产品 wheel 仍纯 Python、旧安装/Skill/历史证据未变。提交：`test: verify installed JSX grammar recovery end to end`。

## T5 — 原生分发件、平台 CI 与实际安装

**新增：** `.github/workflows/native-grammars.yml`、`backends/jsx-grammars/requirements-build.txt`、`tools/build_grammar_bundle.py`、`tools/native_wheel_receipt.py`、`tools/validate_grammar_upstream.py`。**修改：** `README.md`、`backends/jsx-grammars/MANIFEST.in`、`.github/workflows/ci.yml`、`docs/INSTALL.md`、`docs/JS_TS_SUPPORT.md`、`docs/SUPPORT_MATRIX.md`。

- [x] `requirements-build.txt` 固定 `cibuildwheel==4.3.0`、`auditwheel==6.8.2`、`abi3audit==0.0.26`；companion build-system 固定 setuptools 84.0.0。版本来源见本轮 `build-tool-versions.json`；对新 Linux 组合仍须实际验证，失败由主代理调查，不盲目升级。复用现有 checkout/setup-python/upload-artifact 的固定 action commit，使用 `python -m cibuildwheel`，不新增浮动 action。普通用户不安装审计工具。
- [x] 原生 jobs 从同一个 product commit 构建：Linux x86_64 manylinux、Mac ARM，CPython 3.11 Limited API；不手工伪造平台 tag。Mac deployment target=11.0，但最终支持声明以 Mac 15 runner 实测为准。
- [x] 所有 native wheel 严格 abi3audit，Linux repair 后核对依赖与 tags，Mac 核对 load commands；产物 artifact 包含每个 wheel、生成源身份、机型与工具链。不要跳过缺 wheel 的平台。
- [x] 构建选择器只取 `cp311-manylinux_x86_64` / `cp311-macosx_arm64`，Linux 使用 manylinux2014 并记录实际镜像 digest，Mac 设置 deployment target=11.0。先运行 `python -m cibuildwheel --print-build-identifiers backends/jsx-grammars` 核对实际选择，再构建，不能误产 cp314 wheel 后改名成 abi3。
- [x] CI 的每个 JS job 先下载该提交构建的 companion wheel，以 `--no-index --only-binary=:all: --find-links` 安装，再安装主产品 extra；四个 Linux Python 与两个 Mac Python 均按实际 wheel 安装。base jobs 不安装 companion。
- [x] 现有 native 固定测试列表增加 `tests.test_jsx_ampersand`，保持零 skip 要求；原生命周期、地图 DOM/SVG job 保留。
- [x] `build_grammar_bundle.py --wheelhouse ABS --out NEW_ZIP` 只接受版本 0.1.0 的两个预期平台 wheel，验证元数据、tag、SHA；缺失/重复/源码包/多版本退出非零。zip 内含两个 wheel 和 manifest，排序/时间戳固定以便重建核对，不吞掉不合格 wheel。
- [x] 安装文档按规格第5节先校验后端包，再仅本地安装 companion；补充基础安装单文件校验、平台不符错误、未发布候选不能猜 URL、升级后重导出 Skill 与回滚。普通用户无需 Node、编译器或 API key。
- [x] 验证错误平台的隔离安装只拒绝，不连公共索引尝试同名包；两个目标平台的文档命令从 Release 模拟目录实际执行。

出口：记录远端 exact head 的全部实际 job 状态，不能把一台 Mac 或旧 PR45 结果算成本轮通过。wheel 不够、依赖/ABI/安装失败即回到对应阶段 debug。提交：`ci: build and validate supported native grammar wheels`。

## T6 — 审查、候选与稳定发布闭环

**文件：** 新建 `docs/delivery/2026-10-09-jsx-grammar-repair.md`；本轮新证据目录的 `products.json`、`preservation.json`、`completion.json`、中文报告。发布日期变化时以实际日期新建记录，不回写历史。

- [x] 主代理逐个审查 grammar 四处规则、生成差异、LICENSE/provenance、C capsule、依赖/extra、base 懒加载、源码引用和安装失败路径。源码/wheel/安装 runtime 与生成 parser SHA 必须匹配。
- [x] 审核只针对已发现风险补测，不机械重跑500组。单目标重查不解释为全样本新成绩，不把原型或源码测试算作安装验证。
- [x] 创建修复草稿 PR 并附到当前聊天；若 CF-001 PR45 未合并，以其分支为 base 明示依赖，不能把它的修复误计为本次新增。合并顺序先CF-001再本修复，核对 base/head 和最终 tree。
- [x] 生成 1.0.1rc2 发布件清单：pure Python wheel、两个 native wheel、后端zip、校验件、元数据与证据。所有候选产物不覆盖 rc1 或0.0.0.dev0。
- [ ] 只有 T1–T5 全部出口通过且审查无未解决发布阻塞，才准备正式1.0.1：更新版本后重建、核对实际正式SHA/包身份，重跑必要安装与 exact-head CI；不能给 rc2 wheel 改名。
- [ ] GitHub Release 上传主wheel、后端zip及校验件，下载发布件再装新目录做同一五步调查。没有可下载且可安装的后端就不能称为完成发布。
- [ ] 安装切换在发布件复验后进行；保存旧入口，使用已有升级/回滚流程；Skill 导出到新目录或按既有受保护绑定流程处理，不覆盖自定义 Skill。1.0.0 仍可通过绝对路径运行。
- [x] 中文交付报告逐项列“已完成/仍有范围限制”，明确 Flow、正文裸 &、动态调用等范围；报告 exact commit、wheel SHA、native版本/平台、命令数、CI链接、真实仓库结果与回滚入口。

最终闭环条件：用户按随发行件提供的文档能安装 JS/TS 环境，对原 R051 使用五命令获得真实结构与引用，并能退回旧版本。任何一个环节仍靠本地原型、源码 cwd、编译器或未提供的 PyPI 包，都不能勾选完成。

## 机械执行与异常返回规则

本清单的大多数任务涉及依赖、ABI、判断或发布，必须由主代理执行。若后续拆出纯文档替换等机械任务，先按 AGENTS 检查当前周配额，并给单个 bounded executor 提供 Objective、Allowed changes、Forbidden changes、Exact steps、Validation、Expected result、Stop conditions；返回后主代理看真实 diff 和新验证回执。原生失败、CST差异、源码/平台不符不得转交 Luna 猜测修复。

## 本轮实施记录（2026-10-09）

T1–T4 已以实际产品实现、独立安装和原 R051 验证通过；本地最后完整回归 563 项，无 skip。上游原有 corpus 116 + 112 全部通过。证据在本清单全局约束指定的新目录，原型和产品证据分开。T5 首次远端运行编译/repair/ABI 通过，但 `{project}/tests` 错误指向主项目；已改为 `{package}/tests`，从源码目录外的安装后原生测试 3 项通过。该失败保留在 `ci-initial-failure.txt`；T5 完成以修正后 exact-head CI 和最终分发安装为准。草稿 PR46 依赖未合并的 PR45。

T5 现已通过：a41a5c1 的 push/PR 各15任务成功，两平台 cp311-abi3 wheels已下载核验，Mac原样文档安装与原R051复查通过。aa20a7e 将同一安装文档原样执行加入 Linux 独立安装，push/PR各15任务通过。候选产物仍归 a41a5c1，后续CI/文档不重标已有wheel。T6候选交付项目已完成，正式1.0.1重建/发布/全局切换3项继续待办。详见 [交付记录](../../delivery/2026-10-09-jsx-grammar-repair.md)。
