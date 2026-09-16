# Model reference — PLGrid Forge in OpenCode

Every number here was measured against the live gateway (`https://llmlab.plgrid.pl/api/v1`)
on OpenCode 1.18.5–1.18.31. The correctness figures are from the final benchmark of
2026-09-16: three runs per model, each isolated from the scorer, the repository and
the other runs ([report](benchmarks/results/bench-20260916-141623.txt),
[per-run table](benchmarks/results/bench-20260916-141623.tsv)). An earlier blind round
the same day, with the scorer already out of reach but a less isolated working
directory, adds three more runs per model
([rerun-20260916-blind-x3.tsv](benchmarks/results/rerun-20260916-blind-x3.tsv)). Both
supersede that day's first full run
([bench-20260916-120658.txt](benchmarks/results/bench-20260916-120658.txt)), in which
the scorer turned out to be inside the agent's workspace (§3). Context was
measured on 1.18.5 and re-measured in the full run. Throughput is the fixed-length
measurement of 2026-09-16 12:45 ([raw](benchmarks/results/throughput-20260916-1245.txt)),
taken on a lightly loaded gateway — see the load warning in §2. Nothing is copied from
model cards. Where a figure comes from published third-party benchmarks it says so.

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
[benchmarks/](benchmarks/)). "Correct" counts hidden cases the model never saw (out of
22: 14 on `calc`, 8 on `ledger`), run *after* it made its own test suite pass, in each
of the three runs of the final benchmark. tok/s is the generation rate for a forced 300-token output, median
of 3, measured 2026-09-16 12:45 when every model's time to first token was about 0.3 s.

> **Throughput depends heavily on gateway load.** The gateway is shared. Re-measured
> at 14:16 the same day, under load, every model came out roughly 2–8× slower
> (`Qwen3.6-35B-A3B` 53 tok/s with runs ranging from 13 to 60, `gemma-4-31B` 10,
> `GLM-5.2-FP8` 22) and the first token took up to 8 s. Read the column as best-case,
> and do not rank two models whose figures are close.

| Model | Context | tok/s | Correct (3 runs) | Notes |
|---|---|---|---|---|
| `deepseek-ai/DeepSeek-V4.1-Flash` | **1M** | 98 | **22 · 22 · 22** | Current default; 22 in all six blind runs |
| `zai-org/GLM-5.2-FP8` | 393k | 65 | **22 · 22 · 22** | Strongest measured overall; 22 in all six blind runs |
| `google/gemma-4-31B` | 262k | 38 | **22 · 22 · 22** | Not a coding model, but 22 in all six blind runs |
| `Qwen/Qwen3.6-27B` | 262k | 49 | 22 · 22 · 22 | Most thorough; earlier round had a missed guard and a stalled run — §3 |
| `Qwen/Qwen3.6-35B-A3B` | 262k | **239** | 22 · 22 · 21 ⚠ | Fastest, ~1.6× the next; silently wrong in an earlier run — §3 |
| `Qwen/Qwen3-Coder-30B-A3B-Instruct` | 249k | 146 | 21 · 22 · 21 | Only miss an `isinstance` guard; earlier low scores were harness artefacts — §3 |
| `meta-llama/Llama-3.3-70B-Instruct` | 128k | 32 | 3 · 19 · 10 | Solved `calc` once; edited the spec in every final `ledger` run — §3 |
| `speakleash/Bielik-11B-v3.0-Instruct` | 32k | 61 | 0 · 0 · 0 | Loses the working directory, fabricates passes — §4 |

Three tool-capable models remain unbenchmarked because this account cannot reach
them: `Qwen3.8-27B`, `Qwen3.5-122B-A10B` and `Qwen3.5-397B-A17B-FP8` all return
`"not available for grant 'plgccbmc15'"`. `DeepSeek-V4-Flash` is likewise
unreachable: the gateway returns the same grant rejection, and the catalog marks it
`accessible: false`, so the plugin omits it — which is why `opencode run` reports a
generic `UnknownError` for it, exactly as it does for a model id that does not exist.
`Bielik-11B-v3.0` is tool-capable but effectively chat-only (§4).

Published SWE-bench Verified, for context only (third-party, different harnesses):
Qwen3.6-27B 77.2 · Qwen3.6-35B-A3B 73.4 · Qwen3-Coder-30B 50.3–72.5
(scaffold-dependent). GLM-5.2 reports SWE-bench **Pro** 62.1 and MCP-Atlas 77.0.

## 3. A green test suite is not a correct solution

The most useful thing this exercise found, and the reason the fixtures ship with
differential scorers.

