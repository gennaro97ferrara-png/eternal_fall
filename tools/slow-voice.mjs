#!/usr/bin/env node
// ─────────────────────────────────────────────────────────────────────────────
// slow-voice.mjs — rallenta TUTTE le capsule (assets/voice/cap_*.mp3) di un fattore,
// preservando il tono (ffmpeg atempo). Da lanciare UNA VOLTA a fine generazione.
//
// È IDEMPOTENTE: tiene traccia dei file già rallentati in assets/voice/.slowed.json,
// quindi rilanciarlo NON li rallenta due volte (rallenta solo i nuovi).
//
// USO:   node tools/slow-voice.mjs            (default 0.85 = 15% più lento)
//        SPEED=0.8 node tools/slow-voice.mjs  (più lento)
//        SPEED=0.9 node tools/slow-voice.mjs  (meno lento)
// Richiede ffmpeg nel PATH.
// ─────────────────────────────────────────────────────────────────────────────
import { readdir, readFile, writeFile, rm, rename, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
const pexec = promisify(execFile);

const VDIR = join(dirname(fileURLToPath(import.meta.url)), '..', 'assets', 'voice');
const MARK = join(VDIR, '.slowed.json');
const SPEED = +(process.env.SPEED || 0.85);   // <1 = più lento; atempo regge 0.5–2.0 in un passaggio

async function main() {
  if (SPEED <= 0 || SPEED > 1) { console.error('SPEED deve essere tra 0.5 e 1.0 (es. 0.85).'); process.exit(1); }
  let done = {};
  if (existsSync(MARK)) { try { done = JSON.parse(await readFile(MARK, 'utf8')) || {}; } catch {} }

  const files = (await readdir(VDIR)).filter(f => /^cap_.*\.mp3$/.test(f)).sort();
  let slowed = 0, skipped = 0, failed = 0;
  for (const f of files) {
    if (done[f] === SPEED) { skipped++; continue; }   // già rallentato a QUESTA velocità
    const p = join(VDIR, f), tmp = p + '.slow.mp3';
    try {
      await pexec('ffmpeg', ['-y', '-loglevel', 'error', '-i', p, '-filter:a', 'atempo=' + SPEED, '-q:a', '4', tmp]);
      if ((await stat(tmp)).size > 256) { await rm(p); await rename(tmp, p); done[f] = SPEED; slowed++; }
      else { await rm(tmp).catch(() => {}); failed++; }
    } catch (e) { failed++; await rm(tmp).catch(() => {}); console.warn('  ✗', f, e.message.slice(0, 80)); }
    if (slowed % 50 === 0 && slowed) { await writeFile(MARK, JSON.stringify(done)); process.stdout.write(`  …${slowed} rallentati\n`); }
  }
  await writeFile(MARK, JSON.stringify(done));
  console.log(`✓ rallentati ${slowed} a ${SPEED}× | già fatti ${skipped} | falliti ${failed} | totale cap_*.mp3 ${files.length}`);
}
main().catch(e => { console.error('✗', e.message); process.exit(1); });
