# Caduta Eterna

Live visiva immersiva e **infinita**: un uomo, sempre di spalle, che precipita per sempre
nell'universo. Generata in tempo reale (WebGL / Three.js) usando **asset reali** per il
fotorealismo: la Via Lattea vera come sfondo e come mappa di riflessi, pianeti con texture
NASA/CC, modello d'astronauta retroilluminato come silhouette solenne. Nessun video, nessun
loop, nessuno stacco: il cosmo è procedurale e non si ripete mai. Costo di generazione **zero**.

## Come avviarla

I moduli ES e gli asset locali non si caricano da `file://` (blocco CORS): serve un mini
server locale. Dalla cartella `caduta-eterna/`:

```bash
python3 -m http.server 8080        # oppure:  npx --yes serve -l 8080 .
```

Apri **http://localhost:8080**, schermo intero con **F**, e premi **Entra** (il click attiva
l'audio: lo richiede il browser). Scorciatoia macOS: doppio click su `serve.command`.

> Three.js viene caricato da CDN (unpkg, versione fissata) al primo avvio e poi resta in
> cache. Gli asset pesanti (Via Lattea, astronauta, pianeti) sono **in locale** in `assets/`,
> quindi la live non dipende da una CDN per le immagini. Se vuoi azzerare ogni dipendenza di
> rete a runtime posso vendorizzare anche Three.js in locale: chiedimelo.

## Asset (cartella `assets/`)

| File | Cosa | Fonte / licenza |
|---|---|---|
| `milkyway_8k.jpg` (6000×3000) | sfondo equirettangolare + riflessi IBL | ESO / S. Brunier — CC BY 4.0 |
| `astronaut.glb` | il modello dell'uomo | Poly by Google (`<model-viewer>`) — CC BY |
| `2k_*.jpg` + `2k_saturn_ring_alpha.png` | texture pianeti + anelli | Solar System Scope — CC BY 4.0 |

I crediti sono mostrati in piccolo in basso a destra (richiesto dalle licenze CC BY).

## Generare un nuovo astronauta (fal.ai)

Script `gen-astronaut.js` (zero dipendenze): genera con fal.ai un astronauta **immagine → 3D**
e salva `assets/astronaut.glb` (fa il backup del precedente). Prompt già tarato su **testa ben
visibile / zaino piccolo**, visto **di spalle**.

```bash
export FAL_KEY=la-tua-chiave-fal        # NON committarla
node gen-astronaut.js                    # FLUX → Rodin (default)
# varianti:
GEN3D=hunyuan node gen-astronaut.js      # modello 3D alternativo
PROMPT="..." node gen-astronaut.js       # prompt personalizzato
IMAGE_URL=https://... node gen-astronaut.js   # salta FLUX, usa una tua immagine
```

Poi ricarica la live. Se il `.glb` ti piace, lo illumino come tuta piena e ci stampo **"I FALL"**.
Le braccia/gambe ora si muovono già con un'**animazione procedurale** (nuotata/forbice in
caduta libera). Per arti **veramente articolati** (scheletro vero) → ricetta **Mixamo** (gratis):

