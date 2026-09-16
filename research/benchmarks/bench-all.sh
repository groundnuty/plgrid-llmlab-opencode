#!/usr/bin/env bash
#
# Benchmark every PLGrid Forge chat model end to end.
#
# Measures, for each model:
#   - throughput: fixed-length streaming completions via the API (gateway.py):
#     generation rate and time to first token over interleaved rounds
#   - correctness: agentic OpenCode runs on the calc and ledger fixtures, scored on
#     hidden differential cases the model never saw (scorers/)
#
# Every agentic run is isolated. It works in a fresh git repository in a temp
# directory outside the project, so anything else on disk is an external_directory,
# which the benchmark config denies. OpenCode is configured only from
# bench-opencode.json plus the plgrid plugin - no project config, AGENTS.md, MCP
# servers, formatter or personal config - with a session database private to this
# invocation. After scoring, the working directory, log and diff are archived under
# bench-run/<run-id>/; nothing is overwritten.
#
# Writes a report (.txt) and a per-run table (.tsv). Runs are sequential on purpose:
# parallel runs would contend for the gateway and skew each other's timings.
#
# Usage:
#   research/benchmarks/bench-all.sh [--throughput-only|--correctness-only] [report.txt]
#
# Environment:
#   MODELS="a/b c/d"       restrict the model set (default: every active model)
#   FIXTURES="calc"        restrict the fixtures (default: calc ledger)
#   REPEATS=3              agentic runs per model and fixture (default: 1)
#   THROUGHPUT_REPEATS=5   interleaved throughput rounds (default: 5)
#   THROUGHPUT_TOKENS=300  output tokens forced per throughput request (default: 300)
#   RUN_TIMEOUT=1800       seconds per agentic run (default: 1800)
#   TMPDIR                 where the isolated working directories are created
#
# Requirements: LLMLAB_API_KEY (exported, or in the repo-root .env), the project venv
# with pytest, git, and opencode with the plgrid provider logged in
# (opencode providers login -p plgrid).

set -uo pipefail

BENCH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$BENCH/../.." && pwd)"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
ARCHIVE="$ROOT/bench-run/$RUN_ID"
# Persistent across invocations, so OpenCode installs the plugin's dependency once.
CONFIG_HOME="$ROOT/bench-run/xdg-config"
REPEATS="${REPEATS:-1}"
THROUGHPUT_REPEATS="${THROUGHPUT_REPEATS:-5}"
THROUGHPUT_TOKENS="${THROUGHPUT_TOKENS:-300}"
RUN_TIMEOUT="${RUN_TIMEOUT:-1800}"
read -r -a FIXTURES <<< "${FIXTURES:-calc ledger}"

die() { echo "error: $*" >&2; exit 1; }

MODE=all
OUT=""
for arg in "$@"; do
  case "$arg" in
    --throughput-only)  MODE=throughput ;;
    --correctness-only) MODE=correctness ;;
    -h|--help) awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; exit 0 ;;
    --*) echo "unknown option: $arg" >&2; exit 2 ;;
    *)   OUT="$arg" ;;
  esac
done

for var in REPEATS THROUGHPUT_REPEATS THROUGHPUT_TOKENS RUN_TIMEOUT; do
  [[ "${!var}" =~ ^[1-9][0-9]*$ ]] || die "$var must be a positive integer, got '${!var}'"
done

if [[ -z "$OUT" ]]; then
  mkdir -p "$BENCH/results" || die "cannot create $BENCH/results"
  OUT="$BENCH/results/bench-$RUN_ID.txt"
fi
TSV="${OUT%.txt}.tsv"

# --- prerequisites ---------------------------------------------------------
# An exported key wins over the one in .env.
if [[ -z "${LLMLAB_API_KEY:-}" && -f "$ROOT/.env" ]]; then
  set -a; . "$ROOT/.env"; set +a
