import requests, numpy as np
from pathlib import Path

# 1. ENGLISH DATA - not Shakespeare
# TinyStories + your voice = modern English
url = "https://raw.githubusercontent.com/roneneldan/TinyStories/master/TinyStories_all_data/valid.txt"
try:
    txt = requests.get(url, timeout=10).text[:400000]
    print("TinyStories English loaded")
except:
    txt = (Path("my_texts.txt").read_text()+"\n")*200 if Path("my_texts.txt").exists() else ""
    txt += "The meaning of life is to bloom. BLOOM is the best LLM on Termux. I live in Lovejoy, Georgia. The computer learns English. " * 5000
    print("Using my_texts.txt x200 + English seed")

txt = txt + "\n" + (Path("my_texts.txt").read_text()*50 if Path("my_texts.txt").exists() else "")
chars=sorted(set(txt)); vs=len(chars); stoi={c:i for i,c in enumerate(chars)}; itos={i:c for i,c in enumerate(chars)}
data=np.array([stoi[c] for c in txt])
print(f"ENGLISH vocab {vs} len {len(txt)}")

H=128; T=64; B=16
Wxh=np.random.randn(vs,H)*0.01; Whh=np.random.randn(H,H)*0.01; Why=np.random.randn(H,vs)*0.01
bh=np.zeros(H); by=np.zeros(vs)
mWxh=np.zeros_like(Wxh); mWhh=np.zeros_like(Whh); mWhy=np.zeros_like(Why); mbh=np.zeros_like(bh); mby=np.zeros_like(by)

def sample(h, seed, n=200):
    x=np.zeros((vs,1)); x[seed]=1
    out=""
    for _ in range(n):
        h=np.tanh(Wxh.T@x + Whh.T@h + bh[:,None])
        y=Why.T@h + by[:,None]
        p=np.exp(y-y.max()); p/=p.sum()
        idx=np.random.choice(vs,p=p.ravel())
        x=np.zeros((vs,1)); x[idx]=1
        out+=itos[idx]
    return out

it=0; best=10
hprev=np.zeros((H,1))
while True:
    it+=1
    idx=np.random.randint(0,len(data)-T-1)
    xs=data[idx:idx+T]; ys=data[idx+1:idx+T+1]
    xs_one=np.zeros((vs,T)); xs_one[xs,np.arange(T)]=1
    # forward
    hs={-1:hprev}; loss=0
    for t in range(T):
        hs[t]=np.tanh(Wxh.T@xs_one[:,t,None] + Whh.T@hs[t-1] + bh[:,None])
    # loss + backward (truncated)
    dWxh=np.zeros_like(Wxh); dWhh=np.zeros_like(Whh); dWhy=np.zeros_like(Why); dbh=np.zeros_like(bh); dby=np.zeros_like(by)
    dhnext=np.zeros((H,1))
    for t in reversed(range(T)):
        y=Why.T@hs[t] + by[:,None]
        p=np.exp(y-y.max()); p/=p.sum()
        loss-=np.log(p[ys[t],0]+1e-8)
        dy=p.copy(); dy[ys[t]]-=1
        dWhy+=hs[t]@dy.T; dby+=dy.ravel()
        dh=Why@dy + dhnext
        dhraw=(1-hs[t]**2)*dh
        dbh+=dhraw.ravel(); dWxh+=xs_one[:,t,None]@dhraw.T; dWhh+=hs[t-1]@dhraw.T
        dhnext=Whh@dhraw
    loss/=T
    # adam-ish
    for p,d,m in [(Wxh,dWxh,mWxh),(Whh,dWhh,mWhh),(Why,dWhy,mWhy)]:
        m[:]=0.9*m+0.1*d; p-=0.001*m
    bh-=0.001*dbh; by-=0.001*dby
    hprev=hs[T-1]
    if it%100==0:
        print(f"{it} loss {loss:.3f} best {best:.3f} ENGLISH")
        if loss<best:
            best=loss
            print(sample(hprev, stoi[txt[0]], 300)+"\n---")
