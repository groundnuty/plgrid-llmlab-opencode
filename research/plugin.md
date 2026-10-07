# The provider plugin

`.opencode/plugins/plgrid.js` registers PLGrid Forge as an OpenCode provider without
touching any public registry.

## Why a plugin rather than a config block

You can define a custom provider entirely in `opencode.json`:

```json
"provider": {
  "plgrid": {
    "npm": "@ai-sdk/openai-compatible",
    "options": { "baseURL": "https://llmlab.plgrid.pl/api/v1",
                 "apiKey": "{file:~/.config/opencode/plgrid.key}" },
    "models": { "…": { "…": "…" } }
  }
}
```

That works, but the key has to live in a file or an environment variable, because
`opencode providers login` only accepts providers from OpenCode's built-in registry:

```
$ opencode providers login -p plgrid
Error: Unknown provider "plgrid"
```

A plugin's `auth` hook removes that limitation. It makes `plgrid` a first-class
provider for the credential system, so the key lands in
`~/.local/share/opencode/auth.json` and never appears in any config file.

The alternative — submitting the provider to the `models.dev` registry — would work
too, but it advertises grant-gated academic models to every OpenCode user
world-wide, expects USD pricing where PLGrid bills in credits, and puts you behind a
review cycle for every model-list change. For a service where access is gated per
grant, a plugin is the better fit, not a lesser one.

## How it works

The file serves both OpenCode release lines (see the README's *OpenCode 1.x and 2.x*)
through one default export:

```js
export default { id: "plgrid", server: PLGridForge, setup }
```

1.x calls `server`, and 2.x calls `setup`. 2.x rejects a plugin that has only named
exports, with *"Plugin must export a default definition with an id and an effect or
setup function"*, which is how the plugin failed there before this export was added.

On **1.x**, `server` returns two hooks, and they share a small merge helper.

**`config`** — injects the provider and all 20 models at startup:

```js
config: async (config) => {
  config.provider = config.provider ?? {}
  const user = config.provider.plgrid ?? {}
  config.provider.plgrid = {
    npm: "@ai-sdk/openai-compatible",
    name: "PLGrid Forge (Cyfronet)",
    ...user,
    options: { baseURL: BASE_URL, ...(user.options ?? {}) },
    models: mergeModels(MODELS, user.models ?? {}),
  }
}
```

Anything you put under `provider.plgrid` in your own `opencode.json` wins over the
plugin's defaults, and `options` and `models` are merged rather than replaced. So you
can set a provider option without losing the gateway URL, and change one model
without losing the rest — for example, a smaller output budget for one model:

```json
"provider": {
  "plgrid": {
    "models": { "Qwen/Qwen3.6-27B": { "limit": { "context": 262144, "output": 8192 } } }
  }
}
```

Check what OpenCode resolved with `opencode debug config`: the result should still
list all 20 models and keep `baseURL` in `options`. (A plain object spread here would
not — see [pitfalls.md](pitfalls.md).)

**`auth`** — registers the provider with the credential system:

```js
auth: {
  provider: "plgrid",
  loader: async (getAuth) => {
    const auth = await getAuth()
    if (auth?.type === "api") return { apiKey: auth.key }
    return {}
  },
  methods: [{ type: "api", label: "API Key (llmlab.plgrid.pl -> Grants -> Generate API Key)" }],
}
```

On **2.x** there is no `config` or `auth` hook and no mutable global config. `setup`
registers the same things through transforms:

- `ctx.integration.transform` adds a `key` login method under the ID `plgrid`. That
  makes `opencode auth login plgrid` work, and stores the key in
  `~/.local/share/opencode/opencode.db`.
- `ctx.provider.transform` creates the provider on 2.x's built-in
  `@opencode/ai/providers/openai-compatible` package, with the same `baseURL`, and
  adds every model from the same `MODELS` table. Fields are mapped as follows:
  - `tool_call` becomes `capabilities.tools`.
  - `attachment` becomes `capabilities.input`. This must be set explicitly, because 2.x
    otherwise assumes every model accepts images.
  - `interleaved.field` becomes `compatibility.reasoningField`.
  - `limit` stays `limit`. Models without measured limits keep 2.x's defaults.

The provider is left on 2.x's default `auto` activation, so its models stay hidden
until a key is stored. A per-model override in `opencode.json`, like the one above,
works on 2.x as well. 2.x converts the 1.x `provider` block itself and applies it on
top of the plugin's defaults, so the overridden model keeps its other fields.

## Verified behaviour

The transcript below is from **1.x**. With the 2.x commands, the same setup was checked
on 2.0.24 on 2026-10-06:

- `opencode models` lists all 20 models.
- `opencode auth login plgrid` stores the key.
- A run with `-m plgrid/Qwen/Qwen3.6-35B-A3B` answers.
- The default model completes a file-writing task through a tool call.



In a directory containing **only** `.opencode/plugins/plgrid.js` — no
`opencode.json`, no environment variables:

```
$ opencode models plgrid
plgrid/CYFRAGOVPL/Llama-PLLuM-70B-chat-250801
… all 20 models …

$ opencode providers login -p plgrid
◆  Enter your API key
└  Done                    # auth.json now holds {"plgrid":{"type":"api","key":"plg-…"}}

$ opencode run -m plgrid/Qwen/Qwen3.6-27B 'Create ok.txt containing exactly: SHIPPED'
←  Write ok.txt
$ cat ok.txt
SHIPPED
```

Also verified in the interactive TUI: `/models` groups all 20 under
*"PLGrid Forge (Cyfronet)"* with their display names, the status line names the
model and the provider, and switching model mid-session works. It is not a
headless-only mechanism.

## Model metadata is measured, not guessed

Each entry carries:

- `limit.context` — from the gateway's own `max_model_len` error messages
- `tool_call` — the gateway's `function_calling_supported` field, confirmed by a
  structured tool call
- `limit.output` — deliberately well under `context` (see the `limit.output` pitfall
  in [pitfalls.md](pitfalls.md))
- `reasoning` and `interleaved: { field: "reasoning" }` on models that return chain of
  thought in a `reasoning` field; `interleaved` only names the field OpenCode uses to
  send past reasoning back (see [pitfalls.md](pitfalls.md))
- `attachment: true` on the vision model

**Every active chat model is listed, whichever grant can reach it.** Access is per
grant, and the catalog's `accessible` field is answered for the caller's account, so
a list filtered by it would be right for one account and wrong for the rest. A model your
grant cannot use fails legibly, with the gateway's `not available for grant` error.
Inactive models are left out. Limits are omitted only for models no grant used to
build this list could reach, so OpenCode's defaults apply to those.

## Distributing it

1. **Copy the file** — `.opencode/plugins/` for one project,
   `~/.config/opencode/plugins/` for every project. Recipients run
   `opencode providers login -p plgrid` (1.x) or `opencode auth login plgrid` (2.x)
   with their own grant key.
2. **Git** — clone into the plugins directory, or reference it from the `plugin`
   array in `opencode.json`. Updates arrive with `git pull`.
3. **npm** — publish and `opencode plugin <name> --global`; OpenCode installs into
   `~/.cache/opencode/node_modules/`.

## Maintenance note

The model list is a point-in-time snapshot and PLGrid adds and retires models. A
future version could build the map dynamically at startup from
`/api/v1/models-plgrid-format`, which already returns `function_calling_supported`
and `is_active` — most of what the config needs. The static list is deliberate for
now: it is reviewable, and it carries measured context limits the endpoint does not
report.
