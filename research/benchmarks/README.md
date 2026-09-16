# Agentic benchmark fixtures

Two fixtures for measuring whether a model can actually do multi-file work in
OpenCode — plus the thing that makes them useful, **differential scorers** that test
cases the model never saw.

## Why differential scoring

The obvious way to benchmark a coding agent is to give it a failing test suite and
check whether the suite passes afterwards. That is not enough. A model can make every
test green while leaving the code wrong, because the tests do not constrain the cases
they do not cover.

This is not hypothetical. On `calc`, one model produced a solution where `pytest`
reported `6 passed` and `evaluate("2 * 3 * 4")` returned `10` instead of `24` — its
algorithm collapsed consecutive multiplications, which the suite never exercised. A
pass/fail benchmark would have recorded that model as flawless.

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

In the final 2026-09-16 runs, 14 of the 18 solutions that passed the suite reached for
`decimal.Decimal` unprompted, which is the right instinct for money.

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
inherits it); `git`; and `opencode` with the plgrid provider logged in
(`opencode providers login -p plgrid`). `--help` lists the environment variables.

Each agentic run, in order:

1. copies the fixture into a fresh temp directory named `r<N>-<fixture>` and makes it
   a git repository with one pristine commit;
2. hashes the spec (`test_<fixture>.py`) and the scorer;
3. runs `opencode run --auto --agent bench -m plgrid/<model> '<prompt>'` there, with
   the fixture's prompt from the script and a 30-minute timeout;
4. once the agent has exited — never before — re-checks both hashes, records the diff
   against the pristine commit, restores the original spec if the agent edited it, and
   runs `scorers/<fixture>.py` on the directory;
5. archives the directory, the log and the diff under `bench-run/<run-id>/<model>/`.

