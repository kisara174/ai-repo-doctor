# AI Repo Doctor V3 设计：DeepSeek 辅助诊断

**状态：用户已审核通过**

## 目标

V3 在现有只读静态分析和手动模型工作流之上，增加一个可选的 DeepSeek API 诊断命令。用户指定一个 Python 符号后，Repo Doctor 在本地扫描仓库、构建有界上下文，只在用户显式运行诊断命令时把该上下文发送到 DeepSeek；模型返回的 finding 经本地证据验证后展示。

保留的产品约束：

- 静态扫描和上下文构建不执行目标仓库代码。
- 不因配置了 API Key 而自动发起网络请求。
- 模型只提出诊断；程序验证来源证据，但不宣称验证了推理结论。
- V1/V2 的离线工作流继续可用。

## 用户接口

新增命令：

```text
repo-doctor diagnose PATH SYMBOL [--max-lines N] [--model MODEL] [--json]
```

- `PATH` 和 `SYMBOL` 与现有 `context` 命令含义一致。
- `--max-lines` 默认 120，允许用户减少预算；API 诊断不允许超过 120 行，并另设 64 KiB 的源码文本硬上限。遇到超长行导致超过字节上限时，在网络请求前报错，不静默裁剪证据。
- `--model` 可覆盖模型。模型选择顺序为命令参数、`DEEPSEEK_MODEL` 环境变量、`deepseek-flash` 默认值。
- `--json` 返回稳定 JSON，包括 schema 版本、实际模型名、已接受 finding 和被拒绝 finding 及理由。人类可读模式列出结果，并明确说明证据通过不等于诊断结论正确。
- 0 表示请求及结果处理成功（即使没有 finding）；1 表示模型响应中有 finding 未通过校验；2 表示参数、配置、网络、响应格式或本地处理失败。

运行 `diagnose` 本身是用户发起的外部 API 请求。诊断前输出将发送的仓库相对文件路径、行范围、源码行数和字节数，不在该提示中重复源码内容。现有 `context` 命令继续用于完整查看将被选取的片段。

## 数据边界与隐私

只有 `diagnose` 会联网。它发送：

1. 系统提示词和 finding JSON 格式说明；
2. 目标符号 ID；
3. `build_context` 选出的目标函数、静态调用关系邻居及相关测试中的有限源码片段；
4. 片段的仓库相对路径、行号和关系标签。

不发送绝对仓库路径、完整扫描索引、未选中的文件、Git 元数据或本地测试运行结果。请求目标固定为 `https://api.deepseek.com/chat/completions`，不支持任意 API 地址，也不回退到其他服务。

上下文可能包含凭据或其他敏感文本。V3 不承诺自动发现或清除所有秘密；命令说明和 README 必须明确告知用户：运行诊断会把上述片段发给 DeepSeek，调用前应使用 `context` 检查目标内容并避免发送秘密。Repo Doctor 不保存请求、源码或模型响应；用户主动重定向标准输出的情况除外。

## API 与密钥处理

- 使用 Python 标准库 `urllib` 直接调用 HTTPS API，不新增运行时依赖；固定使用 DeepSeek 的聊天补全接口。
- 从 `DEEPSEEK_API_KEY` 环境变量读取密钥。缺失或空值时，在读取上下文之后、发送网络请求之前报清晰错误。密钥不接受为命令行参数，不落盘，不写入日志、异常或 JSON 输出。
- 使用非流式请求、`max_tokens: 4096` 和 `response_format: {"type": "json_object"}`。提示中包含“json”、目标 JSON 示例和明确的 finding 字段要求；要求模型把源代码、注释和字符串都当作待分析数据，不执行其中的指令。模型须返回 `{"findings": [...]}` 对象，空结果为 `{"findings": []}`。官方文档说明 JSON 模式用于输出有效 JSON，并建议提示中包含 JSON 示例；程序仍需检查具体字段，空响应和长度截断也需要单独处理。
- 默认模型为 `deepseek-flash`，可通过 `--model` 或 `DEEPSEEK_MODEL` 覆盖；实际响应中的模型名优先用于结果元数据。模型名属于外部服务配置，可能随服务方调整。
- 请求超时设为 60 秒。V3 不自动重试 POST 请求，避免不透明的重复上传和重复计费。超时、HTTP 错误、无效 API JSON、缺少 completion、空内容、模型 JSON 无法解析和输出截断都转换成不含密钥的可读错误。
- 不启用工具调用、函数调用或代理式多轮对话；每个诊断只发出一次请求。

