#!/usr/bin/env node
/* ============================================================================
   Eternal Fall — bridge server (zero dipendenze, Node 18+)

   Serve il sito statico E l'endpoint /api/stars che il frontend già interroga
   (index.html → pollCatalog ogni 10s). Per ogni persona del pubblico accende
   una stella col suo nome:
     • CHAT dal vivo  → ogni autore che scrive in chat (nome sempre disponibile)
     • MEMBRI / Super Chat → riconosciuti dagli eventi di chat
     • ISCRITTI RECENTI → polling best-effort (molti nascondono l'iscrizione)

   Avvio:   node server.js        (oppure: node --env-file=.env server.js)
   Config:  via variabili d'ambiente o file .env (vedi .env.example).
   Senza credenziali YouTube il server funziona lo stesso: serve il sito e
   /api/stars resta vuoto, quindi la live gira anche offline.
   ============================================================================ */
'use strict';
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const url = require('url');

/* ---------- config / .env minimale ---------- */
(function loadDotEnv(){
  try {
    const p = path.join(__dirname, '.env');
    if (!fs.existsSync(p)) return;
    for (const line of fs.readFileSync(p, 'utf8').split('\n')) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
      if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
    }
  } catch (e) {}
})();
const CFG = {
  PORT: parseInt(process.env.PORT || '8099', 10),
  ROOT: __dirname,
  API_KEY: process.env.YT_API_KEY || '',
  VIDEO_ID: process.env.YT_VIDEO_ID || '',
  LIVE_CHAT_ID: process.env.YT_LIVE_CHAT_ID || '',
  CLIENT_ID: process.env.YT_OAUTH_CLIENT_ID || '',
  CLIENT_SECRET: process.env.YT_OAUTH_CLIENT_SECRET || '',
  REFRESH_TOKEN: process.env.YT_OAUTH_REFRESH_TOKEN || '',
  CHAT: process.env.YT_CHAT !== '0',          // default on se configurabile
  SUBS: process.env.YT_SUBS !== '0',
  DEDUP_MS: parseInt(process.env.STAR_DEDUP_MS || '900000', 10), // un nome non si ripete entro 15 min
};

/* ---------- store delle stelle ---------- */
const events = [];            // {name, key, ts}
const lastSeenByKey = new Map();
let companions = 0;
const STORE_MAX = 5000;

function addStar(name, key) {
  name = String(name || '').trim().slice(0, 40);
  if (!name) return false;
  key = key || ('name:' + name.toLowerCase());
  const now = Date.now();
  const prev = lastSeenByKey.get(key);
  if (prev && now - prev < CFG.DEDUP_MS) return false;   // anti-spam / anti-doppione
  lastSeenByKey.set(key, now);
  events.push({ name, key, ts: now });
  if (events.length > STORE_MAX) events.splice(0, events.length - STORE_MAX);
  companions++;
  log('★ stella:', name);
  return true;
}

