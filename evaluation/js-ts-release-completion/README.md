# JSX/TSX 定向调查

`cases.json` 在产品运行前，由主代理手工核对带物理行号的真实源码冻结。
固定三个已见仓库的 commit/tree、来源 SHA、组件行段、import 原文和两个直接 helper 调用。JSX 案例只要求结构和上下文，不把组件标签作为运行调用。

运行 `python runner.py --out ABS_NEW_DIR [--cli ABS_INSTALLED_CLI] [--baseline]`。
未指定 CLI 时使用本工作树源码和已有 native 后端解释器；baseline 必须指定独立 0.7.0 CLI。
每仓库执行 overview、symbols、context(120行)、impact(depth2)、map；helper ID 另经 symbols 获取。
保存命令、预期/实际退出码、输出摘要、源码引用、逐跳导入证据和 SVG 投影检查。
baseline 中不存在的前端组件 context/impact 预期退出2；不将其算成产品通过。
不运行目标代码、不安装目标依赖、不改变历史评分；本组为定向复核，不是盲测或200仓库全量结论。
