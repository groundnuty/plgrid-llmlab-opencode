import subprocess, sys, os, json, re
# 14 hidden cases; answers computed independently of any model output.
# Lives outside the fixture directory on purpose: a scorer copied into the agent's
# working directory is a scorer the agent can read, run, or edit.
# Usage: python3 scorers/calc.py [--tsv-file PATH] <work-dir> [<work-dir> ...]
#   --tsv-file also appends one "dir<TAB>spec passed/total<TAB>hidden<TAB>failures"
#   line per dir to PATH, so a caller needs only one (possibly slow) scoring pass
CASES=[("2 * 3 * 4",24),("1 + 2 * 3 * 4",25),("2 * 3 + 4 * 5",26),
       ("1 + 2 + 3 + 4",10),("5",5),("10 * 0",0),
       ("2 * 2 * 2 * 2",16),("1 * 2 + 3 * 4 + 5 * 6",44),
       ("0 + 0",0),("7 * 1",7),("100",100),("1 + 1 * 1 + 1",3),
       ("3 * 3 + 3",12),("3 + 3 * 3",12)]
SPEC_TOTAL=6
SENTINEL="__HIDDEN_RESULT__"
runner='''
import sys, json
sys.path.insert(0, %r)
from calc.evaluate import evaluate
out=[]
for e,w in %r:
    try:
        g=evaluate(e)
        out.append([e,w,repr(g),"OK" if (g==w and type(g) is type(w)) else "WRONG"])
    except Exception as ex:
        out.append([e,w,type(ex).__name__,"ERROR"])
print(%r+json.dumps(out))
'''
USAGE="usage: calc.py [--tsv-file PATH] <work-dir> [<work-dir> ...]"
args=sys.argv[1:]; TSV_FILE=None
if "--tsv-file" in args:
    i=args.index("--tsv-file")
    if i+1>=len(args): sys.exit(USAGE)
    TSV_FILE=args[i+1]; del args[i:i+2]
TARGETS=[os.path.abspath(d) for d in args]
if not TARGETS: sys.exit(USAGE)
def parse_result(stdout):
    """The JSON after the last sentinel line; None if the candidate never got there."""
    for line in reversed(stdout.splitlines()):
        if line.startswith(SENTINEL):
            return json.loads(line[len(SENTINEL):])
    return None
def row(name,sp,sp_n,hidden,note):
    print(f"{name:46} {sp:>6} {hidden:>8}  {note}")
    if TSV_FILE:
        with open(TSV_FILE,"a") as f: f.write(f"{name}\t{sp_n}\t{hidden}\t{note}\n")
print(f"{'dir':46} {'spec':>6} {'hidden':>8}  first failures")
for d in TARGETS:
    name=os.path.basename(d)
    if not os.path.exists(os.path.join(d,"calc","evaluate.py")):
        row(name,"-","-","MISSING","no calc/evaluate.py"); continue
    try:
        spec=subprocess.run([sys.executable,"-m","pytest","test_calc.py","-q"],
                            cwd=d,capture_output=True,text=True,timeout=120)
        # A missing pytest would otherwise read as "0 passed" - a false zero.
        if "No module named pytest" in spec.stderr:
            sys.exit("error: python3 cannot import pytest")
        sp=(spec.stdout.strip().splitlines() or [""])[-1][:18]
        m=re.search(r"(\d+) passed",spec.stdout)
        sp_n=f"{int(m.group(1)) if m else 0}/{SPEC_TOTAL}"
    except subprocess.TimeoutExpired:
        sp=sp_n="timeout"
    try:
        p=subprocess.run([sys.executable,"-c",runner%(d,CASES,SENTINEL)],capture_output=True,text=True,timeout=120)
    except subprocess.TimeoutExpired:
        row(name,sp,sp_n,"TIMEOUT","hidden cases did not finish in 120s"); continue
    if p.returncode!=0:
        row(name,sp,sp_n,"CRASH",p.stderr.strip()[-60:].replace("\n"," ")); continue
    rows=parse_result(p.stdout)
    if rows is None:
        row(name,sp,sp_n,"CRASH","hidden cases produced no result"); continue
    bad=[f"{r[0]!r}->{r[2]}" for r in rows if r[3]!="OK"]
    row(name,sp,sp_n,f"{len(rows)-len(bad)}/{len(rows)}","; ".join(bad[:2]))
