# Model reference — PLGrid Forge in OpenCode

Every number here was measured against the live gateway (`https://llmlab.plgrid.pl/api/v1`)
with OpenCode 1.18.5. Nothing is copied from model cards. Where a figure comes from
published third-party benchmarks it says so.

Re-check any of it yourself with the commands in [reproducing.md](reproducing.md).

---

## 1. Function calling is the gate

OpenCode is an agent harness: it asks the model for structured `tool_calls` and then
executes them. A model that cannot emit them cannot read a file, write a file or run
a command — only produce chat text.

The gateway is authoritative on this. `GET /api/v1/models-plgrid-format` returns a
`function_calling_supported` boolean per model. **Only 11 of the 17 chat models in
the plugin have it** (the embedding model is excluded from the plugin).

Trust that field over inference. Probing with `tool_choice: "auto"` and watching for
an HTTP 400 gives a *false positive* on at least one model (`QwQ-32B`): vLLM accepts
the parameter, but the model has no tool-call parser configured, so nothing usable
comes back.

## 2. The tool-capable models

Measured on two agentic fixtures plus hidden differential cases (method in
[benchmarks/](benchmarks/)). "Correct" counts hidden cases the model never saw, run
*after* it made its own test suite pass. Throughput is median of 3 at the gateway
with an identical 300-token budget.

| Model | Context | tok/s | Correct | Notes |
|---|---|---|---|---|
| `deepseek-ai/DeepSeek-V4.1-Flash` | **1M** | — | not measured | Current default; context measured, reliability not yet |
| `zai-org/GLM-5.2-FP8` | 393k | 62 | 22/22 | Strongest measured overall |
| `Qwen/Qwen3-Coder-30B-A3B-Instruct` | 249k | 90 | 21/22 | One missing `isinstance` guard |
| `google/gemma-4-31B` | 262k | 37 | 22/22 | Not a coding model, but reliable |
| `Qwen/Qwen3.6-27B` | 262k | 26 | 22/22 | Most thorough, slowest by 6× |
| `Qwen/Qwen3.6-35B-A3B` | 262k | **165** | **19/22** ⚠ | Fastest; see §3 |
| `speakleash/Bielik-11B-v3.0-Instruct` | 32k | — | see §4 | Polish; not for agentic work |

Four more tool-capable models (`Llama-3.3-70B-Instruct`, `Qwen3.8-27B`,
`Qwen3.5-122B-A10B`, `Qwen3.5-397B-A17B-FP8`) have not been benchmarked; the
Qwen3.5/3.8 rows are also grant-gated here. `Bielik-11B-v3.0` is tool-capable but
chat-only (§4).

Published SWE-bench Verified, for context only (third-party, different harnesses):
Qwen3.6-27B 77.2 · Qwen3.6-35B-A3B 73.4 · Qwen3-Coder-30B 50.3–72.5
(scaffold-dependent). GLM-5.2 reports SWE-bench **Pro** 62.1 and MCP-Atlas 77.0.

## 3. A green test suite is not a correct solution

The most useful thing this exercise found, and the reason the fixtures ship with
differential scorers.

**`Qwen/Qwen3.6-35B-A3B` produced a solution where `pytest` reported `6 passed`
while `evaluate("2 * 3 * 4")` returned `10` instead of `24`.** Its two-pass
algorithm collapsed consecutive multiplications — a case the specification happened
never to exercise. In a second run on the same task with the same prompt it produced
a clean recursive-descent parser with correct precedence and associativity.

The two outcomes are indistinguishable from outside without hidden test cases.

Practical consequences:

- **Do not give this model unattended work**, however fast it is. Use it where a
  human or another agent reviews the diff.
- **When you specify work with tests, assume the model optimises for the tests.**
  Include the edge cases you care about, or verify separately.

`Qwen3-Coder-30B`'s single miss is the same category, narrower: a missing
`isinstance` guard in `__eq__`, so `Money(10, "PLN") == 42` raised `AttributeError`
instead of returning `False`. Untested behaviour is unconstrained behaviour.

Worth recording the positive too: five of six models reached for `decimal.Decimal`
unprompted when a test required money not to drift, which is the right instinct.

Across 18 agentic runs, **no model edited the test suite** to force a pass (md5-guarded),
and **no raw tool-call markup leaked** into output.

## 4. The 6 models without function calling

