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

So each fixture ships with a `score.py` that runs hidden cases with answers derived
independently of any model output.

## The fixtures

### `calc/` — multi-file defect fixing

Six failing tests, three defect classes across two files:

- `tokenize` returns strings, so arithmetic concatenates instead of adding
- no operator precedence (`2 + 3 * 4` is evaluated left to right)
- no empty-input guard (`IndexError` instead of `ValueError`)

Hidden cases: 14 arithmetic expressions, including chained multiplication
(`2 * 3 * 4`), mixed precedence (`1 * 2 + 3 * 4 + 5 * 6`) and type-strictness — a
result of `"6"` is counted wrong even where `== 6` would pass.

### `ledger/` — a design change

Seven failing tests that cannot be satisfied by patching lines. The suite demands a
concept the code does not have: `Money` must carry a currency, cross-currency
arithmetic must raise, `Account` must be currency-aware, and accumulated deposits
must not drift in floating point.

Hidden probes: eight behaviours the suite omits — chained addition, mixed-currency
rejection in *both* operand orders, `Money == 42` (must not raise), case-sensitive
currency comparison, drift over 100 additions and over a different value, the
currency of an empty balance, and depositing a correct-currency `Money` object.

Five of six models reached for `decimal.Decimal` unprompted here, which is the right
instinct for money.

## Running them

Each fixture directory is self-contained: the package under test, its `test_*.py`
specification, and `score.py`. Copy it somewhere writable, point an agent at it, then
score.

```bash
# 1. copy a pristine fixture into a working directory inside your project
cp -r research/benchmarks/calc ./bench-run && cd ./bench-run

# 2. record the spec hash, to detect a model editing the tests instead of the code
md5 -q test_calc.py            # or: md5sum test_calc.py

# 3. let the agent work
opencode run --auto -m plgrid/zai-org/GLM-4.7-Flash \
  'The test suite in test_calc.py is the specification and must NOT be modified.
   Run it with python3 -m pytest, then fix the code under calc/ until every test
   passes. Re-run the tests after each change. Report the final pytest summary line.'

# 4. confirm the spec is untouched, then score — only after the run has finished
md5 -q test_calc.py
python3 score.py
```

`score.py` prints the spec result and the hidden-case result side by side, so a false
pass is immediately visible. Run against the pristine fixture it reports
`6 failed … 0/14`, which is the expected starting state:

```
dir      spec                hidden  first failures
calc     6 failed in 0.03s   0/14    '2 * 3 * 4'->TypeError; …
```

For `ledger`, substitute `test_ledger.py` and `ledger/`, and use the prompt in
[../models.md](../models.md) — it needs an explicit hint that a design change is
expected, or a model may try to patch lines and stall.

## Method notes

Things that will corrupt your results if you skip them:

- **Run models sequentially.** Parallel `opencode` instances contend on one SQLite
  database and die with `database is locked`.
- **Score only settled directories.** Reading a working directory while the agent is
  still writing gives a half-finished file. This produced a completely wrong verdict
  on one model before it was caught — a model scored 0/6 mid-run and 14/14 once
  finished.
- **Guard the spec.** Hash the test file before and after. A model that edits the
  tests has not solved anything. (In 18 runs, none did.)
- **Do not trust the exit code.** `opencode run` occasionally exits 0 having done
  nothing. Assert on the artifact.
- **Work inside the project directory.** Runs under `/tmp` may have writes rejected
  as `external_directory`, which looks exactly like model failure but is a permission
  refusal.
- **Cap `steps`.** It defaults to `Infinity`; a spinning model will not stop on its
  own.

## Limits

Two fixtures, one language, self-contained files, 18 runs. Enough to separate
"reliably correct on multi-file work" from "not", and enough to catch one real
reliability problem. Not enough to say anything about large codebases, long sessions
near context limits, or ambiguous requirements — extend the fixtures if that is what
you need to know.
