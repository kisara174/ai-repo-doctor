# AI Repo Doctor V3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit DeepSeek-backed `diagnose` command that sends only bounded, selected Python context to DeepSeek and locally validates every returned finding against both the repository and the submitted context.

**Architecture:** Keep scanning and context selection local. Add a small standard-library HTTP client for the fixed DeepSeek Chat Completions endpoint, then a diagnosis module for prompt construction, source-size checks, response-shape checks, and context-scoped evidence validation. The CLI orchestrates one request, displays the upload summary on stderr, and returns accepted/rejected findings on stdout.

**Tech Stack:** Python 3.11+, standard-library `urllib`, `unittest`, existing AST index/context/evidence modules.

**Spec:** `docs/superpowers/specs/2026-09-24-repo-doctor-v3-design.md`

## Global Constraints

- The API request target is fixed to `https://api.deepseek.com/chat/completions`; no alternate provider, endpoint, or fallback is added.
- Read the API key only from `DEEPSEEK_API_KEY`; never accept it as a command-line argument, persist it, or print it.
- Resolve model as `--model`, then `DEEPSEEK_MODEL`, then `deepseek-flash`.
- Use non-streaming JSON mode, `max_tokens=4096`, and a 60-second timeout; do not retry a request.
- `diagnose` accepts 1–120 context lines and at most 64 KiB of selected UTF-8 source text; reject over-budget input before opening a network request.
- `diagnose` sends only the target symbol, selected context blocks, repository-relative paths, line numbers, relation labels, and prompt; never send an absolute root, full index, or unselected source.
- Findings must cite only line ranges and exact source quotes included in the request as well as pass the existing repository evidence checks.
- Do not execute target repository code, tests, commands, model tools, or patches.
- Keep all existing commands offline and preserve their current output semantics.
- Add no runtime dependencies. All API tests use mocked HTTP responses and make no network requests.

---

## File Structure

- Create `repo_doctor/deepseek.py` for the fixed HTTPS request, API-envelope handling, JSON parsing, and safe provider errors.
- Create `repo_doctor/diagnosis.py` for prompt construction, source byte accounting, DeepSeek payload validation, and evidence scoping to submitted context.
- Modify `repo_doctor/cli.py` to add the `diagnose` command and text/JSON renderers.
- Create `tests/test_deepseek.py` for transport construction and provider response/error behavior.
- Create `tests/test_diagnosis.py` for prompt boundaries, source limits, response shape, and evidence scope.
- Modify `tests/test_cli.py` for command wiring, key/model configuration, upload summary, exit codes, and JSON-only stdout.
- Modify `README.md` to document optional DeepSeek diagnosis, required environment variables, cloud data flow, and sensitive-source cautions.
- Do not modify `pyproject.toml`; `urllib` is in the standard library.

## Task 1: Add the DeepSeek JSON transport

**Files:**
- Create: `repo_doctor/deepseek.py`
- Create: `tests/test_deepseek.py`

**Interfaces:**
- `DeepSeekError(Exception)` represents safe, user-facing request and response failures. Its message must never contain the API key, Authorization header, or request body.
- `DeepSeekResult` is a frozen dataclass with `model: str` and `payload: dict`.
- `complete_json(system_prompt: str, user_prompt: str, *, api_key: str, model: str, timeout: float = 60.0) -> DeepSeekResult` sends exactly one request and returns the provider model plus parsed JSON object.
- `complete_json` accepts a top-level JSON object only. The diagnosis layer validates its `findings` member in Task 2.

- [x] **Step 1: Write transport tests with a fake HTTP response**

Add a `FakeResponse` helper to `tests/test_deepseek.py` whose `read()` returns UTF-8 JSON bytes. Patch `urllib.request.urlopen`; never contact DeepSeek from a test.

Add a success test whose fake API response has this shape:

```python
{
    "model": "deepseek-flash",
    "choices": [{
        "finish_reason": "stop",
        "message": {"content": "{\"findings\": []}"},
    }],
}
```

Assert `complete_json` returns `DeepSeekResult("deepseek-flash", {"findings": []})`, calls `urlopen` exactly once with `https://api.deepseek.com/chat/completions` and timeout `60.0`, and sends a body with the requested model, `stream is False`, `max_tokens == 4096`, and `response_format == {"type": "json_object"}`. Assert the request carries `Authorization: Bearer test-secret`.

Add separate failing tests for HTTP 401, URL/timeout failure, invalid API-envelope JSON, missing `choices`, empty message content, malformed model JSON, a non-object model result, and `finish_reason == "length"`. For HTTP and URL errors, assert `str(exception)` does not contain `test-secret`. For an HTTP error, assert `urlopen` was called exactly once.

- [x] **Step 2: Run the focused tests and verify the missing implementation fails**

