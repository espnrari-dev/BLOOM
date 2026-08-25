import requests, numpy as np
from pathlib import Path
Path("bloom_frontier").mkdir(exist_ok=True)

txt=requests.get("https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt",timeout=15).text
try:
    txt+="\n"+Path("my_texts.txt").read_text()
    print("added my_texts.txt")
except: pass
chars=sorted(list(set(txt))); vs=len(chars)
stoi={c:i for i,c in enumerate(chars)}; itos={i:c for i,c in enumerate(chars)}
data=np.array([stoi[c] for c in txt],dtype=np.int32)
print(f"FRONTIER vocab {vs} len {len(txt)}")

# --- hyper ---
B=16; T=64; H=128; n_layer=2; lr=3e-4
nh=4; hs=H//nh

# init
def rand(*s): return np.random.randn(*s)*0.02
Wte=rand(vs,H); Wpe=rand(T,H)
layers=[]
for _ in range(n_layer):
    layers.append(dict(
        ln1_g=np.ones(H), ln1_b=np.zeros(H),
        Wq=rand(H,H), Wk=rand(H,H), Wv=rand(H,H), Wo=rand(H,H),
        ln2_g=np.ones(H), ln2_b=np.zeros(H),
        W1=rand(H,4*H), b1=np.zeros(4*H),
        W2=rand(4*H,H), b2=np.zeros(H)
    ))
lnf_g=np.ones(H); lnf_b=np.zeros(H)
Why=rand(H,vs); by=np.zeros(vs)

# adam
params=[]
for p in [Wte,Wpe]: params.append(p)
for l in layers:
    for k in ['ln1_g','ln1_b','Wq','Wk','Wv','Wo','ln2_g','ln2_b','W1','b1','W2','b2']: params.append(l[k])
params+=[lnf_g,lnf_b,Why,by]
m=[np.zeros_like(p) for p in params]; v=[np.zeros_like(p) for p in params]

def ln_fwd(x,g,b,eps=1e-5):
    mean=x.mean(-1,keepdims=True); var=((x-mean)**2).mean(-1,keepdims=True)
    std=np.sqrt(var+eps); xn=(x-mean)/std; out=xn*g+b
    return out,(x,xn,mean,std,g)
def ln_bwd(dout,cache):
    x,xn,mean,std,g=cache
    dxn=dout*g
    dvar=np.sum(dxn*(x-mean)*-0.5*std**-3,axis=-1,keepdims=True)
    dmean=np.sum(dxn*-1/std,axis=-1,keepdims=True)+dvar*np.mean(-2*(x-mean),axis=-1,keepdims=True)
    dx=dxn/std + dvar*2*(x-mean)/H + dmean/H
    dg=np.sum(dout*xn,axis=(0,1)); db=np.sum(dout,axis=(0,1))
    return dx,dg,db

def gelu(x): return 0.5*x*(1+np.tanh(np.sqrt(2/np.pi)*(x+0.044715*x**3)))
def gelu_bwd(dout,x):
    # approx derivative
    c=np.sqrt(2/np.pi); c3=0.044715
    tanh_arg=c*(x+c3*x**3); tanh_out=np.tanh(tanh_arg)
    left=0.5*(1+tanh_out); right=0.5*x*(1-tanh_out**2)*c*(1+3*c3*x**2)
    return dout*(left+right)

mask = np.full((T,T), -1e10); mask = np.triu(mask, k=1) # causal

