# 1.0.1rc2 JSX 原生 grammar 修复候选交付

日期：2026-10-09。状态：修复候选已实现并完成平台构建和安装验收；草稿 PR46，未合并、未发布、未切换全局安装。正式版本仍为 1.0.0。

## 目标与实际修复

CF-002：合法 JSX 带引号属性 URL 中的裸 `&` 被上游语法拒绝，导致整文件被排除。本次在固定的 JavaScript 与 TSX 基底 grammar 各改四处规则，并重生成原生 parser；原始源码字节不变。保留 ERROR/MISSING 整文件排除，不接受恢复树，不使用 JS→TSX 回退。

主产品仍是纯 Python wheel，版本 1.0.1rc2。可选 companion `ai-repo-doctor-grammars` 0.1.0 提供 JavaScript/TSX capsule；普通 TypeScript 使用官方 0.23.2。Python-only 不需要 companion。维护源、补丁、许可证和 25 个冻结文件校验值随仓库提交；重生成及篡改拒绝验证通过。

本轮继承 CF-001 的物理行修复，未把它计为本次新增。设计及清单见 [规格](../superpowers/specs/2026-10-09-jsx-ampersand-grammar-design.md)、[执行清单](../superpowers/plans/2026-10-09-jsx-ampersand-grammar.md)。

## 候选身份与四个安装输入

产品 wheel 和两平台后端均来自精确提交 `a41a5c1e4208a7ba2d644b52019a9f7b3bedc765`。之后的 CI/文档提交须单独记录，不改写这些已生成产物的归属。

| 文件 | SHA256 |
| --- | --- |
| ai_repo_doctor-1.0.1rc2-py3-none-any.whl | `a813efadf72ad54da383021f3d1f3be6dac7d9a5522fd0e97f36617e84ab572a` |
| jsx-backend-wheels-0.1.0.zip | `899ce90ea091959abbcb565a0013c640701df0be2cbe2dc0258a7d0351be736e` |

另提供上述两文件各自的 `.sha256`。后端包包括 Linux x86_64 manylinux 和 macosx_11_0_arm64 两个 cp311-abi3 wheel、同提交构建回执和 manifest。严格 ABI 审计通过；Mac 二进制 deployment target 已核对，Linux 镜像 digest 保存在构建日志。Mac 11.0 tag 不等于已在 Mac 11 实测；实际 runner 为 Mac 15。

本机证据及候选目录：

```text
/Users/kisara/.local/share/ai-repo-doctor/evaluations/v1-0-1-jsx-grammar-delivery-v1
  products.json
  runtime-equivalence.json
  preservation.json
  review.json
  ci-corrected-push.json
  ci-corrected-pr.json
  real-r051-ci-native/summary.json
  candidate-1.0.1rc2/
```

使用 [安装指导](../INSTALL.md) 的 rc2 小节。在新目录放置四文件后校验，先仅本地安装 companion，再安装主产品 extra。companion 不假设存在于 PyPI，用户无需 Node、编译器或 API key。此目录已有验收环境 `venv-js`，再次安装需选择新目录。

## 验收事实

| 门禁 | 实际结果 |
| --- | --- |
| 产品完整回归，已安装 native extra | 563 项通过，无 skip |
| 冻结生成/来源 | 25 文件 SHA 核对、12 生成文件逐字节重生成通过；篡改副本拒绝 |
| 上游原有 corpus | JavaScript 116/116，TypeScript/TSX 112/112；未改期望 |
| companion 安装 | 3 个原生测试方法，52 个合法组合及坏语法反例；wheel、sdist 重建和严格 abi3 审计通过 |
| 五套独立安装验证器 | 33 + 10 + 31 + 11 + 16 = 101 条命令，实际/预期退出码匹配 |
| 原仓库本地 native 安装 | 7 条命令通过 |
| 原仓库 CI native 分发包安装 | 7 条命令通过；文档安装脚本在本机新目录原样执行成功 |
| bundle | CI 产物本地重建逐字节一致；缺平台、重复平台、错源码、被篡改 wheel、额外版本 5 类输入全部拒绝 |
| 不支持平台 | pip 仅本地匹配 Windows wheel 时明确拒绝，没有下载回退或创建目标安装目录 |
| 产品运行身份 | 35 个源码/wheel/新旧候选安装 runtime 文件一致；3 个 native 安装文件与 CI wheel 一致 |

