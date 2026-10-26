const assert=require('node:assert/strict');
const {MosaicQueue}=require('../src/now_playing/web/mosaic.js');
const album=n=>({id:String(n),artwork_url:'/artwork/'+String(n).padStart(64,'0')});
const queue=new MosaicQueue();
queue.update([]);assert.deepEqual(queue.next(5),[]);
queue.update([album(1)]);assert.deepEqual(queue.next(3).map(a=>a.id),['1','1','1']);
queue.update([album(1),album(1),album(2),album(3)]);
assert.deepEqual(queue.next(4).map(a=>a.id),['1','2','3','1']);
assert.deepEqual(queue.next(2).map(a=>a.id),['2','3']);
queue.update(Array.from({length:100},(_,i)=>album(i)));
const seen=new Set();
for(let i=0;i<10;i++)queue.next(12).forEach(a=>seen.add(a.id));
assert.equal(seen.size,100);
queue.update([{id:'unsafe',artwork_url:'https://external.example/art.jpg'},album(1)]);
assert.deepEqual(queue.next(2).map(a=>a.id),['1','1']);
console.log('Mosaic queue checks passed: empty, repetition, deduplication, fair rotation, local artwork only.');
const growing=new MosaicQueue();
growing.update(Array.from({length:100},(_,i)=>album(i)));
growing.next(40);
growing.update(Array.from({length:101},(_,i)=>album(i)));
assert.equal(growing.next(1)[0].id,'40');
console.log('Collection growth preserves rotation position.');
(async()=>{
  global.document={hidden:false,addEventListener(){},getElementById(){return null;}};
  global.window={addEventListener(){}};
  global.matchMedia=()=>({matches:true,addEventListener(){}});
  const errors=[];
  const recovered=new global.AlbumMosaic({});
  recovered.visible=true;recovered.revision=1;recovered.broken.add('1');
  recovered.cells=[{album:'1',element:{}}];
  let discarded=false;
  recovered.layout=()=>{discarded=true;};
  global.fetch=async()=>({ok:true,json:async()=>({revision:1,albums:[album(1)]})});
  try {
    await recovered.refresh();
    assert.equal(recovered.queue.albums.length,1,'same-revision recovery must restore previously failed albums');
    assert.equal(discarded,false,'existing painted covers must survive collection recovery');
  } catch(error) {errors.push(error);} finally {recovered.stopTimers();}
  const mosaic=new global.AlbumMosaic({});
  mosaic.visible=true;mosaic.queue.update([album(1),album(2)]);
  mosaic.preload=async item=>{if(item.id==='1'){mosaic.broken.add('1');return null;}return {remove(){}}};
  const cell={album:null,element:{firstElementChild:null,append(){},setAttribute(){}}};
  await mosaic.paint(cell,album(1),0);
  try {assert.equal(cell.album,'2','reduced-motion initial holes must be refilled');} catch(error) {errors.push(error);}
  if(errors.length) throw new AggregateError(errors,'Mosaic recovery failed');
  console.log('Mosaic recovery checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
