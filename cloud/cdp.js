// mini client CDP (zero deps).
//   node cdp.js <ws-page-url> eval '<expr>'      -> stampa il valore
//   node cdp.js <ws-page-url> shot <outfile.jpg> -> Page.captureScreenshot -> salva il file
const http = require('http'), crypto = require('crypto'), fs = require('fs');
const wsUrl = process.argv[2], mode = process.argv[3], arg = process.argv[4];
const u = new URL(wsUrl);
const key = crypto.randomBytes(16).toString('base64');
const req = http.request({ host: u.hostname, port: u.port, path: u.pathname,
  headers: { Connection: 'Upgrade', Upgrade: 'websocket', 'Sec-WebSocket-Key': key, 'Sec-WebSocket-Version': '13' } });
const TO = setTimeout(() => { console.log('TIMEOUT'); process.exit(2); }, 12000);
req.on('upgrade', (res, socket) => {
  function send(obj){
    const p = Buffer.from(JSON.stringify(obj)), len = p.length, mask = crypto.randomBytes(4);
    let h;
    if (len < 126) h = Buffer.from([0x81, 0x80 | len]);
    else if (len < 65536) h = Buffer.from([0x81, 0xFE, (len>>8)&255, len&255]);
    else { h = Buffer.alloc(10); h[0]=0x81; h[1]=0xFF; h.writeUInt32BE(len, 6); }
    const m = Buffer.alloc(len); for (let i=0;i<len;i++) m[i] = p[i]^mask[i&3];
    socket.write(Buffer.concat([h, mask, m]));
  }
  let buf = Buffer.alloc(0);
  socket.on('data', d => {
    buf = Buffer.concat([buf, d]);
    while (buf.length >= 2) {
      if ((buf[0] & 0x0f) === 0x8) { process.exit(0); } // close
      let len = buf[1] & 127, off = 2;
      if (len === 126) { len = buf.readUInt16BE(2); off = 4; }
      else if (len === 127) { len = Number(buf.readBigUInt64BE(2)); off = 10; }
      if (buf.length < off + len) break;
      const payload = buf.slice(off, off+len).toString(); buf = buf.slice(off+len);
      let msg; try { msg = JSON.parse(payload); } catch(e){ continue; }
      if (msg.id === 1) {
        clearTimeout(TO);
        if (mode === 'shot') {
          fs.writeFileSync(arg, Buffer.from(msg.result.data, 'base64'));
          console.log('shot salvato: ' + arg + ' (' + fs.statSync(arg).size + ' bytes)');
        } else {
          console.log(JSON.stringify(msg.result));
        }
        process.exit(0);
      }
    }
  });
  if (mode === 'shot') send({ id:1, method:'Page.captureScreenshot', params:{ format:'jpeg', quality:70 } });
  else send({ id:1, method:'Runtime.evaluate', params:{ expression: arg, returnByValue:true, awaitPromise:true } });
});
req.on('error', e => { clearTimeout(TO); console.log('ERR ' + e.message); process.exit(1); });
req.end();
