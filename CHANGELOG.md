# 变化记录

## 1.0.0 — 未发布

当前开发版本为 1.0.0.dev1。以下是实施分支的变化，不代表正式下载已可用。

- 固定 overview、symbols、context、impact、map 五命令的公共参数、JSON 和退出码合同，保留已有字段；新增 resource_limits 元数据。
- Skill 可通过 `--cli` 绑定绝对安装路径和实际版本，导出名为 repo-doctor-v1；旧 Skill 保留，禁止静默调用旧 PATH 入口。
- 增加单文件 2 MiB、同次累计源码读取 64 MiB、5000 文件、Git 15 秒、协作式分析 60 秒边界；impact 深度限定 1–10。
- 补齐独立环境安装、升级回滚指导以及 macOS arm64/Linux x86_64、Python 3.11–3.14 的实际 CI 组合；未验证系统不作支持承诺。
- 追加三份新固定源码调查和原生 Chrome 地图交互证据；JS 嵌套 helper 可定位，但不能保证解析调用边。
- 正式发布、公开下载后安装、本机入口切换和回滚演练仍待后续发行阶段。许可未确定，1.0 尚不能发行。

升级限制和旧入口处理见 [兼容政策](docs/COMPATIBILITY.md)、[安装指南](docs/INSTALL.md)。

## 0.8.0 — 已发布

- JS/TS 增加 `.jsx/.tsx` 实现分析，TS/TSX 使用对应 grammar。
- ERROR/MISSING 错误文件整文件隔离，拒绝恢复树中的部分证据。
- 保留安全直接 ESM 调用、有限无后缀/index 源码关联和物理来源证据。

实际发行身份、安装验证与范围见 [0.8.0 交付记录](docs/delivery/2026-10-08-v0.8.0-js-ts-completion.md) 和 [GitHub Release](https://github.com/kisara174/ai-repo-doctor/releases/tag/v0.8.0)。历史 200 仓库证据保持原版本归属，不转标为 1.0 新全量回归。
