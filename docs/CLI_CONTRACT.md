# 核心 CLI / JSON 兼容合同

1.x 的稳定调用面以 0.8.0 实际行为为基线；内部 Python 模块不作为稳定 SDK。1.0 实施候选尚不等于正式发布，正式身份以 Release 和交付报告为准。

## 公共规则

- 核心命令为 `overview`、`symbols`、`context`、`impact`、`map`；只读取目标源码，map 写入显式指定的新目录。
- 默认 `--languages python`；可选 javascript、typescript 和逗号组合，归一顺序为 Python/JavaScript/TypeScript，重复项去重。空项/未知语言拒绝。JS/TS 需要 `js` extra，不自动选择。
- 成功 `--json` 的 stdout 是一个 UTF-8 JSON 文档，一般进度信息不混入其中。调用方应忽略未知的新增字段。
- 操作/参数错误退出 **2**，stderr 说明错误，stdout 空；argparse 可能附带 usage。不提供独立错误 JSON schema。
- 退出 **0** 不表示目标代码正确或静态覆盖完整；文件级解析错误可以出现在成功结果中。
- 仓库内文件使用相对 POSIX 路径，输出目录使用绝对路径。源码行号从 **1** 开始，start/end 均包含；行文本保留缩进但不带换行符。
- 符号 ID 为 `相对文件::限定名`，如 `app.py::Service.run`，保留大小写。使用搜索返回的 ID；重复/歧义定义不返回为可用符号，context/impact 拒绝歧义 ID。
- Git revision、fingerprint、工具版本不是运行时验证结果。源码改变后重新调查，不把旧行号当成新证据。

## 参数

REPO 为目标目录，ID 为真实符号 ID。所有核心命令支持 `--json` 和 `--languages CSV`。

| 命令 | 其他参数 | 默认/约束 |
| --- | --- | --- |
| `overview REPO` | 无 | 有界摘要，不返回整个索引 |
| `symbols REPO --query TEXT` | `--limit N` | 默认 20，范围 1–100；query 非空 |
| `context REPO ID` | `--max-lines N`、可重复 `--include-symbol ID`、`--snapshot-out NEW_FILE` | 默认 120，N 为正整数；Python snapshot 额外要求 1–120 |
| `impact REPO ID` | `--depth N` | 默认 2；当前至少 1，1.0 的 1–10 上限将在资源阶段落实 |
| `map REPO --out NEW_DIR` | `--symbol ID`、`--depth N` | depth 默认 1、允许 1/2；目录不能已存在或为符号链接 |

`--include-symbol` 共用一个行预算。JS/TS snapshot 拒绝发生在建立索引/写入快照之前，应改用 `context --json`。

## overview（schema_version = 1）

| 字段 | 类型与含义 |
| --- | --- |
| `root/scan_mode/source_fingerprint` | string；实际根路径、扫描方式、源码摘要 |
| `stats` | object；整数 python_files、symbols、resolved_calls、unresolved_calls、parse_errors、ambiguous_symbols |
| `architecture` | object；整数 production_modules、local_import_edges、cross_file_call_edges；focus_modules array 最多 5 项 |
| `review_leads/leads_omitted` | array / integer；最多 5 条调查线索，各 evidence 最多 4 项；不是确认缺陷 |
| `sample_symbols/symbols_omitted` | array / integer；最多 10 项，按 ID 排序；项含 id/file/kind string、start_line integer |
| `parse_errors/parse_errors_omitted` | array / integer；最多 5 项，项含 file/message string、line integer 或 null |
| `next_commands` | object；symbols/context/impact 为 argv string 数组，QUERY/SYMBOL 是需替换的参数；首项 repo-doctor 应替换成已核验 CLI |
| `limitations/analysis` | string array / object；覆盖边界和语言元数据 |

focus_modules 项含 file string、dependent_file_count/importer_count/caller_file_count/evidence_omitted integer、evidence array（最多 10）。依赖数量不是运行流量。`python_files` 不是总文件数，JS/TS 数量从 analysis.files_by_language 读取。

review_leads 项含 kind/subject/reason/next_step string、review_order/evidence_omitted integer、evidence array；可选 issue_id string 或 caller_count integer，取决于线索类型。subject 最多 300 字符。线索排名不是缺陷严重度承诺。

## symbols（schema_version = 1）

必有 query string、candidates boolean、matches array、analysis object。matches 项含 id/file/name/qualname/kind string、start_line integer；不承诺 end_line 字段存在。

按不区分大小写的 ID/名称/限定名匹配，精确优先、再前缀、再包含；同等级按 ID 排序。没有直接匹配时可返回相似候选并设置 candidates=true，需明确选择；无匹配/候选时可返回空数组并退出 0。

## context（schema_version = 2）