Models the plugin does not register, or the gateway will not serve to this grant, are
listed as skipped with the gateway's own reason (for example `not available for
grant`) instead of being run into a failure. The output is a report,
`results/bench-<run-id>.txt` — one block per run, then a summary table — and
`results/bench-<run-id>.tsv` with one row per run or skipped model;
`python3 research/benchmarks/summarize.py <tsv>` reprints the summary.

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
directory to PATH.

## The benchmark environment

The run should measure the model, not this repository's setup, so OpenCode is
configured from scratch for it:

- **Config.** `XDG_CONFIG_HOME` points at `bench-run/xdg-config/`, which holds only
  [`bench-opencode.json`](bench-opencode.json) and the plgrid plugin, and
  `OPENCODE_DISABLE_PROJECT_CONFIG=1` plus `OPENCODE_DISABLE_CLAUDE_CODE=1` switch off
  the project's `opencode.json`, `.opencode/` and `AGENTS.md`, and Claude Code's global
  files. Runs before this inherited all of those: the repo's `AGENTS.md` (which tells
  agents to delegate, while the benchmark forbids it), the context7 MCP server, the
  formatter, and the personal permissions in `~/.config/opencode`.
- **Agent.** `bench` has the built-in build agent's tools, `steps: 30` (the default is
  unbounded, and a spinning model never stops), and `task` delegation denied, so the
  measured model cannot hand its work to another.
- **Formatter off.** A formatter rewrites files after the agent's edits — once
  including a spec a model had edited — and a model whose idea of a file no longer
  matches the disk fails its next exact-match edit. LSP diagnostics stay on: they are
  information, not changes.
- **Permissions.** `external_directory` and `webfetch` are denied; shell commands are
  allowed except `rm -rf`, `git push`, `git rebase` and `git reset --hard`. Refused
  calls are counted per run as `blocked calls`. In the final 2026-09-16 run there were
  three, all a model mistyping the absolute path of its own working directory — a
  genuinely different path, so correctly refused.
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
  everything around it: on 2026-09-16 `GLM-5.2-FP8` browsed up and read its own
  finished solution to the other fixture. Each run therefore works in its own temp git
  repository, which OpenCode treats as the project, so the rest of the disk is an
  `external_directory` and denied. That covers OpenCode's file tools and paths it can
  see in shell commands, not something like `python3 -c "open('/elsewhere')"`, so the
  runner also flags any log line mentioning `research/benchmarks/` or `bench-run/`.
- **Never name the working directory after the package.** A working directory called
  `ledger/` holding the `ledger/` package let `Qwen3-Coder-30B` write its modules one
  level too high, add an `__init__.py` beside them, and pass the suite —
  `from ledger.money import Money` resolved to the working directory itself — while
  the scorer imported the untouched package and saw 0/8. That happened in 2 of 3 runs.
  Working directories are now named `r<N>-<fixture>`.
- **Run models sequentially.** Concurrent runs compete for the shared gateway and skew
  each other's timings; on a shared session database they also die with
  `database is locked`.
- **Score only settled directories.** Reading a working directory while the agent is
  still writing gives a half-finished file. This produced a completely wrong verdict
  on one model before it was caught — a model scored 0/6 mid-run and 14/14 once
  finished.
- **Guard the spec, and score against the original.** Hash the test file before and
  after. A model that edits the tests has not solved anything, and scoring the edited
  file credits it anyway: `Llama-3.3-70B` edited `test_ledger.py` in every final
  2026-09-16 run, despite the prompt forbidding it, weakening the tests to fit its own
  code until twice they all passed. The runner keeps the edit in the run's diff and
  restores the original before scoring, against which the same code passes 5 of 7.
- **Keep the scorer out of reach.** Until 2026-09-16 each fixture carried its own
  `score.py`, so copying the fixture copied the hidden cases into the agent's working
  directory. On that day's run `DeepSeek-V4.1-Flash` ran it mid-task and reported that
  "the hidden probes pass", and `GLM-5.2-FP8` read it before writing its ledger
  solution — neither result was blind. The scorers now live in `scorers/`, outside the
  fixtures, and the runner hashes the scorer around every run. Treat a run with
  anything on its `scorer access:` line as not blind.
- **Do not trust the exit code.** `opencode run` exits 0 having done nothing —
  `Qwen3.6-27B` once did by ending its turn after two tool calls. Assert on the
  artifact.
- **Repeat.** One run cannot tell a reliable model from a lucky one: `Qwen3.6-35B-A3B`
  scored 22/22 in one run and a silently wrong 17/22 in another. `REPEATS=3` runs each
  model and fixture three times, round-robin, so a slow spell on the gateway hits
  every model.
- **Keep the evidence.** The runner used to reuse one working directory per fixture,
  so each run erased the previous model's files and log — including the only record
  of which models had read the scorer. Every run is now archived.

## Throughput

`gateway.py throughput`, which `bench-all.sh` runs, streams one fixed prompt at
temperature 0 and forces exactly `THROUGHPUT_TOKENS` (default 300) output tokens by
setting both `min_tokens` and `max_tokens`. It reports `tok/s`, the generation rate
from the first to the last streamed token; `ttft s`, the time to first token; and
`e2e tok/s`, tokens over total wall time.

Two things made earlier throughput figures unreliable:

- **Output length was not fixed.** A 300-token budget is not a 300-token output.
  Models that stopped after about 50 tokens had their rate dominated by fixed latency:
  `Qwen3-Coder-30B` measured 88 tok/s that way, and 146 tok/s generation rate when
  forced to 300 tokens the same afternoon.
- **The gateway is shared.** Within two minutes on 2026-09-16, `Qwen3.6-35B-A3B`
  measured 54, 174 and 213 tok/s. Rounds are therefore interleaved across models (a
  load spike hits all of them, not one), repeated `THROUGHPUT_REPEATS` times (default
  5), and the min–max range is printed next to the median. Treat rankings whose ranges
  overlap as ties.

## Limits

Two fixtures, one language, self-contained files. On 2026-09-16 the 8 reachable
tool-capable models ran both fixtures six times, blind, in two rounds: three runs with
the scorer out of reach but the older working-directory layout
([results/rerun-20260916-blind-x3.tsv](results/rerun-20260916-blind-x3.tsv)), then
three fully isolated runs with this runner
([results/bench-20260916-141623.txt](results/bench-20260916-141623.txt)). Six runs per
model is enough to separate "reliably correct on multi-file work" from "not", and
enough to catch real reliability problems — not enough to estimate a failure rate.
Not enough to say anything about large codebases, long sessions near context limits,
or ambiguous requirements — extend the fixtures if that is what you need to know.

Two caveats on the files in `results/`. The throughput section of
`bench-20260916-141623.txt` was measured under heavy gateway load; the figures the
docs quote are from `throughput-20260916-1245.txt`. And that run predates the
restore-before-scoring step, so its `spec` column for `Llama-3.3-70B`'s three `ledger`
runs is against the edited tests (7/7, 5/7, 7/7); the md5 column marks them, and
re-scored against the original all three pass 5 of 7. Hidden scores are unaffected.