1. Vai su **mixamo.com** (login Adobe).
2. **Upload Character** → carica `assets/astronaut.glb` (o l'`.fbx`).
3. Posiziona i marker dell'**Auto-Rigger** (mento, polsi, gomiti, ginocchia, inguine) → *Next*.
4. Scegli un'animazione: cerca **"Floating"**, **"Treading Water"** o **"Falling Idle"**.
5. **Download** → Format **glTF (.glb)**, *With Skin*.
6. Salva come `caduta-eterna/assets/astronaut.glb`, **bumpa `?v=`** in `index.html`, ricarica.

Il codice rileva l'animazione e la riproduce da solo (AnimationMixer), spegnendo quella
procedurale. Niente da modificare a mano.

## L'astronauta: silhouette voluta

Il modello gratuito disponibile è pulito ma **non fotorealistico** da vicino. Per questo è
**retroilluminato dal cosmo** e reso come silhouette scura col bordo luminoso: è l'aspetto più
realistico e cinematografico ottenibile, e centra il "misterioso e solenne / minuscolo davanti
all'immensità" del brief, nascondendo i limiti del modello.

👉 **Vuoi vederlo come tuta dettagliata e illuminata?** Procurati un modello d'astronauta
fotorealistico (`.glb` con mappe PBR — da Sketchfab/Meshy/CGTrader col tuo account) e mettilo
in `assets/astronaut.glb`. Poi alza `envMapIntensity` (~1.0), il fill `rimLight` e abbassa la
retroilluminazione: te lo riconfiguro io se vuoi.

## Diario di bordo (telemetria perenne)

In alto a sinistra, sempre visibile, una telemetria che dimostra che il viaggio è **davvero**
perenne:
- **GIORNO N · hh:mm:ss** — ancorato a una data reale salvata in `localStorage` (`ce_launch`);
  sopravvive ai riavvii di OBS, quindi i giorni contano davvero da quando hai lanciato la live.
- **DISTANCE** — odometro adattivo che si muove a vista: `km → M km → B km → light-years`.
- **pianeti · stelle · meteoriti · lune · buchi neri** incontrati (icone SVG, persistiti).
- **COMPAGNI** — gli spettatori che hanno acceso una stella (cresce in Fase B con la chat).

> Per OBS: in *Proprietà sorgente browser* lascia **disattivato** "Aggiorna browser quando la
> scena diventa attiva" così il `localStorage` (e quindi GIORNO N) non si azzera.

## Novità grafiche

- **Pianeti fotorealistici**: texture reali **4K**, strato **nuvole** sulla Terra, anelli,
  atmosfera, lune. La luce-chiave **orbita lentamente** → i pianeti si vedono a volte
  pienamente illuminati (superficie nitida) e a volte a falce drammatica.
- **I pianeti non spuntano più**: nascono lontanissimi e *arrivano* dal profondo (dissolvenza
  + avvicinamento lungo, ~1–2 min).
- **Il Sole**: passaggio raro vicino a una stella emissiva con **lens flare** — l'uomo in
  silhouette contro il sole è il momento clou.
- **Buchi neri** (raro): event horizon + disco di accrescimento + photon ring + **lensing
  gravitazionale** (lo sfondo si curva attorno al buco nero, stile Interstellar).
- **Interfaccia in inglese**, pannello "SHIP'S LOG" ordinato con **icone SVG** (niente emoji);
  qualità immagine più alta (pixelRatio fino a 2.0, anisotropia max, geometria più fine).
- **Galassie** lontane (spirali) che derivano sullo sfondo; **pianeti più distanti** (non
  invadono la scena); **asteroidi/relitti più dettagliati**.
- **Luce/ombre di scena**: l'astronauta è illuminato dal corpo luminoso vicino (un Sole lo
  scalda da quella direzione) e tinto dal colore della regione.
- **Astronauta**: modello fotoreale (generato con `gen-astronaut.js`), visore scuro (nessun
  volto) → **caduta libera lenta**: ruota su un asse inclinato e gli **arti ondeggiano**
  (animazione procedurale). Mostra la sua scritta "I FALL".
- **Meteoriti realistici**: texture di roccia vera (generata con fal.ai, `gen-image.js`)
  applicata in **triplanar** agli asteroidi → pietre cratterizzate, non blob marroni.
- **Attraversare le nebulose**: durante le regioni nebulosa entri *dentro* nuvole colorate
  che ti avvolgono (immersione), non solo le vedi passare.
- **Nuovi corpi**: **comete** (coda via dal sole), **ammassi globulari**, **pulsar** (fari
  rotanti), **giganti rosse** morenti, **sistemi binari**, **resti di supernova** che attraversi.