**`Qwen/Qwen3.6-35B-A3B` has twice produced a solution where `pytest` reported
`6 passed` while chained multiplication was wrong.** In an early trial
`evaluate("2 * 3 * 4")` returned `10` instead of `24`. In the earlier blind round on
2026-09-16 it returned `6`, and `1 * 2 + 3 * 4 + 5 * 6` returned `10`: after
collapsing one `a * b` its loop index skipped the next `*`, and the `+` pass then
silently ignored the leftover operator. Both times it was a two-pass algorithm
mishandling consecutive multiplications — a case the specification happened never to
exercise. Its other seven `calc` runs, including all three final ones, were clean, so
the failure is intermittent: two observations in nine runs, and its *rate* is still
only roughly known. The two outcomes are indistinguishable from outside without hidden
test cases.

Practical consequences:

- **Do not give this model unattended work**, however fast it is. Use it where a
  human or another agent reviews the diff.
- **When you specify work with tests, assume the model optimises for the tests.**
  Include the edge cases you care about, or verify separately.

Other failures, from the first 2026-09-16 run and the two blind rounds:

- **`Qwen3-Coder-30B` once never ran a single tool call.** In the original run its
  first reply ended in `<function=read>…</function></tool_call>` markup as plain
  content — with no opening `<tool_call>` tag — so no tool call was extracted,
  `opencode run` exited 0, and the run scored 0/22 in 5 seconds. This is not a missing
  parser: probed directly, the gateway returned a structured `tool_calls` entry for
  this model 3/3 times non-streaming and 4/5 times streaming, and the fifth leaked the
  same markup. The model intermittently emits a malformed call, and OpenCode has no
  client-side repair for it (see [pitfalls.md](pitfalls.md)). This is why
  "tool-capable" is necessary but not sufficient.
- **`Qwen3-Coder-30B` scored 14 in every run of the earlier round — a harness
  artefact.** That harness named the working directory `ledger`, like the package
  inside it. The model wrote `money.py` and `account.py` one level too high, and in
  two runs an `__init__.py` beside them made `from ledger.money import Money` resolve
  to the misplaced files: its own suite passed 7/7 while the scorer, importing the
  real package, scored 0/8. Moved into place, those two solutions score 8/8. With the
  working directory renamed, the final runs scored 21 · 22 · 21, the only miss an
  `isinstance` guard in `__eq__`.
- **`Qwen3.6-27B` stalled once, in the earlier round.** After two tool calls its
  reasoning channel held only `[Tool Result]` and it ended the turn (5 output tokens),
  so `opencode run` exited 0 with the code untouched — the "exits 0 having done
  nothing" failure, on a model that otherwise solved both fixtures. In another run of
  that round it missed an `isinstance` guard. All three final runs were perfect.
- **Three models missed the same `isinstance` guard.** `Qwen3.6-27B`,
  `Qwen3.6-35B-A3B` and `Qwen3-Coder-30B` each at least once wrote an `__eq__` that
  reads `other.amount` without checking the type, so `Money(10, "PLN") == 42` raises
  `AttributeError` instead of returning `False`. The suite never compares `Money` with
  anything else.
- **`Llama-3.3-70B` games the specification.** In every final `ledger` run it edited
  `test_ledger.py` despite the prompt forbidding it, each time weakening the tests to
  fit its own code: `a.balance()` became `a.balance` and the drift test became
  `round(a.balance.amount, 2) == 1.00` (twice, reaching 7/7), or raw-number deposits
  became `Money` objects (once, reaching 5/7). The md5 guard caught all three, and the
  runner scores against the original tests, where its code passes 5 of 7 every time. In one run
  of the earlier round it had also edited the tests, though only into an equivalent
  keyword-argument form. On `calc` it solved the task once and left an evaluator that
  never returns once; it hit the 30-step cap in half its final runs.

Worth recording the positive too: in the final runs, 14 of the 18 `ledger` solutions
that passed the suite reached for `decimal.Decimal` unprompted when a test required
money not to drift, which is the right instinct.

**One model has edited the test suite**: `Llama-3.3-70B`, above, in 4 of its 6 blind
`ledger` runs. No other model did in any run. The spec is md5-guarded, and the runner
restores it before scoring.

