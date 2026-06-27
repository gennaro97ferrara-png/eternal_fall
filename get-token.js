#!/usr/bin/env node
/* ============================================================================
   Eternal Fall — generatore guidato del refresh token YouTube (OAuth)
   Zero dipendenze. Ti porta dal "click su Autorizza" al refresh_token in 1 minuto.

   Prerequisiti (una volta sola, su https://console.cloud.google.com):
     1) Crea un progetto → "API e servizi" → abilita "YouTube Data API v3".
     2) "Schermata consenso OAuth": tipo External, aggiungi te stesso come
        "Utente di test".
     3) "Credenziali" → Crea credenziali → ID client OAuth → tipo
        "Applicazione desktop". Copia CLIENT ID e CLIENT SECRET.

   Uso:
     CLIENT_ID=xxx CLIENT_SECRET=yyy node get-token.js
     (oppure mettili in .env e lancia: node --env-file=.env get-token.js)

   Lo script apre il browser, tu clicchi "Consenti", e lui stampa la riga
   YT_OAUTH_REFRESH_TOKEN=... da incollare nel tuo .env. Fine.
   ============================================================================ */
'use strict';
const http = require('http');
const https = require('https');
const { URL, URLSearchParams } = require('url');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');

// carica .env minimale (se presente)
try {
  const p = path.join(__dirname, '.env');
  if (fs.existsSync(p)) for (const line of fs.readFileSync(p, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
} catch (e) {}

const CLIENT_ID = process.env.CLIENT_ID || process.env.YT_OAUTH_CLIENT_ID || '';
const CLIENT_SECRET = process.env.CLIENT_SECRET || process.env.YT_OAUTH_CLIENT_SECRET || '';
const PORT = parseInt(process.env.OAUTH_PORT || '8124', 10);
const REDIRECT = 'http://localhost:' + PORT + '/oauth2callback';
const SCOPE = 'https://www.googleapis.com/auth/youtube.readonly';

if (!CLIENT_ID || !CLIENT_SECRET) {
  console.error('\n✖ Mancano CLIENT_ID / CLIENT_SECRET.');
  console.error('  Esegui:  CLIENT_ID=... CLIENT_SECRET=... node get-token.js');
  console.error('  (li trovi in Google Cloud → Credenziali → ID client OAuth "Desktop")\n');
  process.exit(1);
}

const authUrl = 'https://accounts.google.com/o/oauth2/v2/auth?' + new URLSearchParams({
  client_id: CLIENT_ID, redirect_uri: REDIRECT, response_type: 'code',
  scope: SCOPE, access_type: 'offline', prompt: 'consent',
}).toString();

function postToken(code) {
  return new Promise((resolve, reject) => {
    const body = new URLSearchParams({
      code, client_id: CLIENT_ID, client_secret: CLIENT_SECRET,
      redirect_uri: REDIRECT, grant_type: 'authorization_code',
    }).toString();
    const req = https.request({
      method: 'POST', hostname: 'oauth2.googleapis.com', path: '/token',
      headers: { 'content-type': 'application/x-www-form-urlencoded', 'content-length': Buffer.byteLength(body) },
    }, res => { let b = ''; res.on('data', d => b += d); res.on('end', () => { try { resolve(JSON.parse(b)); } catch (e) { reject(e); } }); });
    req.on('error', reject); req.write(body); req.end();
  });
}

const server = http.createServer(async (req, res) => {
  const u = new URL(req.url, 'http://localhost:' + PORT);
  if (u.pathname !== '/oauth2callback') { res.writeHead(404); return res.end(); }
  const code = u.searchParams.get('code'), err = u.searchParams.get('error');
  if (err) { res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }); res.end('<h2>Autorizzazione annullata: ' + err + '</h2>'); return; }
  try {
    const tok = await postToken(code);
    if (!tok.refresh_token) {
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
      res.end('<h2>Nessun refresh_token ricevuto.</h2><p>Revoca l\'accesso su myaccount.google.com/permissions e riprova (serve prompt=consent + access_type=offline).</p>');
      console.error('\n✖ Nessun refresh_token:', JSON.stringify(tok)); return;
    }
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
    res.end('<body style="font-family:system-ui;background:#0b0f1e;color:#cdd6f4;padding:40px"><h2>✓ Fatto. Puoi chiudere questa pagina.</h2><p>Torna al terminale e copia la riga nel tuo <code>.env</code>.</p></body>');
    console.log('\n✓ Refresh token ottenuto. Incolla questa riga nel tuo .env:\n');
    console.log('YT_OAUTH_REFRESH_TOKEN=' + tok.refresh_token + '\n');
    console.log('(e assicurati di avere anche YT_OAUTH_CLIENT_ID e YT_OAUTH_CLIENT_SECRET nel .env)\n');
    setTimeout(() => process.exit(0), 500);
  } catch (e) {
    res.writeHead(500); res.end('errore'); console.error(e);
  }
});

server.listen(PORT, () => {
  console.log('\n→ Apri questo link nel browser (e clicca "Consenti"):\n\n' + authUrl + '\n');
  console.log('In attesa dell\'autorizzazione su ' + REDIRECT + ' …\n');
  const opener = process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'start' : 'xdg-open';
  exec(opener + ' "' + authUrl + '"', () => {});
});
