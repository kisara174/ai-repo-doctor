# DeepSeek live smoke — 2026-09-25

## Result

One transport attempt was made with `deepseek-flash`. The CLI returned `Could not connect to DeepSeek API`; no valid provider response or usage record was received. The outcome is a connection failure, not evidence that the API key is invalid. Whether the provider received the request or charged for it is unknown. No retry, model switch, key change, or second API call was made.

This run does **not** qualify as a successful connectivity check and provides no model-quality evidence. M07 remains blocked.

## Request audit

The analyzer code was at clean HEAD `24fb68ce67297c80d0c643e6b87802b2e6b009cb`. The intended sample was manifest case `requests-6628-bug`, pinned to Requests commit `7a13c041dbef42f9f3feb14110f02626f6892e9a` at checkout `requests-7a13c041dbef`. Its previously reviewed context had 44 lines / 2,170 source bytes and a 5,594-byte serialized request.

The command accidentally selected a different local Requests checkout:

```sh
python3 -m repo_doctor diagnose /tmp/ai-repo-doctor-diagnosis-checkouts/requests-0b401c76b6e8 src/requests/exceptions.py::JSONDecodeError --max-lines 120 --model deepseek-flash --json
```

That checkout was clean at commit `0b401c76b6e80a4eecf3c690085b2553f6e261ca`, which is not the manifest pin. The CLI reported 56 source lines / 2,766 source bytes. A read-only reconstruction of the exact serialized request gives 6,620 bytes, SHA-256 `4b0d2f67be93a44051d6ba0c875d709722a79ed6cac116f0a0af129731e32faf`; its context SHA-256 is `18593348bbf4768f285147ff49eea7c5ee94cb2b893564423e3ee35716968237`. Ground truth was not present in the serialized context.

The wrong checkout selection means this attempt did not exercise the pre-reviewed frozen case. This was an execution error by the primary agent and is retained in the record; no quality or sample-pair conclusion is drawn from it.

The request used the client's fixed 4,096 output-token limit, 60-second timeout, 256 KiB request limit, and 2 MiB response limit. At the official peak prices, a byte-based planning estimate is about $0.0069 for this request at those limits; it is not a billing record. DeepSeek currently lists `deepseek-flash` as DeepSeek-V4.1-Flash and publishes separate peak/off-peak token prices on its [Models & Pricing page](https://api-docs.deepseek.com/quick_start/pricing/). The API returned no usage data, so actual billing remains unknown.

## Gate

Do not retry within this smoke task. Any future connectivity attempt must be a new, explicitly bounded run using the correct pinned checkout and reviewed payload. Until a valid response is available and reviewed, do not create model scores or claims.
