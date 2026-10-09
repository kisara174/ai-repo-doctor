# JSX 属性裸 & 定向验收

cases.json 固定 R051 的 commit/tree、原源 SHA、人工声明/URL行以及独立 1.0.1rc1 的42个旧符号。候选应恢复 DownloadModal、Editor 和其嵌套 getTemplate；不把组件标签视为调用。

使用 tools/validate_jsx_grammar_install.py 对独立安装CLI执行五步调查，核对原始引用与SVG投影。目标代码不运行，依赖不安装；结果是定向验收，不重标历史500组成绩。
