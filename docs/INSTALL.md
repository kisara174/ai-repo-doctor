# 安装、Codex 接入、升级与回滚

<!-- repo-doctor-install-versions: 1.0.1, 1.0.0, 1.0.1rc2 -->

适用范围：Python 3.11+，Linux x86_64/glibc 与 Mac ARM。实际平台组合见 [支持矩阵](SUPPORT_MATRIX.md)。本页安装目标为 1.0.1；发行身份见 [1.0.1 交付记录](delivery/2026-10-09-v1.0.1-release.md)。Windows、Intel Mac、Linux ARM/musl 暂不承诺。

1.0.1 修复源码物理行引用和 JSX/TSX 带引号属性的裸 `&`。主产品为纯 Python wheel；JS/TS 需要同批独立 native grammar wheels。没有 PyPI 发行，不能只对远端产品 URL 加 `[js]` 而跳过后端安装。

## 1. 下载并校验到新目录

确认 python3 至少为 3.11；若默认解释器较旧，使用合适解释器的绝对路径。安装不修改系统 Python。以下发行件在 Release 可下载后使用，下载或校验失败即停止；不清空既有目录重试。

```sh
set -e
RD_VERSION=1.0.1
RD_ROOT="$HOME/.local/share/ai-repo-doctor/releases/v$RD_VERSION"
mkdir -p "$(dirname "$RD_ROOT")"
mkdir "$RD_ROOT"
RD_URL="https://github.com/kisara174/ai-repo-doctor/releases/download/v$RD_VERSION"
RD_WHEEL="$RD_ROOT/ai_repo_doctor-$RD_VERSION-py3-none-any.whl"
curl --fail --location "$RD_URL/ai_repo_doctor-$RD_VERSION-py3-none-any.whl" --output "$RD_WHEEL"
curl --fail --location "$RD_URL/ai_repo_doctor-$RD_VERSION-py3-none-any.whl.sha256" --output "$RD_WHEEL.sha256"
(cd "$RD_ROOT" && if command -v sha256sum >/dev/null 2>&1; then sha256sum -c "$(basename "$RD_WHEEL").sha256"; else shasum -a 256 -c "$(basename "$RD_WHEEL").sha256"; fi)
```

仅分析 Python 时，在新 venv 安装已校验产品 wheel，无需后端包：

```sh
python3 -m venv "$RD_ROOT/venv"
"$RD_ROOT/venv/bin/python" -m pip install --no-index "$RD_WHEEL"
RD_CLI="$RD_ROOT/venv/bin/repo-doctor"
"$RD_CLI" --version
```

## 2. 完整 Python + JS/TS 安装

在上面的新目录继续下载后端 zip 与校验件，然后按四文件安装步骤建立另一个新环境。普通用户无需 Node、C 编译器或 API key。

```sh
curl --fail --location "$RD_URL/jsx-backend-wheels-0.1.0.zip" --output "$RD_ROOT/jsx-backend-wheels-0.1.0.zip"
curl --fail --location "$RD_URL/jsx-backend-wheels-0.1.0.zip.sha256" --output "$RD_ROOT/jsx-backend-wheels-0.1.0.zip.sha256"
cd "$RD_ROOT"
```

### 从四个已下载文件安装

进入含产品 wheel、产品 `.sha256`、后端 zip、后端 `.sha256` 的目录，原样执行；同名环境或解压目录已存在时停止并选新目录。

```sh
set -e
RD_VERSION=1.0.1
RD_CAND_DIR="$PWD"
check_sha() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum -c "$1";
  else shasum -a 256 -c "$1"; fi
}
check_sha "ai_repo_doctor-$RD_VERSION-py3-none-any.whl.sha256"
check_sha jsx-backend-wheels-0.1.0.zip.sha256
test ! -e "$RD_CAND_DIR/venv-js"
test ! -e "$RD_CAND_DIR/backend-wheels"
python3 -m zipfile -e jsx-backend-wheels-0.1.0.zip "$RD_CAND_DIR/backend-wheels"
python3 -m venv "$RD_CAND_DIR/venv-js"
"$RD_CAND_DIR/venv-js/bin/python" -m pip install --no-index --only-binary=:all: \
  --find-links "$RD_CAND_DIR/backend-wheels" ai-repo-doctor-grammars==0.1.0
"$RD_CAND_DIR/venv-js/bin/python" -m pip install "${RD_CAND_DIR}/ai_repo_doctor-$RD_VERSION-py3-none-any.whl[js]"
RD_CLI="$RD_CAND_DIR/venv-js/bin/repo-doctor"
"$RD_CLI" --version
```

