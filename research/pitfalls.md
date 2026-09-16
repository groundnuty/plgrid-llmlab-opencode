# Common pitfalls

Behaviours that cost real debugging time when running OpenCode against an
OpenAI-compatible gateway with open-weight models. Each one is verified — either in
OpenCode's source (file and line given, v1.18.5) or by observation.

Most of these are invisible in the documentation and several look like model
failures when they are configuration failures.

---

## Configuration

### `${VAR}` shell syntax is not implemented

OpenCode supports exactly two substitutions: `{env:VAR}` and `{file:path}`.
A config written with `"apiKey": "${PLGRID_API_KEY}"` sends the **literal string**
`${PLGRID_API_KEY}` as the bearer token and every request fails with 401. Confirmed
by putting a logging proxy in front of the gateway:

```
AUTH_HEADER='Bearer ${TEST_KEY_VAR}'     # with TEST_KEY_VAR=SECRET123 exported
```

Same trap applies to MCP server blocks using `${GITHUB_PERSONAL_ACCESS_TOKEN}` or
`${CONTEXT7_API_KEY}` — those servers silently fail to authenticate.

### A missing `{file:}` target is a fatal startup error

```
Error: Configuration is invalid at .../opencode.json: bad file reference:
"{file:~/.config/opencode/some-prompt.md}" ... does not exist
```

Every command dies, including `opencode models`. A missing `{env:VAR}`, by contrast,
silently becomes an empty string. If you reference prompt files from your config,
ship them together.

This also makes `{file:}` a single point of failure for credentials: delete the key
file and the whole config stops working, even if the same key is present in
`~/.local/share/opencode/auth.json`. Prefer storing the key in `auth.json` (see
[plugin.md](plugin.md)).

### `limit.output` silently eats your context window

OpenCode sends `limit.output` **verbatim** as `max_tokens` on every request
(confirmed with a logging proxy). A gateway that enforces
`input + max_tokens ≤ context` will then reject requests once the conversation grows
— arriving mid-session as an HTTP 400 that reads like random flakiness.

Keep `output` well under `context`, especially on small-context models. In this
repo's config, 32k-context models are pinned to `output: 4096`; the 200k+ models can
afford 32768.

### Understated `limit.context` is safe but wasteful

Declaring 131072 for a model the gateway reports as 393216 discards two thirds of
the window and triggers compaction far earlier than necessary. Get the real number
from the gateway rather than guessing — see [reproducing.md](reproducing.md).

### Glob keys in the `agent` map are silently ignored

```jsonc
// Does NOT apply settings to agents matching a pattern:
"agent": { "core-development/*": { "model": "…", "description": "…" } }
```

This registers a **literal agent named `core-development/*`** that appears in the
`@` menu and does nothing. Only exact keys apply overrides — verified with a control:
an exact key changed the agent's model, the glob key did not.

If you have agent definition files in subdirectories
(`.opencode/agent/core-development/frontend.md`), configure each by its exact name.

### `OPENCODE_DISABLE_LSP_DOWNLOAD=` set-but-empty is a hard error

```
SchemaError(Expected "true" | "yes" | "on" | "1" | "y" | "false" | ... got "")
```

Set it to a real boolean or leave it unset entirely.

---

## Agents

### An agent's `prompt` REPLACES the base system prompt

`session/llm/request.ts:60`:

```js
...(input.agent.prompt ? [input.agent.prompt] : SystemPrompt.provider(input.model)),
```

Writing a custom `prompt` for an agent **discards OpenCode's entire tool-usage
instruction set**. `AGENTS.md` and the environment block still survive, which is why
this rarely breaks loudly — a capable model infers the conventions anyway.

On weaker models it matters. Every custom agent prompt in this repo therefore ends
with explicit tool discipline:

> Use your tools to inspect real files rather than guessing at contents. Put only
> the parameter value inside a tool call — never reasoning or commentary. Do your
> thinking before the call, then emit a clean call.

Keep that (or equivalent) if you write your own agents.

### `steps` defaults to `Infinity`

`session/prompt.ts:1178`:

```js
const maxSteps = agent.steps ?? Infinity
```