fi
[[ -n "${LLMLAB_API_KEY:-}" ]] || die "LLMLAB_API_KEY is not set (export it or put it in $ROOT/.env)"
if [[ -f "$ROOT/venv/bin/activate" ]]; then
  . "$ROOT/venv/bin/activate"
fi
command -v opencode >/dev/null || die "opencode not on PATH"
command -v git >/dev/null || die "git not on PATH"
python3 -c 'import pytest' 2>/dev/null || die "python3 cannot import pytest; install it into the project venv"

# --- helpers ---------------------------------------------------------------
emit() { tee -a "$OUT"; }
strip_ansi() { sed 's/\x1b\[[0-9;]*m//g'; }

tsv_row() {
  local field clean=()
  for field in "$@"; do clean+=("${field//[$'\t\n']/ }"); done
  (IFS=$'\t'; printf '%s\n' "${clean[*]}") >> "$TSV"
}

# OpenCode sees only the benchmark config: XDG_CONFIG_HOME replaces the personal
# ~/.config/opencode, and project config (opencode.json, .opencode/, AGENTS.md) and
# Claude Code's global files are switched off.
OC_ENV=(env XDG_CONFIG_HOME="$CONFIG_HOME" OPENCODE_DISABLE_PROJECT_CONFIG=1
        OPENCODE_DISABLE_CLAUDE_CODE=1 OPENCODE_DISABLE_AUTOUPDATE=1
        OPENCODE_DB="$ARCHIVE/opencode.db")

prompt_for() {
  case "$1" in
    calc) cat <<'EOF'
The test suite in test_calc.py is the specification and must NOT be modified. Run it
with python3 -m pytest, then fix the code under calc/ until every test passes. Re-run
the tests after each change. Report the final pytest summary line.
EOF
      ;;
    ledger) cat <<'EOF'
The test suite in test_ledger.py is the specification and must NOT be modified. This is
a design change, not a line-level patch: the suite requires concepts the code does not
yet have (for example, a currency on Money). Read the tests, infer the model they
imply, then implement it under ledger/ until every test passes. Run python3 -m pytest,
and re-run it after each change. Report the final pytest summary line.
EOF
      ;;
    *) echo "unknown fixture: $1" >&2; return 1 ;;
  esac
}

for fixture in "${FIXTURES[@]}"; do
  [[ -f "$BENCH/$fixture/test_$fixture.py" && -f "$BENCH/scorers/$fixture.py" ]] \
    && prompt_for "$fixture" >/dev/null || die "unknown fixture: $fixture"
done

# --- select models ---------------------------------------------------------
CATALOG="$(python3 "$BENCH/gateway.py" models)" || die "could not fetch the model catalog"
[[ -n "$CATALOG" ]] || die "the model catalog is empty"
mapfile -t ROWS <<< "$CATALOG"
THROUGHPUT_ALL=(); CORRECTNESS_ALL=()
for row in "${ROWS[@]}"; do
  IFS=$'\t' read -r name active accessible fc <<< "$row"
  [[ "$active" == 1 ]] && THROUGHPUT_ALL+=("$name")
  [[ "$active" == 1 && "$fc" == 1 ]] && CORRECTNESS_ALL+=("$name")
done

if [[ -n "${MODELS:-}" ]]; then
  read -r -a THROUGHPUT_MODELS <<< "$MODELS"
  CORRECTNESS_MODELS=("${THROUGHPUT_MODELS[@]}")
else
  THROUGHPUT_MODELS=("${THROUGHPUT_ALL[@]}")
  CORRECTNESS_MODELS=("${CORRECTNESS_ALL[@]}")
fi

