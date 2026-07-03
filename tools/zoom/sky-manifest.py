#!/usr/bin/env python3
# ============================================================================
# Eternal Fall — sky-manifest: ricostruisce (SENZA riscrivere immagini) la
# sequenza rng esatta usata da tools/vary-skies.py per generare i 50 sfondi
# assets/skies/gen_01..50.jpg (commit 532a0bb: `--w 6144 --vscale 1.0`, base
# di default assets/milkyway_8k.jpg, seed 7) ed emette assets/zoom/sky-gc.json
# con la posizione del CENTRO GALATTICO in ogni sfondo come frazioni
# {u: da sinistra 0..1, v: dall'alto 0..1} + {flip, roll_px} di riferimento.
#
# Come funziona la ricostruzione (specchia vary-skies.py riga per riga):
#   rng = np.random.default_rng(7); per ogni k:
#     roll  = int(rng.integers(0, OUTW))          # np.roll(axis=1): +roll sposta a DESTRA
#     flip  = bool(rng.integers(0, 2))            # applicato DOPO il roll
#     (vscale: rng.uniform SALTATA se --vscale è passato → 1.0 fisso, come nel run reale)
#     voff  = int(rng.integers(-int(OUTH*0.04), int(OUTH*0.04)))
#     gain, gamma, sat = rng.uniform(...) x3      # non spostano il centro, ma vanno
#                                                 # comunque estratti per tenere il rng in fase
#   Il centro galattico nella base ESO è al centro immagine (u=0.5, v=0.5):
#     u = (0.5 + roll/OUTW) mod 1 ; se flip → u = (1 - u) mod 1
#     v = (y0 + sh/2)/OUTH con sh=OUTH*vscale, y0=clamp((OUTH-sh)//2+voff)
#     (a vscale 1.0: sh=OUTH e y0=0 sempre → v=0.5 per tutti)
#
# uso:  python3 tools/zoom/sky-manifest.py                     # scrive il manifest
#       python3 tools/zoom/sky-manifest.py --verify 1,25       # + confronto pixel in memoria
#       python3 tools/zoom/sky-manifest.py --centroid          # + check baricentro bulge su tutti
# ============================================================================
import argparse, json, os, sys
import numpy as np
from PIL import Image

# tinte d'insieme — copia 1:1 da vary-skies.py (servono solo per --verify)
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


def replay_rng(n, outw, outh, vscale_cli, seed):
    """Rigioca la sequenza rng di vary-skies.py nello STESSO ordine di estrazione
    e restituisce i parametri di ogni variante (nessuna immagine toccata)."""
    rng = np.random.default_rng(seed)
    out = []
    for k in range(n):
        roll = int(rng.integers(0, outw))
        flip = bool(rng.integers(0, 2))
        # NB: nel run reale (532a0bb) --vscale 1.0 era passato da CLI → il draw
        # rng.uniform(0.58, 0.72) NON è avvenuto. Saltarlo qui è essenziale per
        # restare in fase con la sequenza.
        vscale = vscale_cli if vscale_cli is not None else float(rng.uniform(0.58, 0.72))
        voff = int(rng.integers(-int(outh * 0.04), int(outh * 0.04)))
        name, tint = TINTS[k % len(TINTS)]
        gain = float(rng.uniform(1.0, 1.25))
        gamma = float(rng.uniform(0.72, 0.84))
        sat = float(rng.uniform(1.05, 1.35))
        out.append(dict(k=k, roll=roll, flip=flip, vscale=vscale, voff=voff,
                        tint_name=name, tint=tint, gain=gain, gamma=gamma, sat=sat))
    return out


