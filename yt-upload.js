#!/usr/bin/env node
/* ============================================================================
   Eternal Fall — upload di un video su YouTube (Data API v3, upload resumable).
   Zero dipendenze. Carica un mp4 come VIDEO NORMALE (non live).

   Prerequisiti (una volta sola): OAuth configurato nel .env
     YT_OAUTH_CLIENT_ID=...
     YT_OAUTH_CLIENT_SECRET=...
     YT_OAUTH_REFRESH_TOKEN=...      (generato da get-token.js)
   Scope richiesto sul token: https://www.googleapis.com/auth/youtube.upload

   Uso:
     node --env-file=.env yt-upload.js <file.mp4> "Titolo" ["Descrizione"] [privacy]
     privacy = private | unlisted | public   (default: unlisted)

   Stampa l'URL del video caricato.
   ============================================================================ */
'use strict';
const fs = require('fs');
const https = require('https');
const path = require('path');

// carica .env minimale (se presente) — così basta `node yt-upload.js ...` senza --env-file
try {
  const p = path.join(__dirname, '.env');
  if (fs.existsSync(p)) for (const line of fs.readFileSync(p, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
} catch (e) {}

const [,, FILE, TITLE, DESC = '', PRIVACY = 'unlisted'] = process.argv;
const CID = process.env.YT_OAUTH_CLIENT_ID;
const CSEC = process.env.YT_OAUTH_CLIENT_SECRET;
const RTOK = process.env.YT_OAUTH_REFRESH_TOKEN;

function die(m){ console.error('ERRORE: ' + m); process.exit(1); }
if (!FILE || !TITLE) die('uso: node --env-file=.env yt-upload.js <file.mp4> "Titolo" ["Descrizione"] [private|unlisted|public]');
if (!fs.existsSync(FILE)) die('file non trovato: ' + FILE);
if (!CID || !CSEC || !RTOK) die('mancano le credenziali OAuth nel .env (YT_OAUTH_CLIENT_ID / _SECRET / _REFRESH_TOKEN). Genera il refresh token con: node --env-file=.env get-token.js');

// --- 1) refresh_token -> access_token ---
function accessToken() {
  return new Promise((res, rej) => {
    const body = new URLSearchParams({ client_id: CID, client_secret: CSEC, refresh_token: RTOK, grant_type: 'refresh_token' }).toString();
    const req = https.request('https://oauth2.googleapis.com/token', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'Content-Length': Buffer.byteLength(body) } }, r => {
      let d = ''; r.on('data', c => d += c); r.on('end', () => {
        try { const j = JSON.parse(d); j.access_token ? res(j.access_token) : rej(new Error('token: ' + d)); } catch (e) { rej(e); }
      });
    });
    req.on('error', rej); req.end(body);
  });
}

// --- 2) avvia sessione resumable (metadati) -> upload URL ---
function startSession(token) {
  return new Promise((res, rej) => {
    const meta = JSON.stringify({
      snippet: { title: TITLE.slice(0, 100), description: DESC.slice(0, 4900), categoryId: '28' /* Science & Technology */ },
      status: { privacyStatus: ['private','unlisted','public'].includes(PRIVACY) ? PRIVACY : 'unlisted', selfDeclaredMadeForKids: false }
    });
    const size = fs.statSync(FILE).size;
    const req = https.request('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json; charset=UTF-8',
        'Content-Length': Buffer.byteLength(meta),
        'X-Upload-Content-Type': 'video/*',
        'X-Upload-Content-Length': size
      }
    }, r => {
      let d = ''; r.on('data', c => d += c); r.on('end', () => {
        if (r.statusCode === 200 && r.headers.location) res({ url: r.headers.location, size });
        else rej(new Error('start ' + r.statusCode + ': ' + d));
      });
    });
    req.on('error', rej); req.end(meta);
  });
}

// --- 3) PUT del file (con barra di avanzamento) ---
function putFile(uploadUrl, size) {
  return new Promise((res, rej) => {
    const u = new URL(uploadUrl);
    const req = https.request(u, { method: 'PUT', headers: { 'Content-Type': 'video/*', 'Content-Length': size } }, r => {
      let d = ''; r.on('data', c => d += c); r.on('end', () => {
        try { const j = JSON.parse(d); j.id ? res(j.id) : rej(new Error('put ' + r.statusCode + ': ' + d)); } catch (e) { rej(new Error('put ' + r.statusCode + ': ' + d)); }
      });
    });
    req.on('error', rej);
    let sent = 0, last = 0;
    const rs = fs.createReadStream(FILE);
    rs.on('data', c => { sent += c.length; const pct = Math.floor(sent / size * 100); if (pct >= last + 5) { last = pct; process.stderr.write('  upload ' + pct + '%\r'); } });
    rs.pipe(req);
  });
}

(async () => {
  try {
    console.error('· autorizzo…');
    const token = await accessToken();
    console.error('· avvio sessione…  (' + (fs.statSync(FILE).size / 1048576).toFixed(1) + ' MB, privacy: ' + PRIVACY + ')');
    const { url, size } = await startSession(token);
    console.error('· carico il video…');
    const id = await putFile(url, size);
    console.error('');
    console.log('OK  https://youtu.be/' + id + '   (Studio: https://studio.youtube.com/video/' + id + '/edit)');
  } catch (e) { die(e.message); }
})();
