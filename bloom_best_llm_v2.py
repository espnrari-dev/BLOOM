import requests, numpy as np
from pathlib import Path

txt=requests.get("https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt",timeout=15).text[:50000]
chars=sorted(list(set(txt))); vs=len(chars)
stoi={ch:i for i,ch in enumerate(chars)}
itos={i:ch for i,ch in enumerate(chars)}
data=np.array([stoi[c] for c in txt])
print(f"vocab {vs} len {len(txt)}")

hidden=128; block=32; batch=16
Wxh=np.random.randn(vs,hidden)*0.1
Whh=np.random.randn(hidden,hidden)*0.1/np.sqrt(hidden)
Why=np.random.randn(hidden,vs)*0.1
bh=np.zeros(hidden); by=np.zeros(vs)
mWxh=np.zeros_like(Wxh); mWhh=np.zeros_like(Whh); mWhy=np.zeros_like(Why); mbh=np.zeros_like(bh); mby=np.zeros_like(by)
vWxh=np.zeros_like(Wxh); vWhh=np.zeros_like(Whh); vWhy=np.zeros_like(Why); vbh=np.zeros_like(bh); vby=np.zeros_like(by)

def forward(xs, h0):
    T,B=xs.shape
    h=np.zeros((T+1,B,hidden))
    h[0]=h0
    logits=np.zeros((T,B,vs))
    for t in range(T):
        h[t+1]=np.tanh(Wxh[xs[t]] + h[t]@Whh + bh)
        logits[t]=h[t+1]@Why + by
    return logits, h

def loss_and_grad(logits, targets, h, xs):
    T,B,_=logits.shape
    m=np.max(logits,axis=-1,keepdims=True); e=np.exp(logits-m); probs=e/np.sum(e,axis=-1,keepdims=True)
    loss=-np.mean(np.log(probs[np.arange(T)[:,None], np.arange(B), targets]+1e-8))
    dlogits=probs.copy(); dlogits[np.arange(T)[:,None], np.arange(B), targets]-=1; dlogits/=T*B
    dWhy=np.zeros_like(Why); dby=np.zeros_like(by); dWxh=np.zeros_like(Wxh); dWhh=np.zeros_like(Whh); dbh=np.zeros_like(bh)
    dh_next=np.zeros((B,hidden))
    for t in reversed(range(T)):
        dlog=dlogits[t]
        dWhy+=h[t+1].T@dlog; dby+=np.sum(dlog,axis=0)
        dh=dlog@Why.T + dh_next
        dh_raw=dh*(1-h[t+1]**2)
        dbh+=np.sum(dh_raw,axis=0)
        dWhh+=h[t].T@dh_raw
        for b in range(B): dWxh[xs[t,b]]+=dh_raw[b]
        dh_next=dh_raw@Whh.T
    return loss, dWxh, dWhh, dWhy, dbh, dby

dew=100.0; gen=0; best=10
for it in range(1000):
    if dew<=0:
        print(f"DEATH gen{gen} dew {dew:.1f} -> REBORN"); gen+=1; dew=100
    idx=np.random.randint(0,len(data)-block-1,size=batch)
    xs=np.zeros((block,batch),dtype=int); ys=np.zeros((block,batch),dtype=int)
    for b,i in enumerate(idx): xs[:,b]=data[i:i+block]; ys[:,b]=data[i+1:i+block+1]
    logits,h=forward(xs, np.zeros((batch,hidden)))
    loss,dWxh,dWhh,dWhy,dbh,dby=loss_and_grad(logits, ys, h, xs)
    beta1=0.9; beta2=0.999; lr=0.005
    for p,m,v,d in [(Wxh,mWxh,vWxh,dWxh),(Whh,mWhh,vWhh,dWhh),(Why,mWhy,vWhy,dWhy),(bh,mbh,vbh,dbh),(by,mby,vby,dby)]:
        m[:]=beta1*m+(1-beta1)*d; v[:]=beta2*v+(1-beta2)*(d*d)
        p-=lr*(m/(1-beta1**(it+1)))/(np.sqrt(v/(1-beta2**(it+1)))+1e-8)
    if loss<best: dew=dew-0.3+1.5; best=loss
    else: dew-=0.3
    if it%50==0:
        cur=np.array([[stoi[txt[0]]]])
        h_state=np.zeros((1,hidden))
        out=txt[0]
        for _ in range(120):
            lg,h_full=forward(cur, h_state)
            h_state=h_full[-1]
            prob=np.exp(lg[-1]-np.max(lg[-1])); prob/=prob.sum()
            nxt=np.random.choice(vs,p=prob[0])
            out+=itos[nxt]
            cur=np.array([[nxt]])
        print(f"{it} gen{gen} dew {dew:.1f} loss {loss:.3f} best {best:.3f} | {out[:120]}")