精确提交 a41a5c1 的 [push CI](https://github.com/kisara174/ai-repo-doctor/actions/runs/37882089192) 与 [PR CI](https://github.com/kisara174/ai-repo-doctor/actions/runs/37882094005) 各 15 个任务全部成功：Linux Python 3.11–3.14 base/js，Mac Python 3.11/3.14 base/js，原生生成/两平台构建/bundle，地图 DOM/SVG。安装 runner 的实际身份和回执已单独下载：10 份 machine.json，20 份安装 summary 共326条命令，另4份生命周期 receipt共132条命令；实际退出码均与预期匹配。Linux为x86_64/glibc2.39，Mac为15.7.9/arm64。后续提交 `aa20a7ea6e89fdb30de209b4d0f253f6c5517b1f` 将安装指导原样执行加入 Linux 独立安装门禁，[push](https://github.com/kisara174/ai-repo-doctor/actions/runs/37882501390) / [PR](https://github.com/kisara174/ai-repo-doctor/actions/runs/37882505827) 也各15任务全部通过。

首次 eb16009 CI 的原生编译、repair 和 ABI 审计通过，但测试目录错误指向主项目，因缺主产品导入失败。a41a5c1 修正 `{project}/tests` 为 `{package}/tests` 后两轮 CI 通过。首次失败日志保留，未修改测试期望或忽略失败。

## 真实仓库闭环

对象：`octokatherine/readme.so`，固定提交 `90420ff0f33d1ef0e9cf4fd67515662ab626acee`，tree `e5e04167acbea9c06287cf7d054804063315d5ad`，属于原 benchmark500 的 R051。

- overview：解析错误 2→0；符号 42→45。
- symbols：旧 42 个符号对象完全不变；恢复 DownloadModal、Editor 和 Editor.getTemplate。
- context：DownloadModal 原始 URL 包含字面 `&`；85 行源码引文逐行匹配，无错位。
- impact：空结果仍不代表没有运行时影响，不作完整调用图承诺。
- map：恢复符号进入地图，两份 SVG 与 JSON 关系投影匹配。
- 目标 129 个 tracked 文件、Git 状态不变；未执行目标源码、未安装目标依赖、未调用在线模型。

固定预期见 `evaluation/jsx-ampersand/cases.json`；验证器只运行传入的独立安装 CLI。第一次安装验证工具误解析 venv Python symlink 导致使用全局解释器，已修复并保留失败回执；成功结果来自后续独立安装，不使用该失败作为产品通过证据。

## 保护与范围

54 个受保护文件、35 个前一候选顶层证据文件、3264 个历史 benchmark500 证据文件均经 SHA 核验不变；主目录既有 15 个未提交改动保留。原 1.0.1rc1、1.0.0 安装和 Skill 均保留。本轮没有再次运行完整500组，不把单目标复查改写成新候选全量成绩。

范围限制继续明确：Flow、JSX 正文裸 `&`、动态回调/方法的完整调用解析不在本次新增支持内；JS/TS 仍是只读五命令分析，快照/案件和自动修复不支持。Windows、Intel Mac、Linux ARM/musl、free-threaded Python 不属于本轮平台承诺。

## 下一步正式发行

[草稿 PR46](https://github.com/kisara174/ai-repo-doctor/pull/46) 以 `codex/source-physical-lines` 为 base，依赖未合并的 [PR45](https://github.com/kisara174/ai-repo-doctor/pull/45)。候选可通过绝对路径使用，全局入口仍为 1.0.0。

1. 先合并 CF-001，再将 PR46 调整到稳定分支，核对最终 tree 和实际 CI。
2. 将版本改为正式 1.0.1 后重新构建；禁止将 rc2 wheel 改名冒充正式包。
3. 对正式源码重新完成必要平台/安装门禁，上传主 wheel、后端包和校验件；公开下载后再验安装与五步调查。
4. 只有正式分发闭环后才切换安装/导出新绑定 Skill；保留旧目录和入口回滚回执。

尚未完成正式发行与全局升级；这些步骤仍在执行清单 T6 保留待办。
