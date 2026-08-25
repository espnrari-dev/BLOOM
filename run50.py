import subprocess, json
from collections import defaultdict

for i in range(50):
    result = subprocess.run(["python3","bloom_frontier.py"], capture_output=True, text=True)
    # print last 2 lines
    print(result.stdout.strip().split("\n")[-3:])

# Final paper
ps=[json.loads(l) for l in open("garden/petals.jsonl")]
by=defaultdict(list)
for p in ps: by[p["season"]].append(p["hit"])

print("\n=== 50-RUN PAPER ===")
for s in sorted(by):
    label={0:"spring",1:"summer",2:"storm"}[s]
    hit=sum(by[s])/len(by[s])
    print(f"S{s} {label}: {hit:.3f} n={len(by[s])}")

seed=json.load(open("garden/seedling.json"))
print(f"gens {seed['gen']} deaths {len(open('garden/lineage.jsonl').readlines())} total_steps {seed['total_steps']}")
for k,v in seed["petals"].items():
    print(f" {k}: {v['mean']:.3f}")

# Evolution of wind
lineage=[json.loads(l) for l in open("garden/lineage.jsonl")]
print("\nWind evolution on death:")
for l in lineage[-10:]:
    print(f" gen {l['gen']} wind {l.get('wind',0):.2f} lifespan {l['lifespan']}")
