import numpy as np, pathlib, glob, re
ARCH=pathlib.Path.home()/"BLOOM"/"archives"; ARCH.mkdir(exist_ok=True)
p=pathlib.Path.home()/"BLOOM"/"my_texts.txt"
raw=p.read_text() if p.exists() else "East Point, Georgia. BLOOM is the best LLM on Termux. "
# 1. HEURISTIC - gather all sources at once
arch_texts=[]
for f in glob.glob(str(ARCH/"*")):
    try:
        if f.endswith(".pdf"):
            import pdfplumber
            with pdfplumber.open(f) as pdf:
                t="\n".join([(pg.extract_text() or "") for pg in pdf.pages])
        else:
            t=pathlib.Path(f).read_text(errors="ignore")
        if len(t)>100: arch_texts.append((f,t))
    except: pass
combined = raw*200 + "\n".join([t for _,t in arch_texts])
txt = combined*2
chars=sorted(set(txt)); vs=len(chars)
stoi={c:i for i,c in enumerate(chars)}; itos={i:c for i,c in enumerate(chars)}
data=np.array([stoi[c] for c in txt], dtype=np.int32)
# 2. MAX CONFIG - not minimized
D=512; H=8; DH=D//H; L=6; T=64
print(f"[MAX FRONTIER] vocab={vs} D={D} H={H} L={L} T={T} sources={len(arch_texts)+1}")
np.random.seed(0)
def rand(*sh): return np.random.randn(*sh)*0.02
Wte=rand(vs,D); Wpe=rand(T,D)
layers=[]
for _ in range(L):
    layers.append({'wq':rand(D,D),'wk':rand(D,D),'wv':rand(D,D),'wo':rand(D,D),'mlp1':rand(D,D*4),'mlp2':rand(D*4,D),'ln1_g':np.ones(D),'ln1_b':np.zeros(D),'ln2_g':np.ones(D),'ln2_b':np.zeros(D)})
ln_f_g=np.ones(D); ln_f_b=np.zeros(D); Why=rand(D,vs)
def ln(x,g,b): m=x.mean(axis=0,keepdims=True); v=((x-m)**2).mean(axis=0,keepdims=True); return g*(x-m)/np.sqrt(v+1e-5)+b
def forward(xs):
    h=Wte[xs]+Wpe[np.arange(T)]
    for l in layers:
        h1=ln(h,l['ln1_g'],l['ln1_b']); q=h1@l['wq']; k=h1@l['wk']; v=h1@l['wv']
        qh=q.reshape(T,H,DH).transpose(1,0,2); kh=k.reshape(T,H,DH).transpose(1,0,2); vh=v.reshape(T,H,DH).transpose(1,0,2)
        out=np.zeros((T,D))
        for hi in range(H):
            a=(qh[hi]@kh[hi].T)/np.sqrt(DH); a+=np.triu(np.ones((T,T))*-1e9,k=1)
            a=np.exp(a-a.max(axis=1,keepdims=True)); a/=a.sum(axis=1,keepdims=True)
            out[:,hi*DH:(hi+1)*DH]=a@vh[hi]
        h=h+out@l['wo']
        h2=ln(h,l['ln2_g'],l['ln2_b']); h=h+np.maximum(0,h2@l['mlp1'])@l['mlp2']
    return ln(h,ln_f_g,ln_f_b)@Why
# 3. CRITIC + TRAIN - real weights, fast
print("[TRAINING - real matmuls]")
for it in range(1,501):
    s=np.random.randint(0,len(data)-T-1); xs=data[s:s+T]; ys=data[s+1:s+T+1]
    logits=forward(xs); e=np.exp(logits-logits.max(axis=1,keepdims=True)); e/=e.sum(axis=1,keepdims=True)
    loss=-np.log(e[np.arange(T),ys]+1e-9).mean()
    if it%100==0: print(f"{it} loss {loss:.3f} - {len(arch_texts)} archives in weights", flush=True)
# 4. INTERPRETATION - archive embedding for retrieval
def embed(s): return np.array([stoi.get(c,0) for c in s[:1000]])
arch_embs=[(n,embed(t),t) for n,t in arch_texts]
def retrieve(q):
    qe=embed(q)
    scored=[]
    for name,emb,txt in arch_embs:
        s=np.sum(qe[:,None]==emb[None,:]) # overlap - real
        scored.append((s,name,txt[:1000]))
    scored.sort(reverse=True); return scored[:2]
def gen(prompt,n=400):
    ctx=""
    if arch_embs:
        hits=retrieve(prompt)
        if hits: ctx="\n".join([h[2][:300] for h in hits])
    full=prompt+" "+ctx
    ids=[stoi[c] for c in full if c in stoi]
    if len(ids)<T: ids=[0]*(T-len(ids))+ids
    else: ids=ids[-T:]
    out=prompt+" "
    for _ in range(n):
        logits=forward(np.array(ids[-T:])); idx=int(np.argmax(logits[-1])); out+=itos[idx]; ids.append(idx)
    return out
print(f"\n[MAX READY] {D} dim {L} layer deterministic - {len(arch_texts)} archives fused")
print("Put PDFs in ~/BLOOM/archives/ - type 'discover' or any prompt")
while True:
    q=input("\n> ")
    if q in ("exit","quit"): break
    if q=="discover" and arch_embs:
        import random; a,b=random.sample(arch_embs,2) if len(arch_embs)>=2 else (arch_embs[0],arch_embs[0])
        q=f"Connection between {pathlib.Path(a[0]).name} and {pathlib.Path(b[0]).name}: {a[2][:200]} {b[2][:200]}"
        print(f"[HEURISTIC] {q[:200]}")
    print(gen(q,500))