/* ---------- comandi dalla chat ---------- */
const commands = [];                     // {cmd, arg, user, ts}
const cmdCooldown = new Map();           // channelId -> lastTs
const CMD_USER_CD = 60000;               // 60s per utente
const CMD_FREE = new Set(['star', 'light', 'message', 'comet', 'wish', 'whales', 'aurora', 'help']);
const CMD_SUB  = new Set(['world', 'nebula', 'blackhole']);   // riservati a iscritti/membri/mod
const CMD_ADMIN = new Set(['musicnext', 'musicpause', 'musicplay']);   // solo pannello regia, mai dalla chat
const BADWORDS = (process.env.STAR_BADWORDS || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
function cleanArg(s) { return String(s || '').replace(/[\u0000-\u001f\u007f]/g, '').replace(/https?:\/\/\S+/gi, '').replace(/\s+/g, ' ').trim().slice(0, 40); }
function isBad(s) { const t = String(s).toLowerCase(); return BADWORDS.some(w => t.includes(w)); }
function parseCommand(text, author) {
  const m = /^!\s*([a-z]+)\b\s*([\s\S]*)$/i.exec(text || ''); if (!m) return;
  const cmd = m[1].toLowerCase(); const arg = cleanArg(m[2]);
  if (!CMD_FREE.has(cmd) && !CMD_SUB.has(cmd)) return;               // comando sconosciuto
  const isSub = !!(author.isChatSponsor || author.isChatModerator || author.isChatOwner);
  if (CMD_SUB.has(cmd) && !isSub) return;                           // riservato agli iscritti
  if (arg && isBad(arg)) return;                                    // moderazione
  const cid = author.channelId || author.displayName || '?';
  const now = Date.now();
  if (now - (cmdCooldown.get(cid) || 0) < CMD_USER_CD) return;      // cooldown per utente
  cmdCooldown.set(cid, now);
  commands.push({ cmd, arg, user: String(author.displayName || '').slice(0, 40), ts: now });
  if (commands.length > 500) commands.splice(0, commands.length - 500);
  log('▸ comando:', cmd, arg || '');
}

/* ---------- PERMANENTI (acquisti: stelle / pianeti, persistiti su disco) ---------- */
const PERM_FILE = path.join(__dirname, 'permanent.json');
let permanent = [];                       // {id,type:'star'|'planet',name,logo,skin,tint,tier,status,until,createdAt}
function loadPerm() { try { if (fs.existsSync(PERM_FILE)) permanent = JSON.parse(fs.readFileSync(PERM_FILE, 'utf8')) || []; } catch (e) { warn('permanent load', e.message); permanent = []; } }
let _permSaveT = null;
function savePerm() { clearTimeout(_permSaveT); _permSaveT = setTimeout(() => { try { fs.writeFileSync(PERM_FILE, JSON.stringify(permanent, null, 2)); } catch (e) { warn('permanent save', e.message); } }, 300); }
function permId() { return 'p_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }
function pruneExpired() { const now = Date.now(); let ch = false; for (const it of permanent) { if (it.until && it.until < now && it.status === 'approved') { it.status = 'expired'; ch = true; } } if (ch) savePerm(); }
loadPerm();

const ADMIN_TOKEN = process.env.ADMIN_TOKEN || '';
function isAdmin(req, parsed) { const t = req.headers['x-admin-token'] || parsed.query.token || ''; return !!ADMIN_TOKEN && t === ADMIN_TOKEN; }
function readBody(req) { return new Promise(resolve => { let b = ''; req.on('data', d => { b += d; if (b.length > 1e6) req.destroy(); }); req.on('end', () => { try { resolve(b ? JSON.parse(b) : {}); } catch (e) { resolve({}); } }); req.on('error', () => resolve({})); }); }

/* ---------- HTTP: statico + /api/stars ---------- */
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp',
  '.gif': 'image/gif', '.svg': 'image/svg+xml', '.glb': 'model/gltf-binary',
  '.gltf': 'model/gltf+json', '.bin': 'application/octet-stream', '.ico': 'image/x-icon',
  '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg', '.wav': 'audio/wav', '.txt': 'text/plain; charset=utf-8',
  '.woff': 'font/woff', '.woff2': 'font/woff2', '.command': 'text/plain; charset=utf-8',
};

const server = http.createServer((req, res) => {
  const parsed = url.parse(req.url, true);
  let pathname; try { pathname = decodeURIComponent(parsed.pathname || '/'); } catch (e) { res.writeHead(400, { 'content-type': 'text/plain' }); return res.end('bad request'); }

  if (pathname === '/api/stars') {
    const since = parseInt(parsed.query.since || '0', 10) || 0;
    const fresh = events.filter(e => e.ts > since).map(e => ({ name: e.name }));
    const cmds = commands.filter(c => c.ts > since).map(c => ({ cmd: c.cmd, arg: c.arg, user: c.user }));
    const lastEv = events.length ? events[events.length - 1].ts : 0;
    const lastCmd = commands.length ? commands[commands.length - 1].ts : 0;
    const ts = Math.max(since, lastEv, lastCmd);
    return sendJSON(res, 200, { stars: fresh, cmds, total: companions, ts });
  }
  if (pathname === '/api/health') {
    return sendJSON(res, 200, { ok: true, companions, chat: !!chatState.liveChatId, subs: CFG.SUBS && hasOAuth() });
  }
  // POST manuale: /api/star?name=Mario  (utile per test o regie esterne)
  if (pathname === '/api/star') {
    const ok = addStar(parsed.query.name, 'manual:' + (parsed.query.name || ''));
    return sendJSON(res, ok ? 200 : 429, { ok });
  }
  // catalogo PERMANENTI approvati (il frontend lo semina all'avvio)
  if (pathname === '/api/permanent') {
    pruneExpired(); const now = Date.now();
    const ok = permanent.filter(it => it.status === 'approved' && (!it.until || it.until > now));
    const stars = ok.filter(it => it.type === 'star').map(it => ({ name: it.name }));
    const planets = ok.filter(it => it.type === 'planet').map(it => ({ name: it.name, logo: it.logo || '', skin: it.skin || 0, tint: it.tint || '' }));
    return sendJSON(res, 200, { stars, planets });
  }
  // --- ADMIN (token via header x-admin-token o ?token=) ---
  if (pathname === '/api/admin/permanent' && req.method === 'GET') {
    if (!isAdmin(req, parsed)) return sendJSON(res, 401, { error: 'unauthorized' });
    return sendJSON(res, 200, { items: permanent });
  }
  if (pathname === '/api/admin/permanent' && req.method === 'POST') {
    if (!isAdmin(req, parsed)) return sendJSON(res, 401, { error: 'unauthorized' });
    readBody(req).then(b => {
      const type = b.type === 'planet' ? 'planet' : 'star';
      const name = String(b.name || '').slice(0, 40).trim();
      if (!name) return sendJSON(res, 400, { error: 'name required' });
      const days = parseInt(b.days, 10) || 0;
      const it = { id: permId(), type, name, logo: String(b.logo || '').slice(0, 300), skin: parseInt(b.skin, 10) || 0,
        tint: String(b.tint || '').slice(0, 16), tier: String(b.tier || 'basic').slice(0, 16),
        status: (b.status === 'approved' || b.status === 'pending') ? b.status : 'pending',
        until: days > 0 ? Date.now() + days * 86400000 : 0, createdAt: Date.now() };
      permanent.push(it); savePerm(); log('✦ permanente:', type, name, it.status);
      sendJSON(res, 200, { item: it });
    });
    return;
  }
  if (pathname === '/api/admin/permanent/action' && req.method === 'POST') {
    if (!isAdmin(req, parsed)) return sendJSON(res, 401, { error: 'unauthorized' });
    const id = parsed.query.id, action = parsed.query.action;
    const it = permanent.find(x => x.id === id);
    if (!it && action !== 'delete') return sendJSON(res, 404, { error: 'not found' });
    if (action === 'approve') it.status = 'approved';
    else if (action === 'reject') it.status = 'rejected';
    else if (action === 'delete') permanent = permanent.filter(x => x.id !== id);
    else return sendJSON(res, 400, { error: 'bad action' });
    savePerm();
    return sendJSON(res, 200, { ok: true });
  }
  // TEST comandi dall'admin: inietta un comando nella coda (la scena lo prende al prossimo polling ~10s)
  if (pathname === '/api/admin/command' && req.method === 'POST') {
    if (!isAdmin(req, parsed)) return sendJSON(res, 401, { error: 'unauthorized' });
    const cmd = String(parsed.query.cmd || '').toLowerCase();
    const arg = cleanArg(parsed.query.arg || '');
    if (!CMD_FREE.has(cmd) && !CMD_SUB.has(cmd) && !CMD_ADMIN.has(cmd)) return sendJSON(res, 400, { error: 'comando sconosciuto' });
    commands.push({ cmd, arg, user: 'admin', ts: Date.now() });
    if (commands.length > 500) commands.splice(0, commands.length - 500);
    log('▸ test comando (admin):', cmd, arg || '');
    return sendJSON(res, 200, { ok: true, cmd, arg });
  }

  // statico
  if (pathname === '/') pathname = '/index.html';
  const filePath = path.join(CFG.ROOT, path.normalize(pathname));
  const rel = path.relative(CFG.ROOT, filePath);
  // nega: traversal, qualsiasi dotfile (.env/.git/.gitignore/.claude…), e i file sensibili del progetto
  if (!filePath.startsWith(CFG.ROOT) || rel.split(path.sep).some(s => s.startsWith('.')) ||
      /^(server|get-token|gen-[^\/]*)\.js$|^serve\.command$|^(package(-lock)?|permanent)\.json$/.test(rel)) {
    res.writeHead(403); return res.end('forbidden');
  }
  fs.stat(filePath, (err, stat) => {
    if (err || !stat.isFile()) { res.writeHead(404, { 'content-type': 'text/plain' }); return res.end('not found'); }
    const ext = path.extname(filePath).toLowerCase(), type = MIME[ext] || 'application/octet-stream';
    const range = req.headers.range, streamable = /\.(mp3|wav|ogg|m4a|aac)$/i.test(ext);
    if (range && streamable) {
      const m = /^bytes=(\d*)-(\d*)$/.exec(range);
      if (!m) { res.writeHead(416, { 'content-range': 'bytes */' + stat.size }); return res.end(); }
      const start = m[1] ? parseInt(m[1], 10) : 0;
      const end = m[2] ? Math.min(parseInt(m[2], 10), stat.size - 1) : stat.size - 1;
      if (start > end || start >= stat.size) { res.writeHead(416, { 'content-range': 'bytes */' + stat.size }); return res.end(); }
      res.writeHead(206, { 'content-type': type, 'cache-control': 'no-cache', 'accept-ranges': 'bytes',
        'content-range': `bytes ${start}-${end}/${stat.size}`, 'content-length': end - start + 1 });
      return fs.createReadStream(filePath, { start, end }).pipe(res);
    }
    res.writeHead(200, { 'content-type': type, 'cache-control': 'no-cache', 'content-length': stat.size,
      ...(streamable ? { 'accept-ranges': 'bytes' } : {}) });
    fs.createReadStream(filePath).pipe(res);
  });
});

function sendJSON(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', 'access-control-allow-origin': '*' });
  res.end(body);
}

/* ---------- helper HTTPS (GET/POST JSON) ---------- */
function httpsJSON(method, fullUrl, headers, body) {
  return new Promise((resolve, reject) => {
    const u = new url.URL(fullUrl);
    const opts = { method, hostname: u.hostname, path: u.pathname + u.search, headers: headers || {} };
    const r = https.request(opts, resp => {
      let buf = '';
      resp.on('data', d => (buf += d));
      resp.on('end', () => {
        let j = null; try { j = buf ? JSON.parse(buf) : {}; } catch (e) {}
        if (resp.statusCode >= 200 && resp.statusCode < 300) resolve(j);
        else reject(Object.assign(new Error('HTTP ' + resp.statusCode), { status: resp.statusCode, body: j }));
      });
    });
    r.on('error', reject);
    if (body) r.write(body);
    r.end();
  });
}

/* ---------- OAuth (refresh token → access token) ---------- */
let _tok = { value: '', exp: 0 };
function hasOAuth() { return !!(CFG.CLIENT_ID && CFG.CLIENT_SECRET && CFG.REFRESH_TOKEN); }
async function accessToken() {
  if (!hasOAuth()) return '';
  if (_tok.value && Date.now() < _tok.exp - 60000) return _tok.value;
  const body = new url.URLSearchParams({
    client_id: CFG.CLIENT_ID, client_secret: CFG.CLIENT_SECRET,
    refresh_token: CFG.REFRESH_TOKEN, grant_type: 'refresh_token',
  }).toString();
  const j = await httpsJSON('POST', 'https://oauth2.googleapis.com/token',
    { 'content-type': 'application/x-www-form-urlencoded', 'content-length': Buffer.byteLength(body) }, body);
  _tok = { value: j.access_token, exp: Date.now() + (j.expires_in || 3600) * 1000 };
  return _tok.value;
}
async function authHeaders() {
  const t = await accessToken();
  return t ? { authorization: 'Bearer ' + t } : {};
}
const API = 'https://www.googleapis.com/youtube/v3/';
function withKey(u) { return CFG.API_KEY ? (u + (u.includes('?') ? '&' : '?') + 'key=' + CFG.API_KEY) : u; }

/* ---------- CHAT dal vivo → stelle ---------- */
const chatState = { liveChatId: CFG.LIVE_CHAT_ID, pageToken: '', primed: false };
async function resolveLiveChatId() {
  if (chatState.liveChatId) return chatState.liveChatId;
  // 1) da un VIDEO_ID (basta API key)
  if (CFG.VIDEO_ID) {
    const j = await httpsJSON('GET', withKey(API + 'videos?part=liveStreamingDetails&id=' + CFG.VIDEO_ID), await authHeaders());
    const id = j && j.items && j.items[0] && j.items[0].liveStreamingDetails && j.items[0].liveStreamingDetails.activeLiveChatId;
    if (id) { chatState.liveChatId = id; return id; }
  }
  // 2) dalla live attiva del canale (OAuth)
  if (hasOAuth()) {
    const j = await httpsJSON('GET', API + 'liveBroadcasts?part=snippet&broadcastStatus=active&broadcastType=all&maxResults=1', await authHeaders());
    const id = j && j.items && j.items[0] && j.items[0].snippet && j.items[0].snippet.liveChatId;
    if (id) { chatState.liveChatId = id; return id; }
  }
  return '';
}
async function pollChat() {
  let nextMs = 8000;
  try {
    const id = await resolveLiveChatId();
    if (!id) { schedule(pollChat, 30000); return; }
    let u = API + 'liveChatMessages?liveChatId=' + encodeURIComponent(id) + '&part=snippet,authorDetails&maxResults=200';
    if (chatState.pageToken) u += '&pageToken=' + chatState.pageToken;
    const j = await httpsJSON('GET', withKey(u), await authHeaders());
    chatState.pageToken = j.nextPageToken || chatState.pageToken;
    nextMs = Math.max(4000, j.pollingIntervalMillis || 8000);
    const items = j.items || [];
    // alla prima passata NON accendiamo lo storico: prendiamo solo i nuovi da qui in poi
    if (!chatState.primed) { chatState.primed = true; }
    else {
      for (const m of items) {
        const a = m.authorDetails || {};
        const name = a.displayName;
        const key = 'chat:' + (a.channelId || name);
        // nuovi membri / super chat = stella speciale (stesso flusso, dedup separato)
        addStar(name, key);
        const text = (m.snippet && m.snippet.displayMessage) || '';
        if (text.charAt(0) === '!') parseCommand(text, a);   // comando dalla chat (es. !comet, !whales, !star <nome>)
      }
    }
  } catch (e) {
    warn('chat:', e.status || '', (e.body && e.body.error && e.body.error.message) || e.message);
    if (e.status === 403 || e.status === 404) { chatState.liveChatId = ''; nextMs = 30000; }
  }
  schedule(pollChat, nextMs);
}

/* ---------- ISCRITTI RECENTI → stelle (best-effort, OAuth) ---------- */
const subState = { seen: new Set(), primed: false };
async function pollSubs() {
  let nextMs = 60000;
  try {
    if (!hasOAuth()) { return; } // niente polling senza OAuth
    const j = await httpsJSON('GET', API + 'subscriptions?part=subscriberSnippet&mySubscribers=true&maxResults=50', await authHeaders());   // best-effort: l'API non garantisce l'ordine
    const items = j.items || [];
    for (const it of items) {
      const s = it.subscriberSnippet || {};
      const cid = s.channelId; const name = s.title;
      if (!cid) continue;
      if (!subState.seen.has(cid)) {
        subState.seen.add(cid);
        if (subState.primed) addStar(name, 'sub:' + cid);  // alla prima passata solo "prime"
      }
    }
    subState.primed = true;
  } catch (e) {
    warn('subs:', e.status || '', (e.body && e.body.error && e.body.error.message) || e.message);
  } finally {
    schedule(pollSubs, nextMs);
  }
}

/* ---------- util ---------- */
function ts() { return new Date().toISOString().slice(11, 19); }
function log(...a) { console.log('[' + ts() + ']', ...a); }
function warn(...a) { console.warn('[' + ts() + '] ⚠', ...a); }
function schedule(fn, ms) { setTimeout(() => { fn().catch(e => warn('loop', e.message)); }, ms); }

/* ---------- 24/7: poda le mappe di dedup così non crescono all'infinito ---------- */
setInterval(() => {
  const cut = Date.now() - CFG.DEDUP_MS;
  for (const [k, t] of lastSeenByKey) if (t <= cut) lastSeenByKey.delete(k);
  if (subState.seen.size > 5000) subState.seen = new Set([...subState.seen].slice(-3000));
}, 60000);

/* ---------- avvio ---------- */
server.listen(CFG.PORT, () => {
  log('Eternal Fall bridge → http://localhost:' + CFG.PORT);
  const yt = [];
  if (CFG.CHAT && (CFG.VIDEO_ID || CFG.LIVE_CHAT_ID || hasOAuth())) yt.push('chat');
  if (CFG.SUBS && hasOAuth()) yt.push('iscritti');
  log(yt.length ? ('YouTube attivo: ' + yt.join(' + ')) : 'YouTube non configurato (serve solo il sito; /api/stars vuoto). Vedi .env.example');
  if (CFG.CHAT && (CFG.VIDEO_ID || CFG.LIVE_CHAT_ID || hasOAuth())) schedule(pollChat, 1500);
  if (CFG.SUBS && hasOAuth()) schedule(pollSubs, 3000);
});
process.on('uncaughtException', e => warn('uncaught', e.message));
process.on('unhandledRejection', e => warn('unhandled', (e && e.message) || e));
