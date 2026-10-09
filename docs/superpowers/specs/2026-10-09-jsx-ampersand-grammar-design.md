# CF-002：JSX 属性裸 & 的原生语法修复设计

日期：2026-10-09。状态：设计及隔离原型；尚未接入产品、发布或切换安装。

用户已明确接受自行维护原生语法库。本设计替代此前“仅增加限制提示”的临时方向。

## 1. 目标与已验证事实

目标：直接解析 JSX 属性中包含裸 `&` 的原始源码，恢复符号、上下文和地图；保留所有 ERROR/MISSING 整文件隔离规则。

- 固定目标：`octokatherine/readme.so`，本地 benchmark500 manifest 的 R051。
- `components/DownloadModal.js` SHA256：`b6380f2e4d103d36e5ea03dc6ea3d3104afd07fbf96a93334be374a7a438f08f`。
- 原 JavaScript grammar 0.25.0 和 TSX grammar 0.23.2 均拒绝 `src="?a=1&b=2"`。
- 已检查的上游发布版及 master 尚未修复该属性规则；本结论对应本轮调查，不保证未来发布不变。
- JavaScript 固定源提交：`44c892e0be055ac465d5eeddae6d3e194424e7de`，tag v0.25.0。
- TypeScript 固定源提交：`f975a621f4e7f532fe322e13c4f79495e0a7b2e7`，tag v0.23.2。
- TSX 继承 JavaScript 0.23.1；其固定源提交为 `3a837b6f3658ca3618f2022f8707e29739c91364`。不能用 JS 0.25.0 整体替换 TSX 基底。

根因：属性 fragment 规则拒绝 `&` 后接字母或 `#` 且不能形成完整实体的文本；原规则还可能把 `&` 后的闭合引号吞进 fragment。JSX 字符串允许裸 &，不能据此判定目标项目语法无效。

## 2. 方案取舍

| 方案 | 结论 | 理由 |
| --- | --- | --- |
| 独立原生 companion wheel，修补 grammar 后重新生成 parser | 采用 | 直接消费原始字节，基础 CLI 继续为纯 Python wheel，可沿用 GitHub 分发 |
| 在主 CLI wheel 内嵌原生 extension | 不采用 | Python-only 安装也被平台和编译绑定，扩大本次改动范围 |
| 修改待分析源码或接受错误恢复树 | 不采用 | 不能满足原始证据和坏文件零证据要求 |

仅修复**带引号 JSX 属性**。JSX 正文裸 & 的 scanner 问题、Flow、动态调用解析和新增命令不在本次范围。

## 3. 最小 grammar 补丁

对 JS 0.25.0 与 TSX 使用的 JS 0.23.1 基底应用同一补丁：

```javascript
// 在 _jsx_string 的单、双引号 repeat(choice(...)) 各增加一项：
alias(token.immediate('&'), $.string_fragment),

// 保留原来可解析 fragment 的组合方式，但不得吞掉对应闭合引号：
unescaped_double_jsx_string_fragment: _ =>
  token.immediate(prec(1, /([^"&]|&[^#"A-Za-z])+/)),
unescaped_single_jsx_string_fragment: _ =>
  token.immediate(prec(1, /([^'&]|&[^#'A-Za-z])+/)),
```

完整 `&amp;`、`&#38;`、`&#x26;` 继续由现有 `html_character_reference` 规则匹配；裸 & 使用 string_fragment。保留原来可解析输入的 CST，不借本次修改实体的有效性政策。

维护工具链固定 tree-sitter-cli 0.25.10；本地原型使用 Node 26.11.0。JS 生成语言 ABI 15；TSX 显式 `generate --abi 14`，不升级原语言 ABI。语言 ABI 与 Python 的 abi3 是两个独立概念。

生成的 C、scanner、headers 随源码固定提交。安装和运行时不下载 grammar、不执行 Node、不重新生成 parser。维护者可在临时目录重生成并逐字节核对；不得手改生成 C 代替 grammar 补丁。

## 4. 包结构与后端选择

新增独立发行包 `ai-repo-doctor-grammars`，首个产品后端版本拟为 `0.1.0`，Python import 为 `ai_repo_doctor_grammars`。包名是本项目本地 wheel 的身份，不声称已注册或发布到 PyPI。

只包含两个 grammar：补丁后的 JavaScript 与 TSX。普通 `.ts` 继续使用官方 tree-sitter-typescript 0.23.2，不复制或改变它的生成 parser。

公共后端接口：

```python
language_javascript()  # PyCapsule，名称 tree_sitter.Language
language_tsx()         # PyCapsule，名称 tree_sitter.Language
```

主项目 extra 的目标依赖合同：

```toml
js = ["tree-sitter==0.26.0", "ai-repo-doctor-grammars==0.1.0", "tree-sitter-typescript==0.23.2"]
```

`_parser` 检查三者精确版本；JS 与 TSX 使用 companion，TS 使用官方 grammar。不回退到旧 JS parser、不把 JS 交给 TSX parser。缺包/版本不符时明确拒绝并指向该版本的安装说明。

仅 JS/TS 分支加载后端。`import repo_doctor`、Python-only 命令和安装不加载或要求 native companion。五命令、JSON schema、符号 ID、行预算、ERROR/MISSING 隔离保持现有合同。

## 5. 可安装的分发方案

现有正式产品通过 GitHub Release wheel 分发；本次不引入 PyPI 凭据要求。

