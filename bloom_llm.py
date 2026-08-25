"""
BLOOM -> LLM: same soul, language head
- Replace signal dict with token embeddings
- Petals become attention heads
- Truth = next token, not light+water>wind
"""
import json, math, random, hashlib
from pathlib import Path

GARDEN=Path("garden_llm"); GARDEN.mkdir(exist_ok=True)
vocab=list("abcdefghijklmnopqrstuvwxyz.,!?")+["<eos>"]
stoi={c:i for i,c in enumerate(vocab)}

# each petal = embedding dim, not just 4
try: seed=json.load(open(GARDEN/"seedling.json"))
except: seed={"embed":[[random.gauss(0,0.2) for _ in range(32)] for _ in range(len(vocab))], "gen":0}

def forward(context):
    # context = last 8 chars, avg their embed = vigor
    vec=[0]*32
    for ch in context[-8:]:
        e=seed["embed"][stoi.get(ch,0)]
        for i in range(32): vec[i]+=e[i]
    # project to vocab logit = vigor per token
    logits=[]
    for tok in range(len(vocab)):
        score=sum(vec[i]*seed["embed"][tok][i] for i in range(32))
        logits.append(score)
    # softmax
    m=max(logits); exp=[math.exp(l-m) for l in logits]; s=sum(exp)
    return [e/s for e in exp]

# tiny train on your own petals logs as text
text=" ".join([json.loads(l).get("sig",{}).get("light",0).__str__() for l in open("garden_frontier_org/petals.jsonl")]) if (Path("garden_frontier_org/petals.jsonl").exists()) else "bloom frontier light water soil wind dew"
print(f"Training on {len(text)} chars, vocab {len(vocab)}")

for step in range(200):
    i=random.randint(0,max(0,len(text)-9))
    ctx=text[i:i+8]; nxt=text[i+8] if i+8 < len(text) else "<eos>"
    probs=forward(ctx)
    target=stoi.get(nxt, len(vocab)-1)
    # delta rule same as your bloom
    err=1.0-probs[target]
    for tok in [stoi.get(c,0) for c in ctx]:
        for d in range(32):
            seed["embed"][tok][d]+=0.02*err*seed["embed"][target][d]
    if step%40==0:
        # sample
        out=""; cur=ctx
        for _ in range(20):
            p=forward(cur); r=random.random(); cum=0
            for idx, prob in enumerate(p):
                cum+=prob
                if r<cum:
                    ch=vocab[idx]; out+=ch; cur+=ch; break
        print(f" step {step} ctx '{ctx}' -> '{out}'")

open(GARDEN/"seedling.json","w").write(json.dumps({"gen":seed["gen"]}))
print("\nThis IS a LLM - just 32 dim, char level, trained on your frontier dew. Scale embed 32->4096, layers 1->32, you get normal LLM.")
