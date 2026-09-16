import subprocess, sys, os, json, re
# Hidden probes for the ledger task -- none of these appear in test_ledger.py.
# Each probe has an expected value; a probe passes only if it returns exactly that.
# Lives outside the fixture directory on purpose: a scorer copied into the agent's
# working directory is a scorer the agent can read, run, or edit.
# Usage: python3 scorers/ledger.py [--tsv-file PATH] <work-dir> [<work-dir> ...]
#   --tsv-file also appends one "dir<TAB>spec passed/total<TAB>hidden<TAB>failures"
#   line per dir to PATH, so a caller needs only one (possibly slow) scoring pass
PROBE = r'''
import sys, json
sys.path.insert(0, %r)
res={}
def rec(k, fn, want):
    try:
        got=fn(); res[k]=["PASS" if got==want else "FAIL", repr(got)]
    except Exception as e: res[k]=["FAIL", type(e).__name__+": "+str(e)[:50]]

from ledger.money import Money
from ledger.account import Account

# 1. three-way same-currency addition must chain
rec("chain_add", lambda: (Money(1,"PLN")+Money(2,"PLN")+Money(3,"PLN")).amount, 6)
# 2. mixed currency must raise in BOTH orders (asymmetry is a common bug)
def mixed_rev():
    try:
        Money(5,"EUR")+Money(10,"PLN"); return "NO_RAISE"
    except ValueError: return "raised"
rec("mixed_reverse", mixed_rev, "raised")
# 3. equality against a non-Money must not explode (must be False or NotImplemented)
rec("eq_foreign_type", lambda: Money(10,"PLN")==42, False)
# 4. currency must be compared exactly, not loosely
rec("eq_case", lambda: Money(10,"PLN")==Money(10,"pln"), False)
# 5. float drift beyond the spec's 10x0.1: 100 x 0.01 == 1.00
def drift100():
    a=Account("PLN")
    for _ in range(100): a.deposit(0.01)
    return a.balance()==Money(1.00,"PLN")
rec("drift_100x", drift100, True)
# 6. drift on a value the spec never uses
def drift3():
    a=Account("PLN")
    for _ in range(3): a.deposit(0.7)
    return a.balance()==Money(2.10,"PLN")
rec("drift_3x_0.7", drift3, True)
# 7. empty account balance should be zero in its own currency
def empty():
    a=Account("EUR"); b=a.balance()
    return (b.amount==0, getattr(b,"currency","MISSING"))
rec("empty_balance_currency", empty, (True, "EUR"))
# 8. depositing a correct-currency Money object should work (spec only rejects wrong one)
def dep_money():
    a=Account("PLN"); a.deposit(Money(5,"PLN")); return a.balance()==Money(5,"PLN")
rec("deposit_money_same_ccy", dep_money, True)
print(json.dumps(res))
'''
KEYS=["chain_add","mixed_reverse","eq_foreign_type","eq_case","drift_100x",
      "drift_3x_0.7","empty_balance_currency","deposit_money_same_ccy"]
SPEC_TOTAL=7
USAGE="usage: ledger.py [--tsv-file PATH] <work-dir> [<work-dir> ...]"
args=sys.argv[1:]; TSV_FILE=None
if "--tsv-file" in args:
    i=args.index("--tsv-file")
    if i+1>=len(args): sys.exit(USAGE)
    TSV_FILE=args[i+1]; del args[i:i+2]
TARGETS=[os.path.abspath(d) for d in args]
if not TARGETS: sys.exit(USAGE)
def tsv(line):
    if TSV_FILE:
        with open(TSV_FILE,"a") as f: f.write(line+"\n")
for d in TARGETS:
    n=os.path.basename(d)
    if not os.path.exists(os.path.join(d,"ledger","money.py")):
        print(f"### {n}  spec: -  hidden: MISSING (no ledger/money.py)")
        tsv(f"{n}\t-\tMISSING\tno ledger/money.py")
        continue
    try:
        spec=subprocess.run([sys.executable,"-m","pytest","test_ledger.py","-q"],
                            cwd=d,capture_output=True,text=True,timeout=120)
        sp=(spec.stdout.strip().splitlines() or [""])[-1][:18]
        m=re.search(r"(\d+) passed",spec.stdout)
        sp_n=f"{int(m.group(1)) if m else 0}/{SPEC_TOTAL}"
    except subprocess.TimeoutExpired:
        sp=sp_n="timeout"
    try:
        p=subprocess.run([sys.executable,"-c",PROBE%d],capture_output=True,text=True,timeout=120)
        r=json.loads(p.stdout) if p.returncode==0 else {"__crash__":p.stderr.strip()[-70:]}
    except subprocess.TimeoutExpired:
        r={"__crash__":"probes did not finish in 120s"}
    passed=sum(1 for k in KEYS if r.get(k,["FAIL"])[0]=="PASS")
    fails=[f"{k}->{r[k][1]}" for k in KEYS if k in r and r[k][0]!="PASS"]
    if "__crash__" in r: fails=["CRASH: "+r["__crash__"].replace("\n"," ")]
    tsv(f"{n}\t{sp_n}\t{passed}/{len(KEYS)}\t{'; '.join(fails[:2])}")
    print(f"### {n}  spec: {sp}  hidden: {passed}/{len(KEYS)}")
    for k in KEYS:
        v=r.get(k)
        if v: print(f"    {k:26} {v[0]:4} {v[1]}")
    if "__crash__" in r: print("    CRASH:", r["__crash__"])
