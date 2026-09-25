# Agentic benchmark fixtures

Two fixtures for measuring whether a model can actually do multi-file work in
OpenCode — plus the thing that makes them useful, **differential scorers** that test
cases the model never saw.

## Why differential scoring

The obvious way to benchmark a coding agent is to give it a failing test suite and
check whether the suite passes afterwards. That is not enough. A model can make every
test green while leaving the code wrong, because the tests do not constrain the cases
they do not cover.

This is not hypothetical. On `calc`, a model can produce a solution where `pytest`
reports `6 passed` while `evaluate("2 * 3 * 4")` returns `10` instead of `24` — an
algorithm that collapses one multiplication and skips the next, a case the suite never
exercises. A pass/fail benchmark records that model as flawless.

So each fixture has a scorer in [`scorers/`](scorers/) that runs hidden cases with
answers derived independently of any model output. The scorers live outside the
fixture directories on purpose: a scorer that gets copied into the agent's working
directory is one the agent can read, run, or edit (see *Keep the scorer out of reach*
below).

## The fixtures

### `calc/` — multi-file defect fixing

Six failing tests, three defect classes across two files:

- `tokenize` returns strings, so arithmetic concatenates instead of adding
- no operator precedence (`2 + 3 * 4` is evaluated left to right)
- no empty-input guard (`IndexError` instead of `ValueError`)

Hidden cases: 14 arithmetic expressions, including chained multiplication
(`2 * 3 * 4`), mixed precedence (`1 * 2 + 3 * 4 + 5 * 6`) and type-strictness — a
result of `24.0` is counted wrong even though `== 24` passes, so a float-returning
evaluator can pass the whole suite and still score 0/14. (A string result needs no such
check: `"24" == 24` is already `False`, and the suite fails.)

### `ledger/` — a design change

Seven failing tests that cannot be satisfied by patching lines. The suite demands a
concept the code does not have: `Money` must carry a currency, cross-currency
arithmetic must raise, `Account` must be currency-aware, and accumulated deposits
must not drift in floating point.

Hidden probes: eight behaviours the suite omits — chained addition, mixed-currency
rejection in *both* operand orders, `Money == 42` (must not raise), case-sensitive
currency comparison, drift over 100 additions and over a different value, the
currency of an empty balance, and depositing a correct-currency `Money` object. Each
probe has an explicit expected value and counts as passed only if it returns exactly
that — not merely if it returns without raising.

Most solutions that pass the suite reach for `decimal.Decimal` unprompted, which is
the right instinct for money. The most common miss is `Money == 42`: an `__eq__` that
reads `other.amount` without checking the type raises `AttributeError` instead of
returning `False`, and the suite never compares `Money` with anything else.

## Running them

[`bench-all.sh`](bench-all.sh) runs the fixtures, for one model or the whole catalog:

```bash
# one model, one fixture, three repeats
MODELS="Qwen/Qwen3.6-27B" FIXTURES=calc REPEATS=3 research/benchmarks/bench-all.sh --correctness-only

# everything: throughput for every active model, fixtures for the tool-capable ones
REPEATS=3 research/benchmarks/bench-all.sh
research/benchmarks/bench-all.sh --throughput-only
```

**Prerequisites.** `LLMLAB_API_KEY` exported or in the repo-root `.env`; the project
`venv/` with `pytest` (the script activates it, and the agent's `python3 -m pytest`
inherits it); `git`; `opencode` with the plgrid provider logged in
(`opencode providers login -p plgrid`); bash 4 or newer; and GNU coreutils `timeout`
and `md5sum`. On macOS: `brew install bash coreutils`. The script checks all of this
before it starts. `--help` lists the environment variables.

`MODELS` runs exactly the models you name, including ones the catalog marks as unable
to call tools — useful for checking a model the catalog may have wrong, but a model
without tool calling simply scores 0.

Each agentic run, in order:

1. copies the fixture into a fresh temp directory named `r<N>-<fixture>` and makes it
   a git repository with one pristine commit;