| 字段 | 类型与含义 |
| --- | --- |
| `symbol/max_lines` | string / integer；目标 ID 和总行预算 |
| `blocks` | array；目标优先；项含 symbol/relation/file string、start_line/end_line integer、truncated boolean、lines array |
| `blocks[].lines[]` | `{line: integer, text: string}`；所有块的行数之和不超过 max_lines |
| `call_evidence` | array；与目标直接相邻的已解析调用证据 |
| `semantic_evidence` | array；注册/导出等语义证据，不自动等价于调用 |
| `budget_exhausted` | boolean；块截断或候选符号/导入未全部纳入 |
| `omitted_symbols/omitted_imports` | integer；未纳入源码块的数量 |
| `analysis` | 可选 object；纯 Python 当前省略，语言选择非纯 Python 时提供 |

relation 为可扩展关系说明，如 target/user_selected/caller/callee/import_binding。证据 metadata 的行可能在源码块预算之外；引用原文应继续读取对应源码，不能编造引文。

## impact（schema_version = 2）

必有 symbol string、depth integer、affected_symbols array、module_importers string array、import_evidence array、semantic_relations array。

- affected_symbols 项含 symbol string、distance integer、path string array、call_path_evidence array。沿**反向已解析调用**广度遍历，path 从目标到调用者，各跳证据对应实际 caller/callee；按 distance/symbol 排序，一个调用者返回一次。
- module_importers/import_evidence 是目标文件的直接导入关系，不是函数 depth 范围的完整调用者。导入证据含 source/target string、line integer，JS/TS 可带 esm_source_association object。
- analysis 条件同 context。JS/TS 目标另有 status string（bounded/not-supported）、scope string。
- 隐式/动态调用、运行时替换、仓库外调用及深度之外的关系不构成已验证清单；空结果不能解释为没有影响。

## 共用证据类型

调用证据含 caller/callee/file string、line integer、via_reexports array；后者的项含 file/name string、line integer。JS/TS 导入调用可带 via_esm_import object（实际 import 文件/行段/specifier/绑定/源码关联）；不证明 Node/bundler 运行时解析等价。

via_esm_import 含 file/specifier string、start_line/end_line integer、type_only boolean；imported/alias/resolved_file/resolution_kind 为 string 或 null。esm_source_association 含 file/specifier/target/resolution_kind string、start_line/end_line integer。

语义证据含 kind/target_symbol/evidence_file string、line integer，source_symbol/source_file/exported_name 为 string 或 null；context/impact 中还有 direction string。注册边与调用边分别解释。

## analysis（schema_version = 1）

必有 requested_languages string array、files_by_language object（python/javascript/typescript integer）、capabilities object（所选语言到 string array）、limits array、limits_omitted integer、scope string。

limits 最多 50 项，按文件/行/原因/信息排序；项含 file/reason/message string、line integer 或 null，解析拒绝也进入该列表；省略计数保留。capabilities 不表示完整覆盖。

选择 JS/TS 时另有 esm_source_resolution object（policy string、runtime_resolution=false）和 source_extensions object（所选 JS/TS 语言到后缀数组）。恢复语法树不能泄漏部分可信符号/调用。

## map（命令 schema_version = 1）

命令返回 directory/map_json/html/structure_svg/relations_svg string（绝对路径）、coverage object、analysis object。四个文件为 map.json、map.html、structure.svg、relations.svg；已有目录不会覆盖。

map.json 的 schema_version=1，含 repository、coverage、nodes、edges、file_edges、views、limits、layout、colors、analysis。nodes 按 ID 排序、edges 按 kind/source/target 排序。节点 ID 为 dir:路径、file:路径、symbol:符号ID；根目录为 dir:.。

- 节点必有 id/kind/label/file string、parent string 或 null、is_test boolean。文件节点有 analyzed/python boolean、language string 或 null；符号节点有 symbol ID 及 start/end 行号。
- 边含 id/kind/source/target string、evidence array（file/line）。file_edges 为跨文件投影，不包含同文件函数边。
- limits 为 `{nodes: 200, edges: 500}`，限制每个可见投影，不是整个索引规模。
- views 的 structure/relations 含 mode、nodes、edges、hidden_nodes/hidden_edges、width/height；节点坐标等是呈现细节，不承诺像素永久不变。初始结构视图不是所有嵌套节点已经展开。
- HTML 内嵌资源，使用时无需服务/API；当前视图 SVG 导出与当前节点/边投影一致。页面只展示结构关系。

## 1.x 更新与迁移

现有字段类型、ID 和证据含义保持，新增字段/关系说明可忽略。删除字段、改变类型或将未知改为确定证据须评估兼容并按主版本管理。不为统一数字重编号各命令 schema_version。

1.0 资源边界/Skill 绑定将在对应阶段补入合同。旧 Python 案件不批量重写。其他历史命令可能退出 1（如 findings 部分拒绝或回归失败），不能将核心五命令的退出政策推广到所有接口。
