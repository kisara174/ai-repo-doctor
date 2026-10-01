"""Human-readable investigation report; case.json remains the source of truth."""

import json
import re


def _inline(value: object) -> str:
    text = " ".join(str(value).splitlines())
    return re.sub(r"([\\`*_\[\]<>])", r"\\\1", text)


def _quote(value: str) -> str:
    longest = max((len(match.group()) for match in re.finditer(r"`+", value)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{value}\n{fence}"


def _code(value: object) -> str:
    text = str(value).replace("\n", " ")
    longest = max((len(match.group()) for match in re.finditer(r"`+", text)), default=0)
    fence = "`" * max(1, longest + 1)
    space = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{space}{text}{space}{fence}"


def repair_state(issue: dict) -> str:
    history = issue.get("verification", [])
    after = history[-1] if history and history[-1]["phase"] == "after" else None
    before = None
    if after is not None:
        before = next((item for item in reversed(history[:-1])
                       if item["phase"] == "before" and item["argv"] == after["argv"]), None)
    human = issue.get("human_history", [])
    related = bool(human and human[-1]["status"] == "resolved" and human[-1].get("related_test"))
    if (
        issue.get("human_status") == "resolved" and related and before and after
        and before["status"] == "failed" and after["status"] == "passed"
        and before["source_fingerprint"] == before.get("source_fingerprint_after")
        and after["source_fingerprint"] == after.get("source_fingerprint_after")
        and before["source_fingerprint"] != after["source_fingerprint"]
    ):
        actor = human[-1].get('actor', 'human')
        label = 'Codex 确认关联' if actor == 'codex' else '人工确认关联'
        return f"有修复证据（同一回归命令：修改前失败、源码变更、修改后通过；{label}）"
    if after and after["status"] != "passed":
        return "复查未通过"
    return "仍需复核"


def render_report(case: dict) -> str:
    repo = case["repository"]
    scan = case["scan"]
    stats = scan["stats"]
    lines = [
        "# AI Repo Doctor 调查报告", "",
        f"- 仓库：{_code(repo['root'])}",
        f"- 扫描时间：{_inline(case['created_at'])}",
        f"- 工具版本：{_inline(case['tool_version'])}",
        f"- Git 修订：{_code(repo.get('revision') or 'unavailable')}",
        f"- 源码指纹：{_code(repo['source_fingerprint'])}",
        f"- 扫描方式：{_inline(repo['scan_mode'])}", "",
        "## 仓库概况", "",
        f"- Python 文件：{stats['python_files']}；行数：{stats['python_lines']}；类/函数/方法：{stats['classes']}/{stats['functions']}/{stats['methods']}",
        f"- 已解析调用：{stats['resolved_calls']}；未解析调用：{stats['unresolved_calls']}（覆盖边界，非缺陷）",
        f"- 解析失败：{len(scan['parse_errors'])}；局部导入环：{len(scan['import_cycles'])}",
        "- 省略范围：动态调用、运行时行为与未扫描文件无法由静态图谱证明。", "",
    ]
    if "architecture" in scan:
        architecture = scan["architecture"]
        lines.extend([
            "## 静态架构摘要", "",
            f"- 生产代码模块：{_inline(architecture['production_modules'])}；已解析的本地导入边：{_inline(architecture['local_import_edges'])}；跨文件调用边：{_inline(architecture['cross_file_call_edges'])}",
            "- 下列模块按依赖它的不同生产文件数排序；只统计可静态解析的本地边，不表示运行时调用频率或代码质量。测试文件、外部包、动态导入与未解析调用不在此图中。", "",
        ])
        if not architecture["focus_modules"]:
            lines.extend(["没有模块达到两个不同生产文件的已解析依赖门槛。", ""])
        for module in architecture["focus_modules"]:
            lines.append(
                f"- {_code(module['file'])}：{_inline(module['dependent_file_count'])} 个不同的依赖文件"
                f"（导入者 {_inline(module['importer_count'])}；跨文件调用者 {_inline(module['caller_file_count'])}）"
            )
            for edge in module["evidence"]:
                location = _code(f"{edge['file']}:{edge['line']}")
                if edge["kind"] == "import":
                    lines.append(f"  - 本地导入 {location} → {_code(edge['target'])}")
                else:
                    lines.append(f"  - 已解析调用 {location}：{_code(edge['caller'])} → {_code(edge['callee'])}")
            if module["evidence_omitted"]:
                lines.append(f"  - 另有 {_inline(module['evidence_omitted'])} 条边未在摘要中展开。")
            lines.append("")
    if "review_leads" in scan:
        lines.extend([
            "## 建议先检查", "",
            "检查顺序不代表缺陷严重度：先处理影响扫描完整性的解析失败，再看导入环，最后浏览被至少两个其他生产文件直接调用的符号。后两类是调查入口，不代表已确认缺陷。", "",
        ])
        if not scan["review_leads"]:
            lines.extend(["当前规则没有产生静态检查入口；这不证明仓库没有缺陷。", ""])
        for lead in scan["review_leads"]:
            label = {
                "parse_error": "解析失败",
                "import_cycle": "局部导入环",
                "shared_call_target": "共用调用目标",
            }.get(lead["kind"], lead["kind"])
            heading = f"- 顺序 {lead['review_order']} · {_inline(label)} · {_code(lead['subject'])}"
            if lead.get("issue_id"):
                heading += f" · issue {_code(lead['issue_id'])}"
            if lead.get("caller_count") is not None:
                heading += f" · {lead['caller_count']} 个跨文件生产代码直接调用者"
            lines.extend([heading, f"  - 原因：{_inline(lead['reason'])}",
                          f"  - 下一步：{_inline(lead['next_step'])}"])
            for evidence in lead["evidence"]:
                location = f"{evidence['file']}:{evidence['start_line']}"
                detail = f" · {_code(evidence['caller'])}" if evidence.get("caller") else ""
                message = f" · {_inline(evidence['message'])}" if evidence.get("message") else ""
                lines.append(f"  - 边或位置：{_code(location)}{detail}{message}")
            if lead.get("evidence_omitted"):
                lines.append(f"  - 另有 {lead['evidence_omitted']} 条直接调用边未在摘要中展开；可用 impact 查看。")
            lines.append("")
    target = case.get("target")
    if target:
        impact = target["impact"]
        lines.extend(["## 调查目标与静态影响", "", f"- 符号：{_code(target['symbol'])}",
                      f"- 源码指纹：{_code(target['source_fingerprint'])}",
                      f"- 反向已解析影响：{len(impact['affected_symbols'])} 个符号", ""])
        for distance, heading in ((1, "直接影响"), (2, "间接影响")):
            if distance == 1:
                group = [item for item in impact["affected_symbols"] if item["distance"] == 1]
            else:
                group = [item for item in impact["affected_symbols"] if item["distance"] > 1]
            lines.extend([f"## {heading}", ""])
            if not group:
                lines.extend(["没有已解析的反向调用路径。", ""])
            for item in group:
                lines.append(f"- {_code(item['symbol'])}：{_code(' → '.join(item['path']))}")
                for edge in item.get("call_path_evidence", []):
                    location = f"{edge['file']}:{edge['line']}"
                    lines.append(
                        f"  - 调用边 {_code(location)}："
                        f"{_code(edge['caller'])} → {_code(edge['callee'])}"
                    )
                    for hop in edge.get("via_reexports", []):
                        hop_location = f"{hop['file']}:{hop['line']}"
                        lines.append(
                            f"    - 重导出 {_code(hop_location)}：{_code(hop['name'])}"
                        )
            lines.append("")
        if impact.get("import_evidence"):
            lines.extend(["### 目标模块的直接导入边", ""])
            for edge in impact["import_evidence"]:
                location = f"{edge['source']}:{edge['line']}"
                lines.append(f"- {_code(location)} → {_code(edge['target'])}")
            lines.append("")
    lines.extend(["## 显式复现记录", "", "以下只是命令运行时的观察，不证明根因；源码指纹仅覆盖扫描到的 Python 文件。", ""])
    if not case.get("reproductions"):
        lines.extend(["尚无显式复现记录。", ""])
    for run in case.get("reproductions", []):
        lines.append(
            f"- {_code(run['id'])} · {_inline(run['at'])} · {_inline(run['status'])} · "
            f"exit={run['exit_code']} · 命令 {_code(json.dumps(run['argv'], ensure_ascii=False))} · "
            f"Python 源码 {_code(run['source_fingerprint'])}"
        )
        if run["source_fingerprint"] != run["source_fingerprint_after"]:
            lines.append("  - 执行期间 Python 源码发生变化；不能用于诊断。")
        if run.get("output"):
            lines.extend(["", _quote(run["output"]), ""])
        if run.get("output_truncated"):
            lines.append("  - 输出已截断至 16 KiB。")
        lines.append("")
    lines.extend(["## 请求预览", ""])
    if not case.get("previews"):
        lines.extend(["尚无已保存的请求预览。", ""])
    for preview in case.get("previews", []):
        lines.extend([
            f"- {_inline(preview['at'])} · {_code(preview['target_symbol'])} · {_inline(preview['model'])} · {preview['source_lines']} 行/{preview['source_bytes']} 字节",
            f"  - 请求 SHA-256：{_code(preview['request_sha256'])}",
        ])
        if preview.get("reproduction_id"):
            lines.append(f"  - 显式复现：{_code(preview['reproduction_id'])}")
        lines.append("")
    lines.extend(["## 诊断记录", ""])
    if not case["diagnoses"]:
        lines.extend(["尚未发起云端诊断。", ""])
    for attempt in case["diagnoses"]:
        lines.append(
            f"- {_inline(attempt['at'])}：{_inline(attempt['status'])}；"
            f"目标 {_code(attempt['target_symbol'])}；模型 {_inline(attempt.get('model') or 'unavailable')}；"
            f"接受 {len(attempt.get('accepted_issue_ids', []))}；拒绝 {len(attempt.get('rejected', []))}"
        )
        if attempt.get("error_category"):
            lines.append(f"  - 失败类别：{_inline(attempt['error_category'])}")
        if attempt.get("reproduction_id"):
            lines.append(f"  - 关联显式复现：{_code(attempt['reproduction_id'])}；AI 结论仍待人工复核。")
        for rejected in attempt.get("rejected", []):
            lines.append(f"  - 引文拒绝：{_inline(rejected.get('title', '(untitled)'))}；{_inline('; '.join(rejected['reasons']))}")
    if case.get('imports'):
        lines.extend(['', '## 离线发现导入', ''])
        for item in case['imports']:
            lines.append(f"- {_inline(item['at'])} · {_inline(item['producer'])} · {_inline(item['status'])} · 上下文快照 {_code(item['snapshot_sha256'])} · 接受 {len(item['accepted_issue_ids'])}；拒绝 {len(item['rejected'])}")
            for rejected in item['rejected']:
                lines.append(f"  - {_inline(rejected['title'])}：{_inline('; '.join(rejected['reasons']))}")
    lines.extend(["", "## Issues", ""])
    if not case["issues"]:
        lines.extend(["目前没有已记录 issue。空发现不证明仓库没有缺陷。", ""])
    for issue in case["issues"]:
        history = issue.get('human_history', [])
        actor = history[-1].get('actor', 'human') if history else 'human'
        review_label = 'Codex 判断' if actor == 'codex' else '人工判断'
        lines.extend([
            f"### {issue['id']} · {_inline(issue['title'])}", "",
            f"- 来源：{_inline(issue.get('producer', issue['origin']))}；来源证据：{_inline(issue['evidence_status'])}；{review_label}：{_inline(issue['human_status'])}",
            f"- 修复状态：{repair_state(issue)}",
        ])
        if issue["origin"] == "ai":
            lines.append("- 判断性质：AI 假设；引文通过不代表缺陷已证实。")
        if issue.get("reproduction_id"):
            lines.append(f"- 关联显式复现：{_code(issue['reproduction_id'])}；失败命令不自动证明此 issue。")
        lines.extend(["", "**证据**", ""])
        for evidence in issue.get("evidence", []):
            location = f"{evidence['file']}:{evidence['start_line']}-{evidence['end_line']}"
            lines.append(f"- {_code(location)}")
            if evidence.get("quote"):
                lines.extend(["", _quote(evidence["quote"]), ""])
            if evidence.get("message"):
                lines.append(f"  - {_inline(evidence['message'])}")
        lines.extend(["", f"**推理：** {_inline(issue['reasoning'])}", "",
                      f"**影响：** {_inline(issue['impact'])}", "",
                      f"**建议：** {_inline(issue['suggested_fix'])}", ""])
        if "confidence" in issue:
            lines.extend([f"模型自报置信度：{issue['confidence']}（不代表产品判定）", ""])
        if issue.get("human_history"):
            lines.extend(["**复核记录**", ""])
            for item in issue["human_history"]:
                lines.append(f"- {_inline(item['at'])} · {_inline(item.get('actor', 'human'))} · {_inline(item['status'])} · {_inline(item['note'])} · 测试关联：{'是' if item.get('related_test') else '未确认'}")
            lines.append("")
        if issue.get("verification"):
            lines.extend(["**回归记录**", ""])
            for item in issue["verification"]:
                lines.append(f"- {_inline(item['at'])} · {_inline(item['phase'])} · {_inline(item['status'])} · exit={item['exit_code']} · {item['duration_seconds']}s · 命令 {_code(json.dumps(item['argv'], ensure_ascii=False))} · 源码 {_code(item['source_fingerprint'])}")
                if item.get("source_fingerprint_after") != item["source_fingerprint"]:
                    lines.append("  - 运行期间 Python 源码发生变化；该次结果不能作为修复闭环证据。")
                if item.get("output"):
                    lines.extend(["", _quote(item["output"]), ""])
                if item.get("output_truncated"):
                    lines.append("  - 输出已截断至 16 KiB。")
            lines.append("")
    lines.extend(["## 结论边界", "", "静态事实只说明源码结构；引文通过只说明模型引用了已发送的源码；问题是否真实仍需人工与回归验证。", ""])
    return "\n".join(lines)