Run: `python3 -m unittest tests.test_deepseek -v`

Expected: FAIL because `repo_doctor.deepseek` does not yet exist.

- [x] **Step 3: Implement the fixed-endpoint client**

Implement the request with `urllib.request.Request`, UTF-8 JSON, `Content-Type: application/json`, and the Bearer authorization header. Use the exact body fields from Step 1. Catch `urllib.error.HTTPError`, `urllib.error.URLError`, `TimeoutError`, API-envelope parse failures, and malformed model content; raise concise `DeepSeekError` messages without response bodies or headers. Treat `finish_reason == "length"`, empty content, missing model, missing choice, or a non-object JSON response as errors. Do not add a retry loop.

The request body has this exact shape:

```python
request_data = {
    "model": model,
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    "stream": False,
    "max_tokens": 4096,
    "response_format": {"type": "json_object"},
}
request = urllib.request.Request(
    API_URL,
    data=json.dumps(request_data).encode("utf-8"),
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    method="POST",
)
```

- [x] **Step 4: Run focused and full tests**

Run: `python3 -m unittest tests.test_deepseek -v`

Expected: all transport tests PASS without network access.

Run: `python3 -m unittest discover -s tests -q`

Expected: all existing tests and the new transport tests PASS.

- [x] **Step 5: Commit the transport unit**

```bash
git add repo_doctor/deepseek.py tests/test_deepseek.py docs/superpowers/plans/2026-09-24-repo-doctor-v3.md
git diff --cached --check
git commit -m "feat: add DeepSeek JSON client"
```

## Task 2: Build bounded prompts and scope evidence to sent snippets

**Files:**
- Create: `repo_doctor/diagnosis.py`
- Create: `tests/test_diagnosis.py`

**Interfaces:**
- `DEFAULT_MODEL = "deepseek-flash"` and `MAX_CONTEXT_LINES = 120` are shared by CLI and diagnosis validation.
- `build_diagnosis_prompts(context: dict) -> tuple[str, str]` returns system and user prompt strings. The user prompt serializes only `symbol`, `blocks`, and `call_evidence`; it omits `root` and any non-context index data.
- `context_source_usage(context: dict) -> tuple[int, int]` returns `(line_count, utf8_source_bytes)`, counting selected source lines and one newline byte per line.
- `validate_context_budget(context: dict) -> tuple[int, int]` returns those counts and raises `ValueError` if the context exceeds 120 lines or 64 KiB.
- `validate_diagnosis_payload(index: RepoIndex, payload: dict, context: dict) -> dict` requires a list in `payload["findings"]`, invokes `validate_findings`, and rejects otherwise-valid evidence unless every evidence range and quote lies inside a submitted context block.

- [x] **Step 1: Write prompt, budget, response-shape, and evidence-scope tests**

Build a temporary repository like the existing evidence tests, with `app.py` containing `unsafe()` at lines 1–2 and a second function at lines 4–5. Build the index and context for `app.py::unsafe` with a two-line budget.

Add tests asserting:

1. The system prompt requires JSON shaped as `{"findings": [...]}`, lists all required finding fields, says to return `{"findings": []}` when there is no supported issue, and treats source comments/strings as data rather than instructions.
2. The user prompt contains `app.py::unsafe` and its selected source, and does not contain the temporary absolute repository path or the unselected function source.
3. `context_source_usage` returns the selected line count and UTF-8 byte count including line separators; `validate_context_budget` accepts an in-limit context and raises `ValueError` for a synthetic context over 64 KiB or 120 lines.
4. A payload `{"findings": [valid_finding]}` with evidence in the selected target block is accepted.
5. A finding quoting the real but unselected second function is rejected with a reason naming the submitted-context scope; repository-grounded evidence alone is insufficient.
6. An evidence range extending beyond a selected block and a payload whose `findings` value is missing or not a list are rejected as specified (invalid top-level response shape raises `ValueError`; invalid evidence becomes a rejected finding).

- [x] **Step 2: Run the focused tests and verify they fail**

Run: `python3 -m unittest tests.test_diagnosis -v`

Expected: FAIL because `repo_doctor.diagnosis` does not yet exist.

- [x] **Step 3: Implement prompt and budget helpers**

Build the user prompt from an allowlist of context fields rather than serializing an arbitrary caller dictionary. Represent each source line with its original number and text. Include the exact response envelope example `{"findings": []}` in the system prompt. Count only submitted source lines and their UTF-8 bytes; raise before the API call if line count exceeds 120 or source text exceeds `64 * 1024` bytes.

The serialized user context has this exact shape:

```python
context_payload = {
    "symbol": context["symbol"],
    "blocks": context["blocks"],
    "call_evidence": context["call_evidence"],
}
user_prompt = json.dumps(context_payload, ensure_ascii=False)
```