There is no loop cap out of the box. A model that spins, spins until you stop it —
and spinning is a characteristic open-weight failure mode. On hitting the cap
OpenCode injects a "MAXIMUM STEPS REACHED / respond with text only" message, which
is the supported circuit-breaker.

This repo sets 5–40 per agent by role.

### The built-in `plan` agent cannot delegate

`agent/agent.ts` gives it `task: { general: "deny" }` and restricts edits to
`.opencode/plans/*.md`. It is a read-only planner that is **explicitly barred** from
handing work to an implementer.

If you want planner-delegates-to-implementer, define your own primary agent with
`task` allowed and write tools denied — the `architect` agent in this repo's
`opencode.json`.

### The TUI is not a reliable audit trail for delegation

A subagent invocation can complete without a visible marker in the TUI while the
files change anyway. To see which subagent actually ran:

```bash
opencode session list
opencode export <session-id>     # look for tool: "task" and its subagent_type
```

---

## Runtime

### `opencode run` occasionally exits 0 having done nothing

Observed roughly 4 times in ~45 headless runs: the command returns success with no
output and no file change; an immediate re-run of the identical command works.

Attempts to reproduce it deliberately — fresh directory with a minimal config, fresh
directory with a full config, multi-step prompt — all succeeded first time, so the
trigger is unidentified. A race in first-run initialisation is plausible but
unproven.

**Because the exit code is 0, nothing signals failure.** For interactive use this is
a non-issue. If you script `opencode run` in CI, assert on the expected artifact
rather than the exit status.

### Concurrent `opencode` invocations hit `database is locked`

There is one SQLite database at `~/.local/share/opencode/`. Running several
instances in parallel makes them contend and fail. Run sequentially.

### Writes outside the project directory are auto-rejected

A run whose working directory is under `/tmp` (or any path outside the project) will
have its writes refused as `external_directory` unless permitted. In a headless
benchmark this looks exactly like the model failing, when it never got to act. Use
`--auto`, or an in-project working directory.

### LSP needs the server binary installed

`"lsp": true` alone starts nothing if the language server is absent — agents then
silently fall back to guessing, or improvise `npx pyright`. Install what you need:

```bash
npm install -g pyright                                    # Python
npm install -g typescript typescript-language-server      # TS/JS
```

When it *is* working it is worth having: after every edit OpenCode injects the
language server's diagnostics back into the agent's context —

```
LSP errors detected in this file, please fix:
ERROR [2:12] Operator "+" not supported for types "int" and "Literal['x']"
```

— and models act on it, fixing their own type errors unprompted.

### `compaction.prune` cannot help small-context models

`session/compaction.ts`:

```js
export const PRUNE_MINIMUM = 20_000
export const PRUNE_PROTECT = 40_000
```

Prune only fires when more than 20k tokens remain prunable *after* protecting the
most recent 40k of tool output — so roughly 60k of accumulated tool output is needed
before it does anything. A 32k-context model can never reach that. It is useful for
200k+ models only, and it is opt-in.

---

## Model-side behaviour

### Reasoning models need `interleaved`

GLM, Qwen and DeepSeek reasoning models stream chain-of-thought in a separate delta
field. The field name is a property of the deployment: the current PLGrid gateway
(vLLM 0.29) emits `reasoning`, older ones used `reasoning_content`, and OpenCode's
own default for an `@ai-sdk/openai-compatible` provider whose model id contains
`deepseek` is `reasoning_content`. Set it explicitly. Without

```json
"interleaved": { "field": "reasoning" }
```

the thinking either vanishes or leaks into the answer as raw `<think>` text.

Caveat from OpenCode's source: `provider/transform.ts` **skips** interleaved
handling entirely when the provider package is `@openrouter/ai-sdk-provider`. With
`@ai-sdk/openai-compatible` (what this repo uses) it applies.

### Malformed tool calls are two different problems

Widely conflated; the mitigations differ.

**Class 1 — server-side parser mismatch (self-hosting only).** vLLM's own
documentation states that without `strict: true` on a tool, *"the model generates
freely and tool calls are extracted from raw text… arguments may occasionally be
malformed."* OpenCode never sets `strict: true` for `@ai-sdk/openai-compatible`, so
this path is always taken.

