const assert=require('node:assert/strict');
require('../src/now_playing/web/mosaic.js');
global.document={hidden:false,addEventListener(){}};
global.window={addEventListener(){}};
global.matchMedia=()=>({matches:true,addEventListener(){}});
const album=n=>({id:String(n),artwork_url:'/artwork/'+String(n).padStart(64,'0')});
(async()=>{
  const mosaic=new global.AlbumMosaic({hidden:true});
  const rendered=[];
  mosaic.layout=()=>{rendered.push(mosaic.queue.albums.map(a=>a.id));mosaic.cells=[{album:'1',element:{}}];};
  mosaic.queue.update([album(1)]);
  mosaic.revision=1;
  let requests=0;
  global.fetch=async()=>{requests++;return {ok:true,json:async()=>({revision:2,albums:[album(1),album(2)]})}};
  try {
    mosaic.show();
    await new Promise(setImmediate);
    assert.deepEqual(rendered.at(-1),['1','2'],'returning to mosaic must rebuild with all freshly fetched covers');
    mosaic.hide();mosaic.show();
    await new Promise(setImmediate);
    assert.equal(requests,2,'each new mosaic appearance needs a fresh request');
  } finally {mosaic.hide();}
  const racing=new global.AlbumMosaic({hidden:true});
  racing.layout=()=>{};
  const pending=[];
  global.fetch=()=>new Promise(resolve=>pending.push(resolve));
  try {
    racing.show();
    racing.hide();
    racing.show();
    assert.equal(pending.length,2,'an older in-flight request must not suppress the new entry fetch');
    pending[1]({ok:true,json:async()=>({revision:3,albums:[album(3)]})});
    await new Promise(setImmediate);
    pending[0]({ok:true,json:async()=>({revision:1,albums:[album(1)]})});
    await new Promise(setImmediate);
    assert.deepEqual(racing.queue.albums.map(a=>a.id),['3'],'stale responses cannot overwrite a fresh collection');
  } finally {racing.hide();}
  console.log('Mosaic entry refresh checks passed: immediate rebuild, every appearance, stale response rejection.');
})().catch(e=>{console.error(e);process.exitCode=1});