The system prompt requires this response envelope and the finding fields already enforced by `validate_findings`:

```json
{"findings": [{"title": "...", "category": "...", "confidence": 0.0, "evidence": [{"file": "...", "start_line": 1, "end_line": 1, "quote": "..."}], "reasoning": "...", "impact": "...", "suggested_fix": "..."}]}
```

- [x] **Step 4: Implement the context-scoped finding gate**

Require `payload` to be a dictionary containing a list-valued `findings`. Pass that list to `validate_findings(index, findings)`. For each otherwise-accepted evidence item, require its file to match a submitted block, its full line interval to be inside that block, and its quote to occur in the submitted block lines for that interval. Move failures from `accepted` to `rejected`, preserving the existing `index` and `finding` and adding a clear scope reason. Leave existing `validate_findings` behavior and the `validate` CLI contract unchanged.

Implement the per-finding context check with this signature:

```python
def context_scope_errors(finding: dict, blocks: list[dict]) -> list[str]:
    """Return reasons when evidence falls outside the exact submitted lines."""
```

- [x] **Step 5: Run focused and full tests**

Run: `python3 -m unittest tests.test_diagnosis -v`

Expected: all prompt, budget, shape, and evidence-scope tests PASS.

Run: `python3 -m unittest discover -s tests -q`

Expected: all existing and new tests PASS.

- [x] **Step 6: Commit the diagnosis unit**

```bash
git add repo_doctor/diagnosis.py tests/test_diagnosis.py docs/superpowers/plans/2026-09-24-repo-doctor-v3.md
git diff --cached --check
git commit -m "feat: scope findings to submitted context"
```

## Task 3: Add the explicit `diagnose` CLI command

