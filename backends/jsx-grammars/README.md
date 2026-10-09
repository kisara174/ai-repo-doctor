# AI Repo Doctor 原生 JSX grammar companion

包版本 0.1.0，提供 JavaScript 和 TSX capsule；普通 TypeScript 继续使用官方 grammar。
修复仅发生在 grammar：原始目标字节不改写，错误恢复树不获准返回证据。

来源和每个受控文件 SHA 在 provenance.json；上游 MIT 版权见 licenses/，本项目新增代码沿用根 LICENSE。
不能把本包伪装成上游 tree-sitter-javascript 的原始版本。

## 用户安装

从所选 GitHub Release 下载并校验后端 wheel 包。在新 venv 中先离线安装 companion，再安装主产品 extra：

```sh
python -m pip install --no-index --only-binary=:all: --find-links /absolute/backend-wheels ai-repo-doctor-grammars==0.1.0
python -m pip install '/absolute/ai_repo_doctor-VERSION-py3-none-any.whl[js]'
```

实际发布版本及完整步骤见主产品 docs/INSTALL.md。未发布候选不得猜测下载 URL。
首轮支持 Linux x86_64/glibc 和 Mac ARM，具体 Python/系统承诺以对应提交的 CI 证据为准。
主产品 Python-only 安装不需要本包。用户无需 Node、C 编译器或 API key。

## 维护者重生成

固定 Node 26.11.0、tree-sitter-cli 0.25.10。仅在审查本地固定依赖后运行 tools 中的 npm ci，安装脚本只允许固定的 tree-sitter-cli 下载其官方二进制。

```sh
npm ci --prefix backends/jsx-grammars/tools
python tools/check_grammar_provenance.py --root backends/jsx-grammars
python backends/jsx-grammars/tools/regenerate.py --check
```

可用 `--cli /absolute/tree-sitter` 指定同版本现有工具。修改 grammar 并审查补丁后，显式 `--write` 更新生成文件和校验值，再执行 `--check` 和完整上游 corpus。
生成器只在临时目录构造 TSX 的 JS 0.23.1 基底链接。不能把 JS 0.25.0 当成 TSX 的基底，不手改生成 C。

companion wheel 使用 CPython 3.11 Limited API。语言 ABI（JS 15/TSX 14）与 Python abi3 不同，均需验证。
编译失败直接失败；没有 extension 的纯 Python companion 不是有效产物。
