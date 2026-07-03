#!/usr/bin/env python3
# ============================================================================
# Eternal Fall — downsample 2× del NASA SVS Deep Star Maps 32k EXR → base sky
# 16384×8192 (JPEG/PNG) per tools/vary-skies.py. Lettura A BLOCCHI di scanline
# (mai tutta l'immagine in RAM: il piano float32 pieno sarebbe ~6.4GB), media
# 2×2 in LUCE LINEARE (fisicamente corretta: le stelle-punto non si spengono),
# poi gamma 2.2 — stessa convenzione di tools/zoom/exr-crop.py (L1 della
# catena zoom viene dallo stesso file → il crossfade sfera→L1 combacia).
#
# uso:  python3 tools/exr-downsample.py assets/zoom/_src/starmap_2020_32k_gal.exr \
#           assets/milkyway_16k.jpg [--gamma 2.2] [--gain 1.0] [--block 1024]
# ============================================================================
import argparse
import numpy as np
import OpenEXR, Imath
from PIL import Image

Image.MAX_IMAGE_PIXELS = None   # 16384×8192 supera il limite anti-decompression-bomb di PIL

p = argparse.ArgumentParser(description="downsample 2x a blocchi di un EXR scanline gigante")
p.add_argument("exr")
p.add_argument("out")
p.add_argument("--gamma", type=float, default=2.2, help="lineare -> v^(1/gamma), come exr-crop.py")
p.add_argument("--gain", type=float, default=1.0, help="moltiplicatore pre-gamma")
p.add_argument("--block", type=int, default=1024, help="scanline per blocco (RAM ~0.8GB a 1024)")
a = p.parse_args()

f = OpenEXR.InputFile(a.exr)
dw = f.header()["dataWindow"]
W = dw.max.x - dw.min.x + 1
H = dw.max.y - dw.min.y + 1
half = Imath.PixelType(Imath.PixelType.HALF)
ow, oh = W // 2, H // 2
out = np.zeros((oh, ow, 3), np.uint8)
blk = max(2, a.block - (a.block % 2))   # blocchi PARI: la media 2×2 non deve mai cavalcare due blocchi

for y0 in range(0, H - 1, blk):
    y1 = min(H, y0 + blk)
    rows = (y1 - y0) // 2 * 2
    if rows <= 0:
        break
    canali = []
    for c in "RGB":
        raw = f.channel(c, half, scanLine1=y0, scanLine2=y0 + rows - 1)
        canali.append(np.frombuffer(raw, dtype=np.float16).reshape(rows, W).astype(np.float32))
    rgb = np.stack(canali, axis=-1)
    ds = (rgb[0::2, 0::2] + rgb[0::2, 1::2] + rgb[1::2, 0::2] + rgb[1::2, 1::2]) * 0.25
    ds = np.clip(ds * a.gain, 0.0, 1.0) ** (1.0 / a.gamma)
    out[y0 // 2:y0 // 2 + ds.shape[0]] = (ds * 255.0 + 0.5).astype(np.uint8)
    print(f"  righe {y1}/{H}", flush=True)

im = Image.fromarray(out, "RGB")
if a.out.lower().endswith((".jpg", ".jpeg")):
    im.save(a.out, quality=97, subsampling=0)   # stelle = punti 1px colorati: niente chroma 4:2:0
else:
    im.save(a.out)
print(f"ok {a.out} {ow}x{oh} (da {W}x{H}, gamma {a.gamma}, gain {a.gain})")
