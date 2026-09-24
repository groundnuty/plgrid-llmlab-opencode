# Model reference — PLGrid Forge in OpenCode

Every number here was measured against the live gateway (`https://llmlab.plgrid.pl/api/v1`)
with OpenCode 1.18.5, in one benchmark run on 2026-09-24 from a single grant:
[report](benchmarks/results/bench-20260924.txt),
[per-run table](benchmarks/results/bench-20260924.tsv). Nothing is copied from model
cards; where a figure comes from published third-party benchmarks it says so.

Re-check any of it yourself with the commands in [reproducing.md](reproducing.md), or
re-run the whole benchmark with [`bench-all.sh`](benchmarks/README.md).

---

## 1. Function calling is the gate

OpenCode is an agent harness: it asks the model for structured `tool_calls` and then
executes them. A model that cannot emit them cannot read a file, write a file or run
a command — only produce chat text.

`GET /api/v1/models-plgrid-format` returns a `function_calling_supported` boolean per
model. **14 of the 20 active chat models have it**, and the plugin's `tool_call` flags
match the gateway's for all 20. The embedding model is excluded from the plugin.

The field is the right default, but it can lag the deployment: `Qwen/QwQ-32B` is
listed without function calling and still returns structured `tool_calls`. When the
flag and the response disagree, the response wins ([pitfalls.md](pitfalls.md)).

## 2. The tool-capable models

Each model ran two agentic fixtures three times, blind (method in
[benchmarks/](benchmarks/)). **Correct** is hidden cases passed out of 22 — 14 on `calc`,
8 on `ledger` — cases the model never saw, run after it made its own test suite pass,
one figure per run. **tok/s** is the generation rate for a forced 300-token output and
**e2e** the rate over total wall time including the first token (median of 5 rounds,
first token about 0.5 s for every model in this run). **Task s** is the median wall
time of a whole agentic run, calc / ledger — what an agent actually experiences.

| Model | Context | Correct (3 runs) | tok/s | e2e | Task s |
|---|---|---|---|---|---|
| `deepseek-ai/DeepSeek-V4.1-Flash` | **1M** | **22 · 22 · 22** | 88 | 72 | 19 / 27 |
| `deepseek-ai/DeepSeek-V4-Flash` | 700k | **22 · 22 · 22** | 107 | 91 | 35 / 31 |
| `zai-org/GLM-5.3-Flash` | **1M** | **22 · 22 · 22** | — ¹ | — ¹ | 23 / 33 |
| `Qwen/Qwen3.8-27B` | 262k | **22 · 22 · 22** | 88 | 77 | 42 / 82 |
| `Qwen/Qwen3.6-35B-A3B` | 262k | 22 · 22 · 22 ⚠ | **192** | **129** | 17 / 21 |
| `Qwen/Qwen3.6-27B` | 262k | **22 · 22 · 22** | 49 | 45 | 55 / 59 |
| `google/gemma-4-31B` | 262k | **22 · 22 · 22** | 40 | 38 | 30 / 42 |
| `deepseek-ai/DeepSeek-V4-Flash-0731` | 700k | 21 · 22 · 22 | 106 | 90 | 20 / 21 |
| `Qwen/Qwen3-Coder-30B-A3B-Instruct` | 249k | 21 · 14 · 22 | 145 | 114 | 30 / 36 |
| `meta-llama/Llama-3.3-70B-Instruct` | 128k | 5 · 5 · 5 | 33 | 31 | 81 / 107 |
| `speakleash/Bielik-11B-v3.0-Instruct` | 32k | 0 · 0 · 0 | 61 | 55 | 40 / 77 |

¹ `GLM-5.3-Flash` timed out in the throughput pass of this run, though it completed
every agentic run — among the faster ones, going by task time.

Not measurable from this grant: `Qwen3.5-122B-A10B` and `Qwen3.5-397B-A17B-FP8`
(`not available for grant`). `GLM-5.2-FP8` (393k context) is listed as active but timed
out on every request during this run.

