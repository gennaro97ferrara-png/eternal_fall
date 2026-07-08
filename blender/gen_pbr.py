#!/usr/bin/env python3
"""
Batch 4 — bake PBR in spazio-immagine (numpy/PIL, no GPU, secondi).
Genera per OGNI texture pianeta di PMETA (esclusa la stella): <f>_n.png (normal tangent-space)
+ <f>_r.png (roughness). Nome = file sorgente → il wiring in index.html è diretto (meta.f -> <f>_n).
Rilievo = luminanza albedo (macro) + micro-dettaglio FBM multi-ottava (alta freq che il bump 3-tap non dà).
Forza del normale (nstr) proporzionale al bump PMETA: rocciosi forte, gassosi/ghiacciati lieve.
Roughness per tipo: oceano lucido/terra ruvida (earth) · gas quasi-uniforme · roccia ruvida.

Uso:  python3 blender/gen_pbr.py                 (tutti)
      python3 blender/gen_pbr.py 4k_mars ...     (solo alcuni, per nome file)
NB: cartella blender/ ma NON usa bpy — bake immagine puro (affidabile headless). Il bake geometrico
    Blender (displacement->normal+AO con ombre vere) è l'escalation successiva.
"""
import sys, os
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
OUT = os.path.join(ASSETS, "pbr")
os.makedirs(OUT, exist_ok=True)

# file sorgente (senza .jpg) -> parametri.  nH = altezza normal (equirect 2:1 -> larghezza 2x).
#   nstr = forza rilievo (∝ bump PMETA) · detail = quota micro-dettaglio procedurale · rough = modo roughness
BODIES = {
    "4k_earth_daymap":  dict(nH=1024, detail=0.26, nstr=1.6, seed=11, rough="earth"),
    "4k_jupiter":       dict(nH=1024, detail=0.14, nstr=0.7, seed=23, rough="gas"),
    "4k_saturn":        dict(nH=1024, detail=0.14, nstr=0.7, seed=29, rough="gas"),
    "2k_neptune":       dict(nH=1024, detail=0.12, nstr=0.6, seed=31, rough="gas"),
    "2k_uranus":        dict(nH=1024, detail=0.10, nstr=0.5, seed=41, rough="gas"),
    "4k_mars":          dict(nH=1024, detail=0.42, nstr=2.4, seed=37, rough="rock"),
    "4k_mercury":       dict(nH=1024, detail=0.48, nstr=3.0, seed=43, rough="rock"),
    "2k_mercury":       dict(nH=1024, detail=0.48, nstr=3.0, seed=47, rough="rock"),
    "4k_venus_surface": dict(nH=1024, detail=0.30, nstr=1.4, seed=53, rough="rock"),
    "4k_moon":          dict(nH=1024, detail=0.46, nstr=3.2, seed=59, rough="rock"),
}

def load_luma_alb(path, nH):
    im = Image.open(path).convert("RGB").resize((nH * 2, nH), Image.LANCZOS)  # equirect 2:1
    a = np.asarray(im, dtype=np.float32) / 255.0
    lum = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    return lum, a

def fbm(H, W, octaves, seed, base=6):
    out = np.zeros((H, W), dtype=np.float32); amp = 1.0; norm = 0.0
    rng = np.random.default_rng(seed)
    for o in range(octaves):
        cells = base * (2 ** o)
        g = (rng.random((cells, cells * 2)) * 255).astype(np.uint8)
        up = np.asarray(Image.fromarray(g).resize((W, H), Image.BICUBIC), dtype=np.float32) / 255.0
        out += amp * up; norm += amp; amp *= 0.5
    return out / max(norm, 1e-6)

def to_u8(a):
    return np.clip(a * 255.0 + 0.5, 0, 255).astype(np.uint8)

def make_normal(height, strength):
    gx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5   # U wrap (longitudine)
    gy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * 0.5   # V
    nx = -gx * strength; ny = -gy * strength; nz = np.ones_like(height)
    l = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-8
    return to_u8(np.stack([nx / l * 0.5 + 0.5, ny / l * 0.5 + 0.5, nz / l * 0.5 + 0.5], axis=-1))

def make_roughness(alb, mode):
    r, g, b = alb[..., 0], alb[..., 1], alb[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    if mode == "earth":
        land = np.clip((r - b) / 0.13, 0, 1)
        rough = 0.26 + 0.60 * land                    # oceano lucido → terra ruvida
    elif mode == "gas":
        rough = 0.55 + 0.10 * (lum - 0.5)             # gas quasi uniforme
    else:  # rock
        rough = 0.80 + 0.15 * (1.0 - lum)             # roccia ruvida (mari scuri un filo più ruvidi)
    return np.clip(rough, 0.05, 0.98)

def process(fbase, cfg):
    src = os.path.join(ASSETS, fbase + ".jpg")
    if not os.path.exists(src):
        print(f"  SKIP {fbase}: manca {fbase}.jpg"); return
    nH = cfg["nH"]
    lum, alb = load_luma_alb(src, nH)
    H, W = alb.shape[0], alb.shape[1]
    detail = fbm(H, W, octaves=5, seed=cfg["seed"])
    height = (1.0 - cfg["detail"]) * lum + cfg["detail"] * detail
    Image.fromarray(make_normal(height, strength=cfg["nstr"])).save(os.path.join(OUT, f"{fbase}_n.png"))
    # roughness a metà risoluzione (basta): 1024x512
    rgh = make_roughness(alb, cfg["rough"])
    rimg = Image.fromarray(to_u8(rgh)).resize((max(2, W // 2), max(2, H // 2)), Image.LANCZOS)
    rimg.save(os.path.join(OUT, f"{fbase}_r.png"))
    print(f"  {fbase}: _n {W}x{H} (nstr {cfg['nstr']}) + _r {W//2}x{H//2} [{cfg['rough']}]")

def main():
    # rimuovi i nomi vecchi (earth/jupiter/moon) se presenti da un run precedente
    for old in ("earth", "jupiter", "moon"):
        for k in ("n", "r"):
            p = os.path.join(OUT, f"{old}_{k}.png")
            if os.path.exists(p):
                os.remove(p)
    which = sys.argv[1:] or list(BODIES.keys())
    print("PBR bake (image-space) →", OUT)
    for name in which:
        if name in BODIES:
            process(name, BODIES[name])
        else:
            print(f"  ? sconosciuto: {name} (disponibili: {', '.join(BODIES)})")

if __name__ == "__main__":
    main()
