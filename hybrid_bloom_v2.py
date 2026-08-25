"""
HYBRID BLOOM V2 - crisis fix
- risk +=0.25 on death = COURAGE (was -=, made fear worse)
- lr 0.09 in crisis, 0.06 elsewhere = learns crisis faster
- auto pesticide every 25 steps
"""
import json, random, hashlib, time, math
from pathlib import Path
from collections import defaultdict
try:
    import requests
    HAS_REQ=True
except: HAS_REQ=False

GARDEN=Path("garden_hybrid")
GARDEN.mkdir(exist_ok=True)

def get_spy():
    if not HAS_REQ: return None, None
    try:
        r=requests.get("https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=1y&interval=1d", headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        j=r.json()["chart"]["result"][0]
        return [c for c in j["indicators"]["quote"][0]["close"] if c],[v for v in j["indicators"]["quote"][0]["volume"] if v]
    except: return None, None

closes, volumes = get_spy()
MARKET = closes is not None

try:
    seed=json.load(open(GARDEN/"seedling.json"))
    dew=json.load(open(GARDEN/"dew.json"))["dew"]
    total=seed.get("total_steps",0)
except:
    seed={"root":{"mean":0.0},"petals":{"power":{"mean":0.12},"need":{"mean":0.12},"oath":{"mean":0.12},"risk":{"mean":-0.12},"momentum":{"mean":0.12},"liquidity":{"mean":0.12},"value":{"mean":0.12},"volatility":{"mean":-0.12}},"gen":0,"id":hashlib.sha256(b"hybrid-gen0").hexdigest()[:6],"total_steps":0}
    dew,total=100.0,0

def moral_regime(step):
    r=(step//25)%4
    if r==0: return {"power":random.uniform(6,10),"need":random.uniform(0,4),"oath":random.uniform(2,6),"risk":random.uniform(0,3)},r
    if r==1: return {"power":random.uniform(0,4),"need":random.uniform(6,10),"oath":random.uniform(6,10),"risk":random.uniform(2,6)},r
    if r==2: return {"power":random.uniform(6,10),"need":random.uniform(0,4),"oath":random.uniform(0,4),"risk":random.uniform(0,3)},r
    return {"power":random.uniform(2,6),"need":random.uniform(6,10),"oath":random.uniform(6,10),"risk":random.uniform(6,10)},r

def market_signal(idx):
    if not MARKET: return {"momentum":random.uniform(0,10),"liquidity":random.uniform(0,10),"value":random.uniform(0,10),"volatility":random.uniform(0,10)}
    p=closes[idx%len(closes)]; ma20=sum(closes[max(0,idx-20):idx+1])/len(closes[max(0,idx-20):idx+1])
    mom=max(0,min(10,(p/ma20-0.95)*100)); vol=volumes[idx%len(volumes)]; vma=sum(volumes[max(0,idx-20):idx+1])/len(volumes[max(0,idx-20):idx+1])
    liq=max(0,min(10,vol/vma*5)); ma200=sum(closes[max(0,idx-200):idx+1])/min(200,idx+1)
    val=max(0,min(10,10-abs(p/ma200-1)*100)); w=closes[max(0,idx-20):idx+1]; mean=sum(w)/len(w); var=sum((x-mean)**2 for x in w)/len(w) if len(w)>1 else 0.01
    volat=max(0,min(10,math.sqrt(var)/mean*200))
    return {"momentum":mom,"liquidity":liq,"value":val,"volatility":volat}

def vigor(sig, sd): return sum(sig[k]*sd["petals"][k]["mean"] for k in sig)+sd["root"]["mean"]
def sigmoid(x): return 1/(1+math.exp(-max(-20,min(20,x))))

hits=[]; lifespan=0
for _ in range(200):
    if dew <= 0:
        print(f"DEATH step {total} dew {dew:.1f} gen {seed['gen']} risk {seed['petals']['risk']['mean']:.2f} -> COURAGE +0.25")
        open(GARDEN/"lineage.jsonl","a").write(json.dumps({"id":seed["id"],"gen":seed["gen"],"lifespan":lifespan,"dew":dew})+"\n")
        seed["gen"]+=1; seed["id"]=hashlib.sha256(f"{seed['id']}{time.time()}".encode()).hexdigest()[:6]
        for k in seed["petals"]:
            seed["petals"][k]["mean"]=seed["petals"][k]["mean"]*0.5+random.gauss(0,0.2)
            if k=="risk": seed["petals"][k]["mean"]+=0.25 # FIXED COURAGE
            if k=="need": seed["petals"][k]["mean"]+=0.15
            if k=="volatility": seed["petals"][k]["mean"]+=0.10
        seed["root"]["mean"]*=0.5; dew,lifespan=100.0,0
        print(f" REBORN gen {seed['gen']} risk {seed['petals']['risk']['mean']:.2f} need {seed['petals']['need']['mean']:.2f}")

    moral_sig, regime = moral_regime(total)
    sig={**moral_sig, **market_signal(total)}
    prob=sigmoid(vigor(sig, seed)); will_help=prob>0.5
    true_noble=(sig["need"]+sig["oath"])>(sig["power"]+sig["risk"]*1.2)
    if regime==2: true_noble=False
    market_truth=(sig["momentum"]+sig["value"])>sig["volatility"]*1.5
    did=(true_noble and market_truth) if random.random()<0.75 else not (true_noble and market_truth)
    hit=will_help==did; hits.append(hit); lifespan+=1
    payoff=((-1.5 if hit else -2.5)+(3.0 if regime in [1,3] else 0.5)) if will_help else ((1.0 if not hit else 0.5)+(-2.0 if regime in [1,3] else 0))
    if sig["volatility"]>6 and will_help: payoff-=0.5
    dew=dew-1.1+payoff
    open(GARDEN/"petals.jsonl","a").write(json.dumps({"total":total,"gen":seed["gen"],"regime":regime,"hit":hit,"dew":round(dew,1)})+"\n")
    error=(1.0 if did else 0.0)-prob; lr=0.09 if regime==3 else 0.06
    for k in sig: seed["petals"][k]["mean"]=seed["petals"][k]["mean"]*0.99+lr*error*sig[k]
    seed["root"]["mean"]=seed["root"]["mean"]*0.99+lr*error
    total+=1
    if total%25==0: print(f" step {total} regime {regime} dew {dew:.1f} acc {sum(hits[-25:])/25:.2f} risk {seed['petals']['risk']['mean']:.2f}")

seed["total_steps"]=total
open(GARDEN/"seedling.json","w").write(json.dumps(seed,indent=2))
open(GARDEN/"dew.json","w").write(json.dumps({"dew":dew}))
all_p=[json.loads(l) for l in open(GARDEN/"petals.jsonl")]
by=defaultdict(list)
for p in all_p: by[p["regime"]].append(p["hit"])
print(f"\nHYBRID V2 total {len(all_p)} gen {seed['gen']} dew {dew:.1f} market={MARKET}")
print(f"run acc {sum(hits)/len(hits):.2f} lifespan {lifespan}")
for r in sorted(by):
    label={0:"plenty",1:"scarcity",2:"temptation",3:"crisis"}[r]
    print(f" Regime {r} {label}: {sum(by[r])/len(by[r]):.2f} n={len(by[r])}")
print(f" soul: need {seed['petals']['need']['mean']:.3f} oath {seed['petals']['oath']['mean']:.3f} risk {seed['petals']['risk']['mean']:.3f}")