> **Throughput depends on gateway load.** The gateway is shared. Under load the same
> models measure 2–8× slower, and the first token can take several seconds — which
> matters more for an agent than the generation rate, because an agent makes many
> short requests. Read tok/s as best-case, and do not rank two models whose figures
> are close.

Published SWE-bench Verified, for context only (third-party, different harnesses):
Qwen3.6-27B 77.2 · Qwen3.6-35B-A3B 73.4 · Qwen3-Coder-30B 50.3–72.5
(scaffold-dependent).

## 3. A green test suite is not a correct solution

The most useful thing these fixtures show, and the reason they ship with differential
scorers.

- **`Llama-3.3-70B` passed the whole `calc` suite and got every hidden case wrong.**
  Its evaluator returns `24.0` for `2 * 3 * 4`: equal to `24` for the suite's `==`, the
  wrong type for anything that relies on an `int`. `pytest` reported `6 passed`; the
  hidden cases scored 0/14. In its other two `calc` runs it left a syntax error
  (a bad indent, a missing `:`), so the code does not import at all.
- **`Llama-3.3-70B` rewrites the specification.** In all three `ledger` runs it edited
  `test_ledger.py` despite the prompt forbidding it, weakening the tests to fit its own
  code. The md5 guard catches it, and the runner scores against the original tests.
- **`Bielik-11B-v3.0` fabricates results.** It scored 0 in every run while reporting
  success — in one `calc` run it printed `24 passed in 0.12s` for a six-test suite and
  "All tests have been successfully fixed", having changed no file at all.