- **Piogge di meteore su date reali** (Perseidi ad agosto, Geminidi a dicembre…) → il cielo
  si accende davvero in quei giorni.
- **Strutture & mistero**: **relitti** di navi alla deriva e **monoliti** ("una forma troppo
  perfetta per essere naturale"); il mistero lontano mai raggiunto; il **viaggiatore parallelo**.
- **Dilatazione del tempo**: vicino a un buco nero il mondo **rallenta** e l'orologio "sfasa"
  (il GIORNO resta però ancorato al tempo reale). La musica si fa cupa.
- **Musica reattiva**: si gonfia vicino ai pianeti, diventa un rombo cupo vicino ai buchi neri,
  brilla durante le supernovae.
- **Eventi/anniversari**: supernovae rare; al GIORNO 1/7/30/100/365… il cielo lo "festeggia".
- **Regia**: la camera fa *incombere* i pianeti vicini; esposizione adattiva; raffiche di velocità.
- **Auto-scaler**: se il PC scende sotto i ~46 fps, abbassa da solo qualità/risoluzione → niente
  scatti sulla live. Telemetria leggibile anche da mobile.

### Test rapidi (console del browser, F12)
```js
cadutaDebugPlanet()       // pianeta ravvicinato (casuale)
cadutaDebugPlanet(true)   // il Sole (con lens flare)
cadutaDebugPlanet(false,5)// pianeta per indice (5=Terra, 0=Giove, 1=Saturno, 9=Sole)
cadutaDebugEvent('mystery'|'parallel'|'nova'|'blackhole'|'comet'|'cluster'|'wreck'|'mono'|'nebula')
cadutaAddStar('un nome')  // accende subito una stella del pubblico (lo farà la chat in Fase B)
```

## Le "regioni" del viaggio

Un *director* interpola dolcemente tra mood cosmici (galassia, vuoto, nebulosa, pianeta,
cintura d'asteroidi, brace, gelo, abisso): luce, esposizione, colore, nebbie colorate,
densità di pianeti/asteroidi/polvere, audio. Transizioni 18–32 s, permanenze 34–120 s +
jitter → **non si ripete mai**. La Via Lattea reale ruota lentissima = senso di viaggio.

## Setup per la live YouTube (OBS)

1. **Sorgente → Browser**, URL `http://localhost:8080`, **1920×1080** (o 2560×1440), **60 FPS**.
2. ✅ *Controlla la sorgente quando non è visibile*.
3. **Interagisci** una volta nella finestra per far partire l'audio.
4. *Impostazioni → Avanzate → Sorgenti browser → Accelerazione hardware* attiva.

L'audio (sintetizzato, sempre diverso) entra da solo nel mix di OBS.

## Regolare (in `index.html`)

| Cosa | Dove |
|---|---|
| Luce dell'uomo (silhouette ↔ tuta visibile) | `keyLight` / `rimLight` / `AmbientLight` in `build()`, `envMapIntensity` nel `man.traverse` |
| Mood/colori delle regioni | array `PRESETS` |
| Durata regioni / transizioni | `Director.step` (`this.dur`, `this.hold`) |
| Velocità del viaggio | `speed` nei preset |
| Dimensione dell'uomo in scena | `1.95/size.y` in `build()` e `targetDist` nel loop |
| Bagliore / grana / vignetta | `bloomPass`, `CineShader.uniforms` |
| Volume / carattere audio | classe `AmbientEngine` |

## Prestazioni / 24-7

- 60 FPS, ~12 MB heap nel test. Coordinate sempre limitate (oggetti riciclati) + tempo shader
  con wrap → nessun degrado di precisione/float anche dopo ore.
- `pixelRatio` ≤ 1.75, `dt` clampato, nessuna allocazione pesante nel loop caldo.
- GPU integrate: abbassa la risoluzione OBS o `DUST_N` / `AST_N`.
