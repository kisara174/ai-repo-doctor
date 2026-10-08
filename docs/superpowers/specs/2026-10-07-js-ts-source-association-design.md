# JS/TS 保守源码关联设计

日期：2026-10-07。状态：用户已确认并实施；正式版交付状态见执行清单。

## 1. 目标与成功定义

让 Codex 在调查采用无后缀或目录 index 导入的 JS/TS 源码时，取得唯一实现文件的依赖关系及有来源的安全直接调用，减少手工补读。人类仍使用现有 HTML/SVG 结构关系图。

完成条件：合成合同的正负例通过；七条旧覆盖缺口得到文件关联；dembrane 的 pyRound 调查取得正确调用与导入来源；四条真实歧义不连接；Python 与现有明确扩展路径保持兼容；冻结候选的独立安装与精确提交 CI 通过。调查提升和未知范围都写入交付报告。

潜在收益依据见 [研究报告](../../evaluations/2026-10-07-extensionless-source-survey.md)：9,706 条潜在声明、39/80 个已看过的仓库。这不是产品通过率、调用准确率或运行时保证。

## 2. 方案比较与选择

| 方案 | 收益 | 成本与限制 | 选择 |
|---|---|---|---|
| 唯一候选源码关联 | 可沿现有文件边及安全直接调用继续调查 | 必须标注来源、保留歧义拒绝 | 推荐 |
| 只输出候选提示 | 不改变调用图 | Codex 仍逐个补读，另增候选展示接口 | 本轮不采用 |
| 完整 Node/TS/bundler 解析 | 可按具体配置模拟更多解析 | 需要解析配置与优先级，范围显著扩大 | 后续另立目标 |

## 3. 全局约束

- Python 3.11+；现有依赖固定版本不变，不新增依赖。
- 默认语言仍为 Python；JS/TS 需要 `[js]` 与显式 `--languages`。
- 实现扩展仍只有 `.js`、`.mjs`、`.ts`；声明文件、JSX/TSX、CommonJS、alias、运行时调用与多跳再导出调用不新增支持。
- 不新增 CLI 命令、网络服务、API 调用、目标代码执行或自动修复。
- 关联仅限扫描器可见、安全、仓库内文件；沿用 ignore、软链接、源码身份与读取检查。
- 候选唯一性先判断，再判断目标是否被选择和成功解析。
- 地图节点 200、边 500 上限不变；viewer 不修改；人类界面仍只呈现结构关系。
- 0.6.0 发行证据、历史 200 评分、主目录既有 14 个改动、全局 0.5.3 和已安装 Skill 保持原样。

## 4. 路径关联合同

现有明确扩展路径和 TS `.js` 到唯一源码的替换维持旧规则。新增分支仅处理 `./`、`../` 开头、最后部分无后缀的静态声明。包含反斜杠、NUL、`?`、`#`、`%` 或尾随 `/` 的路径不进入新增分支；不解码 URL、不解释转义。`../.` 可在规范化后按相同候选规则处理，但不能越出仓库。

对规范化 stem 构造候选并集：

```python
SUFFIXES = ('.ts', '.js', '.mjs', '.tsx', '.jsx', '.d.ts',
            '.mts', '.cts', '.cjs', '.d.mts', '.d.cts', '.json', '.node')
options = {stem}
options.update(stem + suffix for suffix in SUFFIXES)
options.update(stem + '/index' + suffix for suffix in SUFFIXES)
matches = sorted(options.intersection(path_set))
```

`path_set` 必须来自现有扫描器的全部可见文件，不先过滤语言、实现扩展或解析状态。`.ts` 与 `.d.ts`、文件与 index、`.js` 与 `.ts` 同时出现都拒绝；没有扩展的 exact stem 文件也参与竞争，不能略过。

若 `stem/package.json` 可见，整个新增关联分支拒绝。这里有意不模拟目录配置的优先级，即使另有同名实现文件也不选。配置文件不读取、不执行。有限后缀集合不是所有加载器格式；集合外的自定义加载器语义仍未知。

只有一个候选时，还必须满足：在 `index.file_languages` 中、语言是 JS/TS、扩展是当前实现扩展、没有整文件解析错误。否则未知。不存在时不猜测路径；不回退到外部包、alias、生成目录或仓库外文件。

成功来源种类：旧路径 `unique-local-source`；新增文件 `unique-extensionless-source`；新增目录 `unique-directory-index-source`。

新分支失败 reason 固定为：`unsupported-source-specifier`、`outside-source-root`、`directory-package-configuration`、`no-local-source-candidate`、`ambiguous-local-source-candidates`、`unselected-or-unsupported-local-source`、`parse-error-local-source`。外部/alias 和旧明确路径继续沿用旧 reason。limits 仍去重、显示最多 50 条并报告省略数。