后端包仅提供已验证的 Linux x86_64/glibc 与 Mac ARM wheel，由 pip 选择。不兼容时仅本地匹配失败就停止，不从公共索引下载同名 companion 或要求用户编译。安装主产品 extra 的两个官方依赖可能联网；安装后的五个只读调查命令离线工作，不运行目标源码或安装其依赖。发行 source commit 与详细回执见 Release 的 SOURCE_COMMIT.txt 和 release-receipt.json。

以下 rc2 段落仅供保留旧候选使用；新正式安装使用上面的 1.0.1。

### 1.0.1rc2 原生 grammar 候选（尚未正式发布）

此候选修复 JSX/TSX 属性中的裸 `&`。它需要同批交付的独立后端包；不能直接套用上面 1.0.0 的 JS-extra 下载步骤，也不能假设 companion 已存在于 PyPI。

先取得维护者提供的四个已验收文件：产品 wheel 及其 `.sha256`，`jsx-backend-wheels-0.1.0.zip` 及其 `.sha256`。进入只放置这些文件的新目录，执行：

```sh
set -e
RD_CAND_DIR="$PWD"
check_sha() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum -c "$1";
  else shasum -a 256 -c "$1"; fi
}
check_sha ai_repo_doctor-1.0.1rc2-py3-none-any.whl.sha256
check_sha jsx-backend-wheels-0.1.0.zip.sha256
test ! -e "$RD_CAND_DIR/venv-js"
test ! -e "$RD_CAND_DIR/backend-wheels"
python3 -m zipfile -e jsx-backend-wheels-0.1.0.zip "$RD_CAND_DIR/backend-wheels"
python3 -m venv "$RD_CAND_DIR/venv-js"
"$RD_CAND_DIR/venv-js/bin/python" -m pip install --no-index --only-binary=:all: \
  --find-links "$RD_CAND_DIR/backend-wheels" ai-repo-doctor-grammars==0.1.0
"$RD_CAND_DIR/venv-js/bin/python" -m pip install "${RD_CAND_DIR}/ai_repo_doctor-1.0.1rc2-py3-none-any.whl[js]"
"$RD_CAND_DIR/venv-js/bin/repo-doctor" --version
```

后端包中提供 Linux x86_64/glibc 和 Mac ARM 的兼容 wheel，由 pip 选择；本地后端安装失败就停止，不去公共索引找同名包，也不要求用户编译。Node、编译器和审计工具只属于维护构建环境。Python-only 候选安装只需验证产品 wheel 并在另一新 venv 安装它，无需解压或安装 companion。

后续调查及 Skill 绑定使用该新 venv 的绝对 CLI 路径。此过程不切换全局入口；旧 1.0.0 环境与 Skill 可继续使用。实际候选产物身份、平台门禁和发布状态以维护者随附的交付记录为准。

## 3. 绑定并加载 Codex Skill

```sh
RD_SKILL="$HOME/.agents/skills/repo-doctor-v1"
"$RD_CLI" skill export --cli "$RD_CLI" --out "$RD_SKILL"
```

目录必须不存在。导出生成 SKILL.md 和 installation.json，后者记录通过版本核对的绝对 CLI 路径；符号链接入口会绑定到真实版本文件。请保留现有 repo-doctor Skill。若 repo-doctor-v1 已存在，检查它的绑定并另选新目录，不覆盖自定义内容。

打开**新 Codex 会话**，明确指定 `$repo-doctor-v1`，并给目标仓库路径和调查问题。确认它先读取 binding、执行 `--version` 并使用同一个绝对 CLI。只看到文件导出成功还不能证明 Codex 已加载新 Skill；旧对话可能仍持有旧 Skill 内容。

旧的无 `--cli` 导出仍可生成模板，但在调查前需重新绑定；不要直接退回 PATH 中的旧 repo-doctor。导出前的显式 `--cli` 会执行该工具的 `--version`，应指向你刚安装并信任的 Repo Doctor。

## 4. 最小完整使用链

选择自己的仓库和一个新地图目录；用 symbols 返回的真实 ID 替换下面 ID，不复制占位参数直接执行：

