# 安装、Codex 接入、升级与回滚

适用范围：macOS/Linux，Python 3.11+。1.0 尚在实施；正式平台组合由后续支持矩阵和发行报告确认，Windows 暂不承诺。

**以下 1.0.0 公共下载步骤仅在正式 Release 发布后可用。** 开发候选应使用维护者提供的本地 wheel，并将 RD_VERSION 设为实际版本（当前为 1.0.0.dev1）；不能把开发候选称为正式 1.0。

## 1. 选择来源与安装目录

确认 `python3 --version` 至少为 3.11；若系统默认较旧，使用已经安装的合适解释器绝对路径替换 python3。安装不修改系统 Python。

正式版本发布后，在新终端下载 wheel 和校验文件到**新目录**：

```sh
set -e
RD_VERSION=1.0.0
RD_ROOT="$HOME/.local/share/ai-repo-doctor/releases/v$RD_VERSION"
mkdir -p "$(dirname "$RD_ROOT")"
mkdir "$RD_ROOT"
RD_WHEEL="$RD_ROOT/ai_repo_doctor-$RD_VERSION-py3-none-any.whl"
RD_URL="https://github.com/kisara174/ai-repo-doctor/releases/download/v$RD_VERSION"
curl --fail --location "$RD_URL/ai_repo_doctor-$RD_VERSION-py3-none-any.whl" --output "$RD_WHEEL"
curl --fail --location "$RD_URL/SHA256SUMS" --output "$RD_ROOT/SHA256SUMS"
(cd "$RD_ROOT" && shasum -a 256 -c SHA256SUMS)
```

校验失败立即停止，不能继续安装。已有同名目录则保留并调查其版本，不清空重试。Linux 若无 shasum，可使用 `sha256sum -c SHA256SUMS`。

开发候选将 RD_WHEEL 设为本地 wheel 的绝对路径，另选一个新 RD_ROOT，核对随附 SHA256 和源码提交后进入下一步；不要访问尚未发布的下载 URL。

## 2. 安装到独立环境

推荐完整环境（Python 与可选 JS/TS）：

```sh
python3 -m venv "$RD_ROOT/venv"
"$RD_ROOT/venv/bin/python" -m pip install "$RD_WHEEL[js]"
RD_CLI="$RD_ROOT/venv/bin/repo-doctor"
"$RD_CLI" --version
```

仅使用 Python 时，在一个单独的新环境将 pip 参数改为 `"$RD_WHEEL"`，不加 `[js]`。缺 extra 时显式选择 JS/TS 会报错并提示安装方式，不会默默只分析 Python。

安装依赖可能需要联网；安装后的五个只读调查命令无需 API key、服务或网络，也不运行目标项目代码。分析 JS/TS 不需要 Node；开发产品的 DOM 验证环境另有 Node 依赖。

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
- **尚未发布的版本下载失败**：当前开发版使用本地候选 wheel；正式下载步骤等实际 Release 就绪后执行。