- **`Qwen3.6-35B-A3B` can be silently wrong.** It is perfect in this run, but on these
  same fixtures it has twice produced a `calc` solution whose whole suite passed while
  chained multiplication was wrong (`2 * 3 * 4` → `10`, or → `6`): a two-pass
  algorithm that skips the second of two consecutive `*`. Its other runs were clean, so
  the failure is intermittent and its rate unknown — which is exactly what makes it
  unsuitable for unattended edits. The runs are recorded in
  [PR #1](https://github.com/groundnuty/plgrid-llmlab-opencode/pull/1).
- **`Qwen3-Coder-30B` sometimes announces a tool call and stops.** In one `ledger`
  run it read two files, wrote "Let me examine the current implementation of
  money.py", and ended its turn without calling a tool: 9 seconds, exit 0, nothing
  changed, 0/8. It can also emit a tool call as plain text that OpenCode cannot parse.
  Either way `opencode run` reports success.
- **The most common miss is `Money == 42`.** An `__eq__` that reads `other.amount`
  without checking the type raises `AttributeError` instead of returning `False`; the
  suite never compares `Money` with anything else.

Worth recording the positive too: 21 of the 26 `ledger` solutions that passed the suite
reached for `decimal.Decimal` unprompted when a test required money not to drift,
which is the right instinct. In all 66 runs, no model other than `Llama-3.3-70B` touched
the test file, and no run showed any sign of a model reading or modifying a scorer.

Practical consequences:

- **Do not give a model unattended work because it is fast.** Give it unattended work
  because it has been right every time you checked.
- **When you specify work with tests, assume the model optimises for the tests.**
  Include the edge cases you care about, or verify separately.
- **Never trust a model's report of its own test run.** Re-run the tests yourself.

## 4. The 6 models without function calling

`QwQ-32B` · `Qwen3-VL-8B-Instruct` · `Bielik-11B-v2.6-Instruct` ·
`Llama-PLLuM-70B-chat-250801` · `pllum-12b-nc-chat-250715` · `sqrl-9b`
*(not reachable from any grant we have tested)*

They are still worth having configured for chat, translation and Polish-language
work — **but only through a tools-disabled agent.**

Measured throughput (same method as §2): `Qwen3-VL-8B` 87, `QwQ-32B` 83,
`Llama-PLLuM-70B` 71, `PLLuM-12B` 59, `Bielik-11B-v2.6` 53 tok/s.

### `tool_call: false` is not enough on its own

Marking a model `tool_call: false` does *not* stop OpenCode sending tools. The
built-in `build` and `plan` agents attach a tools array to every request, and the
gateway rejects it outright:

```
Bad Request: {"detail": "\"auto\" tool choice requires --enable-auto-tool-choice
and --tool-call-parser to be set", "status_code": 400}
```

Both agents fail, so the model is **completely unusable**, not merely tool-less. The
fix is a dedicated agent with tools switched off — the `chat` agent in this repo's
`opencode.json`:

```json
"agent": { "chat": { "mode": "primary", "tools": { "*": false } } }
```

In the TUI, cycle to it with **Tab** before selecting any of these models.

### Two special cases

`Bielik-11B-v3.0-Instruct` **has** function calling but is worse than the models that
lack it: it scores 0 on both fixtures and reports passes it never achieved (§3). It
also emits `<think>` blocks in the content channel, which no configuration can
redirect. Treat it as a chat/translation model, and never trust its self-reported test
results.

`Qwen3-VL-8B-Instruct` is the only vision model. `attachment: true` is verified —
given a base64 PNG via `image_url` it correctly described the image — but it cannot
call tools, so use it through the `chat` agent.

## 5. Access: grants, and non-commercial flags

- **Grant access is per key.** An API key belongs to one grant, and several models
  are restricted to some grants: in this run `Qwen3.5-122B-A10B` and
  `Qwen3.5-397B-A17B-FP8` answered `not available for grant`. The default model,
  `DeepSeek-V4.1-Flash`, and `DeepSeek-V4-Flash` are restricted too. The catalog's
  `accessible` field is answered for your account, so check your own with
  [`list_models.py`](list_models.md) rather than trusting anyone else's list. If a
  model you want is not available, apply for it via the PLGrid Helpdesk — access is
  granted per grant.
- **Non-commercial flags** (`DeepSeek-V4.1-Flash`, `GLM-5.2-FP8`, `GLM-5.3-Flash`,
  `Qwen3.6-27B`, `gemma-4-31B`, `PLLuM-12B`) do not affect academic or research use,
  which is what PLGrid grants are for. They only bind users with a commercial
  affiliation.

Credit cost per million tokens ranges from 0.05 (embedding) to 7.15
(`Llama-PLLuM-70B`), and a typical short agentic exchange costs a small fraction of a
credit. Cost is unlikely to drive your model choice; capability and grant access will.
Per-request usage is returned as `used_plgrid_credits`.

## 6. Recommended assignments

Reasoning behind the agents in `opencode.json`:

| Role | Model | Why |
|---|---|---|
| default, planning, research | `DeepSeek-V4.1-Flash` | Perfect record, 1M context |
| fast mechanical edits (`fastfix`) | `DeepSeek-V4.1-Flash` | Fastest to finish a task among the models with a perfect record |
| code review | `Qwen3.6-27B` | Perfect record, and a different model family from the author; slow, a deliberate quality-over-speed trade |
| `small_model` (titles) | `gemma-4-31B` | Reliable, open to all grants |
| Polish-language chat | `Bielik-11B-v3.0` | Via the `chat` agent only |

**If your grant cannot use the DeepSeek models**, the best choices open to all grants
are `Qwen3.6-27B` for the default, `architect` and `researcher` roles, and
`gemma-4-31B` for `fastfix` — both perfect in every run here. `Qwen3.6-35B-A3B` is the
fastest model and open to all grants, but see §3 before letting it edit unattended.

## 7. Honest limits

These are open-weight models. The best of them are roughly Sonnet-class on a good day;
the rest sit below that. For well-specified single-file and small multi-file work they
are genuinely good and fast. For multi-file refactors with ambiguous requirements,
expect a real gap against frontier models.

The benchmark behind this page is two fixtures in one language, on self-contained
files, three runs per model, from one grant. That is enough to tell "reliable" from
"not" on these fixtures, not to estimate failure rates, and it says nothing about
large codebases, long sessions near context limits, or ambiguous requirements.

What you get in exchange for the capability gap: data stays on Polish academic
infrastructure, administrators cannot read request or response content, and nothing
goes to a foreign vendor.
