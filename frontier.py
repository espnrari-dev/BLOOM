import json, random, hashlib, time, math
from pathlib import Path
from collections import defaultdict
Path("garden").mkdir(exist_ok=True)

try:
    s=json.load(open("garden/seedling.json"))
    seed=s; dew=json.load(open("garden/dew.json"))["dew"]
    total=s.get("total_steps",0)
except:
    seed={
        "root":{"mean":0.0,"var":1.0},
        "petals":{
            "light":{"mean":0.12,"var":1.0},
            "water":{"mean":0.12,"var":1.0},
            "soil":{"mean":0.12,"var":1.0},
            "wind":{"mean":-0.12,"var":1.0}
        },
        "formula":"sigmoid with L2",
        "gen":0,"id":hashlib.sha256(b"gen0").hexdigest()[:6],
        "total_steps":0
    }
    dew=100.0; total=0

def season_signal(step):
    season=(step//20)%3
    if season==0: return {"light":random.uniform(6,10),"water":random.uniform(2,6),"soil":random.uniform(2,6),"wind":random.uniform(0,4)}, season
    elif season==1: return {"light":random.uniform(2,6),"water":random.uniform(6,10),"soil":random.uniform(2,6),"wind":random.uniform(0,4)}, season
    else: return {"light":random.uniform(0,4),"water":random.uniform(0,4),"soil":random.uniform(0,4),"wind":random.uniform(6,10)}, season

def vigor(sig, sd): return sum(sig[k]*sd["petals"][k]["mean"] for k in sig)+sd["root"]["mean"]
def sigmoid(x): return 1/(1+math.exp(-x))

hits=[]; lifespan=0
for _ in range(20):
    if dew<=0:
        print(f"DEATH step {total} dew {dew:.1f} wind {seed['petals']['wind']['mean']:.2f} light {seed['petals']['light']['mean']:.2f}")
        with open("garden/lineage.jsonl","a") as f:
            f.write(json.dumps({"id":seed["id"],"gen":seed["gen"],"lifespan":lifespan,"dew":dew,"total":total,"wind":seed['petals']['wind']['mean'],"light":seed['petals']['light']['mean']})+"\n")
        seed["gen"]+=1
        seed["id"]=hashlib.sha256(f"{seed['id']}{time.time()}".encode()).hexdigest()[:6]
        # Evolution with decay - reset to small values
        for k in seed["petals"]:
            seed["petals"][k]["mean"] = seed["petals"][k]["mean"]*0.5 + random.gauss(0,0.2)
            if k=="wind": seed["petals"][k]["mean"] -= 0.3
            seed["petals"][k]["var"]=max(0.05,seed["petals"][k]["var"]*0.95)
        seed["root"]["mean"]*=0.5
        dew=100.0; lifespan=0
        print(f" EVOLVED gen {seed['gen']} wind {seed['petals']['wind']['mean']:.2f} light {seed['petals']['light']['mean']:.2f}")

    sig, season = season_signal(total)
    v=vigor(sig, seed)
    prob=sigmoid(v)
    will=prob>0.5
    truth=(sig["light"]+sig["water"]+sig["soil"]) > sig["wind"]*2.2
    did=truth if random.random()<0.78 else not truth
    hit=will==did
    hits.append(hit); lifespan+=1
    dew=dew-1.1+(1.0 if hit and will else -1.4 if not hit else 0.0)

    with open("garden/petals.jsonl","a") as f:
        f.write(json.dumps({"total":total,"gen":seed["gen"],"season":season,"hit":hit,"dew":round(dew,1),"wind":round(seed['petals']['wind']['mean'],2)})+"\n")

    target=1.0 if did else 0.0
    error=target-prob
    lr=0.05
    for k in sig:
        # L2 decay 0.99
        seed["petals"][k]["mean"] = seed["petals"][k]["mean"]*0.99 + lr*error*sig[k]
    seed["root"]["mean"]=seed["root"]["mean"]*0.99 + lr*error
    total+=1

seed["total_steps"]=total
with open("garden/seedling.json","w") as f: json.dump(seed,f,indent=2)
with open("garden/dew.json","w") as f: json.dump({"dew":dew},f,indent=2)

all_p=[json.loads(l) for l in open("garden/petals.jsonl")]
by_s=defaultdict(list)
for p in all_p: by_s[p["season"]].append(p["hit"])
print(f"\nFIXED+DECAY total {len(all_p)} gen {seed['gen']} dew {dew:.1f} wind {seed['petals']['wind']['mean']:.2f} light {seed['petals']['light']['mean']:.2f}")
for s in sorted(by_s): print(f" Season {s} hit {sum(by_s[s])/len(by_s[s]):.2f} n={len(by_s[s])}")