- 主产品仍提供 `py3-none-any.whl`。
- companion 采用 CPython Limited API，`Py_LIMITED_API=0x030B0000` 与 `cp311-abi3` tag 一致。
- 首轮仅承诺现有已验收范围：Linux x86_64 / glibc、Mac ARM；Windows、Intel Mac、Linux ARM、musl、free-threaded Python 暂不承诺。
- Linux wheel 在 manylinux 构建环境生成并 auditwheel repair；Mac 设置 `MACOSX_DEPLOYMENT_TARGET=11.0`。必须验证真实依赖和最低部署目标，不能只改文件名。
- 两个 companion wheel 汇成 `jsx-backend-wheels-0.1.0.zip`；manifest 包含版本、源码提交、工具链、每个 wheel tag/SHA、上游与补丁身份。
- Release 提供产品 wheel、后端 zip、各自单文件 `.sha256` 和完整 SHA256SUMS。Python-only 用户只需验证产品 wheel 的单文件校验，不能因未下载后端而校验失败。

安装 JS extra 的顺序：在新发行目录验证、解压后端包，先从**仅本地**目录安装 companion，再安装产品 extra：

```sh
python -m pip install --no-index --only-binary=:all: --find-links "$RD_BACKENDS" \
  'ai-repo-doctor-grammars==0.1.0'
python -m pip install "${RD_WHEEL}[js]"
```

`RD_BACKENDS` 是已核验解压目录，`RD_WHEEL` 是已核验产品 wheel。第一步不得使用公共索引或源码构建兜底；不兼容平台应明确失败，不下载同名未知包。第二步仅从公共索引安装原有官方依赖，companion 由已安装的精确版本满足。开发 CI 同样先安装本轮 companion wheel。

本地原型 wheel 的 tag 为 macosx_27_0_arm64，**不能作为 Mac 15 或正式产物**。只有完成上述构建与平台门禁后才能替换它。

## 6. 必须通过的出口

1. 修补后的两个 grammar：完整上游 corpus、产品新反例和已有 native 合同通过。
2. 合法属性：单双引号、URL、多参数、实体、尾部 &、多行、中文/emoji、CRLF；原始字节与 span 一致。
3. 真正的未闭合引号、缺括号或函数体仍 ERROR/MISSING；整文件不能泄漏符号、导入或调用边。不能用“包含 &”来放行。
4. R051 原始固定源完成独立安装 CLI 的 overview→symbols→context→impact→map；两个原错误消失，旧符号不变，引用逐行匹配，SVG/JSON 投影一致。不能把组件标签猜成调用。
5. base/JS 两套新 venv 通过既有生命周期及安装验证；native 模块实际来自 site-packages，加载的不是源码或原型 dylib。
6. Linux Python 3.11/3.12/3.13/3.14，Mac ARM Python 3.11/3.14，从同一候选发布件安装通过；abi3audit 严格通过。仅一台 Mac 3.14 不够。
7. 同一环境保留旧版本可回滚；只有候选、平台与安装出口全部通过，才可准备 1.0.1 稳定发布。旧 500 组结果不重标。

## 7. 原型结果及边界

证据目录：`/Users/kisara/.local/share/ai-repo-doctor/evaluations/v1-0-1-jsx-url-v1`。

- 上游 JS corpus 116/116；TS/TSX 项目 corpus 112/112，均为本轮修改后的本地生成器运行结果。
- 52 个合法属性组合通过，32 个是旧 parser 拒绝而原型成功；此前可解析组合的 CST 一致。
- 6 个真正语法错误组合继续整文件排除。
- 原始 R051：错误 2→0，符号 42→45；原有符号对象一致；DownloadModal 上下文 85 行逐行匹配、0 错位。
- 原型中通过进程内替换 grammar capsule 完成产品索引检查；不是独立安装的产品 CLI 验收。
- 已本地编译 companion 试验 wheel；它使用 `0.0.0.dev0`，不是计划中的 0.1.0 产品包。最终 ABI 和安装结果见同目录后续可行性报告。

## 8. 维护责任、回滚与停止条件

主代理负责依赖、原生构建、兼容、调试、审查和发布判断，不把这些交给 Luna。只在后续存在小范围、机械、独立可验证的任务时按 AGENTS 路由。

保留上游 MIT LICENSE 和版权，不将上游代码全部改署名为 kisara174；项目自身新增代码沿用 MIT/kisara174。provenance 列完整 commit、输入/生成文件 SHA、patch 和工具链。不要把 upstream 原包版本伪装成本项目自维护包。

上游若发布可用修复，先做差异与定向门禁，再决定移除 companion；不自动追随 master。ABI 审计、旧 CST、错误隔离、原源引用、平台或安装任一失败即阻止发布，先定位；不扩到 Flow 或换后端绕过门禁。

保留原 1.0.0 环境、Skill 绑定和当前 1.0.1rc1 产物；修复先形成新的 1.0.1rc2 候选，最终发行版本由已通过的精确提交确定。禁止原地替换旧 wheel 或证据。

## 官方依据

- [JSX 字符串定义](https://react.github.io/jsx/#sec-jsx-string-characters)
- [JS 0.25.0 grammar](https://github.com/tree-sitter/tree-sitter-javascript/blob/v0.25.0/grammar.js)
- [TSX 0.23.2 继承规则](https://github.com/tree-sitter/tree-sitter-typescript/blob/v0.23.2/common/define-grammar.js)
- [上游正文 & 问题 #366](https://github.com/tree-sitter/tree-sitter-javascript/issues/366)：与本次属性问题相关，但 scanner 修复不能直接当成本次属性修复。
- [Python Stable ABI](https://docs.python.org/3/c-api/stable.html)
- [cibuildwheel 的 abi3 与审计](https://cibuildwheel.pypa.io/en/stable/faq/#building-cpython-abi3-wheels-limited-api)
- [pip 本地 find-links](https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-f)
