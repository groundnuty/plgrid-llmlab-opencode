# Using the GUI

How to set up PLGrid access in OpenCode's graphical apps: the desktop app and the web
interface. They use the same server as the TUI, so the plugin, the config, the agents
and the key are the same; only where you click differs.

The steps were tested with the 2.x desktop app and the 1.x and 2.x web UI. The 1.x
desktop app has not been tested. What was tested, and how, is in
[research/gui.md](research/gui.md).

## 1. Check your OpenCode version

In the desktop app, open **Settings → About**: `Version 2.…` means 2.x. For the web
UI, run `opencode --version` in a terminal, as in the
[README](README.md#1-check-your-opencode-version). Steps 4 and 5 differ between 1.x and
2.x.

## 2. Copy the setup files

The graphical apps have no installer for plugins, so copy the files as in the
[README](README.md#2-copy-the-setup-files), with the commands there or with a file
manager. The plugin folder `.opencode` is hidden; show hidden files to see it.

- **Per project:** `.opencode/`, `AGENTS.md` and `opencode.json` go into the root of your
  project. PLGrid is then available in that project only.
- **Machine-wide:** `plgrid.js` goes into `~/.config/opencode/plugins/` and
  `opencode.json` becomes `~/.config/opencode/opencode.json`. PLGrid is then
  available in every project.

## 3. Open your project

- **Desktop app:** on the home screen, click **Add project** and choose your project
  folder. With a machine-wide install, any project works.
- **Web UI, 1.x:** run `opencode web` in your project directory.
- **Web UI, 2.x:** open the address that `opencode service status` prints, then open your
  project.

Copy the files before you start the app. If it was already running and PLGrid does not
appear in step 4, close it and start it again. On 2.x the background service keeps
running after the app closes, so restart it too with `opencode service restart`. The
desktop app's own copy of `opencode` is in `~/.config/ai.opencode.desktop/cli/`.

## 4. Log in to PLGrid

Skip this step if you already logged in with the CLI
([README, step 3](README.md#3-log-in-and-verify)): the apps use the same stored key.
Have your key from <https://llmlab.plgrid.pl> (**Grants → Generate API Key**) at hand.

### OpenCode 2.x, per project

1. Open a session in your project.
2. Type `/connect` and press **Enter**.
3. Choose **PLGrid Forge (Cyfronet)** from the list.
4. Paste your key into **PLGrid Forge (Cyfronet) API key** and click **Continue**.
5. In **Choose a model to start with**, click **DeepSeek V4.1 Flash (non-commercial)**,
   then **Continue**.

The global **Settings → Providers** page does not offer PLGrid with a per-project
install, because the plugin is loaded only inside the project. Log in from a session.

### OpenCode 2.x, machine-wide

1. Open **Settings → Providers**.
2. Click **Show more providers** and choose **PLGrid Forge (Cyfronet)**.
3. Paste your key into **PLGrid Forge (Cyfronet) API key** and click **Continue**.
4. In **Choose a model to start with**, click **DeepSeek V4.1 Flash (non-commercial)**,
   then **Continue**.

**Settings → Providers** now lists PLGrid Forge (Cyfronet) under **Connected
providers**. `/connect` in any session, as in the per-project steps, works too.

> [!WARNING]
> Choose the model in the last step. **Continue** alone selects the first model in the
> list, GLM-5.2 FP8, which timed out on every request in the benchmark, and new
> sessions then start on it. To fix that later, choose DeepSeek V4.1 Flash in the
> model picker.

### OpenCode 1.x

1. Open the model picker in the message box.
2. Click **Manage models**, then **Connect provider**.
3. Choose **PLGrid Forge (Cyfronet)**, paste your key and confirm.

**Settings → Providers** lists PLGrid as "Connected (Config)" even with no key stored,
so it has no Connect button there; use the model picker.

## 5. Set up the app once

### OpenCode 2.x

1. **Turn on the agent picker.** Open **Settings → Preferences** and turn on **Show
   agent**. Without it every session uses the built-in `build` agent, and `architect`
   and `chat` cannot be chosen.
2. **Turn on the PLGrid models, if they are missing.** After logging in from the app
   they are on. If you logged in with the CLI, open the model picker → **Manage
   models** and turn on the **PLGrid Forge (Cyfronet)** group.

Both settings belong to the app, not to the project: set them once.

### OpenCode 1.x web UI

Pick the model by hand. A new session starts on OpenCode's own "Big Pickle" instead of
the default from `opencode.json`. Choosing the `architect` agent switches to its
configured model.

## 6. Check

1. Open a new session in your project.
2. The model picker shows a **PLGrid Forge (Cyfronet)** group with 20 models, and the
   message box shows **DeepSeek V4.1 Flash (non-commercial)**.
3. The agent picker lists **Architect** and **Chat** next to Build and Plan.
4. Send a short message, for example "Reply with OK". An answer means the key works.

If your grant cannot use DeepSeek V4.1 Flash, the answer is *"not available for grant"*;
see *Known issues* in the [README](README.md#known-issues).

## Desktop app notes

- **Download.** <https://opencode.ai/download> serves the 2.x desktop app. The 1.x
  desktop app is only on GitHub, as the `opencode-desktop-*` assets of a
  [1.x release](https://github.com/anomalyco/opencode/releases/tag/v1.18.35). On Linux
  the 1.x and 2.x `.deb` packages have the same name, so installing one replaces the
  other.
- **`npx` on PATH.** The app takes its environment from your login shell. The context7
  MCP server in `opencode.json` needs `npx`, so it must be on the PATH your shell
  startup files set, not only in a terminal you opened.
- **One background service.** The 2.x desktop app runs the background service from its
  own copy of OpenCode, which a 2.x TUI on the same machine then uses too.