def gc_uv(p, outw, outh):
    """Posizione del centro galattico (frazioni u,v) per i parametri p.
    Base ESO: centro galattico esattamente al centro (u=v=0.5).
    np.roll(+r, axis=1) sposta il contenuto a DESTRA di r px → u += r/W;
    il flip orizzontale avviene DOPO il roll → u = 1-u."""
    u = (0.5 + p["roll"] / outw) % 1.0
    if p["flip"]:
        u = (1.0 - u) % 1.0
    sh = int(outh * p["vscale"])
    y0 = max(0, min(outh - sh, (outh - sh) // 2 + p["voff"]))
    v = (y0 + sh / 2.0) / outh
    return u, v


# ---------------------------------------------------------------------------
# verifica pixel: replica ESATTA di load_base()+process() di vary-skies.py,
# tutto in memoria, e confronto con il JPEG su disco (diff media per canale
# attesa ~0.5-2/255 = solo round-trip JPEG; roll/flip sbagliati → diff enormi)
# ---------------------------------------------------------------------------

def load_base(path, outw, outh):
    im = Image.open(path).convert("RGB").resize((outw, outh), Image.LANCZOS)
    arr = np.asarray(im, np.float32) / 255.0
    p = float(np.percentile(arr, 99.7))
    arr = arr * (0.82 / max(p, 0.12))
    return np.clip(arr, 0, 1)


POLE_DIM = 0.85   # copia 1:1 da vary-skies.py (fondo ai poli = base non compressa attenuata, non più nero)

def process(base, p, outw, outh):
    img = np.roll(base, p["roll"], axis=1)
    if p["flip"]:
        img = img[:, ::-1, :].copy()
    img = np.clip(img, 0, 1) ** p["gamma"]
    img = img * p["gain"]
    g = img.mean(-1, keepdims=True)
    img = g + (img - g) * p["sat"]
    img = img * np.array(p["tint"], np.float32)
    img = np.clip(img, 0, 1)
    sh = int(outh * p["vscale"])
    small = Image.fromarray((img * 255 + 0.5).astype(np.uint8)).resize((outw, sh), Image.LANCZOS)
    canvas = (img * (POLE_DIM * 255) + 0.5).astype(np.uint8)
    y0 = max(0, min(outh - sh, (outh - sh) // 2 + p["voff"]))
    sm = np.asarray(small, np.float32)
    F = max(8, int(outh * 0.03))
    alpha = np.ones((sh, 1, 1), np.float32)
    ramp = (np.arange(F, dtype=np.float32) + 1) / F
    alpha[:F, 0, 0] = ramp
    alpha[-F:, 0, 0] = ramp[::-1]
    canvas[y0:y0 + sh] = (sm * alpha + canvas[y0:y0 + sh].astype(np.float32) * (1 - alpha) + 0.5).astype(np.uint8)
    return canvas


def verify_pixels(indices, params, base_path, skies_dir, outw, outh):
    """Rigenera in memoria le varianti richieste e misura la differenza media
    assoluta per canale rispetto ai JPEG su disco. Ritorna True se tutte ok."""
    base = load_base(base_path, outw, outh)
    ok = True
    for idx in indices:
        p = params[idx - 1]
        fn = os.path.join(skies_dir, f"gen_{idx:02d}.jpg")
        disk = np.asarray(Image.open(fn).convert("RGB"), np.int16)
        mem = process(base, p, outw, outh).astype(np.int16)
        mad = [float(np.abs(mem[..., c] - disk[..., c]).mean()) for c in range(3)]
        good = max(mad) < 2.5   # solo rumore di quantizzazione JPEG (q95, 4:4:4)
        ok &= good
        print("verify gen_%02d  roll=%d flip=%d  MAD RGB = %.3f %.3f %.3f /255  %s"
              % (idx, p["roll"], p["flip"], *mad, "OK" if good else "MISMATCH"))
    return ok


def check_centroids(manifest, repo_root, outw):
    """Controllo indipendente su TUTTI gli sfondi: baricentro circolare di
    luminanza (pesato sul bulge, i pixel più brillanti) vs u predetto."""
    worst = 0.0
    for path, e in manifest.items():
        im = Image.open(os.path.join(repo_root, path)).convert("L").resize((768, 384), Image.BILINEAR)
        col = np.asarray(im, np.float32).sum(0)
        w = np.clip(col - np.percentile(col, 50), 0, None) ** 3   # esalta il bulge
        ang = np.arange(768) / 768.0 * 2 * np.pi
        cx = float(np.arctan2((w * np.sin(ang)).sum(), (w * np.cos(ang)).sum()) / (2 * np.pi) % 1.0)
        d = abs(cx - e["u"]); d = min(d, 1 - d)   # distanza circolare
        worst = max(worst, d)
        print("centroid %-28s  u_pred=%.4f  u_lum=%.4f  d=%.4f" % (path, e["u"], cx, d))
    print("centroid: errore circolare max = %.4f (frazione di larghezza)" % worst)
    return worst


def main():
    ap = argparse.ArgumentParser(description="Manifest u,v del centro galattico per gli sfondi sky (nessuna immagine scritta)")
    ap.add_argument("--n", type=int, default=50, help="numero varianti gen_XX (default 50)")
    ap.add_argument("--w", type=int, default=6144, help="OUTW usato alla generazione (default 6144)")
    ap.add_argument("--vscale", type=float, default=1.0, help="vscale passato da CLI alla generazione; 'none' non supportato: il run reale era 1.0")
    ap.add_argument("--seed", type=int, default=7, help="seed del default_rng (default 7, hardcoded in vary-skies.py)")
    ap.add_argument("--base", default="assets/milkyway_8k.jpg", help="immagine base ESO (centro galattico a u=v=0.5)")
    ap.add_argument("--skies", default="assets/skies", help="cartella dei gen_XX.jpg")
    ap.add_argument("--out", default="assets/zoom/sky-gc.json", help="manifest JSON di uscita")
    ap.add_argument("--verify", default="", help="varianti da rigenerare in memoria e confrontare coi JPEG, es. '1,25' ('' = salta)")
    ap.add_argument("--centroid", action="store_true", help="check baricentro di luminanza su tutti gli sfondi")
    a = ap.parse_args()
    outw, outh = a.w, a.w // 2

    # percorsi relativi alla radice del repo (due livelli sopra tools/zoom/)
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    params = replay_rng(a.n, outw, outh, a.vscale, a.seed)

    # manifest: base originale + 50 varianti
    manifest = {}
    manifest[a.base] = {"u": 0.5, "v": 0.5, "flip": False, "roll_px": 0}
    for p in params:
        u, v = gc_uv(p, outw, outh)
        manifest[f"{a.skies}/gen_{p['k']+1:02d}.jpg"] = {
            "u": round(u, 6), "v": round(v, 6),
            "flip": p["flip"], "roll_px": p["roll"],
        }

    # verifica pixel (obbligatoria per fidarsi del manifest)
    if a.verify:
        idxs = [int(x) for x in a.verify.split(",") if x.strip()]
        if not verify_pixels(idxs, params, os.path.join(repo_root, a.base),
                             os.path.join(repo_root, a.skies), outw, outh):
            print("VERIFICA FALLITA: manifest NON scritto"); sys.exit(1)

    # check indipendente sul bulge luminoso (opzionale, copre tutti i 51 file)
    if a.centroid:
        check_centroids(manifest, repo_root, outw)

    out_path = os.path.join(repo_root, a.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc = {
        "_meta": {
            "descrizione": "posizione del centro galattico (frazioni: u da sinistra, v dall'alto) in ogni sfondo sky",
            "generatore": "tools/zoom/sky-manifest.py (replica rng di tools/vary-skies.py, commit 532a0bb)",
            "args_generazione": {"seed": a.seed, "w": outw, "h": outh, "vscale": a.vscale, "n": a.n},
        },
        "skies": manifest,
    }
    with open(out_path, "w") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    print("scritto", a.out, "(%d sfondi)" % len(manifest))


if __name__ == "__main__":
    main()
