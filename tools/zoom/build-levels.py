#!/usr/bin/env python3
# ============================================================================
# Eternal Fall — costruisce i LIVELLI dello "zoom infinito" annidato: da un
# JSON di configurazione (catena di inquadrature sempre più strette, una
# dentro l'altra, centri concentrici) produce assets/zoom/<nome>.jpg + il
# manifest assets/zoom/levels.json che la regia live usa per lo zoom.
#
# Per ogni livello:
#   1. carica la sorgente: file locale OPPURE piramide Zoomify (scaricata via
#      tools/zoom/fetch-tiles.py importato come modulo — niente subprocess)
#   2. ritaglia attorno a center_px con dimensioni crop_px (nero oltre i bordi)
#   3. ruota di rotate_deg attorno al centro del ritaglio (bicubico, expand=False)
#   4. normalizza la luminosità con la STESSA convenzione di tools/vary-skies.py
#      (99.7° percentile → 0.82) ma con gain LIMITATO (default 0.5..3),
#      regolabile per livello col campo "norm"
#   5. gamma opzionale (campo "gamma", <1 schiarisce le ombre = più stelle)
#   6. ridimensiona: lato lungo <= out_max (LANCZOS, MAI upscale)
#   7. salva JPEG quality=95 subsampling=0 (stelle = punti 1px: niente 4:2:0)
#
# Alla fine stampa il report della catena (rapporto angolare tra livelli
# consecutivi, con avviso se >4.5 o <2) e con --contact genera un
# contact-sheet: ogni livello in miniatura con il rettangolo dell'inquadratura
# del livello SUCCESSIVO disegnato sopra (per controllare l'allineamento).
#
# uso:  python3 tools/zoom/build-levels.py --config tools/zoom/zoom-config.json
#       python3 tools/zoom/build-levels.py --config ... --contact /cartella/scratch
# ============================================================================
import argparse, importlib.util, json, os, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw

# fetch-tiles.py ha il trattino nel nome → import via importlib (stessa cartella)
_QUI = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("fetch_tiles", os.path.join(_QUI, "fetch-tiles.py"))
fetch_tiles = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch_tiles)

def normalizza(arr, norm):
    """Normalizzazione luminosità, stessa convenzione di load_base() in
    tools/vary-skies.py: porta il 99.7° percentile a ~0.82 (con la stessa
    soglia anti-divisione 0.12). Qui però il gain è LIMITATO (default 0.5..3)
    per non stravolgere ritagli molto scuri/chiari. Campo "norm" del livello:
    false = salta, oppure {"pct":99.7, "target":0.82, "min":0.5, "max":3.0}."""
    if norm is False:
        return arr, 1.0
    n = norm if isinstance(norm, dict) else {}
    p = float(np.percentile(arr, float(n.get("pct", 99.7))))
    gain = float(n.get("target", 0.82)) / max(p, 0.12)
    gain = min(max(gain, float(n.get("min", 0.5))), float(n.get("max", 3.0)))
    return np.clip(arr * gain, 0, 1), gain

def carica_sorgente(liv, cache, jobs):
    """Sorgente → PIL.Image già ritagliata crop_px attorno a center_px (nero ai bordi).
    - type "file":    center_px in pixel del file, crop_px in pixel del file
    - type "zoomify": center_px in pixel FULL-RES della piramide, crop_px in
                      pixel del livello scelto (source.level, default "max")"""
    src = liv["source"]
    cx, cy = liv["center_px"]
    cw, ch = liv["crop_px"]
    if src["type"] == "file":
        im = Image.open(src["path"]).convert("RGB")
        x0, y0 = round(cx - cw / 2), round(cy - ch / 2)
        return im.crop((x0, y0, x0 + cw, y0 + ch))    # .crop oltre i bordi = riempito di nero
    if src["type"] == "zoomify":
        img, info = fetch_tiles.fetch_region(src["base"], src.get("level", "max"),
                                             cx, cy, cw, ch, cache=cache, jobs=jobs)
        print(f"  zoomify: livello {info['livello']}/{info['livelli'] - 1} "
              f"({info['wl']}x{info['hl']} px), {info['tiles']} tile "
              f"({info['scaricati']} scaricati, {info['da_cache']} da cache, {info['byte'] / 1e6:.2f} MB)")
        return img
    raise SystemExit(f"source.type sconosciuto: {src['type']!r} (uso 'file' o 'zoomify')")

def costruisci_livello(liv, cache, jobs):
    """Pipeline completa di UN livello → PIL.Image pronta da salvare."""
    im = carica_sorgente(liv, cache, jobs)
    rot = float(liv.get("rotate_deg", 0.0))
    if rot:
        # rotazione ANTIORARIA attorno al centro del ritaglio; expand=False
        # (stessa cornice), gli angoli scoperti restano neri come il padding
        im = im.rotate(rot, resample=Image.BICUBIC, expand=False, fillcolor=(0, 0, 0))
    arr = np.asarray(im, np.float32) / 255.0
    arr, gain = normalizza(arr, liv.get("norm"))
    gamma = liv.get("gamma")
    if gamma:
        arr = np.clip(arr, 0, 1) ** float(gamma)      # <1 = schiarisce le ombre (rivela stelle deboli)
    im = Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8))
    out_max = int(liv.get("out_max", 8192))
    if max(im.size) > out_max:                        # mai upscale: solo riduzione
        s = out_max / max(im.size)
        im = im.resize((max(1, round(im.size[0] * s)), max(1, round(im.size[1] * s))), Image.LANCZOS)
    return im, gain

