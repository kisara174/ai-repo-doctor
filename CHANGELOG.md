# 变化记录

## 1.0.1rc2 — 2026-10-09（原生后端修复候选）

- 修复 JSX/TSX 带引号属性中的裸 `&` 及 URL 参数解析；原始源码字节和引用保持不变。
- JS extra 使用本项目固定的独立 grammar wheel，Python-only wheel 和普通 TS grammar 保持原安装边界。
- ERROR/MISSING 仍整文件排除；Flow 和 JSX 正文裸 `&` 不在新增范围。
- 候选须配合相同发行件的后端 wheel 包安装，未发布候选不使用猜测的公开下载地址。
- 继承 rc1 物理行修复；历史 500 组结果不重标为本候选全量验证。

## 1.0.1rc1 — 2026-10-08（修复候选）

- 修复换页符及其他非换行控制字符导致 context 源码文字与分析器行号错位的问题。
- 统一 Python/JS/TS 源文件计数、源码引用及 Python findings/快照取证的行切分规则，保持各分析器的坐标语义。
- 正确引用可以导入，错位引用会拒绝；Python 编码声明、BOM、CRLF/CR、行预算保持兼容。
- 本候选不扩展 JSX URL 或 Flow 语法支持；1.0.0 的 500 组评估仍属于原版本。

## 1.0.0 — 2026-10-08

正式发行身份和公开下载核验见 [1.0 交付记录](docs/delivery/2026-10-08-v1.0.0-product-closure.md)。

- 采用 MIT 许可，wheel 包含许可声明及标准 SPDX 元数据。
- 固定 overview、symbols、context、impact、map 五命令的公共参数、JSON 和退出码合同，保留已有字段；新增 resource_limits 元数据。
- Skill 可通过 `--cli` 绑定绝对安装路径和实际版本，导出名为 repo-doctor-v1；旧 Skill 保留，禁止静默调用旧 PATH 入口。
- 增加单文件 2 MiB、同次累计源码读取 64 MiB、5000 文件、Git 15 秒、协作式分析 60 秒边界；impact 深度限定 1–10。
- 补齐独立环境安装、升级回滚指导以及 macOS arm64/Linux x86_64、Python 3.11–3.14 的实际 CI 组合；未验证系统不作支持承诺。
- 追加三份新固定源码调查和原生 Chrome 地图交互证据；JS 嵌套 helper 可定位，但不能保证解析调用边。
- 正式发布、公开下载后安装、本机入口切换和回滚演练仍待后续发行阶段。许可已明确为 MIT（版权署名 kisara174），1.0 仍待发行验收。

升级限制和旧入口处理见 [兼容政策](docs/COMPATIBILITY.md)、[安装指南](docs/INSTALL.md)。

## 0.8.0 — 已发布

- JS/TS 增加 `.jsx/.tsx` 实现分析，TS/TSX 使用对应 grammar。
- ERROR/MISSING 错误文件整文件隔离，拒绝恢复树中的部分证据。
- 保留安全直接 ESM 调用、有限无后缀/index 源码关联和物理来源证据。

实际发行身份、安装验证与范围见 [0.8.0 交付记录](docs/delivery/2026-10-08-v0.8.0-js-ts-completion.md) 和 [GitHub Release](https://github.com/kisara174/ai-repo-doctor/releases/tag/v0.8.0)。历史 200 仓库证据保持原版本归属，不转标为 1.0 新全量回归。
