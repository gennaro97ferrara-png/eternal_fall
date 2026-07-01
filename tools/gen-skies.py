#!/usr/bin/env python3
# ============================================================================
# Eternal Fall — generatore di cieli stellati equirettangolari REALISTICI
# (stile Via Lattea: cielo scuro FITTO di stelle + banda galattica tenue +
# dust lanes + bulge; colori sobri, non "nebulosa dipinta"). Output equirect 2:1.
#
# uso:  python3 tools/gen-skies.py 50 --w 4096 --out assets/skies
#       python3 tools/gen-skies.py --sample --w 3072 --out /tmp/samples
# ============================================================================
import sys, os, math
import numpy as np
from PIL import Image

W = 4096; OUTDIR = "assets/skies"; N = 50; START = 1; SAMPLE = False
args = sys.argv[1:]; i = 0
while i < len(args):
    a = args[i]
    if a == "--w": W = int(args[i+1]); i += 2
    elif a == "--out": OUTDIR = args[i+1]; i += 2
    elif a == "--start": START = int(args[i+1]); i += 2
    elif a == "--sample": SAMPLE = True; i += 1
    elif a.isdigit(): N = int(a); i += 1
    else: i += 1
H = W // 2

def up(low, H, W):  # upsample periodico in x (seamless in longitudine)
    oh, ow = low.shape
    xs = np.arange(W) * (ow / W); x0 = np.floor(xs).astype(int); fx = xs - x0
    fx = (fx*fx*(3-2*fx))[None, :]; x0 %= ow; x1 = (x0 + 1) % ow
    ys = np.arange(H) * (oh / H); y0 = np.floor(ys).astype(int); fy = ys - y0
    fy = (fy*fy*(3-2*fy))[:, None]; y0 = np.clip(y0, 0, oh-1); y1 = np.clip(y0+1, 0, oh-1)
    a = low[np.ix_(y0, x0)]; b = low[np.ix_(y0, x1)]; c = low[np.ix_(y1, x0)]; d = low[np.ix_(y1, x1)]
    return (a+(b-a)*fx) + ((c+(d-c)*fx)-(a+(b-a)*fx))*fy