def contact_sheet(voci, immagini, cartella):
    """Striscia di controllo: ogni livello in miniatura + rettangolo rosso con
    l'inquadratura del livello SUCCESSIVO (rapporto angolare, centri assunti
    concentrici) → verifica visiva veloce dell'allineamento della catena."""
    TH = 360
    pezzi = []
    for i, (v, im) in enumerate(zip(voci, immagini)):
        tw = max(1, round(im.size[0] * TH / im.size[1]))
        t = im.resize((tw, TH), Image.LANCZOS)
        d = ImageDraw.Draw(t)
        if i + 1 < len(voci):
            rx = voci[i + 1]["angle_deg"][0] / v["angle_deg"][0]
            ry = voci[i + 1]["angle_deg"][1] / v["angle_deg"][1]
            rw, rh = tw * rx, TH * ry
            d.rectangle([(tw - rw) / 2, (TH - rh) / 2, (tw + rw) / 2, (TH + rh) / 2],
                        outline=(255, 60, 60), width=2)
        d.text((6, 6), f"{v['_name']}  {v['angle_deg'][0]:g}x{v['angle_deg'][1]:g} deg",
               fill=(255, 220, 80))
        pezzi.append(t)
    M = 12
    sheet = Image.new("RGB", (sum(p.size[0] for p in pezzi) + M * (len(pezzi) + 1), TH + 2 * M), (24, 24, 28))
    x = M
    for p in pezzi:
        sheet.paste(p, (x, M))
        x += p.size[0] + M
    os.makedirs(cartella, exist_ok=True)
    fn = os.path.join(cartella, "zoom-contact-sheet.png")
    sheet.save(fn)
    print("contact-sheet:", fn)

def main():
    ap = argparse.ArgumentParser(description="costruisce i livelli dello zoom annidato + manifest levels.json")
    ap.add_argument("--config", default="tools/zoom/zoom-config.json", help="JSON con la catena dei livelli")
    ap.add_argument("--outdir", default="assets/zoom", help="cartella di uscita (jpg + levels.json)")
    ap.add_argument("--cache", default=None, help="cartella cache dei tile Zoomify (riprende fetch interrotti)")
    ap.add_argument("--jobs", type=int, default=6, help="download concorrenti per le sorgenti Zoomify")
    ap.add_argument("--contact", nargs="?", const="", default=None, metavar="DIR",
                    help="genera il contact-sheet di controllo in DIR (default: cartella temporanea)")
    a = ap.parse_args()

    cfg = json.load(open(a.config))
    os.makedirs(a.outdir, exist_ok=True)
    voci, immagini = [], []
    for liv in cfg["levels"]:
        nome = liv["name"]
        print(f"— {nome}: sorgente {liv['source']['type']}, crop {liv['crop_px'][0]}x{liv['crop_px'][1]} "
              f"@ ({liv['center_px'][0]:g},{liv['center_px'][1]:g}), rot {liv.get('rotate_deg', 0):g}°")
        im, gain = costruisci_livello(liv, a.cache, a.jobs)
        fn = os.path.join(a.outdir, nome + ".jpg")
        im.save(fn, quality=95, subsampling=0)   # stelle = punti colorati 1px: niente chroma 4:2:0
        print(f"  ok {fn} {im.size[0]}x{im.size[1]} (gain luminosità x{gain:.2f})")
        # nel manifest: percorso relativo alla cwd (la regia carica "assets/zoom/...")
        # — se l'outdir è fuori dall'albero (test), resta solo il nome del file
        rel = os.path.relpath(fn)
        if rel.startswith(".."):
            rel = os.path.basename(fn)
        voci.append({"file": rel, "angle_deg": liv["angle_deg"],
                     "credit": liv.get("credit", ""), "px": list(im.size), "_name": nome})
        immagini.append(im)

    # manifest per la regia live (il campo _name serve solo al contact-sheet)
    manifest = {"levels": [{k: v for k, v in voce.items() if k != "_name"} for voce in voci]}
    mfn = os.path.join(a.outdir, "levels.json")
    json.dump(manifest, open(mfn, "w"), indent=2)
    print("manifest:", mfn)

    # report catena: il rapporto angolare tra livelli consecutivi è il "fattore
    # di zoom" di ogni passaggio — comodo tra ~2 e ~4.5 (oltre: salto troppo
    # brusco per il crossfade; sotto 2: livelli quasi uguali, spreco)
    print("— catena zoom —")
    for i in range(len(voci) - 1):
        r = voci[i]["angle_deg"][0] / voci[i + 1]["angle_deg"][0]
        avviso = "   ATTENZIONE: fuori dal range consigliato 2..4.5" if (r > 4.5 or r < 2) else ""
        print(f"  {voci[i]['_name']} ({voci[i]['angle_deg'][0]:g}°) → "
              f"{voci[i + 1]['_name']} ({voci[i + 1]['angle_deg'][0]:g}°): x{r:.2f}{avviso}")

    if a.contact is not None:
        contact_sheet(voci, immagini, a.contact or tempfile.gettempdir())

if __name__ == "__main__":
    main()
