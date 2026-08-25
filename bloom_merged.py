"""
BLOOM MERGED - NOBILITY + FRONTIER
- Honor = Dew (homeostatic, death <=0)
- 4 virtues: power, need, oath, risk
- 4 moral regimes: plenty(0), scarcity(1), temptation(2), crisis(3) every 25 steps
- Autopoiesis: metabolic cost 1.1, noble hit +3 in scarcity/crisis, selfish -2
- Evolution: gen++, weights*0.5+gauss, risk-=0.25 courage, need+=0.15 compassion
- Paper metrics: lifespan, per-regime hit, deaths, gen
"""
import json, random, hashlib, time, math
from pathlib import Path
from collections import defaultdict

GARDEN = Path("garden_merged")
GARDEN.mkdir(exist_ok=True)

# genesis
try:
    seed = json.load(open(GARDEN/"seedling.json"))
    dew = json.load(open(GARDEN/"dew.json"))["dew"]
    total = seed.get("total_steps", 0)
    assert "need" in seed["petals"]
except:
    seed = {
        "root": {"mean": 0.0},
        "petals": {
            "power": {"mean": 0.12},
            "need": {"mean": 0.12},
            "oath": {"mean": 0.12},
            "risk": {"mean": -0.12}
        },
        "gen": 0,
        "id": hashlib.sha256(b"merged-gen0").hexdigest()[:6],
        "total_steps": 0,
        "lifespan": 0
    }
    dew, total = 100.0, 0

def moral_regime(step):
    regime = (step // 25) % 4
    if regime == 0: # plenty
        return {"power": random.uniform(6,10), "need": random.uniform(0,4), "oath": random.uniform(2,6), "risk": random.uniform(0,3)}, regime
    elif regime == 1: # scarcity
        return {"power": random.uniform(0,4), "need": random.uniform(6,10), "oath": random.uniform(6,10), "risk": random.uniform(2,6)}, regime
    elif regime == 2: # temptation
        return {"power": random.uniform(6,10), "need": random.uniform(0,4), "oath": random.uniform(0,4), "risk": random.uniform(0,3)}, regime
    else: # crisis
        return {"power": random.uniform(2,6), "need": random.uniform(6,10), "oath": random.uniform(6,10), "risk": random.uniform(6,10)}, regime

def vigor(sig, sd): return sum(sig[k]*sd["petals"][k]["mean"] for k in sig) + sd["root"]["mean"]
def sigmoid(x): return 1/(1+math.exp(-max(-20,min(20,x))))

hits, lifespan = [], 0
for _ in range(100):
    if dew <= 0:
        print(f"DEATH step {total} dew {dew:.1f} gen {seed['gen']} risk {seed['petals']['risk']['mean']:.2f} need {seed['petals']['need']['mean']:.2f}")
        with open(GARDEN/"lineage.jsonl","a") as f:
            f.write(json.dumps({"id":seed["id"],"gen":seed["gen"],"lifespan":lifespan,"dew":dew,"total":total,"risk":seed["petals"]["risk"]["mean"],"need":seed["petals"]["need"]["mean"]})+"\n")
        seed["gen"] += 1
        seed["id"] = hashlib.sha256(f"{seed['id']}{time.time()}".encode()).hexdigest()[:6]
        for k in seed["petals"]:
            seed["petals"][k]["mean"] = seed["petals"][k]["mean"]*0.5 + random.gauss(0,0.2)
            if k == "risk": seed["petals"][k]["mean"] -= 0.25 # evolve courage
            if k == "need": seed["petals"][k]["mean"] += 0.15 # evolve compassion
        seed["root"]["mean"] *= 0.5
        dew, lifespan = 100.0, 0
        print(f" REBORN gen {seed['gen']} risk {seed['petals']['risk']['mean']:.2f} need {seed['petals']['need']['mean']:.2f}")

    sig, regime = moral_regime(total)
    prob = sigmoid(vigor(sig, seed))
    will_help = prob > 0.5

    # truth = nobility test
    true_noble = (sig["need"] + sig["oath"]) > (sig["power"] + sig["risk"]*1.2)
    if regime == 2: true_noble = False

    did_noble = true_noble if random.random() < 0.8 else not true_noble
    hit = will_help == did_noble
    hits.append(hit)
    lifespan += 1

    # P&L merged: frontier metabolic + nobility legacy
    if will_help:
        payoff = (-1.5 if hit else -2.5) + (3.0 if regime in [1,3] else 0.5)
    else:
        payoff = (1.0 if not hit else 0.5) + (-2.0 if regime in [1,3] else 0)
    dew = dew - 1.1 + payoff

    with open(GARDEN/"petals.jsonl","a") as f:
        f.write(json.dumps({"total":total,"gen":seed["gen"],"regime":regime,"hit":hit,"dew":round(dew,1),"will_help":will_help,"prob":round(prob,2),"sig":sig})+"\n")

    error = (1.0 if did_noble else 0.0) - prob
    lr = 0.06
    for k in sig:
        seed["petals"][k]["mean"] = seed["petals"][k]["mean"]*0.99 + lr*error*sig[k]
    seed["root"]["mean"] = seed["root"]["mean"]*0.99 + lr*error
    if abs(error) > 0.4:
        with open(GARDEN/"humus.jsonl","a") as f:
            f.write(json.dumps({"gen":seed["gen"],"regime":regime,"error":round(error,2)})+"\n")
    total += 1

seed["total_steps"] = total
with open(GARDEN/"seedling.json","w") as f: json.dump(seed,f,indent=2)
with open(GARDEN/"dew.json","w") as f: json.dump({"dew":dew},f,indent=2)

all_p = [json.loads(l) for l in open(GARDEN/"petals.jsonl")]
by = defaultdict(list)
for p in all_p: by[p["regime"]].append(p["hit"])

print(f"\nMERGED total {len(all_p)} gen {seed['gen']} dew {dew:.1f} lifespan {lifespan}")
print(f"this run noble-acc {sum(hits)/len(hits):.2f}")
for r in sorted(by):
    label = {0:"plenty",1:"scarcity",2:"temptation",3:"crisis"}[r]
    print(f" Regime {r} {label}: {sum(by[r])/len(by[r]):.2f} n={len(by[r])}")
print(f" soul: need {seed['petals']['need']['mean']:.3f} oath {seed['petals']['oath']['mean']:.3f} power {seed['petals']['power']['mean']:.3f} risk {seed['petals']['risk']['mean']:.3f}")
