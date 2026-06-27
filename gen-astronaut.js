#!/usr/bin/env node
/*
  gen-astronaut.js — genera un nuovo astronauta con fal.ai (immagine → 3D) e lo salva
  in assets/astronaut.glb (fa un backup del precedente). Zero dipendenze (solo Node).

  USO:
    export FAL_KEY=la-tua-chiave-fal     # NON la committare
    node gen-astronaut.js

  OPZIONI (variabili d'ambiente):
    GEN3D=rodin|hunyuan|trellis          # modello image-to-3D (default: rodin = miglior per personaggi)
    PROMPT="..."                         # sovrascrive il prompt dell'immagine
    IMAGE_URL=https://...                # salta FLUX e usa una tua immagine già pronta

  NOTE:
    - Il prompt genera l'astronauta DI SPALLE (è ciò che si vede), TESTA ben visibile e
      ZAINO PICCOLO. La schiena verrà dettagliata; il davanti (mai visto) può restare grezzo.
    - Se un modello cambia nomi dei campi, lo script stampa il JSON grezzo del risultato
      così puoi vedere dov'è l'URL del .glb e adattare la funzione mesh() qui sotto.
*/
const https = require('https');
const fs = require('fs');
const path = require('path');

const FAL_KEY = process.env.FAL_KEY;
if (!FAL_KEY) { console.error('✗ Manca FAL_KEY.  Esegui:  export FAL_KEY=la-tua-chiave'); process.exit(1); }

const OUT = path.join(__dirname, 'assets', 'astronaut.glb');
const IMG_MODEL = 'fal-ai/flux-pro/v1.1';
const PROMPT = process.env.PROMPT ||
  "full-body astronaut floating in deep space, seen from directly behind, the head and helmet clearly visible and prominent above a SLIM low-profile life-support pack (small backpack, not bulky), clean white EVA spacesuit with subtle paneling, the words 'I FALL' printed across the upper back, arms relaxed slightly outward, legs together drifting, plain neutral grey studio background, soft even lighting, photorealistic, sharp focus, centered, whole body in frame";

// preset image-to-3D: id del modello + come passare l'immagine + come leggere l'URL del .glb
const THREEDB = {
  rodin:   { id:'fal-ai/hyper3d/rodin', input: img => ({ input_image_urls:[img], geometry_file_format:'glb', material:'PBR', quality:'medium' }), mesh: r => r.model_mesh && r.model_mesh.url },
  hunyuan: { id:'fal-ai/hunyuan3d/v2',  input: img => ({ input_image_url: img }),  mesh: r => r.model_mesh && r.model_mesh.url },
  trellis: { id:'fal-ai/trellis',       input: img => ({ image_url: img }),        mesh: r => r.model_mesh && r.model_mesh.url },
};
const GEN3D_NAME = process.env.GEN3D || 'rodin';
const GEN3D = THREEDB[GEN3D_NAME];
if (!GEN3D) { console.error('✗ GEN3D sconosciuto:', GEN3D_NAME, '— usa rodin|hunyuan|trellis'); process.exit(1); }

function req(method, url, body) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const data = body ? JSON.stringify(body) : null;
    const r = https.request({
      hostname: u.hostname, path: u.pathname + u.search, method,
      headers: { 'Authorization': 'Key ' + FAL_KEY, 'Content-Type': 'application/json',
        ...(data ? { 'Content-Length': Buffer.byteLength(data) } : {}) },
    }, resp => {
      let b = ''; resp.on('data', c => b += c);
      resp.on('end', () => {
        if (resp.statusCode >= 400) return reject(new Error('HTTP ' + resp.statusCode + ': ' + b));
        try { resolve(b ? JSON.parse(b) : {}); } catch (e) { reject(new Error('JSON non valido: ' + b.slice(0, 300))); }
      });
    });
    r.on('error', reject); if (data) r.write(data); r.end();
  });
}

async function runQueue(model, input) {
  console.log('  → submit', model);
  const sub = await req('POST', 'https://queue.fal.run/' + model, input);
  const statusUrl = sub.status_url, respUrl = sub.response_url;
  if (!statusUrl || !respUrl) throw new Error('risposta inattesa: ' + JSON.stringify(sub));
  let tries = 0;
  for (;;) {
    await new Promise(r => setTimeout(r, 3000));
    const st = await req('GET', statusUrl);
    process.stdout.write('    ' + st.status + (st.queue_position != null ? ' (#' + st.queue_position + ')' : '') + '          \r');
    if (st.status === 'COMPLETED') break;
    if (st.status === 'FAILED' || st.status === 'ERROR') throw new Error('generazione fallita: ' + JSON.stringify(st));
    if (++tries > 300) throw new Error('timeout (troppo lunga)');
  }
  process.stdout.write('\n');
  return await req('GET', respUrl);
}

function download(url, dest) {
  return new Promise((resolve, reject) => {
    const f = fs.createWriteStream(dest);
    https.get(url, r => {
      if (r.statusCode >= 400) { reject(new Error('download HTTP ' + r.statusCode)); return; }
      r.pipe(f); f.on('finish', () => f.close(resolve));
    }).on('error', reject);
  });
}

(async () => {
  try {
    fs.mkdirSync(path.join(__dirname, 'assets'), { recursive: true });

    let imageUrl = process.env.IMAGE_URL;
    if (!imageUrl) {
      console.log('1) Genero l\'immagine (FLUX)…');
      const img = await runQueue(IMG_MODEL, { prompt: PROMPT, image_size: 'portrait_4_3', num_images: 1, output_format: 'jpeg' });
      imageUrl = img.images && img.images[0] && img.images[0].url;
      if (!imageUrl) throw new Error('nessun URL immagine: ' + JSON.stringify(img).slice(0, 300));
      console.log('   immagine:', imageUrl);
      console.log('   (aprila per controllarla: se non ti piace, rilancia o cambia PROMPT)');
    } else {
      console.log('1) Uso la tua IMAGE_URL:', imageUrl);
    }

    console.log('2) Converto in 3D con', GEN3D_NAME, '…');
    const out = await runQueue(GEN3D.id, GEN3D.input(imageUrl));
    const glb = GEN3D.mesh(out);
    if (!glb) { console.log('Risultato 3D (cerca qui l\'URL del .glb e adatta mesh()):\n', JSON.stringify(out, null, 2)); throw new Error('URL del .glb non trovato'); }
    console.log('   modello:', glb);

    if (fs.existsSync(OUT)) { fs.copyFileSync(OUT, OUT.replace(/\.glb$/, '.backup.glb')); console.log('   (backup → astronaut.backup.glb)'); }
    console.log('3) Scarico →', OUT);
    await download(glb, OUT);
    const kb = Math.round(fs.statSync(OUT).size / 1024);
    console.log('✓ Fatto (' + kb + ' KB). Ricarica la live e dimmi com\'è — lo illumino e ci metto "I FALL".');
  } catch (e) {
    console.error('\n✗ ERRORE:', e.message);
    process.exit(1);
  }
})();
