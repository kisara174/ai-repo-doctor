# 使用支持与问题反馈

先查看 [安装指南](docs/INSTALL.md)、[支持平台](docs/SUPPORT_MATRIX.md)、[JS/TS 范围](docs/JS_TS_SUPPORT.md) 和 [资源边界](docs/RESOURCE_LIMITS.md)。1.0 尚在准备，不是已发布版本；当前公开产物为 0.8.0。

## 反馈入口

在 [GitHub Issues](https://github.com/kisara174/ai-repo-doctor/issues) 创建问题。请提供：

1. 实际 CLI 绝对路径类型/安装方式及 `--version`；使用绑定 Skill 时说明 binding 的版本，个人路径可脱敏。
2. 操作系统、架构、Python 版本，以及是否安装 `[js]`。
3. 语言选择、完整命令参数、预期结果、实际退出码和 stderr；不要只描述“失败”。
4. 能复现的最小源码片段、公开固定提交或小型示例；涉及路径关联时保留相对目录结构。
5. `analysis` 中的解析失败、未知、限制和省略计数，以及 context 的截断和 impact 深度；不要把空结果直接当作无影响。

不需要 API key、认证文件、完整私有仓库或个人数据。提交前删除这些内容；如果问题只能在私有代码上复现，先提交脱敏结构和错误现象。

## 分流处理

- **版本不一致**：核对选定 CLI、`--version`、Skill binding；保留旧入口，用正确安装重新导出到新目录。
- **backend unavailable**：在同一虚拟环境安装 js extra，不能只给其他 Python 环境装依赖。
- **超限**：按错误和资源说明缩小源码范围；不要把失败结果当成完整分析。
- **未知关系**：提供声明、使用点及最小反例；记录它是支持范围内缺陷还是范围外能力，不猜测连接。
- **地图不符合预期**：附当前模式、选择、筛选、可见/隐藏数量和 SVG；地图生成后源码变化需重新生成。

维护进度以 Issues、PR 和 [Releases](https://github.com/kisara174/ai-repo-doctor/releases) 为准。不承诺响应时间、修复期限、托管服务或付费支持 SLA。1.x 的兼容与弃用流程见 [兼容政策](docs/COMPATIBILITY.md)。