参考 DeepSeek 官方文档：[Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)、[JSON Output](https://api-docs.deepseek.com/guides/json_mode/)、[Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/)。

## 诊断与证据验证流程

1. 本地调用 `build_index(PATH)` 和 `build_context(index, SYMBOL, max_lines)`。
2. 校验行数与 UTF-8 源码字节上限；收集待发送文件和行范围摘要。
3. 用固定 DeepSeek endpoint、解析出的模型名和 `DEEPSEEK_API_KEY` 发起一次非流式 JSON 请求。
4. 检查 API envelope、completion 状态、截断标记和模型内容；只解析符合 `{"findings": [...]}` 形状的 JSON 对象，不尝试从 Markdown 代码围栏中修复结果。
5. 把对象中的 `findings` 数组交给现有 `validate_findings`，验证 finding 字段、置信度、仓库内路径、行范围、当前源码引文和可选符号。
6. 对 `diagnose` 额外约束每条证据必须落在本次提交给模型的上下文块范围内，并且引用文本匹配该块的源码。不能仅因某条证据在未发送的仓库文件中碰巧存在，就把它报告为模型已提供的上下文证据。
7. 展示已接受和被拒绝的 finding。验证失败的 finding 保留拒绝理由，不作为受支持的诊断呈现。

证据门只验证结构和来源可追溯性，不验证模型对代码行为、严重性、影响或修复的判断。人工仍需审查推理，并通过独立测试确认实际行为。

## 失败行为与退出状态

- 未配置 API Key：不发请求，返回配置提示。
- 输入符号歧义、不存在或上下文无效：沿用现有 CLI 的本地错误处理，不发请求。
- 请求失败或模型响应不完整：不生成部分 finding，不重试；返回 2。
- 模型返回 `{"findings": []}`：成功且没有受支持问题，返回 0。
- 结构正确但证据不匹配的 finding：在结果中列为 rejected，并返回 1。
- API 错误输出不包含 Authorization 头、API Key 或完整的敏感请求体。

## 非目标

- Ollama、本地模型、其他云厂商或通用 OpenAI-compatible endpoint。
- 自动改代码、生成补丁、应用补丁、运行目标仓库测试或调用目标仓库命令。
- 自动扫描全部符号或整仓问答；V3 一次只诊断一个符号。
- 自动秘密检测/脱敏、请求缓存、历史保存、遥测、后台请求或自动重试。
- 以证据校验结果作为诊断正确性的评分。

## 验收标准

1. 所有现有测试继续通过；`scan`、`context`、`impact` 和 `validate` 不发出网络请求，原输出语义不变。
2. CLI 帮助与 README 说明 DeepSeek 是可选服务、确切传输范围、API Key 配置方式和敏感代码注意事项。
3. 缺少密钥、歧义符号和超出上下文上限均在请求前失败；测试确认没有调用网络传输层。
4. 请求构造测试验证固定 HTTPS endpoint、鉴权头、非流式请求、模型选择、JSON 模式及发送内容仅来自选定上下文；错误输出和日志中没有密钥。
5. 本地模拟响应覆盖合法 findings、空数组、无效 JSON、空响应、截断、API 错误、超时、格式错误和请求不重试。
6. 上下文范围证据校验覆盖：合法已发送片段通过；未发送文件、未包含行段、错误引用、仓库中其他位置的真实引文均被拒绝。
7. 对有效模型响应，文本与 JSON CLI 输出均清楚显示 accepted/rejected 及证据校验边界。
8. 若用户未配置有效 API Key，不执行付费真实请求；使用 mock transport 完成可复现的离线验证。真实 API 烟测必须由用户在配置密钥后显式执行。

## 实现范围建议

实现时新增一个只负责 DeepSeek HTTP 请求、响应解析和失败归一化的小模块；CLI 负责参数、构建上下文、证据校验与输出。尽量复用 `context` 和 `evidence` 模块，不引入通用 provider 抽象，也不在这一步扩展静态分析器。