每个 `(file, specifier)` 在一次解析中缓存结果；每次查询固定有限集合，不能逐条扫描全仓库。沿用已有集合去重与排序，重复解析同一 index 不重复增加边或 limits。

## 5. 文件依赖与函数调用

类型导入、namespace 导入、静态再导出可建立文件依赖，但不能据此构造运行时调用。函数调用保持现有规则：顶层安全函数、唯一导入绑定、唯一直接实现导出、无遮蔽/重赋值/方法接收者；type-only、namespace、回调、动态调用、桶文件多跳仍未知。

新增路径关联不取消任何调用防护。文件边存在而调用边不存在是合法结果。空 impact 继续标注 bounded，不能解释为没有影响。

## 6. 来源数据与兼容合同

不修改共享 `CallEdge`/`ImportEdge` 的字段。新增内部记录：

```python
@dataclass(frozen=True, slots=True)
class ESMSourceAssociation:
    file: str
    specifier: str
    target: str
    start_line: int
    end_line: int
    resolution_kind: str
```

RepoIndex 增加两个内部字典，默认均为空：

```python
esm_source_associations: dict[tuple[str, str, int], ESMSourceAssociation]
js_call_imports: dict[tuple[str, str, int], ESMImportRef]
```

前者键为 `(source_file, target_file, import_start_line)`，记录实际产生文件边的声明，包括静态再导出；同一行存在多个等价声明时，用 `(specifier,end_line)` 选最小记录，只表示一条文件边的来源证明。后者键为 `(caller, callee, call_line)`，记录实际通过调用防护的那一条已解析 import ref，不能由名称或文本事后猜测。相同行可能合并多次调用；只返回一条确定性来源证明，不宣称列出全部调用次数。用 `(file,start_line,end_line,alias or '',imported or '')` 选择最小记录。

context.call_evidence 和 impact.call_path_evidence 中，仅有该记录的 JS/TS 导入调用增加 `via_esm_import: asdict(ref)`；保持现有 caller/callee/file/line/via_reexports。无 import 来源的本地调用和 Python 调用不新增这个键。

impact.import_evidence 的 JS/TS 文件边增加 `esm_source_association: asdict(record)`；Python 记录不新增键。用同一个 `_call_edge_data(index, edge)` 序列化 context 和 impact 调用证据，防止两个输出口径不同。

analysis 元数据仅在选择了 JS/TS 时增加：

```json
{"esm_source_resolution": {"policy": "unique-visible-local-source-v1", "runtime_resolution": false}}
```

Python 默认 JSON 不增加新键；map 已有 analysis 可沿用此元数据，不修改共享 scope 文案或 Python capabilities。不要向每条输出重复塞入整个候选集合或源码引文。导入来源字段提供行段引用；原始源码仍由 context blocks 在 max-lines 预算内提供。

## 7. 交付、验证与拒绝发布条件

建议后续功能版目标 0.7.0，候选 0.7.0a1；本次仅提案，不提前修改版本号或创建 tag。

先补正负合同，再实现 resolver 与来源；随后做八个固定仓库的定向验证（七条旧案例加 dembrane），以及 sunanakgo 的四条真实歧义。保留每条来源、真实 ID、输出、摘要、退出码和主代理审查结论。失败后使用新 attempt，不能覆盖失败证据。

需要共享 context/model/languages/map 的兼容验证；已有 97 个相关合同及全套单元测试按实际新增数量记录，不强行维持旧计数。安装验收沿用 base、JS-extra、Python 生命周期，增加新路径与来源检查。候选必须对应冻结提交，安装的 runtime 与 source/wheel 字节一致，精确提交的七项 CI 全绿。

viewer 未改，可保留 0.6.0 继承的原版本实际交互证据，并为新候选生成地图数据/SVG 和 DOM 合同结果；不把旧浏览器结果标成新一轮真实交互。无需为了这一范围重跑 200 仓库或解决 Chrome 连接问题。

歧义被错误连接、类型导入被当调用、Python 输出变化、来源不对应实际绑定、超预算引文、安装不一致、CI 失败任一项都阻止发布。原始未知数量下降不单独构成通过条件。

## 8. 计划对应与审查状态

[执行清单草案](../plans/2026-10-07-js-ts-source-association.md) 的 S0–S6 分别覆盖冻结、解析、来源、地图/文档、真实调查、安装/CI、交付。

设计自审：已明确候选并集、配置阻断、调用护栏、两种来源记录、Python 条件字段、有限集合边界及发布出口。新增语义已由用户“开始实施”确认。实现按本设计完成，正式交付门槛单独记录。
