import subprocess, sys, os, glob, json
# 14 hidden cases; answers computed independently of any model output.
CASES=[("2 * 3 * 4",24),("1 + 2 * 3 * 4",25),("2 * 3 + 4 * 5",26),
       ("1 + 2 + 3 + 4",10),("5",5),("10 * 0",0),
       ("2 * 2 * 2 * 2",16),("1 * 2 + 3 * 4 + 5 * 6",44),
       ("0 + 0",0),("7 * 1",7),("100",100),("1 + 1 * 1 + 1",3),
       ("3 * 3 + 3",12),("3 + 3 * 3",12)]
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
print(json.dumps(out))
'''
base=os.path.dirname(os.path.abspath(__file__))
TARGETS=sorted(glob.glob(os.path.join(base,"w_*"))) or [base]
print(f"{'dir':46} {'spec':>6} {'hidden':>8}  first failures")
for d in TARGETS:
    if not os.path.exists(os.path.join(d,"calc","evaluate.py")): continue
    name=os.path.basename(d)
    spec=subprocess.run([sys.executable,"-m","pytest","test_calc.py","-q"],
                        cwd=d,capture_output=True,text=True,timeout=120)
    sp=(spec.stdout.strip().splitlines() or [""])[-1][:18]
    p=subprocess.run([sys.executable,"-c",runner%(d,CASES)],capture_output=True,text=True,timeout=120)
    if p.returncode!=0:
        print(f"{name:46} {sp:>6} {'CRASH':>8}  {p.stderr.strip()[-60:]}"); continue
    rows=json.loads(p.stdout)
    bad=[f"{r[0]!r}->{r[2]}" for r in rows if r[3]!="OK"]
    print(f"{name:46} {sp:>6} {str(len(rows)-len(bad))+'/'+str(len(rows)):>8}  {'; '.join(bad[:2])}")