2. hashes the spec (`test_<fixture>.py`) and the scorer;
3. runs `opencode run --auto --agent bench -m plgrid/<model> '<prompt>'` there, with
   the fixture's prompt from the script and a timeout (`RUN_TIMEOUT`, default 30
   minutes);
4. once the agent has exited — never before — re-checks both hashes, records the diff
   against the pristine commit, restores the original spec if the agent edited it, and
   runs `scorers/<fixture>.py` on the directory;
5. archives the directory, the log and the diff under `bench-run/<run-id>/<model>/`.

Models the plugin does not register, or the gateway will not serve to your grant, are
listed as skipped with the gateway's own reason (for example `not available for
grant`) instead of being run into a failure. The output is a report,
`results/bench-<run-id>.txt` — one block per run, then a summary table — and
`results/bench-<run-id>.tsv` with one row per run or skipped model;
`python3 research/benchmarks/summarize.py <tsv>` reprints the summary.

Both files are meant to be committed, so on exit [`redact.py`](redact.py) replaces the
temp directory, the checkout path and `$HOME` with `<tmp>`, `<repo>` and `~`, and masks
grant ids. The archive under `bench-run/` (gitignored) keeps the raw logs.

The scorers also work by hand on any working directory, several at once. They print
the spec result and the hidden-case result side by side, so a false pass is
immediately visible; against a pristine fixture they report `6 failed … 0/14`, the
expected starting state:

```
$ python3 research/benchmarks/scorers/calc.py bench-run/<run-id>/Qwen__Qwen3.6-27B/r1-calc
dir                                              spec   hidden  first failures
r1-calc                                        6 passed in 0.01s    14/14
```

`scorers/ledger.py` prints a `spec: … hidden: N/8` line plus one PASS/FAIL line per
probe; `--tsv-file PATH` makes either scorer also append one machine-readable line per
directory to PATH. A solution that prints to stdout does not disturb the result: the
scorer reads it from its own marked line.

## The benchmark environment

The run should measure the model, not this repository's setup, so OpenCode is
configured from scratch for it:

- **Config.** `XDG_CONFIG_HOME` points at `bench-run/xdg-config/`, which holds only
  [`bench-opencode.json`](bench-opencode.json) and the plgrid plugin, and
  `OPENCODE_DISABLE_PROJECT_CONFIG=1` plus `OPENCODE_DISABLE_CLAUDE_CODE=1` switch off
  the project's `opencode.json`, `.opencode/` and `AGENTS.md`, and Claude Code's global
  files. Otherwise a run inherits the repo's `AGENTS.md` (which tells agents to
  delegate, while the benchmark forbids it), MCP servers, the formatter, and your
  personal permissions.
- **Agent.** `bench` has the built-in build agent's tools, `steps: 30` (the default is
  unbounded, and a spinning model never stops), and `task` delegation denied, so the
  measured model cannot hand its work to another.
- **Formatter off.** A formatter rewrites files after the agent's edits — including a
  spec a model has edited — and a model whose idea of a file no longer matches the
  disk fails its next exact-match edit. LSP diagnostics stay on: they are
  information, not changes.
- **Permissions.** `external_directory` and `webfetch` are denied; shell commands are
  allowed except `rm -rf`, `git push`, `git rebase` and `git reset --hard`. Refused
  calls are counted per run as `blocked calls`; the usual cause is a model mistyping
  the absolute path of its own working directory, which is a genuinely different path
  and correctly refused.
- **Sessions.** `OPENCODE_DB` is private to the invocation
  (`bench-run/<run-id>/opencode.db`), so benchmark sessions stay out of your own
  session list. `opencode session list` only shows the current directory's project,
  so find a run's session ID in the database, then export it with the same variable:

  ```bash
  DB=$PWD/bench-run/<run-id>/opencode.db
  python3 -c "import sqlite3,sys; [print(*r) for r in sqlite3.connect(sys.argv[1]).execute('select id, directory from session')]" "$DB"
  OPENCODE_DB=$DB opencode export <session-id>
  ```

## Method notes

Things that will corrupt your results if you skip them. `bench-all.sh` handles each;
they matter if you change it or run a fixture by hand.

- **Isolate every run.** A working directory inside the project lets the agent read
  everything around it, including its own finished solution to the other fixture.
  Each run therefore works in its own temp git repository, which OpenCode treats as
  the project, so the rest of the disk is an `external_directory` and denied. That
  covers OpenCode's file tools and paths it can see in shell commands, not something
  like `python3 -c "open('/elsewhere')"`, so the runner also flags any log line
  mentioning `research/benchmarks/` or `bench-run/`. The isolation is therefore
  best-effort: an agent determined to hide a read could still do it.
- **Never name the working directory after the package.** A working directory called
  `ledger/` holding the `ledger/` package lets a model write its modules one level too
  high, add an `__init__.py` beside them, and pass the suite —
  `from ledger.money import Money` resolves to the working directory itself — while
  the scorer imports the untouched package and sees 0/8. Working directories are
  named `r<N>-<fixture>`.
- **Run models sequentially.** Concurrent runs compete for the shared gateway and skew
  each other's timings; on a shared session database they also die with
  `database is locked`.
- **Score only settled directories.** Reading a working directory while the agent is
  still writing gives a half-finished file and a verdict that has nothing to do with
  the model.
- **Guard the spec, and score against the original.** Hash the test file before and
  after. A model that edits the tests has not solved anything, and scoring the edited
  file credits it anyway — `Llama-3.3-70B` rewrites `test_ledger.py` despite the
  prompt forbidding it, weakening the tests until they fit its code. The runner keeps
  the edit in the run's diff and restores the original before scoring.
- **Keep the scorer out of reach.** A scorer inside the fixture is copied into the
  agent's working directory, and models do find it: they run it mid-task and report
  that the hidden cases pass, or read it before writing their solution. The scorers
  live in `scorers/`, outside the fixtures, and the runner hashes the scorer around
  every run. Treat a run with anything on its `scorer access:` line as not blind.
- **Do not trust the exit code.** `opencode run` can exit 0 having done nothing — a
  model that ends its turn after two tool calls leaves the code untouched. Assert on
  the artifact.
- **Repeat.** One run cannot tell a reliable model from a lucky one: the same model
  can score 22/22 in one run and a silently wrong 17/22 in another. `REPEATS=3` runs
  each model and fixture three times, round-robin, so a slow spell on the gateway hits
  every model.
- **Keep the evidence.** Every run is archived with its log and diff; the log is the
  only record of whether a model went looking for the scorer.

## Throughput

`gateway.py throughput`, which `bench-all.sh` runs, streams one fixed prompt at
temperature 0 and forces exactly `THROUGHPUT_TOKENS` (default 300) output tokens by
setting both `min_tokens` and `max_tokens`. It reports `tok/s`, the generation rate
from the first to the last streamed token; `ttft s`, the time to first token; and
`e2e tok/s`, tokens over total wall time.

Two things make naive throughput figures unreliable:

- **Output length must be fixed.** A 300-token budget is not a 300-token output. A
  model that stops after about 50 tokens has its rate dominated by fixed latency:
  `Qwen3-Coder-30B` measures about 88 tok/s that way and about 146 tok/s when forced to
  300 tokens.
- **The gateway is shared.** Within two minutes one model can measure 54, 174 and
  213 tok/s. Rounds are therefore interleaved across models (a load spike hits all of
  them, not one), repeated `THROUGHPUT_REPEATS` times (default 5), and the min–max
  range is printed next to the median. Treat rankings whose ranges overlap as ties.

For agentic work, `e2e tok/s` is the better guide: an agent makes many short requests,
and a model with a fast generation rate but a slow first token is not fast end to end.

## Limits

Two fixtures, one language, self-contained files, three runs per model. That is
enough to separate "reliably correct on multi-file work" from "not", and enough to
catch real reliability problems — not enough to estimate a failure rate. It says
nothing about large codebases, long sessions near context limits, or ambiguous
requirements; extend the fixtures if that is what you need to know. A run measures
the models your grant can reach, on the gateway's load at the time.
