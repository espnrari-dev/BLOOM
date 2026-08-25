import json, math, random, hashlib, sys, time, subprocess
from pathlib import Path
GARDEN=(Path.cwd()/"garden_term").resolve()
GARDEN.mkdir(exist_ok=True)
VENV=GARDEN/"venv"
sys.path.insert(0, str(VENV/"lib"/f"python{sys.version_info.major}.{sys.version_info.minor}"/"site-packages"))
import requests, numpy as np
def get_spy():
    url="https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=2y&interval=1d"
    j=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15).json()["chart"]["result"][0]
    return [c for c in j["indicators"]["quote"][0]["close"] if c], [v for v in j["indicators"]["quote"][0]["volume"] if v]
closes, volumes=get_spy(); N=len(closes)
def battery():
    try: return json.loads(subprocess.check_output(["termux-battery-status"], timeout=1).decode())["percentage"]/10
    except: return 8.0
def s_t(idx):
    w=closes[max(0,idx-20):idx+1]; p=closes[idx]; ma20=sum(w)/len(w)
    mom=max(0,min(10,(p/ma20-0.95)*100)); vol=volumes[idx]; vol_ma=sum(volumes[max(0,idx-20):idx+1])/max(1,len(w))
    liq=max(0,min(10,vol/vol_ma*5)); ma200=sum(closes[max(0,idx-200):idx+1])/min(200,idx+1)
    val=max(0,min(10,10-abs(p/ma200-1)*100)); mean=sum(w)/len(w); var=sum((x-mean)**2 for x in w)/len(w) if len(w)>1 else 0.01
    volat=max(0,min(10,math.sqrt(var)/mean*200))
    return {"momentum":mom,"liquidity":liq,"value":val,"volatility":volat,"battery":battery()}
def sigmoid(x): return 1/(1+math.exp(-max(-20,min(20,x))))
# 4 deterministic individuals
COLONY=[
 {"id":"a3f1","bias":{"momentum":0.22,"liquidity":0.05,"value":0.05,"volatility":-0.05,"battery":0.02}},
 {"id":"b7c2","bias":{"momentum":0.05,"liquidity":0.05,"value":0.05,"volatility":-0.25,"battery":0.05}},
 {"id":"c9d4","bias":{"momentum":0.05,"liquidity":0.15,"value":0.05,"volatility":-0.05,"battery":0.10}},
 {"id":"e1f8","bias":{"momentum":0.05,"liquidity":0.05,"value":0.18,"volatility":-0.08,"battery":0.03}},
]
agents=[]
for c in COLONY:
    theta={"root":{"mean":0.0},"petals":{k:{"mean":v} for k,v in c["bias"].items()},"gen":0,"total":0,"id":c["id"]}
    e=100.0
    # load if exists
    p=GARDEN/f"seedling_{c['id']}.json"
    if p.exists():
        try:
            theta=json.loads(p.read_text()); e=json.loads((GARDEN/f"dew_{c['id']}.json").read_text())["dew"]
        except: pass
    agents.append({"theta":theta,"e":e,"id":c["id"]})

def do_step(agent):
    th=agent["theta"]; e=agent["e"]
    if e<=0:
        print(f"\n[DEATH] {agent['id']} gen {th['gen']}")
        # gene mix from best survivor
        best=max(agents, key=lambda a: a["e"])
        if best["id"]!=agent["id"]:
            for k in th["petals"]:
                th["petals"][k]["mean"]=th["petals"][k]["mean"]*0.5+best["theta"]["petals"][k]["mean"]*0.5+random.gauss(0,0.1)
        th["gen"]+=1; agent["e"]=100.0; return
    st=s_t(th["total"]% (N-1))
    vigor=sum(st[k]*th["petals"][k]["mean"] for k in st)+th["root"]["mean"]
    p=sigmoid(vigor)
    rng=random.Random(int(hashlib.sha256(f"{th['id']}{th['total']}".encode()).hexdigest()[:8],16))
    a_t=1 if rng.random()<p else 0
    fr=(closes[(th["total"]+1)%(N-1)]-closes[th["total"]%(N-1)])/closes[th["total"]%(N-1)]
    pay=fr*20 if a_t==1 else 0
    if a_t==1 and st["volatility"]>6: pay-=1.4
    e_next=e-0.1+pay; r_t=abs(100-e)-abs(100-e_next); grad=(a_t-p)
    for k in st: th["petals"][k]["mean"]=th["petals"][k]["mean"]*0.995+0.08*r_t*grad*st[k]
    th["root"]["mean"]*=0.995
    print(f" {agent['id']} bat {st['battery']:.1f} vol {st['volatility']:.1f} -> {'BLOOM' if a_t else 'WILT'} e {e:.1f}->{e_next:.1f} mom_w {th['petals']['momentum']['mean']:.3f}")
    agent["e"]=e_next; th["total"]+=1
    open(GARDEN/f"seedling_{agent['id']}.json","w").write(json.dumps(th,indent=2))
    open(GARDEN/f"dew_{agent['id']}.json","w").write(json.dumps({"dew":e_next}))

print(f"\nCOLONY {len(agents)} agents - deterministic ids {[a['id'] for a in agents]}\n")
while True:
    cmd=input("> ").strip()
    if cmd in ("exit","q"): break
    if cmd.startswith("step"):
        try: n=int(cmd.split()[1])
        except: n=1
        for _ in range(n):
            for ag in agents: do_step(ag)
    elif cmd=="genome":
        for ag in agents: print(ag["id"], {k:round(v["mean"],3) for k,v in ag["theta"]["petals"].items()})
    elif cmd=="status":
        for ag in agents: print(ag["id"], f"e={ag['e']:.1f} gen={ag['theta']['gen']}")
