import numpy as np, pathlib
p=pathlib.Path.home()/"BLOOM"/"my_texts.txt"
raw=p.read_text() if p.exists() else "East Point, Georgia. BLOOM is the best LLM on Termux. It learns Shakespeare and my thoughts. "
txt=raw*400
chars=sorted(set(txt))
vs=len(chars)
stoi={c:i for i,c in enumerate(chars)}
itos={i:c for i,c in enumerate(chars)}
data=np.array([stoi[c] for c in txt], dtype=np.int32)
H=128
T=64
np.random.seed(0)
Wxh=np.random.randn(vs,H)*0.02
Whh=np.random.randn(H,H)*0.02
Why=np.random.randn(H,vs)*0.02
bh=np.zeros(H)
by=np.zeros(vs)

def step(x,h):
    return np.tanh(Wxh.T@x + Whh.T@h + bh[:,None])

h=np.zeros((H,1))
for it in range(4000):
    s=np.random.randint(0, len(data)-T-1)
    xs=data[s:s+T]
    ys=data[s+1:s+T+1]
    hs={}
    hs[-1]=h
    for t in range(T):
        xv=np.zeros((vs,1)); xv[xs[t]]=1
        hs[t]=np.tanh(Wxh.T@xv + Whh.T@hs[t-1] + bh[:,None])
    dWxh=np.zeros_like(Wxh); dWhh=np.zeros_like(Whh); dWhy=np.zeros_like(Why)
    dbh=np.zeros_like(bh); dby=np.zeros_like(by)
    dh_next=np.zeros((H,1))
    loss=0
    for t in reversed(range(T)):
        y=Why.T@hs[t]+by[:,None]
        y=y-y.max()
        e=np.exp(y); e=e/e.sum()
        loss-=np.log(e[ys[t],0]+1e-9)
        dy=e.copy(); dy[ys[t]]-=1
        dWhy+=hs[t]@dy.T
        dby+=dy.ravel()
        dh=Why@dy+dh_next
        dh_raw=(1-hs[t]**2)*dh
        dbh+=dh_raw.ravel()
        xv=np.zeros((vs,1)); xv[xs[t]]=1
        dWxh+=xv@dh_raw.T
        dWhh+=hs[t-1]@dh_raw.T
        dh_next=Whh@dh_raw
    Wxh-=0.01*dWxh/T; Whh-=0.01*dWhh/T; Why-=0.01*dWhy/T; bh-=0.01*dbh/T; by-=0.01*dby/T
    h=hs[T-1]
    if it%500==0:
        print(it, round(loss/T,3))

def gen(prompt, n=250):
    h2=np.zeros((H,1))
    for c in prompt:
        if c not in stoi: continue
        xv=np.zeros((vs,1)); xv[stoi[c]]=1
        h2=np.tanh(Wxh.T@xv + Whh.T@h2 + bh[:,None])
    out=prompt
    xv=np.zeros((vs,1)); xv[stoi[prompt[-1]]]=1
    for _ in range(n):
        h2=np.tanh(Wxh.T@xv + Whh.T@h2 + bh[:,None])
        y=Why.T@h2+by[:,None]
        idx=int(np.argmax(y))
        out+=itos[idx]
        xv=np.zeros((vs,1)); xv[idx]=1
    return out

print("ready - deterministic argmax")
while True:
    q=input("\n> ")
    if q in ("exit","quit"): break
    print(gen(q, 300))
