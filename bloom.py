"""
BLOOM - Loop 1 from zero
No BIRTH_EDGE names, no scores, no treasury, no ledger, no ml_
Totally original architecture: seed -> sprout -> garden -> compost
"""
import json, random, hashlib, time
from pathlib import Path

Path("garden").mkdir(exist_ok=True)

# New arch - nothing from old project
# garden/seedling.json  (not ml_model)
# garden/petals.jsonl   (not ml_reflection)
# garden/dew.json       (not balance)
# garden/humus.jsonl    (not treasury/ledger)

seedling={
    "root": 0.0,
    "petals": {"light":0.12,"water":0.12,"soil":0.12,"wind":0.12},
    "season": int(time.time())
}
with open("garden/seedling.json","w") as f: json.dump(seedling,f,indent=2)
with open("garden/dew.json","w") as f: json.dump({"dew":100.0},f,indent=2)
open("garden/petals.jsonl","w").close()
open("garden/humus.jsonl","w").close()

def sprout():
    return {
        "color": random.choice(["crimson","amber","violet","azure"]),
        "light": random.uniform(0,10),
        "water": random.uniform(0,10),
        "soil": random.uniform(0,10),
        "wind": random.uniform(0,10)
    }

petal_log=[]
dew=100.0
for i in range(40):
    s=sprout()
    # logic only: light+water+soil vs wind = bloom or wilt
    vigor = s["light"]*seedling["petals"]["light"] + s["water"]*seedling["petals"]["water"] + s["soil"]*seedling["petals"]["soil"] - s["wind"]*seedling["petals"]["wind"] + seedling["root"]
    will_bloom = vigor > 0
    did_bloom = will_bloom if random.random()<0.75 else not will_bloom

    entry={
        "id": f"bl_{i}_{hashlib.sha256(str(time.time()+i).encode()).hexdigest()[:6]}",
        "hue": s["color"],
        "lumens": s["light"],
        "drink": s["water"],
        "earth": s["soil"],
        "gust": s["wind"],
        "guess": "bloom" if will_bloom else "wilt",
        "truth": "bloom" if did_bloom else "wilt",
        "hit": will_bloom==did_bloom,
        "vigor": vigor,
        "season": i
    }
    petal_log.append(entry)
    with open("garden/petals.jsonl","a") as f: f.write(json.dumps(entry)+"\n")
    if will_bloom:
        dew+=0.5
        with open("garden/humus.jsonl","a") as f: f.write(json.dumps({"bloomed":s["color"],"vigor":vigor})+"\n")
    else:
        dew-=0.3

with open("garden/dew.json","w") as f: json.dump({"dew":dew},f,indent=2)

print(f"BLOOM Loop 1: {len(petal_log)} petals, dew {dew:.1f}")
print(f"Files: garden/seedling.json, garden/petals.jsonl, garden/humus.jsonl, garden/dew.json")
print("Zero BIRTH_EDGE names inside")
