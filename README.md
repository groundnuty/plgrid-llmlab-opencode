# OpenCode + PLGrid Forge

A working, sane OpenCode setup for the PLGrid Forge models on ACK Cyfronet
supercomputers. Drop it in, log in once, and you have an agentic coding assistant
running on Polish academic infrastructure.

Model capabilities and the context limits below were **measured against the live
gateway**, not copied from model cards. A few grant-restricted models could not be
probed from this account and are left at OpenCode's defaults rather than guessed.

**Documentation:**

| | |
|---|---|
| [research/models.md](research/models.md) | Which models work, measured throughput and correctness, recommended assignments |
| [research/pitfalls.md](research/pitfalls.md) | Traps that cost real debugging time — config, agents, runtime, model behaviour |
| [research/plugin.md](research/plugin.md) | How the provider plugin works and how to distribute it |
| [research/reproducing.md](research/reproducing.md) | Commands to re-derive every measurement yourself |
| [research/benchmarks/](research/benchmarks/) | Agentic fixtures with differential scorers |

## Requirements

- A PLGrid account, team, and grant with LLM credits — see the
  [Forge guide](https://guide.plgrid.pl/en/integrated-platforms/plgrid_forge).
  Activate the service at <https://portal.plgrid.pl/services/111>, then generate a
  key at <https://llmlab.plgrid.pl> under **Grants → Generate API Key**.
- [OpenCode](https://opencode.ai) 1.18.5 or newer (`brew install opencode`).
- Optional but recommended: `npm install -g pyright` for in-editor diagnostics
  (see *LSP* below).

## Install

```bash
# per-project
cp -r .opencode AGENTS.md opencode.json /path/to/your/project/

# or machine-wide
cp .opencode/plugins/plgrid.js ~/.config/opencode/plugins/
cp opencode.json ~/.config/opencode/opencode.json
```

Then authenticate once:

```bash
opencode providers login -p plgrid
```

Paste your grant's API key. It is stored in
`~/.local/share/opencode/auth.json` — **never** in any file in this repo.

Verify:

```bash
opencode models plgrid    # should list 17 models
opencode                  # TUI; /models to switch, Tab to switch agent
```

## What you get

**17 models**, of which **11 support function calling** and **5 were benchmarked as
reliably agentic**:

Throughput is measured at the gateway (median of 3, identical 300-token budget).
"Correct" is the share of hidden test cases passed — cases the models never saw,
run *after* they made their own test suite green. See [research/models.md](research/models.md).

| Model | Context | tok/s | Correct | Use for |
|---|---|---|---|---|
| `deepseek-ai/DeepSeek-V4.1-Flash` | 1M | — | not measured | **default** — see note below |
| `zai-org/GLM-5.2-FP8` | 393k | 62 | 22/22 | hardest measured tasks |
| `Qwen/Qwen3-Coder-30B-A3B` | 249k | 90 | 21/22 | well-specified edits |
| `google/gemma-4-31B` | 262k | 37 | 22/22 | `small_model`; simple tasks |
| `Qwen/Qwen3.6-27B` | 262k | 26 | 22/22 | review — most thorough, slowest |
| `Qwen/Qwen3.6-35B-A3B` | 262k | **165** | **19/22** ⚠ | fastest, now `fastfix`, but see below |

`DeepSeek-V4.1-Flash` became the default in `opencode.json` after `GLM-4.7-Flash`
went inactive; it has **not** been through the benchmark suite, so its reliability
is unverified. `GLM-5.2-FP8` remains the measured fallback.

⚠ **`Qwen3.6-35B-A3B` is the fastest model and the only one that produced a
silently-wrong solution.** In one of two trials it made the whole test suite pass
while `evaluate("2 * 3 * 4")` returned 10 instead of 24 — a green suite over broken
code. Its other trial produced a clean recursive-descent parser. Same task, same
prompt. Use it where you review the output; do not use it unattended. When
`GLM-4.7-Flash` went inactive it was pointed at `fastfix` anyway — treat that agent's
diffs as needing review.

`Qwen3-Coder-30B`'s single miss was a missing `isinstance` guard in `__eq__`, so
`Money(10,"PLN") == 42` raised `AttributeError` instead of returning `False`.

The remaining 6 are configured but **cannot use tools** — all 6 lack function
calling entirely. They remain useful for chat, translation, and Polish-language work.
`Bielik-11B-v3.0` does have function calling but loses track of the working
directory, so it is treated as chat-only. Five tool-capable models
(`DeepSeek-V4.1-Flash`, `Llama-3.3-70B-Instruct`, `Qwen3.8-27B`, `Qwen3.5-122B-A10B`,
`Qwen3.5-397B-A17B-FP8`) were not benchmarked.

> **Important:** to use a model without function calling, switch to the `chat`
> agent first (**Tab** in the TUI, or `--agent chat`). The default `build` and
> `plan` agents always send a tools array, and those models reject it with a hard
> HTTP 400.

**5 agents:**

| Agent | Type | Model | Purpose |
|---|---|---|---|
| `architect` | primary | DeepSeek-V4.1-Flash | Plans and delegates; **cannot edit files** |
| `chat` | primary | any | No tools — for the non-function-calling models |
| `researcher` | subagent | DeepSeek-V4.1-Flash | Traces code paths, read-only |
| `reviewer` | subagent | Qwen3.6-27B, t=0.1 | Finds defects, read-only |
| `fastfix` | subagent | Qwen3.6-35B-A3B | Small mechanical edits — needs review |

Invoke subagents with `@researcher`, `@reviewer`, `@fastfix`. Cycle primary agents
(`architect`, `chat`, and the built-in `build`/`plan`) with **Tab** in the TUI, or
pass `--agent <name>` to `opencode run`.

`AGENTS.md` is deliberately short and contains only directives — it is prepended to
every agent's system prompt, so anything descriptive in it is paid for on every
request. OpenCode already injects the agent and command descriptions from
`opencode.json`; do not restate them there.

**3 commands:** `/check` (typecheck + test + fix), `/review` (review the diff),
`/explain <thing>` (trace with file:line citations).

**Permissions:** `bash` asks by default; read-only inspection is allow-listed;
`rm -rf`, `git push`, `git rebase` and `git reset --hard` are denied outright.
`git commit` asks.

## LSP

`"lsp": true` is set, and it is worth having: after **every edit** OpenCode feeds
the language server's diagnostics straight back to the agent, which then fixes its
own type errors unprompted.

But it needs the server binary installed. With no `pyright` on `PATH`, `lsp: true`
silently starts nothing:

```bash
npm install -g pyright        # Python
npm install -g typescript typescript-language-server   # TS/JS
```

## Customise

Nothing here is sacred. Common changes:

- **Different default model** — edit `"model"` at the top.
- **Project rules** — edit `AGENTS.md`. It is loaded into every agent's prompt.
  On an existing codebase, run `/init` first to generate a draft.
- **Reuse existing Claude Code config** — OpenCode reads Claude Code's formats:
  ```json
  "instructions": ["AGENTS.md", "~/.claude/rules/common/*.md"],
  "skills":       { "paths": ["~/.claude/skills"] }
  ```
  Your existing `~/.claude/skills` folder works as-is.
- **MCP servers** — add an `mcp` block; see the
  [docs](https://opencode.ai/docs/mcp-servers/). Add one at a time and verify each.

## Known issues

- **Several models are grant-gated.** `Qwen3.5-122B-A10B`, `Qwen3.5-397B-A17B-FP8`,
  `Qwen3.8-27B` and `DeepSeek-V4-Flash-0731` return *"not available for grant 'N'"*
  unless your grant covers them; `DeepSeek-V4.1-Flash` and `GLM-5.2-FP8` are
  restricted to specific grants too, though they answered on the default grant here.
  Apply via Helpdesk if you need them.
- **`opencode run` occasionally exits 0 having done nothing** (~3 in 40 runs, cause
  unidentified). Harmless interactively. If you script it, assert on the expected
  artifact, not the exit code.
- **The default model is itself grant-restricted.** The gateway lists
  `deepseek-ai/DeepSeek-V4.1-Flash` as accessible to specific grants only
  (`plgccbmc15`, `plgtraining2026` at the time of writing) and it carries a
  non-commercial flag. If every request fails with *"not available for grant 'N'"*,
  change `model` and the `architect`/`researcher` pins to
  `plgrid/Qwen/Qwen3.6-35B-A3B`, which is open to all grants.
- **Several models are flagged non-commercial** by the gateway (`GLM-5.2-FP8`,
  `Qwen3.6-27B`, `gemma-4-31B`, `DeepSeek-V4.1-Flash`, `DeepSeek-V4-Flash-0731`,
  `PLLuM-12B`). Irrelevant for academic and research use, which is what PLGrid grants
  are for. It only matters if you have a commercial affiliation — then substitute
  `Qwen3.6-35B-A3B` or `Qwen3-Coder-30B-A3B`.
- **The model list is a snapshot.** PLGrid adds and retires models. Re-check with:
  ```bash
  curl -H "Authorization: Bearer $KEY" \
    https://llmlab.plgrid.pl/api/v1/models-plgrid-format | python3 -m json.tool
  ```
  That endpoint is authoritative for `function_calling_supported` and `is_active`.

## Honest expectations

These are open-weight models, not frontier ones. `GLM-5.2` and `Qwen3.6-27B` are
roughly Sonnet-class on a good day; the rest are below that. For well-specified
single-file work they are genuinely good and fast. For multi-file refactors with
ambiguous requirements, expect a real gap versus Claude or GPT.

What you get in return: your data stays on Polish academic infrastructure, PLGrid
administrators cannot read request or response content, and nothing goes to a
foreign vendor.

## Four things worth knowing (all verified in OpenCode source)

These bite open-weight models harder than frontier ones, and none are obvious from
the docs. [research/pitfalls.md](research/pitfalls.md) has the full list with
source references.

**1. `steps` defaults to `Infinity`** (`session/prompt.ts:1178`). No loop cap out of
the box — a model that spins, spins forever. This config sets a cap per agent
(5–40). Adjust rather than remove.

**2. An agent's `prompt` REPLACES the base system prompt** — it does not append
(`session/llm/request.ts:60`). If you write a custom agent prompt, you silently drop
OpenCode's tool-usage instructions. That is why every prompt here ends with explicit
tool discipline. Keep it if you edit them.

**3. Malformed tool calls are two different bugs.** Self-hosting: vLLM needs
`--enable-auto-tool-choice` plus the right `--tool-call-parser` — and it documents
**no parser** for GLM-5.x, Qwen3.5/3.6, DeepSeek V4, Kimi K2.5+ or MiniMax, so for
self-hosting prefer a model one generation back (`glm47`, `qwen3_xml`, `hermes`
have parsers). Hosted: models sometimes emit tool markup inside the *reasoning*
channel, which no flag fixes — see
[issue #6708](https://github.com/anomalyco/opencode/issues/6708). OpenCode has
declined to add client-side repair, so if you hit it, reduce `limit.context` below
where it starts.

**4. `compaction.prune` does nothing for small-context models.** It needs ~60k of
accumulated tool output before it fires (`PRUNE_MINIMUM` 20k, `PRUNE_PROTECT` 40k).
Useful for the 200k+ models here, irrelevant at 32k.

## Why the agents are split the way they are

The topology follows the pattern experienced practitioners report, which inverts the
intuition that the big model should do the work:

> *"The big expensive models are great at planning tasks and reviewing the
> implementation… The small cheap models are actually great (and fast) at generating
> decent code if they have the right direction up front."*

So: DeepSeek-V4.1-Flash plans (`architect`) and investigates (`researcher`),
Qwen3.6-27B reviews at temperature 0.1, Qwen3.6-35B-A3B does the mechanical edits.
The `architect` **cannot edit files at all** — it must delegate, which stops a mid-tier
planner making a mess directly.

Note the built-in `plan` agent cannot do this: it has `task: { general: "deny" }`
hardcoded, so it can never hand work to an implementer. That is why `architect`
exists as a custom agent.

Also: **the TUI does not reliably show delegation.** Use
`opencode export <session-id>` if you need to audit which subagent actually ran.

---

## Licence

Config and documentation — do what you like with it.
