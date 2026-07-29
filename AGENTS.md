# Working agreement

This file is loaded into the system prompt of every agent in this project (via
`"instructions": ["AGENTS.md"]` in `opencode.json`). It is the OpenCode
equivalent of `CLAUDE.md`.

The models here are PLGrid Forge open-weight models, not frontier models. They
follow explicit instructions well and drift when left to infer intent, so this
file is deliberately concrete.

## Before you write code

- Read the files you are about to change. Do not edit from memory of a filename.
- If the request is ambiguous in a way that changes the output, ask. One question,
  then proceed.
- Do not add dependencies without saying so first.

## While writing

- Match the surrounding code: its naming, its comment density, its idioms. A
  patch should be unnoticeable in a diff review except for the behaviour change.
- Prefer new values over mutating existing ones.
- Small files over large ones. Extract when a file grows past ~400 lines.
- Handle errors explicitly. Never swallow an exception silently.
- Validate input at boundaries — anything from a user, a file, or an API.
- No hardcoded secrets, ever. Environment or a key file.

## Verifying

- Run the code. `python3 the_file.py` or the project's test command.
- Report what actually happened, including failures, with the real output.
- If you did not verify something, say that you did not.
- The language server reports diagnostics back to you after every edit, inside a
  `<diagnostics>` tag. Treat those as authoritative and fix them before moving
  on — do not re-run a linter by hand to double-check.

## Commands

- `/check` — type-check and test, then fix what fails
- `/review` — review the working diff for defects
- `/explain <thing>` — trace how something works, with file:line citations

## Do not

- Do not commit or push unless asked.
- Do not reformat files you were not asked to touch.
- Do not describe work as complete when part of it is unfinished — say which part.

## Available subagents

Invoke with `@name`:

- `@researcher` — traces how something works across the codebase. Read-only,
  pinned to the largest-context model.
- `@reviewer` — reviews a change for real defects. Read-only, temperature 0.1.
- `@fastfix` — small mechanical edits on the fastest model (~5s).

Switch primary agents with **Tab**. For larger multi-step tasks use `architect`:
it plans and delegates to the subagents above but cannot edit files itself. Use the `chat` agent for the PLGrid models
that lack function calling, or they will fail with HTTP 400.