def fbm(H, W, rng, octaves=6, base=6, gain=0.5):
    s = np.zeros((H, W), np.float32); amp = 1.0; tot = 0.0
    for k in range(octaves):
        ow = base*(2**k); oh = max(2, ow//2)
        s += amp*up(rng.random((oh, ow)).astype(np.float32), H, W); tot += amp; amp *= gain
    return s/tot

def ridged(H, W, rng, octaves=6, base=8):
    return 1.0 - np.abs(2.0*fbm(H, W, rng, octaves, base) - 1.0)

# temperature stellari realistiche (blu-bianco -> bianco -> giallo -> arancio), pesate verso il bianco
STAR_TINTS = np.array([
    [0.72,0.80,1.00],[0.85,0.90,1.00],[1.0,1.0,1.0],[1.0,1.0,1.0],[1.0,1.0,1.0],
    [1.00,0.97,0.88],[1.00,0.90,0.75],[1.00,0.82,0.62]], np.float32)

def add_stars(img, rng, n, bmin, bmax, gamma, weight=None, tintstr=0.6):
    """n stelle 1px, luminosità power-law; densità pesata da weight (0..1)."""
    x = rng.integers(0, W, n); y = rng.integers(0, H, n)
    if weight is not None:
        p = 0.30 + 0.95*weight[y, x]
        keep = rng.random(n) < p
        x, y = x[keep], y[keep]
    m = x.shape[0]
    b = (bmin + (bmax-bmin)*(rng.random(m)**gamma)).astype(np.float32)
    t = STAR_TINTS[rng.integers(0, len(STAR_TINTS), m)]
    t = 1.0 + (t-1.0)*tintstr
    col = (b[:, None]*t).astype(np.float32)
    np.add.at(img, (y, x), col)

def add_bright(img, rng, n, weight=None):
    """stelle brillanti PICCOLE e nitide, glow minimo (niente blob)."""
    g = 2; ky, kx = np.mgrid[-g:g+1, -g:g+1]
    ker = np.exp(-(kx*kx+ky*ky)/1.6).astype(np.float32); ker /= ker.max()
    for _ in range(n):
        x = int(rng.integers(0, W)); y = int(rng.integers(g, H-g))
        if weight is not None and rng.random() > (0.22 + 0.9*float(weight[y, x])): continue
        br = float(rng.uniform(0.7, 1.35)); t = STAR_TINTS[rng.integers(0, len(STAR_TINTS))]
        cols = (np.arange(x-g, x+g+1) % W)
        img[y-g:y+g+1][:, cols] += ker[:, :, None]*t*br
        if br > 1.15:  # spike sottile solo sulle pochissime più brillanti
            sp = 5; xr = (np.arange(x-sp, x+sp+1) % W)
            img[y][xr] += ((1-np.abs(np.arange(-sp, sp+1))/sp)[:, None]*0.35*br*t)

# tinta d'insieme del cielo — AMPIA varietà di colore
COLORS = np.array([
    [1.00, 0.93, 0.82],   # neutro caldo (come il nightscape di riferimento)
    [1.00, 0.83, 0.58],   # dorato/ambra
    [0.70, 0.82, 1.00],   # blu
    [0.72, 1.00, 0.94],   # teal / verde-acqua
    [0.88, 0.80, 1.00],   # viola
    [1.00, 0.80, 0.86],   # rosa
    [0.84, 1.00, 0.86],   # verde tenue
    [0.93, 0.96, 1.00],   # bianco-azzurro
    [1.00, 0.90, 0.95],   # rosa-cipria
], np.float32)

def make(kind, seed):
    rng = np.random.default_rng(seed)
    img = np.zeros((H, W, 3), np.float32)
    lat = (np.arange(H)[:, None]/(H-1))*2 - 1
    lon = (np.arange(W)[None, :]/W)*2*math.pi
    basecol = COLORS[rng.integers(0, len(COLORS))]

    # ---- banda Via Lattea SOTTILE e delicata (flusso di stelle, non nuvola) ----
    tilt = rng.uniform(0.05, 0.28)*(1 if rng.random() < .5 else -1)
    wave = rng.uniform(0.03, 0.11); phase = rng.uniform(0, 6.28); wob = rng.uniform(0.02, 0.06)
    center = tilt*np.sin(lon+phase) + wave*np.sin(2*lon+phase*1.4) + wob*np.sin(3*lon+phase*0.7)
    width = rng.uniform(0.13, 0.24)                      # SOTTILE
    d = (lat - center)/width
    band = np.exp(-(d*d)).astype(np.float32)
    weight = np.clip(band + 0.14, 0, 1)                  # stelle OVUNQUE, più dense sul piano

    # velo tenue (haze) — NIENTE grandi nuvole: fine + dust sottile
    fine = fbm(H, W, rng, 7, 9)
    dust = ridged(H, W, rng, 6, 9)
    lanes = np.clip(dust-0.58, 0, 1)*2.2
    haze = band*(0.4 + 0.55*fine)*np.clip(1.0 - lanes, 0.25, 1.0)
    img += haze[..., None]*basecol*0.28                  # velo della banda (sottile ma percepibile)

    # ---- STELLE: protagoniste — TANTISSIME, piccole, nitide e BEN VISIBILI ----
    px = W*H
    add_stars(img, rng, int(px*0.20), 0.20, 0.62, 1.9, weight, 0.7)   # miriade nitida ben visibile
    add_stars(img, rng, int(px*0.075), 0.32, 0.95, 1.5, weight, 0.8)  # deboli-medie
    add_stars(img, rng, int(px*0.020), 0.55, 1.25, 1.3, weight, 0.9)  # medie luminose
    add_bright(img, rng, int(200 + px*0.00005), weight)               # brillanti piccole

    # emissione tenue occasionale (varietà di colore, sottile)
    if rng.random() < 0.5:
        em = np.clip(fbm(H, W, rng, 6, 6) - 0.62, 0, 1)*band
        emc = np.array([[0.50,0.10,0.14],[0.12,0.16,0.42],[0.14,0.34,0.22],[0.34,0.14,0.34]], np.float32)
        img += em[..., None]*emc[rng.integers(0, len(emc))]*0.5

    # tinta d'insieme verso basecol (varietà di colore coerente)
    img = img*(0.55 + 0.45*basecol)                      # spinge il colore del cielo verso la tinta scelta

    # attenua poli + tono: cielo SCURO e delicato, stelle che spiccano
    polefade = (0.5 + 0.5*np.clip(1-np.abs(lat)**3, 0, 1)).astype(np.float32)
    img *= polefade[..., None]
    img += np.array([0.006, 0.008, 0.013], np.float32)
    img = img/(1.0+0.28*img)
    img = np.clip(img*1.75, 0, 1)**(1/1.05)
    return (img*255+0.5).astype(np.uint8)

os.makedirs(OUTDIR, exist_ok=True)
KINDS = ["band", "bulge", "band", "bulge", "band"]   # tutte con banda Via Lattea (varia orientamento/bulge)
if SAMPLE:
    for k, (kind, seed) in enumerate([("band",11),("bulge",22),("band",33),("sparse",44)], 1):
        Image.fromarray(make(kind, seed), "RGB").save(f"{OUTDIR}/sample_{k}_{kind}.jpg", quality=90)
        print("sample", k, kind)
else:
    for n in range(N):
        idx = START+n; kind = KINDS[n % len(KINDS)]; seed = 2000+idx*13
        Image.fromarray(make(kind, seed), "RGB").save(f"{OUTDIR}/gen_{idx:02d}.jpg", quality=90)
        if idx % 10 == 0 or idx == START: print("gen_%02d (%s)" % (idx, kind))
print("done")
