#!/usr/bin/env python3
# ============================================================================
# Eternal Fall — genera N sfondi equirettangolari REALI e VARIATI a partire da
# mappe stellari fotografiche della Via Lattea (Solar System Scope, ESO/SSC).
# Ogni variante: rotazione in longitudine (banda in posizione diversa = varietà
# di forma) + eventuale flip + tinta d'insieme (varietà di colore) + schiaritura
# (stelle minuscole reali ben visibili). Seamless (equirect wrappa in longitudine).
#
# uso:  python3 tools/vary-skies.py 50 --w 6144 --out assets/skies
#       python3 tools/vary-skies.py --sample --out /tmp/s
# ============================================================================
import sys, os
import numpy as np
from PIL import Image

OUTW = 6144; OUTDIR = "assets/skies"; N = 50; SAMPLE = False; VSCALE = None   # VSCALE = override compressione verticale (None = random 0.58-0.72; più alto = banda meno schiacciata → più risoluzione/spessa)
BASES = ["assets/milkyway_8k.jpg"]   # ESO/Brunier — Via Lattea reale dettagliata (come gen_25), variata per rotazione+tinta
args = sys.argv[1:]; i = 0
while i < len(args):
    a = args[i]
    if a == "--w": OUTW = int(args[i+1]); i += 2
    elif a == "--out": OUTDIR = args[i+1]; i += 2
    elif a == "--base": BASES = [args[i+1]]; i += 2
    elif a == "--vscale": VSCALE = float(args[i+1]); i += 2
    elif a == "--sample": SAMPLE = True; i += 1
    elif a == "--from": FROM_K = int(args[i+1]); i += 2
    elif a == "--to": TO_K = int(args[i+1]); i += 2
    elif a.isdigit(): N = int(a); i += 1
    else: i += 1
OUTH = OUTW // 2
try: FROM_K
except NameError: FROM_K = 1
try: TO_K
except NameError: TO_K = N

# tinte d'insieme (varietà di COLORE) — vicine al bianco per restare realistiche
TINTS = [
    ("neutro",  [1.00, 0.99, 0.97]),
    ("caldo",   [1.00, 0.90, 0.74]),
    ("ambra",   [1.00, 0.86, 0.62]),
    ("blu",     [0.78, 0.88, 1.00]),
    ("ghiaccio",[0.85, 0.94, 1.00]),
    ("teal",    [0.80, 1.00, 0.96]),
    ("viola",   [0.90, 0.82, 1.00]),
    ("rosa",    [1.00, 0.84, 0.90]),
    ("verde",   [0.86, 1.00, 0.88]),
    ("oro-rosa",[1.00, 0.88, 0.80]),
]

def load_base(path):
    im = Image.open(path).convert("RGB").resize((OUTW, OUTH), Image.LANCZOS)
    arr = np.asarray(im, np.float32) / 255.0
    # normalizza la luminosità: le texture SSC sono molto scure → porta il 99.7° percentile a ~0.82
    p = float(np.percentile(arr, 99.7))
    arr = arr * (0.82 / max(p, 0.12))
    return np.clip(arr, 0, 1)

POLE_DIM = 0.85   # attenuazione del cielo NON compresso usato come fondo ai poli (banda = protagonista)

def process(base, roll, flip, vscale, voff, tint, gain, gamma, sat):
    img = np.roll(base, roll, axis=1)
    if flip: img = img[:, ::-1, :].copy()
    # schiaritura: gamma lift (rivela le stelle deboli) + gain, preservando il nero
    img = np.clip(img, 0, 1) ** gamma
    img = img * gain
    # saturazione (colori stellari un filo più vivi)
    g = img.mean(-1, keepdims=True)
    img = g + (img - g) * sat
    # tinta d'insieme
    img = img * np.array(tint, np.float32)
    img = np.clip(img, 0, 1)
    # comprimi verticalmente e centra: banda "intera" e sottile. Il fondo NON è più nero
    # ("buchi neri" alle estremità quando la camera orbita in verticale a 360°): sotto la
    # banda c'è la STESSA immagine non compressa attenuata (stesso roll/flip/tinta → poli
    # con stelle vere e coerenti; la sua Via Lattea centrale resta interamente COPERTA
    # dalla banda incollata, che è più alta: vscale ≥ ~0.5 con voff ±4%)
    sh = int(OUTH * vscale)
    small = Image.fromarray((img * 255 + 0.5).astype(np.uint8)).resize((OUTW, sh), Image.LANCZOS)
    canvas = (img * (POLE_DIM * 255) + 0.5).astype(np.uint8)
    y0 = max(0, min(OUTH - sh, (OUTH - sh) // 2 + voff))
    # feather verticale (~3% di OUTH) ai bordi della banda: nessuna riga di cucitura
    sm = np.asarray(small, np.float32)
    F = max(8, int(OUTH * 0.03))
    alpha = np.ones((sh, 1, 1), np.float32)
    ramp = (np.arange(F, dtype=np.float32) + 1) / F
    alpha[:F, 0, 0] = ramp
    alpha[-F:, 0, 0] = ramp[::-1]
    canvas[y0:y0 + sh] = (sm * alpha + canvas[y0:y0 + sh].astype(np.float32) * (1 - alpha) + 0.5).astype(np.uint8)
    return canvas

def main():
    bases = [load_base(p) for p in BASES if os.path.exists(p)]
    if not bases:
        print("NESSUNA base trovata:", BASES); sys.exit(1)
    os.makedirs(OUTDIR, exist_ok=True)
    rng = np.random.default_rng(7)
    items = 4 if SAMPLE else N
    for k in range(items):
        base = bases[0] if (len(bases) < 2 or k % 3 != 2) else bases[1]   # ~2/3 Via Lattea ESO, ~1/3 campo stellare
        roll = int(rng.integers(0, OUTW))
        flip = bool(rng.integers(0, 2))
        vscale = VSCALE if VSCALE is not None else float(rng.uniform(0.58, 0.72))    # banda "intera" e sottile, cielo nero su/giù (VSCALE alto = meno schiacciata → più risoluzione)
        voff = int(rng.integers(-int(OUTH*0.04), int(OUTH*0.04)))
        name, tint = TINTS[k % len(TINTS)]
        gain = float(rng.uniform(1.0, 1.25))
        gamma = float(rng.uniform(0.72, 0.84))     # <1 = schiarisce le ombre (rivela più stelle)
        sat = float(rng.uniform(1.05, 1.35))
        if not SAMPLE and not (FROM_K <= k + 1 <= TO_K):
            continue   # fascia --from/--to: le estrazioni rng sopra girano COMUNQUE (fase del seed identica) → due processi possono spartirsi i 50 gen
        arr = process(base, roll, flip, vscale, voff, tint, gain, gamma, sat)
        fn = f"{OUTDIR}/sample_{k+1}_{name}.jpg" if SAMPLE else f"{OUTDIR}/gen_{k+1:02d}.jpg"
        Image.fromarray(arr, "RGB").save(fn, quality=95, subsampling=0)   # stelle = punti colorati 1px: niente chroma 4:2:0 (sbiadisce i colori stellari)
        if SAMPLE or (k+1) % 10 == 0 or k == 0: print("ok", os.path.basename(fn), "tint=%s gain=%.2f gamma=%.2f" % (name, gain, gamma))
    print("done", items)

if __name__ == "__main__":
    main()