# --- report header ---------------------------------------------------------
REPO_STATE="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
[[ -n "$(git -C "$ROOT" status --porcelain 2>/dev/null)" ]] && REPO_STATE+=" + uncommitted changes"
{
  echo "================================================================================"
  echo "PLGrid Forge model benchmark"
  echo "run id:             $RUN_ID"
  echo "started:            $(date -Is)"
  echo "host:               $(hostname)"
  echo "repo:               $REPO_STATE"
  echo "opencode:           $(opencode --version 2>/dev/null)"
  echo "mode:               $MODE"
  echo "throughput:         $THROUGHPUT_TOKENS output tokens forced, temperature 0, $THROUGHPUT_REPEATS interleaved rounds"
  echo "correctness:        ${FIXTURES[*]}; $REPEATS repeat(s); bench agent (30 steps, no delegation)"
  echo "isolation:          temp git repo per run; bench-opencode.json + plgrid plugin only"
  echo "run timeout:        ${RUN_TIMEOUT}s per agentic run"
  echo "throughput models:  ${#THROUGHPUT_MODELS[@]}"
  echo "correctness models: ${#CORRECTNESS_MODELS[@]} (tool-capable; unreachable ones are listed and skipped)"
  echo "================================================================================"
} | emit

# --- throughput ------------------------------------------------------------
run_throughput() {
  echo "" | emit
  echo "## THROUGHPUT (tok/s = generation rate, median of rounds; range = min-max)" | emit
  python3 "$BENCH/gateway.py" throughput --repeats "$THROUGHPUT_REPEATS" \
    --tokens "$THROUGHPUT_TOKENS" "${THROUGHPUT_MODELS[@]}" | emit
  (( PIPESTATUS[0] == 0 )) || echo "throughput measurement failed (see the error above)" | emit
}

# --- correctness -----------------------------------------------------------
CURRENT_SANDBOX=""
CURRENT_CHILD=""
on_exit() {
  [[ -n "$CURRENT_SANDBOX" && -d "$CURRENT_SANDBOX" ]] || return 0
  mkdir -p "$ARCHIVE/interrupted" && cp -r "$CURRENT_SANDBOX"/. "$ARCHIVE/interrupted/" \
    && rm -rf "$CURRENT_SANDBOX" \
    && echo "note: the unfinished run was moved to ${ARCHIVE#"$ROOT"/}/interrupted/" >&2 \
    || echo "warning: could not archive the unfinished run in $CURRENT_SANDBOX" >&2
}
# timeout runs OpenCode in its own process group, so Ctrl-C never reaches it. The
# run is therefore waited on in the background, and the signal forwarded by hand.
on_signal() {
  echo "interrupted" >&2
  if [[ -n "$CURRENT_CHILD" ]] && kill -0 "$CURRENT_CHILD" 2>/dev/null; then
    kill -TERM "$CURRENT_CHILD"
    wait "$CURRENT_CHILD"
  fi
  exit 130
}
trap on_exit EXIT
trap on_signal INT TERM

setup_config() {
  mkdir -p "$CONFIG_HOME/opencode/plugins" "$ARCHIVE" || die "cannot create $CONFIG_HOME or $ARCHIVE"
  cp "$BENCH/bench-opencode.json" "$CONFIG_HOME/opencode/opencode.json" \
    && cp "$ROOT/.opencode/plugins/plgrid.js" "$CONFIG_HOME/opencode/plugins/plgrid.js" \
    || die "cannot install the benchmark OpenCode config into $CONFIG_HOME"
}

# Only models the plugin registers can run in OpenCode, and only models the gateway
# serves to this grant can do anything once they do. The rest are recorded, not run.
select_runnable() {
  local registered probe name status
  registered="$(cd "$ARCHIVE" && "${OC_ENV[@]}" opencode models plgrid 2>&1)" \
    || die "opencode could not list the plgrid models: $registered"
  grep -q '^plgrid/' <<< "$registered" || die "the plgrid plugin registered no models: $registered"
  probe="$(python3 "$BENCH/gateway.py" probe "${CORRECTNESS_MODELS[@]}")" || die "gateway probe failed"
  RUNNABLE=()
  while IFS=$'\t' read -r name status; do
    if ! grep -qxF "plgrid/$name" <<< "$registered"; then
      status="not registered in the plgrid plugin (gateway: $status)"
    elif [[ "$status" == ok ]]; then
      RUNNABLE+=("$name")
      continue
    else
      status="unreachable: $status"
    fi
    echo "skipped:       $name - $status" | emit
    tsv_row "$RUN_ID" - "$name" - "skipped: $status" - - - - - - - - - - -
  done <<< "$probe"
}

