// Behavior tests for the real display script; minimal DOM is a boundary double.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const elements = new Map();
class Element {
  textContent = ''; hidden = false; src = ''; dataset = {}; listeners = {};
  addEventListener(name, handler) { this.listeners[name] = handler; }
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
}
for (const id of ['title','artist','album','artwork','track','activity','activity-text']) elements.set(id, new Element());
const document = {getElementById: id => elements.get(id), body: new Element()};
let now = 0;
let response = {status:'matched',activity:'music_detected',revision:1,track:{id:'1',title:'<b>literal title</b>',artist:'An artist',album:null,artwork_url:null}};
let fail = false;
const timers = [];
const context = vm.createContext({document, URL, location: {href:'http://localhost/'}, performance:{now:()=>now}, AbortSignal:{timeout:()=>({})}, fetch:async()=>{if(fail)throw Error('offline');return {ok:true,json:async()=>response}},setTimeout:(fn)=>timers.push(fn),console});
const source = fs.readFileSync('src/now_playing/web/app.js','utf8');
vm.runInContext(source,context);
(async()=>{
  await new Promise(setImmediate);
  assert.equal(elements.get('title').textContent,'<b>literal title</b>');
  assert.equal(elements.get('album').hidden,true);
  assert.equal(elements.get('artwork').src,'/artwork.svg');
  assert.equal(document.body.dataset.state,'matched');
  assert.equal(elements.get('activity-text').textContent,'Music detected');
  response = {...response,activity:'identifying'};
  await timers.shift()();
  assert.equal(elements.get('activity-text').textContent,'Identifying song…');
  assert.equal(elements.get('track').hidden,false);
  fail = true; now = 10001;
  await timers.shift()();
  assert.equal(document.body.dataset.state,'unavailable');
  assert.equal(elements.get('activity-text').textContent,'Listening paused');
  assert.equal(elements.get('track').hidden,true);
  fail = false;
  await timers.shift()();
  assert.equal(document.body.dataset.state,'matched'); // same revision must recover
  response = {...response,revision:2,track:{...response.track,artwork_url:'javascript:bad'}};
  await timers.shift()();
  assert.equal(elements.get('artwork').src,'/artwork.svg');
  response = {...response,revision:3,track:{...response.track,artwork_url:'https://example.com/broken.jpg'}};
  await timers.shift()();
  elements.get('artwork').listeners.error();
  assert.equal(elements.get('artwork').src,'/artwork.svg');
  elements.get('artwork').listeners.error();
  assert.equal(elements.get('artwork').src,'/artwork.svg');
  response={...response,revision:4,track:{...response.track,artwork_url:'https://is1-ssl.mzstatic.com/image/thumb/cover.jpg/400x400cc.jpg'}};
  await timers.shift()();
  assert.equal(elements.get('artwork').src,'https://is1-ssl.mzstatic.com/image/thumb/cover.jpg/1200x1200cc.jpg');
  elements.get('artwork').listeners.error();
  assert.equal(elements.get('artwork').src,'https://is1-ssl.mzstatic.com/image/thumb/cover.jpg/400x400cc.jpg');
  elements.get('artwork').listeners.error();
  assert.equal(elements.get('artwork').src,'/artwork.svg');
  response={...response,revision:5,track:{...response.track,artwork_url:'https://is1-ssl.mzstatic.com/image/thumb/cover.jpg/3000x3000bb.jpg'}};
  await timers.shift()();
  assert.equal(elements.get('artwork').src,'https://is1-ssl.mzstatic.com/image/thumb/cover.jpg/3000x3000bb.jpg');
  response={status:'idle',track:null,revision:6}; await timers.shift()();
  assert.equal(elements.get('track').hidden,true);
  assert.equal(elements.get('activity-text').textContent,'Listening');
  console.log('Display behavior checks passed (metadata, fallback, offline, reconnect, idle).');
})().catch(e=>{console.error(e);process.exitCode=1});
