# OpenCode + PLGrid Forge

A working, sane OpenCode setup for the PLGrid Forge models on ACK Cyfronet
supercomputers. Drop it in, log in once, and you have an agentic coding assistant
running on Polish academic infrastructure.

Model capabilities, context limits and the benchmark figures below were **measured
against the live gateway**, not copied from model cards.

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

Choose one of the two setups.

**Per project.** Copy the plugin, the agent directives and the config into the root of
your project:

```bash
cp -r .opencode AGENTS.md opencode.json /path/to/your/project/
```

**Machine-wide.** Create OpenCode's global plugin directory, if it does not exist yet:

```bash
mkdir -p ~/.config/opencode/plugins
```

Copy the provider plugin into it:

```bash
cp .opencode/plugins/plgrid.js ~/.config/opencode/plugins/
```

Install the config as your global OpenCode config. This overwrites an existing
`~/.config/opencode/opencode.json` — if you already have one, merge the two by hand
instead:

```bash
cp opencode.json ~/.config/opencode/opencode.json
```

Then authenticate once:

```bash
opencode providers login -p plgrid
```

Paste your grant's API key. It is stored in
`~/.local/share/opencode/auth.json` — **never** in any file in this repo.

Verify that the provider is registered — this should list 20 models:

```bash
opencode models plgrid
```

Then start the TUI. Use `/models` to switch model and **Tab** to switch agent:

```bash
opencode
```

## What you get

**20 models**, of which **14 support function calling**. On the benchmark fixtures,
run three times each and scored on hidden cases the model never saw
([method](research/benchmarks/README.md), [results](research/models.md)), these are
the ones worth using for agentic work:

| Model | Context | Correct (3 runs, /22) | Task s | Use for |
|---|---|---|---|---|
| `deepseek-ai/DeepSeek-V4.1-Flash` | 1M | 22 · 22 · 22 | 19 / 27 | **default**, `architect`, `researcher`, `fastfix` |
| `deepseek-ai/DeepSeek-V4-Flash` | 700k | 22 · 22 · 22 | 35 / 31 | alternative without reasoning |
| `Qwen/Qwen3.6-27B` | 262k | 22 · 22 · 22 | 55 / 59 | `reviewer` — thorough, slow |
| `google/gemma-4-31B` | 262k | 22 · 22 · 22 | 30 / 42 | `small_model` |
| `zai-org/GLM-5.3-Flash` | 1M | 22 · 22 · 22 | 23 / 33 | strong alternative default |
| `Qwen/Qwen3.8-27B` | 262k | 22 · 22 · 22 | 42 / 82 | alternative reviewer |
| `Qwen/Qwen3.6-35B-A3B` | 262k | 22 · 22 · 22 ⚠ | 17 / 21 | fastest — review its output |

"Task s" is the median wall time of one whole agentic run (calc / ledger fixture) —
what an agent actually waits for. Generation rates are in
[research/models.md](research/models.md); they depend heavily on gateway load.

⚠ **`Qwen3.6-35B-A3B` is the fastest model and open to every grant, but it can be
silently wrong.** On these fixtures it has produced solutions whose whole test suite
passed while `evaluate("2 * 3 * 4")` returned `10` — a green suite over broken code,
indistinguishable from outside without hidden test cases. It was clean in this run;
the failure is intermittent. Use it where you review the output, not unattended.

Three tool-capable models are **not safe to use unattended**, and `opencode run` still
exits 0 when they fail. `Llama-3.3-70B` returns floats where integers are expected (a whole suite
green, every hidden case wrong) and **rewrites the test file** to fit its code.
`Bielik-11B-v3.0` scores 0 and **reports passes it never achieved**. `Qwen3-Coder-30B`
is usually right but sometimes announces a tool call and ends its turn without making
it, changing nothing.

The remaining 6 models **cannot use tools**. They remain useful for chat, translation
and Polish-language work.

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
| `fastfix` | subagent | DeepSeek-V4.1-Flash | Small, well-specified mechanical edits |

