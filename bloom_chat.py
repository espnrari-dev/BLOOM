import numpy as np, requests
txt=requests.get("https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt",timeout=15).text[:50000]
chars=sorted(list(set(txt))); vs=len(chars)
stoi={ch:i for i,ch in enumerate(chars)}; itos={i:ch for i,ch in enumerate(chars)}
print(f"vocab {vs} chars loaded")
hidden=128
Wxh=np.random.randn(vs,hidden)*0.1; Whh=np.random.randn(hidden,hidden)*0.1/np.sqrt(hidden); Why=np.random.randn(hidden,vs)*0.1
bh=np.zeros(hidden); by=np.zeros(vs)
try:
    d=np.load("garden_best_llm/W.npz"); Wxh,Whh,Why,bh,by=d["Wxh"],d["Whh"],d["Why"],d["bh"],d["by"]
    print(f"loaded W.npz loss ~1.45")
except: print("fresh weights")

def gen(seed, n=400, temp=0.7):
    # clean seed to known chars only
    clean="".join([c for c in seed if c in stoi])
    if not clean: clean="\n"
    h=np.zeros((1,hidden))
    # prime with seed
    for ch in clean[:-1]:
        x=np.array([[stoi[ch]]]); hh=np.tanh(Wxh[x[0]] + h@Whh + bh); h=hh
    cur=np.array([[stoi[clean[-1]]]]); out=clean
    for _ in range(n):
        hh=np.tanh(Wxh[cur[0]] + h@Whh + bh); lg=hh@Why+by
        lg/=temp; p=np.exp(lg-np.max(lg)); p/=p.sum()
        nxt=np.random.choice(vs,p=p[0]); out+=itos[nxt]; cur=np.array([[nxt]]); h=hh
    return out

while True:
    s=input("\nseed> ")
    if s=="q": break
    print(gen(s, 500))
