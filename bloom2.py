import json, random
with open("garden/seedling.json") as f: seed=json.load(f)
petals=[json.loads(l) for l in open("garden/petals.jsonl")]

# Learn: if light+water+soil was high on hits, increase those petals
hits=[p for p in petals if p["hit"] and p["guess"]=="bloom"]
if hits:
    seed["petals"]["light"] += sum(p["lumens"] for p in hits)/len(hits)*0.001
    seed["petals"]["water"] += sum(p["drink"] for p in hits)/len(hits)*0.001
    seed["petals"]["soil"] += sum(p["earth"] for p in hits)/len(hits)*0.001
    seed["root"] += 0.01

with open("garden/seedling.json","w") as f: json.dump(seed,f,indent=2)
print(f"Loop 2 - seedling grew: {seed['petals']}")