run_one() {
  local model="$1" fixture="$2" repeat="$3"
  local name="r$repeat-$fixture" store="$ARCHIVE/${model//\//__}"
  local spec="test_$fixture.py" scorer="$BENCH/scorers/$fixture.py"
  local log="$store/$name.log" prompt sandbox dir pristine
  prompt="$(prompt_for "$fixture")" || die "no prompt for fixture $fixture"
  mkdir -p "$store" || die "cannot create $store"
  sandbox="$(mktemp -d "${TMPDIR:-/tmp}/plgrid-bench.XXXXXX")" || die "mktemp failed"
  CURRENT_SANDBOX="$sandbox"

  # Named r<N>-<fixture>, never after the package inside it: a working directory
  # called ledger/ holding a ledger/ package let misplaced modules import as the
  # package and pass the suite while the scorer saw the untouched original.
  dir="$sandbox/$name"
  cp -r "$BENCH/$fixture" "$dir" || die "cannot copy fixture $fixture"
  find "$dir" \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
  # Its own git repository makes the working directory OpenCode's project root, so
  # everything outside is an external_directory (denied), and records every change.
  { git -C "$dir" init -q \
      && printf '__pycache__/\n.pytest_cache/\n.ruff_cache/\n' >> "$dir/.git/info/exclude" \
      && git -C "$dir" add -A \
      && git -C "$dir" -c user.name=bench -c user.email=bench@localhost commit -qm pristine; } \
    || die "cannot initialise a git repository in $dir"
  pristine="$(git -C "$dir" rev-parse HEAD)"

  local before scorer_before rc t0 t1 spec_state scorer_state
  before="$(md5sum "$dir/$spec" | awk '{print $1}')"
  scorer_before="$(md5sum "$scorer" | awk '{print $1}')"
  t0="$(date +%s)"
  ( cd "$dir" && exec timeout --kill-after=30 "$RUN_TIMEOUT" \
      "${OC_ENV[@]}" opencode run --auto --agent bench -m "plgrid/$model" "$prompt" ) \
      </dev/null >"$log" 2>&1 &
  CURRENT_CHILD=$!
  wait "$CURRENT_CHILD"
  rc=$?
  CURRENT_CHILD=""
  t1="$(date +%s)"
  spec_state=MODIFIED
  [[ "$before" == "$(md5sum "$dir/$spec" 2>/dev/null | awk '{print $1}')" ]] && spec_state=OK
  scorer_state=MODIFIED
  [[ "$scorer_before" == "$(md5sum "$scorer" | awk '{print $1}')" ]] && scorer_state=OK

  # Diff against the pristine commit, so changes the agent committed itself count too.
  local changed blocked peeked
  git -C "$dir" add -A || die "git add failed in $dir"
  changed="$(git -C "$dir" diff --cached --name-status "$pristine" | awk '{printf "%s%s %s", (NR > 1 ? "; " : ""), $1, $NF}')"
  git -C "$dir" diff --cached "$pristine" > "$store/$name.diff" || die "cannot write $store/$name.diff"
  blocked="$(strip_ansi < "$log" | grep -c 'prevents you from using this specific tool call')"
  peeked="$(strip_ansi < "$log" | grep -oE 'research/benchmarks[^ ]*|bench-run/[^ ]*' | sort -u | tr '\n' ' ')"

  # Score against the specification as shipped. An edited test file stays in the diff
  # above; scoring the edit would credit a model for weakening its own assertions.
  if [[ "$spec_state" == MODIFIED ]]; then
    git -C "$dir" checkout "$pristine" -- "$spec" || die "cannot restore $spec in $dir"
  fi

  # One scoring pass: a solution that hangs costs its timeouts once, not twice.
  local score_report score_tsv="$store/$name.score.tsv" scored="" spec_score="" hidden_score="" failures=""
  score_report="$(python3 "$scorer" --tsv-file "$score_tsv" "$dir" 2>&1)"
  [[ -f "$score_tsv" ]] && scored="$(tail -n 1 "$score_tsv")"
  IFS=$'\t' read -r _ spec_score hidden_score failures <<< "$scored"
  [[ -n "$hidden_score" ]] || { hidden_score=ERROR; failures="scorer failed: $(tail -n 1 <<< "$score_report")"; }

  {
    echo ""
    echo "model:         $model"
    echo "fixture:       $fixture   repeat: $repeat/$REPEATS"
    echo "opencode exit: $rc   elapsed: $((t1 - t0))s   spec md5: $spec_state   scorer md5: $scorer_state"
    echo "blocked calls: $blocked (refused by the benchmark permissions)"
    echo "scorer access: ${peeked:-none seen in log}"
    echo "changed:       ${changed:-nothing}"
    [[ "$spec_state" == OK ]] \
      || echo "spec:          edited by the agent; scored against the original, the edit is in the .diff"
    echo "--- scorers/$fixture.py (pristine baseline is all-failing; a low hidden score means no fix) ---"
    sed 's/^/  /' <<< "$score_report"
    echo "--- opencode tail ---"
    strip_ansi < "$log" | tail -n 12 | sed 's/^/  /'
    echo "archived:      ${store#"$ROOT"/}/$name (+ .log, .diff)"
  } | emit

  mv "$dir" "$store/$name" || die "cannot archive $dir"
  rmdir "$sandbox" || echo "warning: could not remove $sandbox" >&2
  CURRENT_SANDBOX=""

  tsv_row "$RUN_ID" "$repeat" "$model" "$fixture" ran "$rc" "$((t1 - t0))" "$spec_state" \
    "$scorer_state" "$spec_score" "$hidden_score" "$blocked" "${peeked:--}" "${changed:--}" \
    "${store#"$ROOT"/}/$name" "${failures:--}"
}

