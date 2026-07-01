#!/usr/bin/env python3
# ============================================================================
# Eternal Fall — generatore di sfondi equirettangolari spettacolari (skybox 360).
# Due famiglie: "band" (banda galattica stile Via Lattea) e "neb" (campo di
# nebulosa colorato). Campi stellari densi, filamenti (ridged noise), dust lanes,
# seamless in orizzontale. Output: assets/skies/gen_NN.jpg (equirect 2:1).
#
# uso:  python3 tools/gen-skies.py [N] [--w 4096] [--out assets/skies] [--start 1]
#       python3 tools/gen-skies.py 4 --sample     # 4 campioni rapidi per revisione
# ============================================================================
import sys, os, math
import numpy as np
from PIL import Image

W = 4096
OUTDIR = "assets/skies"
N = 50
START = 1
SAMPLE = False
args = sys.argv[1:]
i = 0
while i < len(args):
    a = args[i]
    if a == "--w": W = int(args[i+1]); i += 2
    elif a == "--out": OUTDIR = args[i+1]; i += 2
    elif a == "--start": START = int(args[i+1]); i += 2
    elif a == "--sample": SAMPLE = True; i += 1
    elif a.isdigit(): N = int(a); i += 1
    else: i += 1
H = W // 2

# ---- periodic-in-x bilinear upsample (seamless longitudine) ----
def up(low, H, W):
    oh, ow = low.shape
    xs = np.arange(W) * (ow / W)
    x0 = np.floor(xs).astype(int); fx = xs - x0
    fx = (fx*fx*(3-2*fx))[None, :]
    x0 %= ow; x1 = (x0 + 1) % ow
    ys = np.arange(H) * (oh / H)
    y0 = np.floor(ys).astype(int); fy = ys - y0
    fy = (fy*fy*(3-2*fy))[:, None]
    y0 = np.clip(y0, 0, oh-1); y1 = np.clip(y0+1, 0, oh-1)
    a = low[np.ix_(y0, x0)]; b = low[np.ix_(y0, x1)]
    c = low[np.ix_(y1, x0)]; d = low[np.ix_(y1, x1)]
    top = a + (b - a) * fx
    bot = c + (d - c) * fx
    return top + (bot - top) * fy

