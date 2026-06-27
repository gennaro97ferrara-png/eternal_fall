#!/usr/bin/env node
/*
  gen-image.js — genera UNA immagine con fal.ai (FLUX) e la salva.
  USO:  FAL_KEY=... PROMPT="..." OUT=assets/rock.jpg [SIZE=square_hd] node gen-image.js
*/
const https=require('https'), fs=require('fs'), path=require('path');
const FAL_KEY=process.env.FAL_KEY; if(!FAL_KEY){ console.error('Manca FAL_KEY'); process.exit(1); }
const PROMPT=process.env.PROMPT||'seamless texture'; const OUT=process.env.OUT||'out.jpg';
const SIZE=process.env.SIZE||'square_hd'; const MODEL=process.env.IMG_MODEL||'fal-ai/flux-pro/v1.1';
function req(method,url,body){ return new Promise((res,rej)=>{ const u=new URL(url); const data=body?JSON.stringify(body):null;
  const r=https.request({hostname:u.hostname,path:u.pathname+u.search,method,headers:{'Authorization':'Key '+FAL_KEY,'Content-Type':'application/json',...(data?{'Content-Length':Buffer.byteLength(data)}:{})}},
   resp=>{let b='';resp.on('data',c=>b+=c);resp.on('end',()=>{ if(resp.statusCode>=400) return rej(new Error('HTTP '+resp.statusCode+': '+b)); try{res(b?JSON.parse(b):{});}catch(e){rej(new Error('bad json '+b.slice(0,200)));}});});
  r.on('error',rej); if(data)r.write(data); r.end(); }); }
async function runQueue(model,input){ const sub=await req('POST','https://queue.fal.run/'+model,input);
  if(!sub.status_url) throw new Error('no status_url '+JSON.stringify(sub)); let t=0;
  for(;;){ await new Promise(r=>setTimeout(r,2500)); const st=await req('GET',sub.status_url);
    process.stdout.write('  '+st.status+'   \r'); if(st.status==='COMPLETED')break; if(st.status==='FAILED'||st.status==='ERROR') throw new Error('failed '+JSON.stringify(st)); if(++t>120)throw new Error('timeout'); }
  process.stdout.write('\n'); return await req('GET',sub.response_url); }
function download(url,dest){ return new Promise((res,rej)=>{ const f=fs.createWriteStream(dest); https.get(url,r=>{ if(r.statusCode>=400){rej(new Error('dl '+r.statusCode));return;} r.pipe(f); f.on('finish',()=>f.close(res)); }).on('error',rej); }); }
(async()=>{ try{ console.log('FLUX →',PROMPT.slice(0,70),'…');
  const out=await runQueue(MODEL,{prompt:PROMPT,image_size:SIZE,num_images:1,output_format:'jpeg'});
  const url=out.images&&out.images[0]&&out.images[0].url; if(!url) throw new Error('no image '+JSON.stringify(out).slice(0,200));
  fs.mkdirSync(path.dirname(OUT),{recursive:true}); await download(url,OUT);
  console.log('✓',OUT,'('+Math.round(fs.statSync(OUT).size/1024)+' KB)  src:',url);
}catch(e){ console.error('ERRORE:',e.message); process.exit(1); } })();
