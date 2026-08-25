import json, random, hashlib, time, math
from pathlib import Path
from collections import defaultdict
Path("garden").mkdir(exist_ok=True)

# FORCE FRESH for finance - old bloom keys don't match
seed={
    "root":{"mean":0.0},
    "petals":{
        "momentum":{"mean":0.12},
        "liquidity":{"mean":0.12},
        "value":{"mean":0.12},
        "volatility":{"mean":-0.12}
    },
    "gen":0,"id":hashlib.sha256(b"fin-gen0").hexdigest()[:6],
    "total_steps":0
}
capital, total = 100.0, 0
# try load finance seed only
try:
    s=json.load(open("garden/seedling.json"))
    if "momentum" in s["petals"]:
        seed, capital, total = s, json.load(open("garden/dew.json"))["dew"], s.get("total_steps",0)
except:
    pass

def market_regime(step):
    regime = (step // 20) % 3
    if regime==0:
        return {"momentum":random.uniform(6,10),"liquidity":random.uniform(2,6),"value":random.uniform(2,6),"volatility":random.uniform(0,4)}, regime
    elif regime==1:
        return {"momentum":random.uniform(2,6),"liquidity":random.uniform(6,10),"value":random.uniform(2,6),"volatility":random.uniform(0,4)}, regime
    else:
        return {"momentum":random.uniform(0,4),"liquidity":random.uniform(0,4),"value":random.uniform(0,4),"volatility":random.uniform(6,10)}, regime

def vigor(sig, sd): return sum(sig[k]*sd["petals"][k]["mean"] for k in sig) + sd["root"]["mean"]
def sigmoid(x): return 1/(1+math.exp(-x))

hits, lifespan = [], 0
for _ in range(20):
    if capital <= 0:
        print(f"BANKRUPT step {total} cap {capital:.1f} gen {seed['gen']} vol {seed['petals']['volatility']['mean']:.2f}")
        with open("garden/lineage.jsonl","a") as f:
            f.write(json.dumps({"id":seed["id"],"gen":seed["gen"],"lifespan":lifespan,"capital":capital,"total":total})+"\n")
        seed["gen"]+=1
        seed["id"]=hashlib.sha256(f"{seed['id']}{time.time()}".encode()).hexdigest()[:6]
        for k in seed["petals"]:
            seed["petals"][k]["mean"] = seed["petals"][k]["mean"]*0.5 + random.gauss(0,0.2)
            if k=="volatility": seed["petals"][k]["mean"] -= 0.3
        seed["root"]["mean"]*=0.5
        capital, lifespan = 100.0, 0
        print(f" EVOLVED fund gen {seed['gen']} vol {seed['petals']['volatility']['mean']:.2f}")

    sig, regime = market_regime(total)
    prob = sigmoid(vigor(sig, seed))
    will_long = prob > 0.5
    true_long = (sig["momentum"]+sig["liquidity"]+sig["value"]) > sig["volatility"]*2.2
    did_long = true_long if random.random()<0.78 else not true_long
    hit = will_long==did_long
    hits.append(hit); lifespan+=1
    capital = capital - 1.1 + (1.0 if hit and will_long else -1.4 if not hit else 0.0)

    with open("garden/petals.jsonl","a") as f:
        f.write(json.dumps({"total":total,"gen":seed["gen"],"regime":regime,"hit":hit,"capital":round(capital,1)})+"\n")

    error = (1.0 if did_long else 0.0) - prob
    lr=0.05
    for k in sig:
        seed["petals"][k]["mean"] = seed["petals"][k]["mean"]*0.99 + lr*error*sig[k]
    seed["root"]["mean"] = seed["root"]["mean"]*0.99 + lr*error
    total+=1

seed["total_steps"]=total
with open("garden/seedling.json","w") as f: json.dump(seed,f,indent=2)
with open("garden/dew.json","w") as f: json.dump({"dew":capital},f,indent=2)

all_p=[json.loads(l) for l in open("garden/petals.jsonl")]
by=defaultdict(list)
for p in all_p: by[p["regime"]].append(p["hit"])
print(f"\nFINANCE total {len(all_p)} gen {seed['gen']} cap {capital:.1f}")
for r in sorted(by):
    label={0:"bull",1:"sideways",2:"crash"}[r]
    print(f" Regime {r} {label}: {sum(by[r])/len(by[r]):.2f} n={len(by[r])}")
