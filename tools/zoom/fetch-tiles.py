#!/usr/bin/env python3
# ============================================================================
# Eternal Fall — scarica e RICUCE una regione da un'immagine Zoomify (es. le
# "zoomable" ESO su cdn.eso.org). Il formato Zoomify è una piramide di tile
# JPEG: <base>/ImageProperties.xml dichiara WIDTH/HEIGHT/TILESIZE/NUMTILES;
# il livello 0 è l'immagine intera dentro UN solo tile e ogni livello
# raddoppia fino alla risoluzione piena (dimensioni: dal full-res si dimezza
# con floor, convenzione Zoomify/OpenSeadragon). Nome tile:
#   TileGroup{g}/{livello}-{col}-{riga}.jpg
# con g = indice_globale // 256, dove l'indice globale conta i tile dal
# livello 0 in su, riga per riga (row-major) dentro ogni livello.
#
# Scarica SOLO i tile necessari (ThreadPool, default 6 richieste concorrenti
# per essere gentili col CDN, retry con backoff, cache su disco per
# riprendere), ricuce con PIL e ritaglia il rettangolo esatto richiesto
# (nero oltre i bordi dell'immagine). Importabile anche come modulo da
# build-levels.py: la funzione utile è fetch_region().
#
# uso:  python3 tools/zoom/fetch-tiles.py \
#           --base https://cdn.eso.org/images/zoomable/eso1242a/ \
#           --level max --cx 54100 --cy 40751 --w 4096 --h 4096 \
#           --out region.png [--cache /tmp/tiles-eso1242a] [--jobs 6]
#
#       --cx/--cy = centro in pixel FULL-RES (comodo: non cambia col livello)
#       --w/--h   = dimensioni dell'output in pixel DEL LIVELLO scelto
#       --level   = intero oppure "max" (= risoluzione piena)
# ============================================================================
import argparse, io, math, os, sys, time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

UA = {"User-Agent": "eternal-fall-zoom/1.0 (fetch regione Zoomify, uso una tantum)"}

def scarica(url, tentativi=4, timeout=30):
    """GET con retry + backoff esponenziale (i CDN a volte rispondono 5xx/timeout)."""
    for k in range(tentativi):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception:
            if k == tentativi - 1:
                raise
            time.sleep(0.8 * (2 ** k))   # 0.8s, 1.6s, 3.2s

def leggi_proprieta(base, cache=None):
    """ImageProperties.xml → (W, H, tilesize, numtiles), con cache su disco."""
    fn = cache and os.path.join(cache, "ImageProperties.xml")
    if fn and os.path.exists(fn) and os.path.getsize(fn) > 0:
        dati = open(fn, "rb").read()
    else:
        dati = scarica(base + "ImageProperties.xml")
        if fn:
            os.makedirs(cache, exist_ok=True)
            open(fn, "wb").write(dati)
    el = ET.fromstring(dati)
    return (int(el.get("WIDTH")), int(el.get("HEIGHT")),
            int(el.get("TILESIZE", "256")), int(el.get("NUMTILES", "0")))