`QwQ-32B` · `Qwen3-VL-8B-Instruct` · `Bielik-11B-v2.6-Instruct` ·
`Llama-PLLuM-70B-chat-250801` · `pllum-12b-nc-chat-250715` ·
`DeepSeek-V4-Flash-0731` *(also grant-gated)*

They are still worth having configured for chat, translation and Polish-language
work — **but only through a tools-disabled agent.**

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

### One special case worth knowing

`Bielik-11B-v3.0-Instruct` **has** function calling and writes valid Python, but it
loses track of the working directory: in 2 of 3 runs it wrote its output file to the
*parent* directory and then ran the verification command in the child, failing with
`No such file or directory` and never recovering. It also emits `<think>` blocks in
the content channel, which no configuration can redirect. Treat it as a
chat/translation model.

`Qwen3-VL-8B-Instruct` is the only vision model. `attachment: true` is verified —
given a base64 PNG via `image_url` it correctly described the image — but it cannot
call tools, so use it through the `chat` agent.

## 5. Two access gates beyond function calling

`models-plgrid-format` also returns `accessible` (which grants may call the model)
and `is_commercial`.

- **Grant gating is a hard failure.** `zai-org/GLM-5.2-FP8` and the current default
  `deepseek-ai/DeepSeek-V4.1-Flash` are restricted to specific grants, and
  `Qwen3.5-122B-A10B` / `Qwen3.5-397B-A17B-FP8` / `Qwen3.8-27B` /
  `DeepSeek-V4-Flash-0731` return `"not available for grant 'N'"` for this account.
  If the default model fails this way for you, see the model-swap note in the root
  [README](../README.md#known-issues).
- **Non-commercial flags** (`GLM-5.2-FP8`, `Qwen3.6-27B`, `gemma-4-31B`,
  `DeepSeek-V4.1-Flash`, `DeepSeek-V4-Flash-0731`, `PLLuM-12B`) do not affect
  academic or research use, which is what PLGrid grants are for. They only bind users
  with a commercial affiliation, who should substitute `Qwen3.6-35B-A3B` or
  `Qwen3-Coder-30B-A3B`.

Credit cost per million tokens ranges from 0.05 (embedding) to 7.15
(`Llama-PLLuM-70B`), and a typical short agentic exchange costs a small fraction of
a credit. Cost is unlikely to drive your model choice; capability and grant access
will. Per-request usage is returned as `used_plgrid_credits`.

## 6. Recommended assignments

Reasoning behind the agents in `opencode.json`:

| Role | Model | Why |
|---|---|---|
| default, planning, research | `DeepSeek-V4.1-Flash` | Current default: 1M context, but **no benchmark score yet** — swap to `GLM-5.2-FP8` if you want the measured option |
| fast mechanical edits | `Qwen3.6-35B-A3B` | Fastest model; reassigned to `fastfix` when `GLM-4.7-Flash` went inactive — see the warning in §3 |
| code review | `Qwen3.6-27B` | Perfect correctness; slowest measured (26 tok/s), a deliberate quality-over-speed trade |
| `small_model` (titles) | `gemma-4-31B` | Cheap, reliable, no reasoning overhead |
| Polish-language chat | `Bielik-11B-v3.0` | Via the `chat` agent only |

Note what is *not* recommended: `Qwen3.6-35B-A3B` for unattended edits despite being
the fastest model by 34%. Speed is worth nothing if the output is silently wrong.
It is currently the `fastfix` model only because the previous choice was retired —
treat its diffs accordingly.

## 7. Honest limits

These are open-weight models. `GLM-5.2` and `Qwen3.6-27B` are roughly Sonnet-class
on a good day; the rest sit below that. For well-specified single-file and small
multi-file work they are genuinely good and fast. For multi-file refactors with
ambiguous requirements, expect a real gap against frontier models.

The benchmarks behind this page are two fixtures and 18 runs in one language, on
self-contained files. They establish that four of the five benchmarked models are
reliably correct on multi-file defect fixing and small design changes, and they
caught one real reliability problem. They say nothing about large codebases, long
sessions near context limits, or ambiguous requirements. `Qwen3.6-35B-A3B`'s
inconsistency is one observation in three runs — the failure is confirmed, its
*rate* is unknown. `DeepSeek-V4.1-Flash` has not been through the fixtures at all.

What you get in exchange for the capability gap: data stays on Polish academic
infrastructure, administrators cannot read request or response content, and nothing
goes to a foreign vendor.
