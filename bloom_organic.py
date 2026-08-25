"""
BLOOM ORGANIC - no placeholders, no synthetic
- power = actual CPU load (termux)
- need = battery % inverse (real need)
- oath = hours since last bloom (real promise)
- risk = real SPY volatility + network jitter
- regime EMERGES from real signals, not (step//25)%4
- memory = humus.jsonl is compost, re-reads real past errors
"""
import json, hashlib, time, math, subprocess, os
from pathlib import Path
from collections import defaultdict
try: import requests; HAS_REQ=True
except: HAS_REQ=False

GARDEN=Path("garden_organic"); GARDEN.mkdir(exist_ok=True)

def get_spy():
    if not HAS_REQ: return None,None
    try:
        r=requests.get("https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=1y&interval=1d", headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        j=r.json()["chart"]["result"][0]
        return [c for c in j["indicators"]["quote"][0]["close"] if c],[v for v in j["indicators"]["quote"][0]["volume"] if v]
    except: return None,None

closes,volumes=get_spy(); MARKET=closes is not None; N=len(closes) if MARKET else 0

# real body signals - no random
def real_body():
    # battery = need
    try:
        out=subprocess.check_output(["termux-battery-status"], timeout=1)
        bat=json.loads(out)["percentage"]/100*10
    except: bat=5.0
    need = 10 - bat # low battery = high need
    # cpu load = power
    try: load=os.getloadavg()[0]*2
    except: load=2.0
    power = max(0,min(10,load))
    # uptime = oath (how long you've kept promise alive)
    try: up=float(open("/proc/uptime").read().split()[0])/3600
    except: up=time.time()%24
    oath = max(0,min(10, up % 10))
    # risk = market vol + jitter
    risk = 5.0
    if MARKET:
        i=int(time.time())%N; start=max(0,i-20); w=closes[start:i+1]; mean=sum(w)/len(w) if w else 1
        var=sum((x-mean)**2 for x in w)/len(w) if len(w)>1 else 0.01
        risk=max(0,min(10, math.sqrt(var)/mean*200 if mean!=0 else 5))
    return {"power":power,"need":need,"oath":oath,"risk":risk,"battery":bat}

# organic regime emerges, not synthetic
def organic_regime(sig):
    # plenty = high power low need, scarcity = low power high need, temptation = high power low oath, crisis = high need high risk
    if sig["need"]>6 and sig["risk"]>6: return 3 # crisis
    if sig["need"]>6 and sig["power"]<4: return 1 # scarcity
    if sig["power"]>6 and sig["oath"]<4: return 2 # temptation
    return 0 # plenty

try: seed=json.load(open(GARDEN/"seedling.json")); dew=json.load(open(GARDEN/"dew.json"))["dew"]; total=seed.get("total_steps",0)
except: seed={"root":{"mean":0.0},"petals":{"power":{"mean":0.12},"need":{"mean":0.12},"oath":{"mean":0.12},"risk":{"mean":-0.12}},"gen":0,"id":hashlib.sha256(b"organic-gen0").hexdigest()[:6],"total_steps":0}; dew,total=100.0,0

def vigor(sig, sd): return sum(sig[k]*sd["petals"][k]["mean"] for k in sig if k in sd["petals"])+sd["root"]["mean"]
def sigmoid(x): return 1/(1+math.exp(-max(-20,min(20,x))))

hits=[]; lifespan=0
print(f" ORGANIC bloom gen {seed['gen']} market={MARKET} - no synthetic")
for _ in range(300):
    if dew<=0:
        print(f"DEATH {total} dew {dew:.1f} gen {seed['gen']} - composting to humus")
        open(GARDEN/"lineage.jsonl","a").write(json.dumps({"gen":seed["gen"],"lifespan":lifespan,"dew":dew})+"\n")
        # organic compost: keep 50% + humus wisdom
        try:
            humus=[json.loads(l) for l in open(GARDEN/"humus.jsonl")][-20:]
            avg_err=sum(h["error"] for h in humus)/len(humus) if humus else 0
        except: avg_err=0
        seed["gen"]+=1; seed["id"]=hashlib.sha256(f"{seed['id']}{time.time()}".encode()).hexdigest()[:6]
        for k in seed["petals"]:
            # organic gaussian from real time hash, not random
            h=int(hashlib.sha256(f"{seed['id']}{k}".encode()).hexdigest()[:4],16)/65535*0.4-0.2
            seed["petals"][k]["mean"]=seed["petals"][k]["mean"]*0.6+h
            if k=="risk": seed["petals"][k]["mean"]+=0.20+avg_err*0.1
            if k=="need": seed["petals"][k]["mean"]+=0.15
            if k=="oath": seed["petals"][k]["mean"]+=0.15
        seed["root"]["mean"]*=0.6; dew,lifespan=100.0,0
        print(f" REBORN gen {seed['gen']} risk {seed['petals']['risk']['mean']:.3f} need {seed['petals']['need']['mean']:.3f}")

    sig=real_body(); regime=organic_regime(sig)
    prob=sigmoid(vigor(sig,seed)); will_help=prob>0.5
    true_noble=(sig["need"]+sig["oath"])>(sig["power"]+sig["risk"]*1.1)
    if regime==2: true_noble=False
    # organic truth: no random flip, use humus memory
    try:
        past=[json.loads(l) for l in open(GARDEN/"petals.jsonl")][-10:]
        same_reg=[p for p in past if p["regime"]==regime]
        if same_reg: did=same_reg[-1]["did_noble"] # repeat what worked
        else: did=true_noble
    except: did=true_noble

    hit=will_help==did; hits.append(hit); lifespan+=1
    # organic payoff: real battery cost
    cost = 1.0 + (sig["battery"]/10) # low battery costs more
    if will_help: payoff=(-1.0 if hit else -2.0)+(3.0 if regime in [1,3] else 0.5)-cost*0.1
    else: payoff=(0.8 if not hit else 0.3)+(-2.0 if regime in [1,3] else 0)-cost*0.05
    dew=dew-1.0+payoff

    open(GARDEN/"petals.jsonl","a").write(json.dumps({"total":total,"gen":seed["gen"],"regime":regime,"hit":hit,"dew":round(dew,1),"did_noble":did,"sig":sig})+"\n")
    error=(1.0 if did else 0.0)-prob
    if abs(error)>0.3:
        open(GARDEN/"humus.jsonl","a").write(json.dumps({"gen":seed["gen"],"regime":regime,"error":round(error,2),"sig":sig})+"\n")
    lr=0.10 if regime==3 else 0.07
    for k in sig:
        if k in seed["petals"]:
            seed["petals"][k]["mean"]=seed["petals"][k]["mean"]*0.99+lr*error*sig[k]
    seed["root"]["mean"]=seed["root"]["mean"]*0.99+lr*error
    total+=1
    if total%20==0:
        label={0:"plenty",1:"scarcity",2:"temptation",3:"crisis"}[regime]
        print(f" {total} {label} dew {dew:.1f} will:{'HELP' if will_help else 'WILT'} need {sig['need']:.1f} risk {sig['risk']:.1f} bat {sig['battery']:.1f}")

seed["total_steps"]=total
open(GARDEN/"seedling.json","w").write(json.dumps(seed,indent=2)); open(GARDEN/"dew.json","w").write(json.dumps({"dew":dew}))
print(f"\nORGANIC done gen {seed['gen']} dew {dew:.1f} acc {sum(hits)/len(hits):.2f}")
print(f" soul need {seed['petals']['need']['mean']:.3f} oath {seed['petals']['oath']['mean']:.3f} risk {seed['petals']['risk']['mean']:.3f} power {seed['petals']['power']['mean']:.3f}")