Invoke subagents with `@researcher`, `@reviewer`, `@fastfix`. Cycle primary agents
(`architect`, `chat`, and the built-in `build`/`plan`) with **Tab** in the TUI, or
pass `--agent <name>` to `opencode run`. The benchmark's own `bench` agent is not
here: it lives in `research/benchmarks/bench-opencode.json`, loaded only by the
benchmark runner.

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
silently starts nothing.

For Python, install `pyright`:

```bash
npm install -g pyright
```

For TypeScript and JavaScript, install the TypeScript language server:

```bash
npm install -g typescript typescript-language-server
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

- **Some models are restricted to some grants.** An API key belongs to one grant, and
  a model your grant cannot use answers *"not available for grant 'N'"*.
  `DeepSeek-V4.1-Flash` — the default, and the model for `architect`, `researcher` and
  `fastfix` — is restricted, as are `DeepSeek-V4-Flash`, `GLM-5.2-FP8`,
  `GLM-5.3-Flash`, `Qwen3.8-27B` and the `Qwen3.5` models. They include the
  best-performing models here, which is why the default is one of them: **if your
  grant cannot use it, ask for access via the PLGrid Helpdesk.** Until then, set `model`,
  `architect` and `researcher` to `plgrid/Qwen/Qwen3.6-27B` and `fastfix` to
  `plgrid/google/gemma-4-31B` — both open to all grants and perfect on the benchmark.
  Check which models your own key can reach with
  [`research/list_models.py`](research/list_models.md); the catalog's answer depends
  on who asks.
- **`opencode run` occasionally exits 0 having done nothing.** Harmless interactively.
  If you script it, assert on the expected artifact, not the exit code.
- **Several models are flagged non-commercial** by the gateway (`DeepSeek-V4.1-Flash`,
  `GLM-5.2-FP8`, `GLM-5.3-Flash`, `Qwen3.6-27B`, `gemma-4-31B`, `PLLuM-12B`).
  Irrelevant for academic and research use, which is what PLGrid grants are for. It
  only matters if you have a commercial affiliation.
- **A model can be listed and not answer.** `GLM-5.2-FP8` is in the catalog as active
  but timed out on every request when the benchmark was run.
- **The model list is a snapshot.** PLGrid adds and retires models. To re-check the
  raw catalog, export your key as `LLMLAB_API_KEY` and run:
  ```bash
  curl -H "Authorization: Bearer $LLMLAB_API_KEY" https://llmlab.plgrid.pl/api/v1/models-plgrid-format | python3 -m json.tool
  ```
  That endpoint is authoritative for `function_calling_supported` and `is_active`.
  For one line per model with its price and capability tags, run the helper script
  instead. It reads the key from the repo-root `.env` and needs `requests` and
  `python-dotenv` ([details](research/list_models.md)):
  ```bash
  python3 research/list_models.py
  ```

## Honest expectations

These are open-weight models, not frontier ones. The best of them are roughly
Sonnet-class on a good day; the rest are below that. For well-specified
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

Practitioners report a pattern that inverts the intuition that the big model should
do all the work:

> *"The big expensive models are great at planning tasks and reviewing the
> implementation… The small cheap models are actually great (and fast) at generating
> decent code if they have the right direction up front."*

On PLGrid the models cost research credits rather than money, so here the split is
about constraints and independence rather than price:

- The `architect` **cannot edit files at all** — it must delegate, which stops a
  planner making a mess directly.
- `fastfix` gets a narrow prompt and a 15-step cap; the constraint is the point. It
  runs on DeepSeek-V4.1-Flash, the same model as the `architect`, because that model
  had a perfect record and finished tasks fastest.
- The `reviewer` is deliberately a different model family — Qwen3.6-27B at
  temperature 0.1 — so a review is not the author checking its own work.

Note the built-in `plan` agent cannot do this: it has `task: { general: "deny" }`
hardcoded, so it can never hand work to an implementer. That is why `architect`
exists as a custom agent.

Also: **the TUI does not reliably show delegation.** Use
`opencode export <session-id>` if you need to audit which subagent actually ran.

---

## Licence

Config and documentation — do what you like with it.