```sh
REPO='/absolute/path/to/repository'
"$RD_CLI" overview "$REPO" --json
"$RD_CLI" symbols "$REPO" --query NAME --json
ID='ID_RETURNED_BY_SYMBOLS'
"$RD_CLI" context "$REPO" "$ID" --max-lines 120 --json
"$RD_CLI" impact "$REPO" "$ID" --depth 2 --json
NEW_MAP_DIRECTORY='/absolute/path/to/new-map'
"$RD_CLI" map "$REPO" --out "$NEW_MAP_DIRECTORY" --json
```

JS/TS 每条命令增加 `--languages javascript,typescript`；混合仓库选择 `python,javascript,typescript`。默认仅 Python。检查 analysis、截断和省略信息；空影响不证明没有影响。详细 JSON 和错误约定见 [CLI 合同](CLI_CONTRACT.md)。

浏览器打开地图目录的 map.html，供人查看结构与关系，另有 structure.svg、relations.svg。地图不是问题诊断报告；详细判断交给 Codex。Mac 可用 `open "$NEW_MAP_DIRECTORY/map.html"`；有桌面环境的 Linux 可用 xdg-open 或在浏览器选择文件。

## 5. 可选全局入口

显式 RD_CLI 已可长期使用；Skill 的安装绑定不依赖全局 PATH。若需直接输入 repo-doctor，可将 `~/.local/bin/repo-doctor` 链接到新 CLI，并确保 `~/.local/bin` 在 shell 的 PATH 中。

切换前记录原入口是不存在、符号链接还是普通文件，及链接原值；保存到本次新发行目录的 previous-entry.json。**普通文件入口先保留，由维护者处理，不用强制覆盖。** 切换用同目录临时链接与原子 rename；已有临时文件也不得覆盖。不要删除原虚拟环境。

新终端核对：

```sh
command -v repo-doctor
repo-doctor --version
```

结果应为所选版本。旧终端若缓存旧命令位置，可执行 `hash -r` 或新开终端；Skill 仍应使用绑定的绝对路径。

## 6. 升级与回滚

1. 新版本安装到新目录，核验来源/版本，跑上述核心链。
2. 保存当前入口和旧环境位置，导出到新的 Skill 目录并核对 binding；不覆盖旧用户 Skill。
3. 验证新版本后才切换入口，明确加载对应新 Skill；不要混用旧 snapshot 与改变后的源码。
4. 回滚时恢复 previous-entry.json 记录的原入口；原先没有入口时只移除本次创建的链接。验证实际旧版 `--version` 及一次核心查询。
5. 需要回滚 Codex 调用时明确加载保留的旧 Skill/旧 CLI；新的绑定 Skill不会随全局链接自动换版本。
6. 再切回新版并核验。整个演练不删除旧环境、调查数据或地图。

维护者执行正式部署时保存每次切换/回滚回执。结构查询和旧案件数据不需要为升级而批量重写；兼容与分析局限见 CLI 合同和 [JS/TS 支持范围](JS_TS_SUPPORT.md)。

## 常见问题

- **版本不对**：比较 command -v、显式 CLI、binding 三者；用正确绝对路径重新导出到新目录，不自动猜测替代版本。
- **backend unavailable**：确认选中环境安装了固定的 js extra；不要给系统 Python 安装后仍用另一虚拟环境的 CLI。
- **输出已存在**：选择新目录；既有输出作为证据保留。
- **未知/歧义/截断**：选择真实 ID、增加明确相关符号并尊重预算；由 Codex 补读源码，不把未知描述为没有问题。
- **版本下载失败**：核对选定版本的实际 Release 和 wheel 文件名。未发布的开发候选使用维护者提供的本地 wheel，不猜测正式下载地址。

## 1.0 调查边界

升级后请先查看 [资源说明](RESOURCE_LIMITS.md)。五命令 JSON 新增 resource_limits，可忽略新增字段；impact 深度为 1–10。源码预算包含同次指纹/上下文再次读取，超限返回 2，不是完整扫描的成功结果。旧案件不自动改写。

## 升级前核对

从 0.8 升级时，旧的 repo-doctor Skill 和新 repo-doctor-v1 可并存；明确加载一套，避免根据 PATH 猜版本。先核对 [兼容政策](COMPATIBILITY.md) 的变更表和 [CHANGELOG](../CHANGELOG.md)。本轮候选已通过独立消费者和真实地图使用验收，但正式下载、全局切换及回滚演练仍须等正式发行阶段；不能把候选查询成功当作已部署 1.0。问题反馈见 [SUPPORT](../SUPPORT.md)。