def dimensioni_livelli(W, H, T):
    """Dimensioni (w,h) di ogni livello, dal più piccolo (livello 0) al full-res:
    dal full-res si dimezza con floor finché l'immagine sta in UN tile."""
    dims = [(W, H)]
    while dims[-1][0] > T or dims[-1][1] > T:
        dims.append((max(1, dims[-1][0] // 2), max(1, dims[-1][1] // 2)))
    dims.reverse()
    return dims

def offset_livelli(dims, T):
    """Indice globale del PRIMO tile di ogni livello + numero totale di tile
    (i tile si contano dal livello 0 in su, row-major dentro ogni livello)."""
    off, tot = [], 0
    for w, h in dims:
        off.append(tot)
        tot += math.ceil(w / T) * math.ceil(h / T)
    return off, tot

def url_tile(base, off, dims, T, lvl, col, riga):
    """URL del singolo tile: il TileGroup dipende dall'indice GLOBALE del tile."""
    cols = math.ceil(dims[lvl][0] / T)
    g = (off[lvl] + riga * cols + col) // 256
    return f"{base}TileGroup{g}/{lvl}-{col}-{riga}.jpg"

def fetch_region(base, level, cx, cy, w, h, cache=None, jobs=6, progress=True):
    """Scarica e ricuce la regione richiesta.
    cx/cy in pixel FULL-RES, w/h in pixel del livello scelto.
    Ritorna (PIL.Image RGB w×h, dict con i numeri per il riepilogo)."""
    if not base.endswith("/"):
        base += "/"
    # cache in una SOTTODIR per sorgente: XML e tile di basi diverse non
    # devono mai mischiarsi (stesso schema di nomi {lvl}-{col}-{riga}.jpg!)
    if cache:
        slug = "".join(ch if ch.isalnum() else "_" for ch in base.split("//")[-1]).strip("_")
        cache = os.path.join(cache, slug)
    W, H, T, ntiles = leggi_proprieta(base, cache)
    dims = dimensioni_livelli(W, H, T)
    off, tot = offset_livelli(dims, T)
    if ntiles and tot != ntiles:
        print(f"ATTENZIONE: piramide derivata = {tot} tile ma ImageProperties dice {ntiles}: "
              "gli indici TileGroup potrebbero essere sbagliati", file=sys.stderr)
    lvl = len(dims) - 1 if str(level) in ("max", "-1") else int(level)
    if not (0 <= lvl < len(dims)):
        raise SystemExit(f"livello {lvl} fuori range (0..{len(dims) - 1})")
    wl, hl = dims[lvl]
    # centro full-res → coordinate del livello: in proporzione alle dimensioni
    # REALI del livello (col dimezzamento floor il rapporto non è esattamente 2^k)
    cxl = cx * wl / W
    cyl = cy * hl / H
    x0 = round(cxl - w / 2)
    y0 = round(cyl - h / 2)
    canvas = Image.new("RGB", (w, h), (0, 0, 0))   # nero = padding fuori dai bordi
    # intersezione del rettangolo col livello → range di tile da scaricare
    ix0, iy0 = max(x0, 0), max(y0, 0)
    ix1, iy1 = min(x0 + w, wl), min(y0 + h, hl)
    tiles = []
    if ix0 < ix1 and iy0 < iy1:
        c0, c1 = ix0 // T, (ix1 - 1) // T
        r0, r1 = iy0 // T, (iy1 - 1) // T
        tiles = [(c, r) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
    elif progress:
        print("ATTENZIONE: rettangolo del tutto fuori dall'immagine → PNG nero", file=sys.stderr)
    if cache:
        os.makedirs(cache, exist_ok=True)

    def prendi(cr):
        c, r = cr
        fn = cache and os.path.join(cache, f"{lvl}-{c}-{r}.jpg")
        if fn and os.path.exists(fn) and os.path.getsize(fn) > 0:
            return cr, open(fn, "rb").read(), True          # ripreso dalla cache
        dati = scarica(url_tile(base, off, dims, T, lvl, c, r))
        if fn:
            open(fn, "wb").write(dati)
        return cr, dati, False

    scaricati = da_cache = byte_tot = 0
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futuri = [pool.submit(prendi, cr) for cr in tiles]
        for k, fut in enumerate(as_completed(futuri), 1):
            (c, r), dati, cached = fut.result()
            im = Image.open(io.BytesIO(dati)).convert("RGB")
            canvas.paste(im, (c * T - x0, r * T - y0))      # i tile ai bordi sono più piccoli: ok
            byte_tot += len(dati)
            scaricati += (not cached)
            da_cache += cached
            if progress and (k % 25 == 0 or k == len(tiles)):
                print(f"  tile {k}/{len(tiles)}", file=sys.stderr)
    info = dict(W=W, H=H, T=T, livello=lvl, livelli=len(dims), wl=wl, hl=hl,
                cxl=cxl, cyl=cyl, x0=x0, y0=y0, tiles=len(tiles),
                scaricati=scaricati, da_cache=da_cache, byte=byte_tot)
    return canvas, info

def main():
    ap = argparse.ArgumentParser(description="scarica e ricuce una regione da una piramide Zoomify (es. zoomable ESO)")
    ap.add_argument("--base", required=True, help="URL base (la cartella che contiene ImageProperties.xml)")
    ap.add_argument("--level", default="max", help="livello della piramide (intero) oppure 'max' = risoluzione piena")
    ap.add_argument("--cx", type=float, required=True, help="centro X in pixel FULL-RES")
    ap.add_argument("--cy", type=float, required=True, help="centro Y in pixel FULL-RES")
    ap.add_argument("--w", type=int, required=True, help="larghezza output in pixel DEL LIVELLO scelto")
    ap.add_argument("--h", type=int, required=True, help="altezza output in pixel DEL LIVELLO scelto")
    ap.add_argument("--out", required=True, help="file PNG di uscita")
    ap.add_argument("--cache", default=None, help="cartella cache dei tile (permette di riprendere un fetch interrotto)")
    ap.add_argument("--jobs", type=int, default=6, help="download concorrenti (default 6: siate gentili col CDN)")
    a = ap.parse_args()

    img, i = fetch_region(a.base, a.level, a.cx, a.cy, a.w, a.h, cache=a.cache, jobs=a.jobs)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    img.save(a.out)

    # riepilogo — SOLO matematica dei pixel: la scala fisica (px/grado) non fa
    # parte del formato Zoomify, gli angoli si dichiarano in zoom-config.json
    print(f"immagine {i['W']}x{i['H']} px, tile {i['T']}, {i['livelli']} livelli (0..{i['livelli'] - 1})")
    print(f"livello {i['livello']}: {i['wl']}x{i['hl']} px — centro full-res ({a.cx:.0f},{a.cy:.0f}) "
          f"→ livello ({i['cxl']:.1f},{i['cyl']:.1f})")
    print(f"rettangolo x0={i['x0']} y0={i['y0']} {a.w}x{a.h} → {i['tiles']} tile "
          f"({i['scaricati']} scaricati, {i['da_cache']} da cache, {i['byte'] / 1e6:.2f} MB)")
    print(f"ok {a.out} {img.size[0]}x{img.size[1]}")

if __name__ == "__main__":
    main()
