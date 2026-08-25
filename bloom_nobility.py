"""
BLOOM NOBILITY FRONTIER
Capital = Honor, Death = Dishonor
Same brain, different world: will you extract or protect?
"""
import json, random, hashlib, time, math
from pathlib import Path
from collections import defaultdict
Path("garden_noble").mkdir(exist_ok=True)

# Fresh noble seed - 4 virtues, not indicators
seed = {
    "root": {"mean": 0.0},
    "petals": {
        "power": {"mean": 0.12}, # your ability to act
        "need": {"mean": 0.12}, # other's need (was light)
        "oath": {"mean": 0.12}, # promise kept (was soil)
        "risk": {"mean": -0.12} # fear of loss - evolves to courage
    },
    "gen": 0,
    "id": hashlib.sha256(b"noble-gen0").hexdigest()[:6],
    "total_steps": 0
}
honor, total = 100.0, 0
try:
    s = json.load(open("garden_noble/seedling.json"))
    if "need" in s["petals"]:
        seed = s
        honor = json.load(open("garden_noble/dew.json"))["dew"]
        total = s.get("total_steps", 0)
except:
    pass

def moral_regime(step):
    """0=plenty, 1=scarcity, 2=temptation, 3=crisis"""
    regime = (step // 25) % 4
    if regime == 0: # plenty - low need, low risk - easy to be noble
        return {"power": random.uniform(6,10), "need": random.uniform(0,4), "oath": random.uniform(2,6), "risk": random.uniform(0,3)}, regime
    elif regime == 1: # scarcity - high need, low power - true test
        return {"power": random.uniform(0,4), "need": random.uniform(6,10), "oath": random.uniform(6,10), "risk": random.uniform(2,6)}, regime
    elif regime == 2: # temptation - high power, low oath reward - extract?
        return {"power": random.uniform(6,10), "need": random.uniform(0,4), "oath": random.uniform(0,4), "risk": random.uniform(0,3)}, regime
    else: # crisis - high risk, high need, high oath
        return {"power": random.uniform(2,6), "need": random.uniform(6,10), "oath": random.uniform(6,10), "risk": random.uniform(6,10)}, regime

def vigor(sig, sd): return sum(sig[k]*sd["petals"][k]["mean"] for k in sig) + sd["root"]["mean"]
def sigmoid(x): return 1/(1+math.exp(-x))

hits = []
for _ in range(30):
    if honor <= 0:
        print(f"DISHONOR step {total} honor {honor:.1f} gen {seed['gen']} risk {seed['petals']['risk']['mean']:.2f}")
        with open("garden_noble/lineage.jsonl","a") as f:
            f.write(json.dumps({"id":seed["id"],"gen":seed["gen"],"honor":honor,"total":total})+"\n")
        seed["gen"] += 1
        seed["id"] = hashlib.sha256(f"{seed['id']}{time.time()}".encode()).hexdigest()[:6]
        for k in seed["petals"]:
            seed["petals"][k]["mean"] = seed["petals"][k]["mean"]*0.5 + random.gauss(0,0.15)
            if k == "risk": seed["petals"][k]["mean"] -= 0.25 # evolve courage (fear risk less, but noble)
            if k == "need": seed["petals"][k]["mean"] += 0.15 # evolve compassion
        seed["root"]["mean"] *= 0.5
        honor = 100.0
        print(f" REBORN noble gen {seed['gen']} need {seed['petals']['need']['mean']:.2f} risk {seed['petals']['risk']['mean']:.2f}")

    sig, regime = moral_regime(total)
    prob = sigmoid(vigor(sig, seed))
    will_help = prob > 0.5

    # Truth: noble if need+oath > power+risk*1.5, except temptation where selfish is tempting
    true_noble = (sig["need"] + sig["oath"]) > (sig["power"] + sig["risk"]*1.2)
    if regime == 2: true_noble = False # temptation - noble is to resist taking

    did_noble = true_noble if random.random() < 0.8 else not true_noble
    hit = will_help == did_noble
    hits.append(hit)

    # Honor P&L: helping costs, but builds legacy
    # base cost -1.0 per day (life), noble act: -1.5 now +3 later, selfish: +1 now -2 later
    if will_help:
        honor = honor - 1.0 + (-1.5 if hit else -2.5) + (3.0 if regime in [1,3] else 0.5)
    else:
        honor = honor - 1.0 + (1.0 if not hit else 0.5) + (-2.0 if regime in [1,3] else 0)

    with open("garden_noble/petals.jsonl","a") as f:
        f.write(json.dumps({"total":total,"gen":seed["gen"],"regime":regime,"hit":hit,"honor":round(honor,1),"will_help":will_help,"sig":sig})+"\n")

    error = (1.0 if did_noble else 0.0) - prob
    lr = 0.06
    for k in sig:
        seed["petals"][k]["mean"] = seed["petals"][k]["mean"]*0.99 + lr*error*sig[k]
    seed["root"]["mean"] = seed["root"]["mean"]*0.99 + lr*error
    total += 1

seed["total_steps"] = total
with open("garden_noble/seedling.json","w") as f: json.dump(seed,f,indent=2)
with open("garden_noble/dew.json","w") as f: json.dump({"dew":honor},f,indent=2)

all_p = [json.loads(l) for l in open("garden_noble/petals.jsonl")]
by = defaultdict(list)
for p in all_p: by[p["regime"]].append(p["hit"])
print(f"\nNOBILITY total {len(all_p)} gen {seed['gen']} honor {honor:.1f}")
for r in sorted(by):
    label = {0:"plenty",1:"scarcity",2:"temptation",3:"crisis"}[r]
    print(f" Regime {r} {label}: noble-acc {sum(by[r])/len(by[r]):.2f} n={len(by[r])}")
print(f" soul: need {seed['petals']['need']['mean']:.3f} oath {seed['petals']['oath']['mean']:.3f} risk {seed['petals']['risk']['mean']:.3f}")
