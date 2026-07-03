#!/usr/bin/env python3
# ============================================================================
# Eternal Fall — base sky IBRIDA 16k: il pano ESO/Brunier (milkyway_8k.jpg,
# 6000×3000: è LUI il look v13 che piace — colori, polveri, stelle brillanti)
# upscalato a 16384, PIÙ il solo DETTAGLIO ad alta frequenza del NASA SVS
# Deep Star Maps 16k (le migliaia di stelle sottili sub-px che il Brunier non
# risolve). Entrambi equirettangolari GALATTICI con il GC al centro (SPEC:
# "SVS e Brunier = stesso cielo reale, il crossfade combacia").
#
#   out = clip( brunier_up + k · min( relu(nasa − blur(nasa)), cap ) )
#
# relu = solo luce AGGIUNTA (mai scurire la banda); cap = le stelle luminose
# NASA non raddoppiano quelle già presenti nel Brunier (niente "coppie
# fantasma" se le proiezioni divergono localmente di qualche px).
# Prima del blend: verifica di allineamento con cross-correlazione FFT sul
# 25% centrale (downscale 2048) — se il picco non è a (0,0)±TOL si ferma.
#
# uso:  python3 tools/blend-base.py assets/milkyway_8k.jpg assets/milkyway_16k_nasa.jpg \
#           assets/milkyway_16k.jpg [--k 1.0] [--cap 60] [--sigma 2.2] [--tol 12]
# ============================================================================
import argparse
import numpy as np
from PIL import Image, ImageFilter

Image.MAX_IMAGE_PIXELS = None

p = argparse.ArgumentParser(description="base sky ibrida: Brunier (look) + dettaglio fine NASA 16k")
p.add_argument("brunier")
p.add_argument("nasa")
p.add_argument("out")
p.add_argument("--k", type=float, default=1.0, help="peso del dettaglio NASA aggiunto")
p.add_argument("--cap", type=int, default=60, help="tetto (0-255) del dettaglio per stella: niente doppioni delle stelle luminose")
p.add_argument("--sigma", type=float, default=2.2, help="raggio del passa-alto (px a 16k ≈ scala PSF stellare)")
p.add_argument("--tol", type=int, default=12, help="disallineamento RESIDUO massimo tollerato in px full-res")
p.add_argument("--maxshift", type=int, default=400, help="auto-shift massimo applicabile (oltre = orientamento/parità sospetti, stop)")
a = p.parse_args()

nasa = Image.open(a.nasa).convert("RGB")
W, H = nasa.size
bru = Image.open(a.brunier).convert("RGB").resize((W, H), Image.LANCZOS)

# --- allineamento: phase-correlation sulla luminanza del 25% centrale ---
def stima_shift(imA, imB):
    def lum_small(im):
        s = im.resize((2048, 1024), Image.BILINEAR).convert("L")
        arr = np.asarray(s, np.float32)
        return arr[256:768, 512:1536]   # 25% centrale: la banda con la struttura
    A, B = lum_small(imA), lum_small(imB)
    A = A - A.mean(); B = B - B.mean()
    R = np.fft.fft2(A) * np.conj(np.fft.fft2(B))
    R /= np.maximum(np.abs(R), 1e-9)
    pk = np.fft.ifft2(R).real
    iy, ix = np.unravel_index(np.argmax(pk), pk.shape)
    dy = iy if iy <= pk.shape[0] // 2 else iy - pk.shape[0]
    dx = ix if ix <= pk.shape[1] // 2 else ix - pk.shape[1]
    return dx * W // 2048, dy * H // 1024

dx_full, dy_full = stima_shift(bru, nasa)
print(f"allineamento: shift stimato ({dx_full},{dy_full}) px full-res")
if abs(dx_full) > a.maxshift or abs(dy_full) > a.maxshift:
    raise SystemExit(f"shift oltre --maxshift {a.maxshift}px: orientamento/parità sospetti, blend annullato")
if abs(dx_full) > a.tol or abs(dy_full) > a.tol:
    # AUTO-SHIFT: il Brunier definisce la convenzione GC dell'app (sky-gc.json) → si sposta la NASA.
    # roll orizzontale = wrap naturale dell'equirect (360°); verticale: i poli sono neri, innocuo.
    print(f"  auto-shift della NASA di ({dx_full},{dy_full})…")
    nasa = Image.fromarray(np.roll(np.asarray(nasa), (dy_full, dx_full), axis=(0, 1)))
    rx, ry = stima_shift(bru, nasa)
    print(f"  residuo dopo shift: ({rx},{ry}) px")
    if abs(rx) > a.tol or abs(ry) > a.tol:
        raise SystemExit(f"residuo oltre {a.tol}px: blend annullato")

# --- blend a strisce (RAM: mai più di ~2GB) ---
nasa_blur = nasa.filter(ImageFilter.GaussianBlur(a.sigma))
out = Image.new("RGB", (W, H))
STR = 1024
na, nb, br = (np.asarray(x, np.int16) for x in (nasa, nasa_blur, bru))
for y0 in range(0, H, STR):
    y1 = min(H, y0 + STR)
    det = np.clip(na[y0:y1].astype(np.int16) - nb[y0:y1], 0, a.cap)
    o = np.clip(br[y0:y1] + (det * a.k).astype(np.int16), 0, 255).astype(np.uint8)
    out.paste(Image.fromarray(o), (0, y0))
out.save(a.out, quality=97, subsampling=0)
print(f"ok {a.out} {W}x{H} (k={a.k}, cap={a.cap}, sigma={a.sigma})")