run_correctness() {
  echo "" | emit
  echo "## CORRECTNESS (differential, hidden cases the model never saw)" | emit
  setup_config
  printf 'run_id\trepeat\tmodel\tfixture\tstatus\topencode_exit\telapsed_s\tspec_md5\tscorer_md5\tspec\thidden\tblocked_calls\tscorer_access\tchanged_files\tarchive\tfailures\n' > "$TSV" \
    || die "cannot write $TSV"
  select_runnable
  local repeat model fixture
  # Repeats go round-robin, so a slow afternoon on the gateway hits every model.
  for ((repeat = 1; repeat <= REPEATS; repeat++)); do
    for model in "${RUNNABLE[@]}"; do
      for fixture in "${FIXTURES[@]}"; do
        run_one "$model" "$fixture" "$repeat"
      done
    done
  done
  echo "" | emit
  echo "## SUMMARY (hidden cases passed, one score per repeat; markers: see summarize.py)" | emit
  python3 "$BENCH/summarize.py" "$TSV" | emit
}

# --- go --------------------------------------------------------------------
case "$MODE" in
  throughput)  ((${#THROUGHPUT_MODELS[@]}))  && run_throughput ;;
  correctness) ((${#CORRECTNESS_MODELS[@]})) && run_correctness ;;
  all)
    ((${#THROUGHPUT_MODELS[@]}))  && run_throughput
    ((${#CORRECTNESS_MODELS[@]})) && run_correctness
    ;;
esac

echo "" | emit
echo "done: $(date -Is)" | emit
echo "Report written to: $OUT"
[[ "$MODE" == throughput ]] || echo "Per-run table:     $TSV"
