# Zoom Infinito — Specifica tecnica (branch `zoom-infinito`)

Obiettivo: evento di regia "deep dive" — zoom continuo dentro il cielo verso il centro
galattico, stile video ESO GigaGalaxy/VVV, che **non si sgrana mai**: catena di immagini
reali annidate a risoluzione crescente + finale procedurale infinito.
I 50 sfondi esistenti restano IDENTICI: lo zoom parte dallo sfondo correntemente in onda.
Tutto spento di default; nessun impatto se gli asset zoom non ci sono (no-op con warn).

## 1. Principio

Il video di riferimento non zooma una singola immagine: dissolve tra immagini annidate
(panorama → mosaico → deep field). Qui: quando il livello corrente sta per superare la
magnificazione accettabile, il livello successivo (più risoluto, campo più stretto,
stesso centro = centro galattico) è già in fade-in alla scala combaciante.

Magnificazione M = px_schermo / texel_mostrati. Oggi il cielo in onda sta a M≈2.26 (4K,
FOV 52°). Budget dive: M ≤ ~1.8 a metà crossfade, tipicamente 0.5–1.5. Mai oltre.

## 2. Catena livelli (asset in `assets/zoom/`, manifest `levels.json`)

Θ = angolo di cielo reale inquadrato orizzontalmente (parte da hFOV ≈ 82°, decade exp).
p = px/grado del livello. Il livello "riempie" lo schermo quando Θ = A (suo campo).

CATENA DEFINITIVA (come costruita, vedi zoom-config.json — il mosaico Guisard eso0934a
è stato scartato: la rotazione di 55.7° per orizzontare la banda sborda dall'immagine;
il VVV entra più largo (18°) e copre lui il ponte):

| Liv | Sorgente | p (px/°) | Campo A (°) | Note |
|-----|----------|----------|-------------|------|
| L0 | sfondo corrente (sfera sky) | ~17 | 360 | già in scena |
| L1 | NASA SVS Deep Star Maps 32k galattico (exr-crop.py) | 91 | 72×40.5 | ottico, aggancio alla sfera a Θ0 |
| L2 | ESO eso1242a VVV tiles, liv. piramide 5 | 331 | 18×10.1 | IR (come il video di rif.) |
| L3 | VVV tiles liv. 7 | 1325 | 6.18×3.48 | |
| L4 | VVV tiles full-res (liv. 9) | 5302 | 1.545×0.87 | stelle singole |
| L5 | ESO eso1920a HAWK-I tiles liv. 6 | 16949 | 0.395×0.222 | nucleo |
| L6 | HAWK-I tiles full-res (liv. 8) | 67815 | 0.121×0.068 | nuclear star cluster |
| L∞ | stelle procedurali radiali | ∞ | — | infinito vero, loop |

Zoom totale fotografico ~680×, poi procedurale senza limite.
NB: l'EXR 32k NON si decodifica con ffmpeg (piano float = 2^31 byte) né sips (brucia i
toni): usare tools/zoom/exr-crop.py (modulo python OpenEXR, legge solo le scanline utili).
Crop ruotati (rotate_deg da astrometria) perché la banda della Via Lattea resti
orizzontale come negli sfondi attuali. Luminanza normalizzata come vary-skies
(99.7° pct → 0.82). JPEG q95 subsampling=0, lato lungo ≤ 8192 (mai upscale).

## 3. Aggancio ai 50 sfondi esistenti

`assets/zoom/sky-gc.json`: per ogni sky (milkyway_8k + gen_01..50) la posizione {u,v}
del centro galattico nell'immagine (ricostruita dal rng seeded di vary-skies, verificata
pixel-wise). Runtime: uv → direzione mondo sulla sfera (convenzione UV di
SphereGeometry r160 + `sky.rotation` corrente — VERIFICARE empiricamente con marker).
Il rig dello zoom punta lì: il dive parte dal cielo in onda, qualunque dei 50 sia.

## 4. Runtime (sezione nuova in index.html, ~400 righe, "=== DEEP ZOOM ===")

Scene graph: `zoomRig` (Group) orientato per-frame verso la direzione GC; figli = 2 quad
(PlaneGeometry 1×(9/16)) a z=-4500, MeshBasicMaterial {map, transparent, depthWrite:false,
fog:false}, renderOrder -9.5 (tra sfera sky -10 e stelle -9). Solo 2 livelli visibili.

