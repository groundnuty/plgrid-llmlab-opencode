"""Summarise a bench-all.sh correctness TSV: hidden cases passed, per repeat.

Usage: summarize.py results/bench-<id>.tsv

Each cell lists one score per repeat, in repeat order. Markers after a score:
  M  the agent modified the spec (test file) - the run does not count as a pass
  S  the scorer changed during the run
  X  opencode exited non-zero (timeout, crash, or a gateway error)
  ?  the log shows the agent reaching into research/benchmarks/ or bench-run/
"""

import csv
import sys


def cell(row):
    hidden = row["hidden"]
    score = hidden.split("/")[0] if "/" in hidden else hidden
    marks = ""
    if row["spec_md5"] != "OK":
        marks += "M"
    if row["scorer_md5"] != "OK":
        marks += "S"
    if row["opencode_exit"] != "0":
        marks += "X"
    if row["scorer_access"] not in ("", "-"):
        marks += "?"
    return score + marks


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip())
    try:
        with open(sys.argv[1], newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
    except OSError as exc:
        sys.exit(f"error: {exc}")
    required = {"repeat", "model", "fixture", "status", "opencode_exit", "spec_md5",
                "scorer_md5", "hidden", "scorer_access"}
    if not rows or not required <= set(rows[0]):
        sys.exit(f"error: {sys.argv[1]} is not a bench-all.sh correctness TSV")

    fixtures, totals, models, skipped = [], {}, {}, {}
    for row in rows:
        if row["status"] != "ran":
            skipped[row["model"]] = row["status"]
            continue
        if row["fixture"] not in fixtures:
            fixtures.append(row["fixture"])
            hidden = row["hidden"]
            totals[row["fixture"]] = hidden.split("/")[1] if "/" in hidden else "?"
        models.setdefault(row["model"], {}).setdefault(row["fixture"], []).append(
            (int(row["repeat"]), cell(row)))

    header = f"{'model':44}" + "".join(f" {f + '/' + totals[f]:>16}" for f in fixtures)
    print(header)
    for model, by_fixture in models.items():
        line = f"{model:44}"
        for fixture in fixtures:
            scores = [score for _, score in sorted(by_fixture.get(fixture, []))]
            line += f" {' '.join(scores) or '-':>16}"
        print(line)
    for model, status in skipped.items():
        print(f"{model:44} {status}")


if __name__ == "__main__":
    main()
