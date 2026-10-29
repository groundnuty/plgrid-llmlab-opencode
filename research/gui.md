# The graphical apps

OpenCode has two graphical apps next to the terminal TUI: the desktop app and the web
interface. This setup works in both without changes to the plugin, `opencode.json` or
`AGENTS.md`. A few settings have to be made once in the app; [GUI.md](../GUI.md) walks
through them. This page records what was tested and why it works.

## Why it works

The graphical apps are clients of the same OpenCode server the TUI uses. That server
loads the plugin, the config, the agents and commands, and `AGENTS.md`, and reads the
same key store.

- **1.x:** the web UI is served by the installed binary (`opencode web`). The desktop app
  is an Electron shell that bundles a server built from the same release.
- **2.x:** the web UI and the desktop app both connect to the shared background service
  the TUI uses; `opencode service status` prints its address, which also serves the web
  UI. The desktop app ships its own `opencode` binary, in
  `~/.config/ai.opencode.desktop/cli/<version>/`, and runs the background service with
  it.

## Tested

The web UI was tested with 1.18.35 and 2.0.24 on 2026-10-07, and the desktop app with
2.2.1 on 2026-10-29, all on Linux. Each ran in a sandbox HOME with a per-project install
and a real PLGrid key: the web UI driven through headless Chrome, the desktop app
through its DevTools port.

| | 1.x web | 2.x web | 2.x desktop |
|---|---|---|---|
| PLGrid models in the model picker | ✅ all 20 | ⚠️ hidden until the PLGrid group is turned on in **Manage models** | ✅ all 20 after logging in from the app; ⚠️ as 2.x web when the key was stored before |
| Default model from `opencode.json` | ❌ starts on "Big Pickle"; switching to Architect applies its configured model | ✅ DeepSeek V4.1 Flash | ✅ DeepSeek V4.1 Flash; ⚠️ but see *Logging in from the app* below |
| Architect / Chat selectable | ✅ agent picker | ⚠️ only after **Settings → Preferences → Show agent** | ⚠️ as 2.x web |
| Subagents via `@` | ✅ Architect delegated to `@fastfix`; file created | ✅ `@fastfix` created the file | ✅ Architect delegated to `@fastfix`; file created |
| Per-agent models | | | ✅ `reviewer` ran on Qwen3.6-27B, the others on DeepSeek V4.1 Flash |
| `/review`, `/check`, `/explain` | ✅ | ✅ | ✅ `/review` and `/explain` ran their subagents; `/check` started and was stopped before it finished |
| Permission prompts | ✅ | ✅ | ✅ |
| Log in from the GUI | ✅ model picker → Manage models → Connect provider → PLGrid → API key | ✅ `/connect` → PLGrid → API key | ✅ `/connect` → PLGrid Forge (Cyfronet) → API key |
| Key shared with the CLI | ✅ same `auth.json` | ✅ same `opencode.db` | ✅ same `opencode.db`: after the login in the app, `opencode models` listed the 20 models |
| context7 MCP server | | | ✅ connected |

An empty cell was not checked.

Also observed:

- **1.x Settings → Providers lists PLGrid as "Connected (Config)" even with no key
  stored**, so that page has no Connect button. The login is under Manage models →
  Connect provider.
- **2.x global Settings → Providers does not list PLGrid with a per-project install**, in
  the web UI and in the desktop app. The plugin is only loaded inside the project, where
  `/connect` finds it.
- **The desktop app remembers "Show agent" and the Manage models choices per user
  profile,** not per project.

### Logging in from the app

After a login through `/connect`, the 2.x desktop app opens a **Choose a model to start
with** dialog listing the 20 models. Clicking **Continue** without choosing one selected
GLM-5.2 FP8, the first in the list, and new sessions then started on it instead of the
`opencode.json` default. GLM-5.2 FP8 timed out on every request when the benchmark was
run, so pick DeepSeek V4.1 Flash in that dialog: choosing it there, then **Continue**,
started sessions on it. With the key stored before the app first ran, no dialog appears
and sessions start on the configured default.

### Machine-wide install

Tested with the 2.2.1 desktop app on 2026-10-29: a sandbox HOME with `plgrid.js` in
`~/.config/opencode/plugins/`, this repo's `opencode.json` as
`~/.config/opencode/opencode.json`, and a real PLGrid key.

- **Before login, global Settings → Providers offers PLGrid**, unlike with a per-project
  install: **Show more providers** lists PLGrid Forge (Cyfronet), and choosing it opens
  the same key dialog as `/connect`.
- After the key, the same **Choose a model to start with** dialog appears. Afterwards
  Settings → Providers lists PLGrid Forge (Cyfronet) under **Connected providers**.
- In a project with no setup files of its own (the app's start folder), the model
  picker listed all 20 models, and DeepSeek V4.1 Flash, chosen in that dialog, answered
  a prompt.

## The desktop app

- **Downloads.** <https://opencode.ai/download> serves the 2.x desktop app. The 1.x
  desktop app is only available as GitHub release assets (`opencode-desktop-*` on
  [v1.18.35](https://github.com/anomalyco/opencode/releases/tag/v1.18.35)). On Linux both
  `.deb` packages are named `opencode` and install to `/opt/OpenCode`, so installing one
  replaces the other.
- **Environment.** At startup the desktop app runs your login shell (`$SHELL -il`) and
  takes its environment from it. `npx`, which the context7 MCP server needs, must
  therefore be on the PATH set by your shell startup files
  ([anomalyco/opencode#25748](https://github.com/anomalyco/opencode/issues/25748),
  [#49449](https://github.com/anomalyco/opencode/issues/49449)). The tested app was
  started from a terminal, not from the OS menu.
- **Shared service.** The 2.x desktop app runs the background service from its own
  binary, so after it starts, a 2.x TUI on the same machine talks to a service of the
  desktop app's version.

## Not tested

- **The 1.x desktop app.** It runs plugins under Node (Electron), not Bun. `plgrid.js`
  uses no Bun APIs, so it should load, but that is unconfirmed.
- The desktop app on macOS and Windows, and started from the OS menu.
- Open upstream bugs that may affect PLGrid:
  - [anomalyco/opencode#50726](https://github.com/anomalyco/opencode/issues/50726): the
    2.x desktop app does not list custom-provider models until the list refreshes. Not
    seen in 2.2.1: the models appeared right after the login.
  - [anomalyco/opencode#52313](https://github.com/anomalyco/opencode/issues/52313): the
    2.0.20 web UI (Homebrew's version) shows no agents or models.
