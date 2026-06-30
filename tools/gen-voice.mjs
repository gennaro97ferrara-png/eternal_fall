#!/usr/bin/env node
// ─────────────────────────────────────────────────────────────────────────────
// gen-voice.mjs — genera la VOCE del documentario "Eternal Fall" con ElevenLabs.
//
// Sorgente di verità:  assets/voice/capsules.json   (testo + categoria + tipo)
// Output:              assets/voice/cap_<id>.mp3     (un MP3 per capsula)
//                      assets/voice/voice.json       (manifest letto dalla live)
//
// È IDEMPOTENTE: salta gli MP3 già presenti → aggiungere capsule e rilanciare
// costa solo le righe nuove. Le 16 righe-cronaca esistenti (v01..v16) NON vengono
// toccate: vengono preservate nel manifest come strato "anima" (kind:chronicle).
//
// USO:
//   ELEVENLABS_API_KEY=sk-... VOICE_ID=<id_voce> node tools/gen-voice.mjs
// opzioni (env):
//   MODEL_ID   (default eleven_multilingual_v2)
//   FORMAT     (default mp3_44100_128)
//   STABILITY  (default 0.45)  SIMILARITY (default 0.75)  STYLE (default 0.0)
//   ONLY=space,earth   genera solo certe categorie
//   DRY=1      non chiama l'API: ricostruisce solo voice.json dai mp3 già presenti
// ─────────────────────────────────────────────────────────────────────────────
import { readFile, writeFile, readdir, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const VDIR = join(ROOT, 'assets', 'voice');
const SRC  = join(VDIR, 'capsules.json');
const OUT  = join(VDIR, 'voice.json');

const API_KEY = process.env.ELEVENLABS_API_KEY || process.env.ELEVEN_API_KEY || '';
// Voce di Eternal Fall = "Brian - Deep, Resonant and Comforting" (verificata dalla History ElevenLabs delle v01-v16).
// NON si usa ELEVEN_VOICE_ID della factory (= "Daniel", diverso): default a Brian, override solo con VOICE_ID esplicito.
const EF_VOICE_ID = 'nPczCjzI2devNBz1zQrb';
const VOICE_ID = process.env.VOICE_ID || EF_VOICE_ID;
const MODEL_ID = process.env.MODEL_ID || 'eleven_multilingual_v2';            // stesso modello della factory (1 credito/carattere)
const FORMAT   = process.env.FORMAT   || 'mp3_44100_128';
const DRY = process.env.DRY === '1';
const ONLY = (process.env.ONLY || '').split(',').map(s => s.trim()).filter(Boolean);
// impostazioni voce IDENTICHE alla factory (generate_voiceover.py): consegna viva ma documentaristica
const VS = { stability: +(process.env.STABILITY ?? 0.42), similarity_boost: +(process.env.SIMILARITY ?? 0.78), style: +(process.env.STYLE ?? 0.3), use_speaker_boost: true };

const sleep = ms => new Promise(r => setTimeout(r, ms));
const slug = s => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 48);

async function tts(text, outPath) {
  const url = `https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}?output_format=${FORMAT}`;
  for (let attempt = 1; attempt <= 4; attempt++) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'xi-api-key': API_KEY, 'content-type': 'application/json', accept: 'audio/mpeg' },
      body: JSON.stringify({ text, model_id: MODEL_ID, voice_settings: VS }),
    });
    if (res.ok) { const buf = Buffer.from(await res.arrayBuffer()); await writeFile(outPath, buf); return buf.length; }
    const body = await res.text().catch(() => '');
    if (res.status === 429 || res.status >= 500) { const wait = 2000 * attempt; console.warn(`  ↻ ${res.status}, retry in ${wait}ms`); await sleep(wait); continue; }
    throw new Error(`ElevenLabs ${res.status}: ${body.slice(0, 300)}`);
  }
  throw new Error('TTS failed after retries');
}

async function main() {
  if (!existsSync(SRC)) { console.error(`Manca ${SRC}. Crea capsules.json (array di {id,text,cat,kind,tag?,attribution?}).`); process.exit(1); }
  const capsules = JSON.parse(await readFile(SRC, 'utf8'));
  if (!Array.isArray(capsules) || !capsules.length) { console.error('capsules.json vuoto o non è un array.'); process.exit(1); }
  if (!DRY && (!API_KEY || !VOICE_ID)) { console.error('Servono ELEVENLABS_API_KEY e VOICE_ID (oppure DRY=1 per solo-manifest).'); process.exit(1); }

  // 1) preserva le righe-cronaca esistenti dal vecchio manifest (tutto ciò che non è una capsula cap_*)
  let chronicle = [];
  if (existsSync(OUT)) {
    try { const prev = JSON.parse(await readFile(OUT, 'utf8'));
      chronicle = (Array.isArray(prev) ? prev : []).filter(e => e && e.file && !/^cap_/.test(e.file))
        .map(e => ({ ...e, kind: e.kind || 'chronicle' }));
    } catch {}
  }
  if (!chronicle.length) {
    // primo giro: deduci la cronaca dai v*.mp3 presenti (senza testo non possiamo, quindi avvisa)
    const files = (await readdir(VDIR)).filter(f => /^v\d+\.mp3$/i.test(f));
    if (files.length) console.warn(`(nota) trovati ${files.length} file cronaca v*.mp3 ma nessun voice.json: verranno reinclusi solo se erano nel manifest.`);
  }

  // 2) genera gli MP3 mancanti per ogni capsula
  let made = 0, skipped = 0, idx = 0;
  const manifest = [];
  for (const c of capsules) {
    idx++;
    const id = slug(c.id || `${c.cat || 'cap'}_${idx}`);
    if (ONLY.length && !ONLY.includes(c.cat)) continue;
    const file = `cap_${id}.mp3`;
    const outPath = join(VDIR, file);
    const exists = existsSync(outPath) && (await stat(outPath)).size > 256;
    const entry = { file, text: c.text, kind: c.kind || 'capsule', cat: c.cat || 'strange', id };
    if (c.tag) entry.tag = c.tag;
    if (c.attribution) entry.attribution = c.attribution;
    if (c.title) entry.title = c.title;
    if (c.tagline) entry.tagline = c.tagline;
    manifest.push(entry);
    if (exists) { skipped++; continue; }
    if (DRY) { console.warn(`  · manca ${file} (DRY: non generato)`); continue; }
    process.stdout.write(`  ♪ ${file}  «${(c.text || '').slice(0, 48)}…»`);
    const bytes = await tts(c.text, outPath);
    console.log(`  (${(bytes / 1024) | 0} KB)`);
    made++;
    await sleep(350); // gentile con i rate-limit
  }

  // 3) scrivi il manifest: prima le capsule (documentario), poi la cronaca (anima)
  const finalLib = [...manifest, ...chronicle];
  await writeFile(OUT, JSON.stringify(finalLib, null, 2) + '\n', 'utf8');
  const byCat = {}; for (const e of manifest) byCat[e.cat] = (byCat[e.cat] || 0) + 1;
  console.log(`\n✓ voice.json: ${finalLib.length} righe  (capsule ${manifest.length}, cronaca ${chronicle.length})`);
  console.log(`  generati ${made}, già presenti ${skipped}.  per categoria:`, byCat);
  if (DRY) console.log('  (DRY) nessuna chiamata API effettuata.');
}

main().catch(e => { console.error('\n✗', e.message); process.exit(1); });