def forward(ids): # ids (B,T)
    B,Tt=ids.shape
    cache={}
    x = Wte[ids] + Wpe[:Tt][None,:,:] # (B,T,H)
    cache['x0']=x
    for li,l in enumerate(layers):
        # ln1
        xl1,c1=ln_fwd(x,l['ln1_g'],l['ln1_b']); cache[f'ln1_{li}']=c1
        Q=xl1@l['Wq']; K=xl1@l['Wk']; V=xl1@l['Wv']
        cache[f'Q_{li}']=Q; cache[f'K_{li}']=K; cache[f'V_{li}']=V; cache[f'xl1_{li}']=xl1
        # attention B,T,H -> split heads
        Qh=Q.reshape(B,Tt,nh,hs).transpose(0,2,1,3) # B,nh,T,hs
        Kh=Qh*0; Kh=K.reshape(B,Tt,nh,hs).transpose(0,2,1,3)
        Vh=V.reshape(B,Tt,nh,hs).transpose(0,2,1,3)
        scores = (Qh @ Kh.transpose(0,1,3,2))/np.sqrt(hs) + mask[:Tt,:Tt] # B,nh,T,T
        # softmax
        smax=np.max(scores,axis=-1,keepdims=True); exp=np.exp(scores-smax)
        probs=exp/np.sum(exp,axis=-1,keepdims=True)
        cache[f'probs_{li}']=probs; cache[f'Qh_{li}']=Qh; cache[f'Kh_{li}']=Kh; cache[f'Vh_{li}']=Vh
        attn = (probs @ Vh).transpose(0,2,1,3).reshape(B,Tt,H)
        proj = attn @ l['Wo']; cache[f'attn_{li}']=attn
        x = x + proj
        # ln2 + mlp
        xl2,c2=ln_fwd(x,l['ln2_g'],l['ln2_b']); cache[f'ln2_{li}']=c2; cache[f'x1_{li}']=x
        fc1=xl2@l['W1']+l['b1']; fc1g=gelu(fc1)
        fc2=fc1g@l['W2']+l['b2']
        cache[f'xl2_{li}']=xl2; cache[f'fc1_{li}']=fc1; cache[f'fc1g_{li}']=fc1g
        x = x + fc2
    cache['x_last']=x
    xf,cf=ln_fwd(x,lnf_g,lnf_b); cache['lnf']=cf
    logits=xf@Why+by # B,T,vs
    return logits,cache

def sample(start="\n", n=300):
    ids=np.array([[stoi[c] for c in start]],dtype=np.int32)
    for _ in range(n):
        cur=ids[:,-T:]; logits,_=forward(cur)
        p=np.exp(logits[0,-1]-np.max(logits[0,-1])); p/=p.sum()
        nxt=np.random.choice(vs,p=p); ids=np.concatenate([ids,[[nxt]]],axis=1)
    return "".join(itos[i] for i in ids[0])

