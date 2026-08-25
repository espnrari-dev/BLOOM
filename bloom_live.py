import json, random, math, requests
from pathlib import Path
Path("garden_live").mkdir(exist_ok=True)

def get_spy():
    url="https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=2y&interval=1d"
    r=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
    j=r.json()
    res=j["chart"]["result"][0]
    closes=[c for c in res["indicators"]["quote"][0]["close"] if c is not None]
    vols=[v for v in res["indicators"]["quote"][0]["volume"] if v is not None]
    print(f"REAL SPY {len(closes)} days")
    return closes, vols

closes, volumes = get_spy()
N=len(closes)

seed={"root":{"mean":0.0},"petals":{"momentum":{"mean":0.12},"liquidity":{"mean":0.12},"value":{"mean":0.12},"volatility":{"mean":-0.12}},"gen":0,"total_steps":0}
capital=100.0
try:
    s=json.load(open("garden_live/seedling.json"))
    if "momentum" in s["petals"]:
        seed=s
        capital=json.load(open("garden_live/dew.json"))["dew"]
except: pass

def sig_for(idx):
    idx = idx % (N-1)
    window=closes[max(0,idx-20):idx+1]
    price=closes[idx]
    ma20=sum(window)/len(window)
    momentum=max(0,min(10,(price/ma20-0.95)*100))
    vol=volumes[idx] if idx < len(volumes) else 80e6
    vol_ma=sum(volumes[max(0,idx-20):idx+1])/20
    liquidity=max(0,min(10,vol/vol_ma*5))
    ma200=sum(closes[max(0,idx-200):idx+1])/min(200,idx+1)
    value=max(0,min(10,10-abs(price/ma200-1)*100))
    mean=sum(window)/len(window)
    var=sum((x-mean)**2 for x in window)/len(window) if len(window)>1 else 1
    volatility=max(0,min(10,math.sqrt(var)/mean*200))
    regime=2 if volatility>6 else 0 if momentum>6 else 1
    future=(closes[(idx+1)%N]-price)/price
    return {"momentum":momentum,"liquidity":liquidity,"value":value,"volatility":volatility}, regime, future

def vigor(s, sd): return sum(s[k]*sd["petals"][k]["mean"] for k in s)+sd["root"]["mean"]
def sigmoid(x): return 1/(1+math.exp(-x))

total=seed["total_steps"]
hits=[]
for _ in range(20):
    if capital<=0:
        seed["gen"]+=1
        for k in seed["petals"]:
            seed["petals"][k]["mean"]=seed["petals"][k]["mean"]*0.5+random.gauss(0,0.2)
            if k=="volatility": seed["petals"][k]["mean"]-=0.3
        capital=100.0
        print(f"BANKRUPT -> gen {seed['gen']} vol {seed['petals']['volatility']['mean']:.2f}")

    sig, regime, future = sig_for(total)
    prob=sigmoid(vigor(sig, seed))
    will_long=prob>0.5
    true_long=future>0 if sig["volatility"]<6 else False
    hit=will_long==true_long
    hits.append(hit)
    pnl=future*20 if will_long else 0
    capital=capital-0.1+pnl
    with open("garden_live/petals.jsonl","a") as f:
        f.write(json.dumps({"total":total,"regime":regime,"hit":hit,"cap":round(capital,2),"future":round(future,4)})+"\n")
    err=(1.0 if true_long else 0.0)-prob
    for k in sig: seed["petals"][k]["mean"]=seed["petals"][k]["mean"]*0.99+0.05*err*sig[k]
    total+=1

seed["total_steps"]=total
with open("garden_live/seedling.json","w") as f: json.dump(seed,f,indent=2)
with open("garden_live/dew.json","w") as f: json.dump({"dew":capital},f,indent=2)
print(f"\nREAL FINANCE gen {seed['gen']} cap {capital:.2f} hit {sum(hits)/len(hits):.2f} steps {total}/{N} vol {seed['petals']['volatility']['mean']:.2f}")
