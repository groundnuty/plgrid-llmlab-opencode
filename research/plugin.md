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

Two hooks, about 40 lines total.

**`config`** — injects the provider and all 15 models at startup:

```js
config: async (config) => {
  config.provider = config.provider ?? {}
  config.provider.plgrid = {
    npm: "@ai-sdk/openai-compatible",
    name: "PLGrid Forge (Cyfronet)",
    options: { baseURL: BASE_URL },
    models: MODELS,
    ...(config.provider.plgrid ?? {}),   // user overrides win
  }
}
```

Note the spread: anything you put under `provider.plgrid` in your own
`opencode.json` overrides the plugin's defaults, so changing one model's
`limit.output` does not require forking the plugin.

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

## Verified behaviour

In a directory containing **only** `.opencode/plugins/plgrid.js` — no
`opencode.json`, no environment variables:

```
$ opencode models plgrid
plgrid/CYFRAGOVPL/Llama-PLLuM-70B-chat-250801
… all 15 models …

$ opencode providers login -p plgrid
◆  Enter your API key
└  Done                    # auth.json now holds {"plgrid":{"type":"api","key":"plg-…"}}

$ opencode run -m plgrid/zai-org/GLM-4.7-Flash 'Create ok.txt containing exactly: SHIPPED'
←  Write ok.txt
$ cat ok.txt
SHIPPED
```

Also verified in the interactive TUI: `/models` groups all 15 under
*"PLGrid Forge (Cyfronet)"* with their display names, the status line reads
`Build · GLM-5.2 FP8 · PLGrid Forge (Cyfronet)`, and switching model mid-session
works. It is not a headless-only mechanism.

## Model metadata is measured, not guessed

Each entry carries:

- `limit.context` — from the gateway's own `max_model_len` error messages
- `tool_call` — from the gateway's `function_calling_supported` field
- `limit.output` — deliberately well under `context` (see the `limit.output` pitfall
  in [pitfalls.md](pitfalls.md))
- `interleaved: { field: "reasoning_content" }` on reasoning models
- `attachment: true` on the vision model

Grant-gated and inactive models are **included and labelled** rather than omitted, so
that a user without access gets a legible error instead of a missing entry.

## Distributing it

1. **Copy the file** — `.opencode/plugins/` for one project,
   `~/.config/opencode/plugins/` for every project. Recipients run
   `opencode providers login -p plgrid` with their own grant key.
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
