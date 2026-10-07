# JS/TS 支持闭环材料（2026-10-07）

准备材料的历史状态：**J0–J4 prepared-not-run**。`cases/cohort/readiness/test-plan` 等固定输入和原收据不改写为产品通过。

后续执行已经完成：[J5 验证结果](../../docs/evaluations/2026-10-07-js-ts-support-validation.md)、[J6 正式 0.6.0 交付](../../docs/delivery/2026-10-07-v0.6.0-js-ts-support.md)。主代理已补齐八项断言并完成两组调查、安装与远端 CI，勿再次按下文原准备顺序重复执行。执行与发布状态分别记录在本机 `execution-completion-j5.json` 和 `releases/v0.6.0/completion.json`。未执行公开目标代码、未安装目标依赖、未调用云端诊断 API。

## 入口

- [执行计划](../../docs/superpowers/plans/2026-10-07-js-ts-validation-and-support.md)：J0–J6 范围与发行门槛。
- [cases.json](cases.json)：24 类能力合同、现有断言、8 个明确的补充断言任务。空列表不是已验证无关系。
- [cohort.json](cohort.json)：12 个固定提交，JS/TS 各 6 个，小中大各 2 个；每层第一个 discovery，第二个 confirmation。
- 本机完整证据根：`/Users/kisara/.local/share/ai-repo-doctor/evaluations/js-ts-support-v1`。
  - `baseline.json`：稳定 0.5.3、预览 0.6.0a5、wheel/runtime/安装身份及隔离分支。
  - `protection-before.json`：14 个原文件、150789 个历史证据条目、65 个候选 runtime 的保护核验，引用旧清单而不复制或修改历史。
  - `support-matrix.json`、`oracle-review.jsonl`：合同与 7 条旧 oracle 范围误配的源码复核。历史得分不变；无后缀/index 仍未实现。
  - `questions.jsonl`：36 题，固定问题、支持分类、独立预期和实际源码定位动作。
  - `reference.jsonl`：逐条源码引文、物理行和文件 SHA256；`reference-source/` 保留来自 a5 Git blob 的只读参考副本，后续修改测试不会改写独立预期。
  - `source-baseline/`：96 次真实 rg/源码补读的 stdout、stderr、argv、耗时收据。
  - `test-plan.json`：71 条后续命令模板、真实 ID 的绑定规则、独立安装/CI 门槛和效益标准。
  - `readiness.json`、`preparation-report.md`：准备材料核验和阶段结论。

绝对路径是本机证据定位，不是 wheel runtime 的组成。迁移机器须重新定位并按 hash 绑定，不能直接把不存在的路径当作有效来源。两个版本化 JSON 的完整本机副本受 test-plan 的输入哈希约束。

## 当前支持边界

显式选择 `javascript,typescript`；只分析 `.js/.mjs/.ts` 实现，默认 Python 不变。类方法符号可搜索，调用只解析安全顶层直接函数及直达 ESM 导出。回调、对象/方法链、多跳 re-export、动态导入、CommonJS、JSX/TSX、路径别名、无后缀及目录 index 不构成承诺的完整运行调用覆盖。空 impact 不等于没有影响。

所有 12 个仓库都已在历史开发评估中出现。confirmation 是本阶段冻结后的确认组，**不是新的盲测**。七条 oracle 口径复核不修改历史报告，不证明当前 a5 无 bug，也不证明未来覆盖已实现。

## 原准备阶段的执行顺序（已完成，仅保留合同）

1. 读取 `readiness.json`、`baseline.json`，核验输入 hash、候选 wheel/runtime、目标提交与源码，确认稳定入口仍为 0.5.3。
2. 在隔离分支按 cases 中 `supplement_required` 写 8 个外部行为断言：mjs async default、唯一未选中目标、type-only export、namespace 调用未知、目录 index 未知、别名/node_modules、JS 小预算截断、JS include/歧义请求。原测试可覆盖的部分直接复用，不复制 24 个镜像测试。
3. 执行 test-plan 的 `local_contract`，extra 环境不允许 skipped；这是 J5 首次产品测试。首次结果必须原样保存，失败先核对独立预期，再定向定位。
4. 只先执行 discovery。命令中的 binding 从 `symbols` 成功输出的 `matches` 中选取唯一、与源码参考一致的真实 ID；未找到则 blocked，禁止直接猜 ID 或取第一个匹配。
5. context 检查源码引用和预算；impact 检查固定支持内正例与逐跳证据。额外边独立补读。范围外关系解释为未知，不以退出码 0 代替回答正确。
6. 每题逐项记录 answered/bounded/blocked 和全部实际工具/补读动作，比较相同冻结问题的源码基线。可复用已得到的证据，但必须记录复用关系，不能重复抵扣动作。
7. 发现产品 bug 先留失败场景再最小修复。若 runtime 变化，冻结独立 a6 源、wheel 与安装，不改 a5。无后缀/index 的新语义先设计，不混入 C12 旧合同。
8. 固定候选后执行 confirmation，再进行 base/extra/Python 生命周期安装验收及精确 SHA 的 7-job CI。全部门槛达成才进入 J6 正式 0.6.0 交付。

地图及 stdout/stderr 输出采用每仓库/每 attempt 新路径，不覆盖重试记录。已有 200 仓库历史评分和旧收据归属保持原版本。普通 Mac Python 入口保持 0.5.3；预览使用独立绝对入口。

## 仅验证准备材料的命令

下面只检查本机证据及引文，不导入 Repo Doctor，不运行产品或目标仓库：

```sh
python3 - <<'PY'
import json, hashlib
from pathlib import Path
root = Path('/Users/kisara/.local/share/ai-repo-doctor/evaluations/js-ts-support-v1')
plan = json.loads((root / 'test-plan.json').read_text())
for filename, expected in plan['inputs'].items():
    assert hashlib.sha256(Path(filename).read_bytes()).hexdigest() == expected, filename
rows = [json.loads(line) for line in (root / 'reference.jsonl').read_text().splitlines()]
for row in rows:
    path = Path(row['file'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == row['file_sha256'], str(path)
    lines = path.read_text().splitlines()
    assert '\n'.join(lines[row['start_line']-1:row['end_line']]) == row['quote'], str(path)
assert len(plan['case_ids']) == 24 and len(plan['question_ids']) == 36
assert len(json.loads((root / 'cohort.json').read_text())['repositories']) == 12
assert plan['actual_tests_run'] is False and plan['target_code_executed'] is False
print('准备输入与引文一致；未验证产品行为。')
PY
```