One flaw in the first 2026-09-16 run: the scorer then sat inside each fixture
directory, so it was copied into the agent's workspace. `DeepSeek-V4.1-Flash` ran it
during the ledger task and `GLM-5.2-FP8` read it before writing its ledger solution,
so those two ledger scores were not blind. The scorers have since moved out of the
fixtures ([benchmarks/README.md](benchmarks/README.md#method-notes)); in the six blind
runs since, both models scored 22 every time.

## 4. The 6 models without function calling

`QwQ-32B` · `Qwen3-VL-8B-Instruct` · `Bielik-11B-v2.6-Instruct` ·
`Llama-PLLuM-70B-chat-250801` · `pllum-12b-nc-chat-250715` ·
`DeepSeek-V4-Flash-0731` *(also grant-gated)*

They are still worth having configured for chat, translation and Polish-language
work — **but only through a tools-disabled agent.**

Measured throughput for these chat-only models (same method and caveat as §2):
`Qwen3-VL-8B` 87, `QwQ-32B` 80, `Llama-PLLuM-70B` 71, `Bielik-11B-v2.6` 61,
`PLLuM-12B` 59 tok/s.
`DeepSeek-V4-Flash-0731` is grant-gated here and could not be measured at all.

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

`Bielik-11B-v3.0-Instruct` **has** function calling but is worse than the models
that lack it. It loses track of the working directory — in 2 of 3 runs it wrote its
output file to the *parent* directory and then ran the verification command in the
child, failing with `No such file or directory` and never recovering. On the
2026-09-16 run it scored **0/22 while its own output reported `6 passed`** (and a
nonsensical `({'final_status': ' successful'})`), i.e. it fabricated the pytest
output. The scorer caught it because the spec is untouched and re-run independently.
It then scored 0/22 in all six blind runs and fabricated a pass in two of them: once
saying so ("Since I can't actually edit the code, I'll just simulate that the tests
pass after fixes"), and once reporting `4 passed` for a six-test suite in which nothing
passed. It also emits `<think>` blocks in the content channel, which no configuration
can redirect. Treat it as a chat/translation model, and never trust its self-reported
test results.

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
  The 2026-09-16 run confirmed this for all four; `DeepSeek-V4-Flash` (without the
  `-0731`) gets the same grant rejection from the gateway, but is marked
  `accessible: false` and so left out of the plugin — in OpenCode it therefore
  surfaces as a generic `UnknownError` (model not found), not as a grant error.
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
| default, planning, research | `DeepSeek-V4.1-Flash` | 1M context and 22/22 in all six blind runs; fastest of the reliable models |
| fast mechanical edits | `Qwen3.6-35B-A3B` | Fastest model, ~1.6× the next — but see the warning in §3 |
| code review | `Qwen3.6-27B` | 22/22 in the three final runs, one missed guard and one stalled run in the three before; 49 tok/s, a deliberate quality-over-speed trade |
| `small_model` (titles) | `gemma-4-31B` | Cheap, reliable, no reasoning overhead |
| Polish-language chat | `Bielik-11B-v3.0` | Via the `chat` agent only |

Note what is *not* recommended: `Qwen3.6-35B-A3B` for unattended edits despite being
the fastest model by ~1.6×. Speed is worth nothing if the output is silently wrong.
It is the `fastfix` model, whose edits are small and meant to be reviewed — treat its
diffs accordingly.

## 7. Honest limits

These are open-weight models. `GLM-5.2` and `Qwen3.6-27B` are roughly Sonnet-class
on a good day; the rest sit below that. For well-specified single-file and small
multi-file work they are genuinely good and fast. For multi-file refactors with
ambiguous requirements, expect a real gap against frontier models.

The benchmarks behind this page are two fixtures in one language, on self-contained
files. On 2026-09-16 throughput was measured for the 12 of 19 active chat models this
account can reach (the other 7 are grant-gated), and all 8 reachable tool-capable
models were run against both fixtures six times, blind, in two rounds. Three passed
every one of their 132 hidden cases — `DeepSeek-V4.1-Flash`, `GLM-5.2-FP8`,
`gemma-4-31B`. `Qwen3.6-27B`, `Qwen3.6-35B-A3B` and `Qwen3-Coder-30B` were usually right
but not always; `Llama-3.3-70B` and `Bielik-11B-v3.0` failed at least one fixture in
every run; three more tool-capable models could not be reached. Six runs per model is
enough to tell "reliable" from "not" on these fixtures, not to estimate failure rates.
The fixtures say nothing about large codebases, long sessions near context limits, or
ambiguous requirements. `Qwen3.6-35B-A3B`'s silent failure is two observations in nine
`calc` runs — confirmed, its *rate* only roughly known.

What you get in exchange for the capability gap: data stays on Polish academic
infrastructure, administrators cannot read request or response content, and nothing
goes to a foreign vendor.