Driver: Θ(t)=82·exp(-k·t), k default ln(410)/78 ≈ 0.077 (raddoppio ~9s, configurabile).
Scala quad: larghezza apparente del livello i = A_i·(hFOV/Θ) → half-width = 4500·tan(θ/2),
clamp θ<170°. Opacità: fade-in del livello i su Θ ∈ [A_i, 0.72·A_i] (smoothstep in log Θ);
il precedente droppa (visible=false, texture.dispose()) quando il nuovo è a opacità 1.
Preload del livello i+1 quando i raggiunge metà del suo range: createImageBitmap
(imageOrientation:'flipY', flipY texture=false) → niente hitch di decode sul main thread.
Errore load → livello saltato, si allunga la finestra del precedente e/o anticipa L∞ (mai crash).

Ingresso (t 0→4s): L1 fade-in scale-matched sopra la sfera (SVS e Brunier = stesso cielo
reale: il crossfade combacia); rotazione sky congelata con rampa 2s (evita shear al bordo,
ripristinata all'uscita); micro kick FOV +2° con decay (termine additivo nella riga
camera.fov, index.html:3261); nebSheets/dust opacità ×(1-diveBlend) per pulizia e fill-rate.

Finale L∞: layer Points dedicato nel rig (modellato su makeStarLayer: psFloor 1.7·uPix,
additive, uniforms uPix aggiornati come index.html:2956/3803): stelle con flusso radiale
r(t)=r·exp(k·t) dal centro, respawn vicino all'asse → zoom infinito procedurale nitido
a qualsiasi risoluzione. L6 sfuma sotto mentre le procedurali prendono il testimone
("si risolve in stelle", come il finale del video).

Uscita (mode 'once', default dur≈90s) o loop (mode 'loop'): fade-out rig 4s + cycleSky
forzato verso un nuovo sfondo + ripristino rotazione/neb → la caduta eterna riprende.
`cadutaZoomStop()` = abort pulito 3s.

Integrazioni minime (tutte inerti a zoom spento):
- animate(): `deepZoomUpdate(dt)` dentro il try/catch esistente
- updateSky (index.html:2200): guardia — niente auto-cycleSky durante il dive; se un
  crossfade è in corso al trigger, attendere che finisca prima di partire
- camera.fov (index.html:3261): + termine zoomFovKick
- tint: i quad copiano il tint sky corrente (applyDirector index.html:2184, incluso
  boost live 1.06) e lerpano verso neutro nei livelli profondi
- manifests (levels.json, sky-gc.json) caricati lazy al primo cadutaZoom(); assenti → no-op

API: `window.cadutaZoom({dur=90, mode='once', k})`, `window.cadutaZoomStop()`.
NIENTE evento chat, niente trigger automatico del Director (per ora: solo manuale).

Vincoli 24/7 (obbligatori): zero allocazioni per-frame (scratch riusati); timer su dt
accumulato (mai Date.now/shaderTime non wrappato); ogni load con retry/skip; funziona a
PIX=2 finestra e PIX=1 4K nativo (?rec=1); nessuna nuova texture residente a riposo.

## 5. Verifica

1. Contact sheet builder (--contact): ogni livello con il footprint del successivo → allineamento a occhio + eventuale offset fine in zoom-config.json
2. Marker test: sferetta a direzione GC ×5900 → screenshot → deve sedersi sul bulge (per ognuno di 3-4 sfondi diversi via cadutaSky(i))
3. Dive completo con screenshot a t=2,10,25,40,55,70,85: nitidezza (mai "mush"), crossfade senza salti, console pulita
4. Stress: 2 dive consecutivi + abort a metà → renderer.info.memory.textures torna al valore pre-dive (no leak)

## 6. Crediti (CREDITS.md da aggiornare al commit)

ESO CC BY 4.0: ESO/S. Brunier; ESO/S. Guisard (gigagalaxyzoom.org); ESO/VVV Survey/D. Minniti,
ack. I. Toledo, M. Kornmesser; ESO/Nogueras-Lara et al. (HAWK-I). NASA/Goddard SVS (Deep Star Maps 2020).