**Files:**
- Modify: `repo_doctor/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Parser syntax: `diagnose PATH SYMBOL [--max-lines N] [--model MODEL] [--json]`.
- `--max-lines` defaults to 120 and accepts only integers from 1 through 120.
- Model precedence is explicit `--model`, then nonempty `DEEPSEEK_MODEL`, then `DEFAULT_MODEL`.
- Missing/empty `DEEPSEEK_API_KEY`, invalid context, provider failures, and invalid response shape return 2 without printing a key.
- Valid results have top-level fields `schema_version`, `provider`, `model`, `accepted`, and `rejected`; `provider` is `deepseek`.
- `--json` writes only the result JSON to stdout. The preflight upload summary goes to stderr and lists selected repository-relative files/ranges and line/byte totals, but not source contents.
- Return 1 when at least one finding is rejected; return 0 when the request succeeds and all findings are accepted or the model reports no findings.

- [ ] **Step 1: Write in-process CLI tests with a mocked client**

Extend `tests/test_cli.py` with `io.StringIO`, `contextlib.redirect_stdout`, `contextlib.redirect_stderr`, `os.environ`, and `unittest.mock.patch`. Call `repo_doctor.cli.main([...])` against a temporary repository; do not call the live API.

Add tests asserting:

1. `diagnose --json` with `DEEPSEEK_API_KEY=test-secret` and a mocked `DeepSeekResult("deepseek-flash", {"findings": [valid_finding]})` returns 0, emits parseable JSON with the five top-level fields, and reports the target in stderr's preflight summary.
2. JSON stdout contains no preflight prose and stderr does not contain source line text.
3. `--model command-model` overrides `DEEPSEEK_MODEL=environment-model`; without `--model`, the environment value is passed to `complete_json`; with neither, `deepseek-flash` is used.
4. Missing key, `--max-lines 0`, `--max-lines 121`, ambiguous/unknown symbol, and over-64-KiB source make no call to `complete_json` and return 2.
5. A mocked `DeepSeekError` returns 2 with no API key in stderr; a mocked valid response containing one rejected finding returns 1 and reports accepted/rejected results.
6. Existing `scan --json`, `context`, `impact`, and `validate` calls continue to work without `DEEPSEEK_API_KEY` and do not call the mocked API client.

- [ ] **Step 2: Run the focused tests and confirm the new command is missing**

Run: `python3 -m unittest tests.test_cli -v`

Expected: new `diagnose` tests FAIL because the parser and dispatch branch do not exist; existing CLI tests remain PASS.

- [ ] **Step 3: Add parser and dispatch**

Add the `diagnose` subparser with `path`, `symbol`, `--max-lines`, `--model`, and `--json`. In the dispatch branch, validate the range 1–120, build the local index and context, call `validate_context_budget(context)`, then resolve the key and model. If the key is absent, raise a safe local error before calling `complete_json`. Print the selected-file summary to stderr, build prompts, call `complete_json` once, and pass `result.payload` through `validate_diagnosis_payload`.

Register the command with this argument contract:

```python
diagnose = subcommands.add_parser(
    "diagnose", help="Send bounded source context to DeepSeek for diagnosis"
)
diagnose.add_argument("path", type=Path)
diagnose.add_argument("symbol")
diagnose.add_argument("--max-lines", type=int, default=120)
diagnose.add_argument("--model")
diagnose.add_argument("--json", action="store_true")
```

- [ ] **Step 4: Add text and JSON result rendering**

In JSON mode, print exactly one JSON object to stdout with `schema_version: 1`, `provider: "deepseek"`, the provider-reported `model`, and the accepted/rejected arrays. In text mode, list accepted and rejected titles with rejection reasons and print: `Evidence checks confirm source grounding only; they do not prove the diagnosis is correct.` Preserve current exit-code handling for all existing commands.

The JSON result keys are fixed:

```python
{
    "schema_version": 1,
    "provider": "deepseek",
    "model": result.model,
    "accepted": report["accepted"],
    "rejected": report["rejected"],
}
```

- [ ] **Step 5: Run focused and full tests**

Run: `python3 -m unittest tests.test_cli -v`

Expected: all old and new CLI tests PASS; every test uses the mocked transport.

Run: `python3 -m unittest discover -s tests -q`

Expected: the full suite PASS with no API Key and no network access.

- [ ] **Step 6: Commit the CLI unit**

```bash
git add repo_doctor/cli.py tests/test_cli.py
git diff --cached --check
git commit -m "feat: add DeepSeek diagnose command"
```

## Task 4: Document cloud data flow and perform final acceptance

**Files:**
- Modify: `README.md`

**Interfaces:**
- No code interface changes.
- README accurately distinguishes local static analysis/context/evidence checks from remote DeepSeek inference.
- README includes a working shell example using `DEEPSEEK_API_KEY`, optional `DEEPSEEK_MODEL`, and the `diagnose` command.

- [ ] **Step 1: Update the quick start and diagnosis documentation**

Update the README introduction to say DeepSeek diagnosis is optional and requires an API Key, while static commands work offline. Keep the manual context/ChatGPT workflow. Add a DeepSeek section with these commands:

```bash
export DEEPSEEK_API_KEY="your-key"
python3 -m repo_doctor context /path/to/python-repo 'app/services/user.py::UserService.create' --max-lines 120
python3 -m repo_doctor diagnose /path/to/python-repo 'app/services/user.py::UserService.create'
```

Explain that `diagnose` sends only the selected bounded source context and its repository-relative evidence metadata to DeepSeek; it does not send the entire repository. Warn that selected code can contain secrets and should be inspected with `context`. State that accepted findings have grounded quotes but still need human review and runtime/test confirmation. Replace the old claim that automatic API diagnosis is outside V1 with the remaining exclusions: patches, test execution, and broader multi-symbol review.

- [ ] **Step 2: Run the full acceptance checks**

Run: `python3 -m unittest discover -s tests -v`

Expected: all tests PASS without a DeepSeek API Key and without network access.

Run: `python3 -m compileall -q repo_doctor`

Expected: exit code 0.

Run: `python3 -m repo_doctor --help` and `python3 -m repo_doctor diagnose --help`

Expected: help lists `diagnose`, its path/symbol arguments, line budget, model override, and JSON output.

Run: `git diff --check`

Expected: no whitespace errors. Also run `git diff --cached --check` on any staged changes before committing.

- [ ] **Step 3: Review the final diff against every V3 acceptance criterion**

Confirm the only network request path is the explicit `diagnose` command; no secret is printed or persisted; request tests do not reach the network; other commands stay offline; model output is an object with a list-valued `findings`; all accepted evidence is inside submitted blocks; text/JSON output and exit codes match the spec; and README states the cloud data boundary accurately. Do not make a live API call unless the user explicitly configured a key and separately asks for that smoke test.

- [ ] **Step 4: Commit the documentation and acceptance unit**

```bash
git add README.md
git commit -m "docs: explain DeepSeek diagnosis data flow"
```

## Final Acceptance Checklist

- [ ] Existing offline commands work without credentials and make no HTTP calls.
- [ ] Missing credentials, invalid symbol, invalid line limit, and source over 64 KiB fail before the transport is called.
- [ ] DeepSeek transport targets only the official HTTPS endpoint, uses JSON mode, performs one non-streaming request, and does not retry.
- [ ] Model response must be a JSON object with a `findings` list; malformed and truncated responses fail safely.
- [ ] Every accepted finding passes repository grounding and submitted-context scope checks.
- [ ] Text output, JSON output, stderr preflight summary, and exit codes match the V3 specification.
- [ ] README states what is sent to the cloud and warns that context may contain secrets.
- [ ] Full unit suite and compile/help checks pass without a live API call.