Fix with `--enable-auto-tool-choice`, the correct `--tool-call-parser`, and a
matching `--reasoning-parser`. **The coverage gap is the real problem:** vLLM
documents no parser for GLM-5.x, Qwen3.5/3.6 (non-Coder), DeepSeek V4, Kimi K2.5+ or
MiniMax. Parsers that do exist include `glm47` (GLM-4.7/Flash), `qwen3_xml`
(Qwen3-**Coder**), `hermes` (Qwen2.5/QwQ), `deepseek_v3`, `kimi_k2`.

So **for self-hosting, the newest flagship is often the worst choice** — prefer a
model one generation back that has a documented parser. Two corrections to advice
circulating online: the vLLM parser is `qwen3_xml`, not `qwen3_coder` (that name
belongs to the separate `vllm-mlx` project), and Qwen3-Coder is not Qwen3.x — no
parser is documented for the Qwen3.5/3.6 general models.

**Class 2 — tool markup inside the reasoning channel.** No parser flag touches this
and it occurs on hosted endpoints too. Widely reported for GLM-4.7 and Kimi K2, with
some reporters tying onset to >100k context and others seeing it at 10k. OpenCode has
declined to add client-side repair, so the practical mitigation is to declare a
`limit.context` below where degeneration starts.

Note this did **not** occur in any of the 18 agentic runs behind
[models.md](models.md) — it is a real risk, not a certainty.

### There is effectively no client-side tool-call repair

OpenCode's `experimental_repairToolCall` does two things: case-fix a tool name
(`Read` → `read`, a genuinely common open-model slip), or route to an `invalid` tool
that returns an error message the model can retry against. **It never inspects the
content channel**, so markup arriving as text produces no tool call and the hook
never fires.

### Per-family workarounds already in OpenCode

`provider/transform.ts` carries fixes for some families and not others — useful as a
map of what is known-broken upstream. Mistral/Devstral/Codestral need tool-call IDs
of exactly 9 alphanumerics (OpenCode scrubs them) and cannot have a tool message
followed by a user message (OpenCode injects a synthetic `assistant: "Done."`).
DeepSeek requires reasoning on every assistant message (OpenCode injects empty
reasoning parts). **GLM, Qwen and MiniMax have no such handling.**

### Prompt cache invalidation is the hidden cost when self-hosting

Filesystem globbing, context pruning and date injection change the prefix each turn,
so a self-hosted server re-prefills large agentic contexts repeatedly. Reported
independently by several practitioners as the dominant cost of local models. Not an
issue with a hosted gateway that you are not paying for by GPU-second.

---

## Reference notes

- **OpenCode's JSON schema is more reliable than its prose docs.** Fetch
  `https://opencode.ai/config.json` and read it directly. Example: the docs state
  there is no `skills` config key; the schema has `skills.paths` and `skills.urls`,
  and they work.
- **Claude Code configuration is largely reusable.** `~/.claude/skills` is
  auto-discovered with no config at all. `AGENTS.md` is the `CLAUDE.md` equivalent
  and OpenCode falls back to `CLAUDE.md`, then `~/.claude/CLAUDE.md`. Rule files
  elsewhere can be pulled in with an `instructions` glob:
  `"instructions": ["AGENTS.md", "~/.claude/rules/common/*.md"]`.
- **There is no `hooks` config key.** Claude Code's lifecycle hooks have no
  declarative equivalent; the counterpart is a plugin, which is JavaScript. It is
  more capable — a plugin can mutate config, add tools and transform messages — but
  it is code you write. A `tool.execute.after` hook reproduces `PostToolUse` in a
  few lines.
- **Only Kimi gets a tuned system prompt.** `session/system.ts` substring-matches the
  model id; `claude`, `gpt`, `gemini`, `kimi` and `trinity` each get a bespoke
  prompt, and everything else — GLM, Qwen, DeepSeek, MiniMax — gets a generic
  Claude-derived default that addresses none of their actual failure modes. If you
  want model-specific guidance for these families you must supply it yourself via
  `AGENTS.md` or an agent `prompt`.
