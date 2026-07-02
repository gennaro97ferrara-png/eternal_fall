#!/usr/bin/env python3
# ============================================================================
# Eternal Fall — crop da EXR gigante (es. NASA SVS Deep Star Maps 32k) SENZA
# caricare tutta l'immagine: legge solo le scanline del rettangolo richiesto
# (ffmpeg non decodifica il 32k: piano float da 2^31 byte; sips brucia i toni).
# Converte da luce lineare a gamma (default 2.2) e salva PNG 8-bit pronto per
# build-levels.py (che poi normalizza la luminanza come vary-skies).
#
# uso:  python3 tools/zoom/exr-crop.py in.exr out.png \
#           --x 13107 --y 6349 --w 6554 --h 3686 [--gamma 2.2] [--gain 1.0]
# ============================================================================
import argparse
import numpy as np
import OpenEXR, Imath
from PIL import Image

p = argparse.ArgumentParser(description="crop di una regione da EXR scanline gigante")
p.add_argument("exr")
p.add_argument("out")
p.add_argument("--x", type=int, required=True, help="colonna sinistra del crop")
p.add_argument("--y", type=int, required=True, help="riga alta del crop")
p.add_argument("--w", type=int, required=True)
p.add_argument("--h", type=int, required=True)
p.add_argument("--gamma", type=float, default=2.2, help="lineare -> v^(1/gamma)")
p.add_argument("--gain", type=float, default=1.0, help="moltiplicatore pre-gamma")
a = p.parse_args()

f = OpenEXR.InputFile(a.exr)
dw = f.header()["dataWindow"]
W = dw.max.x - dw.min.x + 1
H = dw.max.y - dw.min.y + 1
if not (0 <= a.x and a.x + a.w <= W and 0 <= a.y and a.y + a.h <= H):
    raise SystemExit(f"crop {a.w}x{a.h}@({a.x},{a.y}) fuori dai bordi {W}x{H}")

half = Imath.PixelType(Imath.PixelType.HALF)
canali = []
for c in "RGB":
    # legge SOLO le righe del crop (scanLine1/2), poi taglia le colonne
    raw = f.channel(c, half, scanLine1=a.y, scanLine2=a.y + a.h - 1)
    arr = np.frombuffer(raw, dtype=np.float16).reshape(a.h, W)
    canali.append(arr[:, a.x:a.x + a.w].astype(np.float32))

rgb = np.stack(canali, axis=-1) * a.gain
rgb = np.clip(rgb, 0.0, 1.0) ** (1.0 / a.gamma)
Image.fromarray((rgb * 255.0 + 0.5).astype(np.uint8), "RGB").save(a.out)
print(f"ok {a.out} {a.w}x{a.h} (da {W}x{H}, gamma {a.gamma}, gain {a.gain})")
