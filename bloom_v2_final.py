import requests, numpy as np
from pathlib import Path
Path("garden_best_llm").mkdir(exist_ok=True)
txt=requests.get("https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt",timeout=15).text[:50000]
chars=sorted(list(set(txt))); vs=len(chars)
stoi={ch:i for i,ch in enumerate(chars)}; itos={i:ch for i,ch in enumerate(chars)}
data=np.array([stoi[c] for c in txt])
print(f"vocab {vs} len {len(txt)}")
hidden=128; block=32; batch=16
Wxh=np.random.randn(vs,hidden)*0.1; Whh=np.random.randn(hidden,hidden)*0.1/np.sqrt(hidden); Why=np.random.randn(hidden,vs)*0.1
bh=np.zeros(hidden); by=np.zeros(vs)
mWxh=np.zeros_like(Wxh); mWhh=np.zeros_like(Whh); mWhy=np.zeros_like(Why); mbh=np.zeros_like(bh); mby=np.zeros_like(by)
vWxh=np.zeros_like(Wxh); vWhh=np.zeros_like(Whh); vWhy=np.zeros_like(Why); vbh=np.zeros_like(bh); vby=np.zeros_like(by)
def forward(xs,h0):
    T,B=xs.shape; h=np.zeros((T+1,B,hidden)); h[0]=h0; logits=np.zeros((T,B,vs))
    for t in range(T): h[t+1]=np.tanh(Wxh[xs[t]] + h[t]@Whh + bh); logits[t]=h[t+1]@Why+by
    return logits,h
def loss_grad(logits,targets,h,xs):
    T,B,_=logits.shape; m=np.max(logits,axis=-1,keepdims=True); e=np.exp(logits-m); p=e/np.sum(e,axis=-1,keepdims=True)
    loss=-np.mean(np.log(p[np.arange(T)[:,None], np.arange(B), targets]+1e-8))
    dlog=p.copy(); dlog[np.arange(T)[:,None], np.arange(B), targets]-=1; dlog/=T*B
    dWhy=np.zeros_like(Why); dby=np.zeros_like(by); dWxh=np.zeros_like(Wxh); dWhh=np.zeros_like(Whh); dbh=np.zeros_like(bh); dh_next=np.zeros((B,hidden))
    for t in reversed(range(T)):
        dl=dlog[t]; dWhy+=h[t+1].T@dl; dby+=dl.sum(0); dh=dl@Why.T+dh_next; dh_raw=dh*(1-h[t+1]**2); dbh+=dh_raw.sum(0); dWhh+=h[t].T@dh_raw
        for b in range(B): dWxh[xs[t,b]]+=dh_raw[b]
        dh_next=dh_raw@Whh.T
    return loss,dWxh,dWhh,dWhy,dbh,dby

best=10
for it in range(1,5000):
    idx=np.random.randint(0,len(data)-block-1,size=batch)
    xs=np.zeros((block,batch),dtype=int); ys=np.zeros((block,batch),dtype=int)
    for b,i in enumerate(idx): xs[:,b]=data[i:i+block]; ys[:,b]=data[i+1:i+block+1]
    logits,h=forward(xs,np.zeros((batch,hidden)))
    loss,dWxh,dWhh,dWhy,dbh,dby=loss_grad(logits,ys,h,xs)
    for par,m,v,d in [(Wxh,mWxh,vWxh,dWxh),(Whh,mWhh,vWhh,dWhh),(Why,mWhy,vWhy,dWhy),(bh,mbh,vbh,dbh),(by,mby,vby,dby)]:
        m[:]=0.9*m+0.1*d; v[:]=0.999*v+0.001*d*d
        par-=0.003*(m/(1-0.9**it))/(np.sqrt(v/(1-0.999**it))+1e-8)
    if it%100==0:
        np.savez("garden_best_llm/W.npz",Wxh=Wxh,Whh=Whh,Why=Why,bh=bh,by=by)
        cur=np.array([[stoi['\n']]]); hs=np.zeros((1,hidden)); out="\n"
        for _ in range(200):
            lg,hf=forward(cur,hs); hs=hf[-1]; pr=np.exp(lg[-1]-np.max(lg[-1])); pr/=pr.sum(); nxt=np.random.choice(vs,p=pr[0]); out+=itos[nxt]; cur=np.array([[nxt]])
        print(f"{it} loss {loss:.3f} best {best:.3f} saved\n{out[:200]}\n---"); best=min(best,loss)
