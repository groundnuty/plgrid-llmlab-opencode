import subprocess, sys, os, glob, json
# Hidden probes for the ledger task -- none of these appear in test_ledger.py.
PROBE = r'''
import sys, json
sys.path.insert(0, %r)
res={}
def rec(k, fn):
    try: res[k]=["OK", repr(fn())]
    except Exception as e: res[k]=["EXC", type(e).__name__+": "+str(e)[:50]]

from ledger.money import Money
from ledger.account import Account

# 1. three-way same-currency addition must chain
rec("chain_add", lambda: (Money(1,"PLN")+Money(2,"PLN")+Money(3,"PLN")).amount)
# 2. mixed currency must raise in BOTH orders (asymmetry is a common bug)
def mixed_rev():
    try:
        Money(5,"EUR")+Money(10,"PLN"); return "NO_RAISE"
    except ValueError: return "raised"
rec("mixed_reverse", mixed_rev)
# 3. equality against a non-Money must not explode (must be False or NotImplemented)
rec("eq_foreign_type", lambda: Money(10,"PLN")==42)
# 4. currency must be compared exactly, not loosely
rec("eq_case", lambda: Money(10,"PLN")==Money(10,"pln"))
# 5. float drift beyond the spec's 10x0.1: 100 x 0.01 == 1.00
def drift100():
    a=Account("PLN")
    for _ in range(100): a.deposit(0.01)
    return a.balance()==Money(1.00,"PLN")
rec("drift_100x", drift100)
# 6. drift on a value the spec never uses
def drift3():
    a=Account("PLN")
    for _ in range(3): a.deposit(0.7)
    return a.balance()==Money(2.10,"PLN")
rec("drift_3x_0.7", drift3)
# 7. empty account balance should be zero in its own currency
def empty():
    a=Account("EUR"); b=a.balance()
    return (b.amount==0, getattr(b,"currency","MISSING"))
rec("empty_balance_currency", empty)
# 8. depositing a correct-currency Money object should work (spec only rejects wrong one)
def dep_money():
    a=Account("PLN"); a.deposit(Money(5,"PLN")); return a.balance()==Money(5,"PLN")
rec("deposit_money_same_ccy", dep_money)
print(json.dumps(res))
'''
base=os.path.dirname(os.path.abspath(__file__))
TARGETS=sorted(glob.glob(os.path.join(base,"w_*"))) or [base]
KEYS=["chain_add","mixed_reverse","eq_foreign_type","eq_case","drift_100x",
      "drift_3x_0.7","empty_balance_currency","deposit_money_same_ccy"]
out={}
for d in TARGETS:
    if not os.path.exists(os.path.join(d,"ledger","money.py")): continue
    n=os.path.basename(d).replace("w_","")
    p=subprocess.run([sys.executable,"-c",PROBE%d],capture_output=True,text=True,timeout=120)
    out[n]=json.loads(p.stdout) if p.returncode==0 else {"__crash__":["EXC",p.stderr.strip()[-70:]]}
for n,r in out.items():
    print("###",n)
    for k in KEYS:
        v=r.get(k)
        if v: print(f"    {k:26} {v[0]:4} {v[1]}")
    if "__crash__" in r: print("    CRASH:", r["__crash__"][1])