def fbm(H, W, rng, octaves=6, base=6, gain=0.5):
    s = np.zeros((H, W), np.float32); amp = 1.0; tot = 0.0
    for k in range(octaves):
        ow = base * (2 ** k); oh = max(2, ow // 2)
        low = rng.random((oh, ow)).astype(np.float32)
        s += amp * up(low, H, W); tot += amp; amp *= gain
    return s / tot

def ridged(H, W, rng, octaves=6, base=8):
    return 1.0 - np.abs(2.0 * fbm(H, W, rng, octaves, base) - 1.0)

def lerp(a, b, t):  # a,b: rgb tuple 0..1 ; t: array
    return np.stack([a[c] + (b[c]-a[c]) * t for c in range(3)], -1)

def ramp(t, stops):  # stops: list of (pos, (r,g,b)); t array 0..1
    out = np.zeros(t.shape + (3,), np.float32)
    for j in range(len(stops)-1):
        p0, c0 = stops[j]; p1, c1 = stops[j+1]
        m = (t >= p0) & (t <= p1)
        tt = np.clip((t - p0) / max(1e-6, p1 - p0), 0, 1)
        out[m] = lerp(c0, c1, tt)[m]
    out[t < stops[0][0]] = stops[0][1]
    out[t > stops[-1][0]] = stops[-1][1]
    return out

# ---- palette (colori nebulosa: 2-3 stop) — ampio spettro, tutte vivide ----
def C(h): return tuple(int(h[i:i+2],16)/255 for i in (0,2,4))
PAL = [
    [(0,C('05060f')),(.5,C('123a8a')),(.8,C('4aa3ff')),(1,C('dff0ff'))],   # blu profondo
    [(0,C('070310')),(.5,C('5a1f8a')),(.82,C('b06aff')),(1,C('f0e2ff'))],  # viola/ametista
    [(0,C('0a0410')),(.5,C('8a1f6a')),(.82,C('ff6ac6')),(1,C('ffdcef'))],  # magenta/rosa
    [(0,C('03100c')),(.5,C('127a5a')),(.82,C('4affc0')),(1,C('daffe8'))],  # smeraldo/teal
    [(0,C('100a03')),(.5,C('8a5a12')),(.82,C('ffcf6a')),(1,C('fff2d0'))],  # oro/ambra
    [(0,C('120404')),(.5,C('8a2a12')),(.82,C('ff8a5a')),(1,C('ffe0cf'))],  # fornace calda
    [(0,C('05090f')),(.45,C('0f5a6e')),(.82,C('4ad6ff')),(1,C('dff6ff'))], # cyan glaciale
    [(0,C('080410')),(.45,C('3a2a8a')),(.7,C('6a6aff')),(.9,C('c0a8ff')),(1,C('f0e8ff'))], # indaco->viola
    [(0,C('0e0408')),(.45,C('7a1f3a')),(.8,C('ff5a7a')),(1,C('ffd0dc'))],  # cremisi/rosa
    [(0,C('040c0a')),(.45,C('1f6a4a')),(.75,C('6affb0')),(.92,C('b0ffd8')),(1,C('eafff2'))], # verde aurora
    [(0,C('0c0810')),(.4,C('5a2a7a')),(.7,C('c04aa0')),(.88,C('ff8ad0')),(1,C('ffdcf0'))],   # viola->magenta
    [(0,C('06080e')),(.4,C('1f4a8a')),(.7,C('2aa0d0')),(.88,C('6affd0')),(1,C('dffff0'))],   # blu->teal
    [(0,C('100c04')),(.4,C('8a6a1f')),(.72,C('ffd04a')),(.9,C('ff9a5a')),(1,C('fff0d8'))],   # oro->arancio
    [(0,C('0a0410')),(.4,C('6a1f8a')),(.68,C('b04aff')),(.86,C('ff6ac0')),(1,C('ffdcf4'))],  # ametista->rosa
    [(0,C('040810')),(.5,C('24408a')),(.85,C('88b8ff')),(1,C('eaf2ff'))],  # blu acciaio soft
]
# accenti "secondo colore" per drammaticità multi-hue
ACC = [C('4aa3ff'), C('b06aff'), C('ff6ac6'), C('4affc0'), C('ffcf6a'),
       C('ff8a5a'), C('4ad6ff'), C('6a6aff'), C('ff5a7a'), C('6affb0')]

def stars(H, W, rng, dens=1.0, band=None, bandBoost=3.0):
    """campo stellare: fitto e fioco + medie + poche brillanti con glow."""
    img = np.zeros((H, W, 3), np.float32)
    yy = (np.arange(H)[:, None] / H)
    # densità base modulata dalla banda (se presente) — più stelle sul piano galattico
    base_n = int(W * H * 0.0024 * dens)
    def scatter(n, bmin, bmax, cwarm=0.0, size1=True):
        xs = rng.integers(0, W, n); ys = rng.integers(0, H, n)
        if band is not None:
            keep = rng.random(n) < (0.25 + bandBoost * band[ys, xs])
            xs, ys = xs[keep], ys[keep]
        b = rng.uniform(bmin, bmax, xs.shape[0]).astype(np.float32)
        col = np.stack([b*(1+cwarm*0.3), b, b*(1-cwarm*0.2)], -1)
        np.add.at(img, (ys, xs), col)
        return xs, ys
    scatter(base_n, 0.05, 0.30)                 # fioche
    scatter(base_n // 4, 0.30, 0.7, cwarm=rng.uniform(-.3,.5))   # medie
    # brillanti con glow
    bx, by = scatter(max(40, base_n // 120), 0.8, 1.3, cwarm=rng.uniform(-.2,.6))
    g = 5
    ky, kx = np.mgrid[-g:g+1, -g:g+1]
    ker = np.exp(-(kx*kx+ky*ky)/6.0).astype(np.float32); ker /= ker.max()
    for x, y in zip(bx[:200], by[:200]):
        y0, y1 = max(0, y-g), min(H, y+g+1); x0, x1 = x-g, x+g+1
        kk = ker[(y0-(y-g)):(y1-(y-g))]
        cols = (np.arange(x0, x1) % W)
        tint = np.array([1.0, 0.95, 0.85], np.float32) if rng.random()<0.5 else np.array([0.85,0.92,1.0],np.float32)
        img[y0:y1][:, cols] += (kk[:, :, None] * tint * rng.uniform(0.5, 1.1))
    return img

def make(kind, seed):
    rng = np.random.default_rng(seed)
    pal = PAL[rng.integers(0, len(PAL))]
    acc = ACC[rng.integers(0, len(ACC))]
    img = np.zeros((H, W, 3), np.float32)
    lat = (np.arange(H)[:, None] / (H-1)) * 2 - 1   # -1..1 (polo..polo)
    lon = (np.arange(W)[None, :] / W) * 2 * math.pi

    band = None
    if kind == "band":
        # banda galattica: grande cerchio ondulato+inclinato
        tilt = rng.uniform(0.08, 0.28) * (1 if rng.random()<.5 else -1)
        wave = rng.uniform(0.05, 0.16)
        phase = rng.uniform(0, 6.28)
        center = tilt*np.sin(lon+phase) + wave*np.sin(2*lon+phase*1.7)
        width = rng.uniform(0.14, 0.26)
        d = (lat - center) / width
        band = np.exp(-(d*d)).astype(np.float32)          # 0..1 luminosità banda
        halo = np.exp(-(d*d)*0.28).astype(np.float32)     # alone più largo e tenue
        # nubi/star-clouds lungo la banda + filamenti
        clouds = fbm(H, W, rng, 6, 5)
        neb = np.clip((band*1.2 + halo*0.28) * (0.55+0.8*clouds) - 0.05, 0, 1) ** 1.12
        col = ramp(np.clip(neb*0.82, 0, 0.9), pal)         # cap: non raggiunge il bianco puro (resta colorato)
        # dust lanes scure che tagliano la banda
        dust = ridged(H, W, rng, 5, 10)
        dark = np.clip(1.0 - band*0.95*np.clip(dust-0.42,0,1)*2.6, 0.12, 1.0)
        img += col * neb[..., None] * 1.05
        img += (col*0.5 + np.array(acc)*0.6) * np.clip(neb-0.68,0,1)[..., None] * 0.7   # nuclei star-cloud (tenui)
        img *= dark[..., None]
        img += stars(H, W, rng, dens=1.3, band=band, bandBoost=3.5)
    else:
        # campo di nebulosa: due masse di colore + filamenti + vuoti
        a = fbm(H, W, rng, 7, 4)
        b = fbm(H, W, rng, 6, 6)
        fil = ridged(H, W, rng, 6, 9)
        neb = np.clip(a*0.9 + fil*0.6 - 0.34, 0, 1) ** 1.18
        neb *= (0.6 + 0.95*b)                              # disomogeneità (buchi/densità)
        col1 = ramp(np.clip(a*1.0, 0, 0.92), pal)          # cap: resta colorato, non bianco
        mask2 = np.clip((b-0.5)*2.2, 0, 1)
        col = col1*(1-mask2[...,None]) + (col1*0.45 + np.array(acc)*0.9)*mask2[...,None]
        img += col * neb[..., None] * 1.55
        img += col * np.clip(neb-0.6,0,1)[..., None] * 0.8    # nuclei brillanti (tenui, restano colorati)
        img += stars(H, W, rng, dens=1.15)

    # attenua i poli (l'equirect pizzica: sfuma verso zenith/nadir)
    polefade = (0.35 + 0.65*np.clip(1 - np.abs(lat)**3, 0, 1)).astype(np.float32)
    img *= polefade[..., None]
    # tono: leggero lift nero-spazio + soft clip morbido + saturazione
    img = img + np.array([0.004, 0.006, 0.012], np.float32)
    img = img / (1.0 + 0.5*img)                            # shoulder (evita bruciature ma tiene il punch)
    g = img.mean(-1, keepdims=True)
    img = g + (img - g) * 1.34                             # boost saturazione (colori vividi)
    img = np.clip(img * 1.16, 0, 1) ** (1/1.04)
    return (img*255 + 0.5).astype(np.uint8)

os.makedirs(OUTDIR, exist_ok=True)
if SAMPLE:
    recipes = [("band", 101), ("band", 217), ("neb", 330), ("neb", 442)]
    for k, (kind, seed) in enumerate(recipes, 1):
        arr = make(kind, seed)
        Image.fromarray(arr, "RGB").save(f"{OUTDIR}/sample_{k}_{kind}.jpg", quality=90)
        print("sample", k, kind, seed)
else:
    for n in range(N):
        idx = START + n
        kind = "band" if (n % 5 < 2) else "neb"   # ~40% bande stile Via Lattea, ~60% nebulose
        seed = 1000 + idx*7
        arr = make(kind, seed)
        Image.fromarray(arr, "RGB").save(f"{OUTDIR}/gen_{idx:02d}.jpg", quality=90)
        if idx % 5 == 0 or idx == START: print("gen_%02d (%s)" % (idx, kind))
print("done")