it=0; best=10
while True:
    it+=1
    idx=np.random.randint(0,len(data)-T-1,size=B)
    xb=np.zeros((B,T),dtype=np.int32); yb=np.zeros((B,T),dtype=np.int32)
    for b,i in enumerate(idx): xb[b]=data[i:i+T]; yb[b]=data[i+1:i+T+1]
    logits,cache=forward(xb)
    # loss
    m_log=np.max(logits,axis=-1,keepdims=True); e=np.exp(logits-m_log); probs=e/np.sum(e,axis=-1,keepdims=True)
    loss=-np.mean(np.log(probs[np.arange(B)[:,None],np.arange(T),yb]+1e-8))
    # backward
    dlogits=probs.copy(); dlogits[np.arange(B)[:,None],np.arange(T),yb]-=1; dlogits/=B*T
    #... gradients dict
    grads={}
    # final layer
    xf_cache=cache['lnf']; x_last=cache['x_last']
    # lnf backward
    dxf = dlogits @ Why.T # B,T,H
    dWhy = x_last.transpose(0,2,1) @ dlogits # actually need sum
    # simplify: accumulate
    dWhy = np.einsum('bth,btv->hv', cache['x_last']*0 + xf_cache[1], dlogits) # use xn? approximate with xf
    # for brevity: use exact but simple accum
    # We'll do full backward loop
    # --- quick manual backward for 2 layers ---
    # d for Why,by
    dWhy = np.einsum('bth,btv->hv', forward(xb)[0]*0+0, dlogits) # placeholder will be overwritten below
    # RECOMPUTE proper grads with simple version (no layernorm grad for final for speed)
    xf = ln_fwd(x_last,lnf_g,lnf_b)[0]
    dWhy = np.einsum('bth,btv->hv', xf, dlogits)
    dby = dlogits.sum(axis=(0,1))
    dx = dlogits @ Why.T # B,T,H
    dx,_dgf,_dbf = ln_bwd(dx, cache['lnf'])
    # backward layers
    dparams={}
    # we will collect grads in order of params list
    # for simplicity, zero grads and fill
    for li in reversed(range(n_layer)):
        l=layers[li]
        # mlp backward
        # x = x1 + fc2, so dx goes to both
        dfc2 = dx # (B,T,H)
        dW2 = np.einsum('bth,btv->hv', cache[f'fc1g_{li}'], dfc2) # 4H,H
        db2 = dfc2.sum(axis=(0,1))
        dfc1g = dfc2 @ l['W2'].T
        dfc1 = gelu_bwd(dfc1g, cache[f'fc1_{li}'])
        dW1 = np.einsum('bth,btv->hv', cache[f'xl2_{li}'], dfc1)
        db1 = dfc1.sum(axis=(0,1))
        dxl2 = dfc1 @ l['W1'].T
        dx1_ln, dg2, db2_ln = ln_bwd(dxl2, cache[f'ln2_{li}'])
        dx1 = dx + dx1_ln # residual from mlp
        # attn backward
        dproj = dx1
        dWo = np.einsum('bth,btv->hv', cache[f'attn_{li}'], dproj)
        dattn = dproj @ l['Wo'].T # B,T,H
        # heads
        dattn_h = dattn.reshape(B,T,nh,hs).transpose(0,2,1,3) # B,nh,T,hs
        probs=cache[f'probs_{li}']; Vh=cache[f'Vh_{li}']; Qh=cache[f'Qh_{li}']; Kh=cache[f'Kh_{li}']
        dVh = np.matmul(probs.transpose(0,1,3,2), dattn_h) # B,nh,T,hs (prob^T @ dattn)
        dprobs = np.matmul(dattn_h, Vh.transpose(0,1,3,2)) # B,nh,T,T
        # softmax backward
        sum_dp = np.sum(dprobs*probs,axis=-1,keepdims=True)
        dscores = probs*(dprobs - sum_dp)
        dQh = np.matmul(dscores, Kh)/np.sqrt(hs)
        dKh = np.matmul(dscores.transpose(0,1,3,2), Qh)/np.sqrt(hs)
        # merge heads
        dQ = dQh.transpose(0,2,1,3).reshape(B,T,H)
        dK = dKh.transpose(0,2,1,3).reshape(B,T,H)
        dV = dVh.transpose(0,2,1,3).reshape(B,T,H)
        xl1=cache[f'xl1_{li}']
        dWq = np.einsum('bth,btv->hv', xl1, dQ)
        dWk = np.einsum('bth,btv->hv', xl1, dK)
        dWv = np.einsum('bth,btv->hv', xl1, dV)
        dxl1 = dQ@l['Wq'].T + dK@l['Wk'].T + dV@l['Wv'].T
        dx0_ln, dg1, db1_ln = ln_bwd(dxl1, cache[f'ln1_{li}'])
        dx = dx1 + dx0_ln # residual from attn
        # store grads for this layer
        dparams[f'{li}_W2']=dW2; dparams[f'{li}_b2']=db2
        dparams[f'{li}_W1']=dW1; dparams[f'{li}_b1']=db1
        dparams[f'{li}_Wo']=dWo; dparams[f'{li}_Wq']=dWq; dparams[f'{li}_Wk']=dWk; dparams[f'{li}_Wv']=dWv
        dparams[f'{li}_ln2_g']=dg2; dparams[f'{li}_ln2_b']=db2_ln
        dparams[f'{li}_ln1_g']=dg1; dparams[f'{li}_ln1_b']=db1_ln
    # grads for embeddings
    dWte=np.zeros_like(Wte); dWpe=np.zeros_like(Wpe)
    # approximate: scatter add dx to Wte/Wpe
    for b in range(B):
        for t in range(T):
            dWte[xb[b,t]]+=dx[b,t]
            dWpe[t]+=dx[b,t]
    # adam update
    # build list in same order as params
    glist=[dWte,dWpe]
    for li in range(n_layer):
        glist+=[dparams[f'{li}_ln1_g'],dparams[f'{li}_ln1_b'],dparams[f'{li}_Wq'],dparams[f'{li}_Wk'],dparams[f'{li}_Wv'],dparams[f'{li}_Wo'],dparams[f'{li}_ln2_g'],dparams[f'{li}_ln2_b'],dparams[f'{li}_W1'],dparams[f'{li}_b1'],dparams[f'{li}_W2'],dparams[f'{li}_b2']]
    glist+=[_dgf,_dbf,dWhy,dby]
    for i,(p,g) in enumerate(zip(params,glist)):
        m[i]=0.9*m[i]+0.1*g; v[i]=0.999*v[i]+0.001*g*g
        p-=lr*(m[i]/(1-0.9**it))/(np.sqrt(v[i]/(1-0.999**it))+1e-8)
    if it%50==0:
        print(f"{it} loss {loss:.3f} best {best:.3f} FRONTIER {n_layer}L {H}H")
        if loss<best: best=loss; print(sample()[:400]); np.savez("bloom_frontier/W.npz",Wte=Wte,Wpe=Wpe,Why=Why,by=by)
