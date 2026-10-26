const assert = require('node:assert/strict');
require('../src/now_playing/web/mosaic.js');
const handlers = {};
global.document = {hidden:false, addEventListener(name, fn) {handlers[name] = fn;}, getElementById(){return null;}};
global.window = {addEventListener(){}};
global.matchMedia = () => ({matches:false, addEventListener(){}});
const element = () => ({dataset:{}, attrs:{}, disabled:false,
  setAttribute(k,v){this.attrs[k]=v;}, removeAttribute(k){delete this.attrs[k];},
  contains(node){return node === this;}});
(async () => {
  const mosaic = new global.AlbumMosaic({hidden:false});
  const cell = {album:'a'.repeat(64), label:'Album A', element:element()};
  const other = {album:'b'.repeat(64), label:'Album B', element:element()};
  mosaic.cells = [cell, other]; mosaic.visible = true;
  mosaic.layout = () => {};
  const requests = [];
  let fail = true;
  global.fetch = async (url, options) => {requests.push({url,options}); return {ok:!fail};};
  let refreshed = false;
  mosaic.refresh = async options => {assert.equal(options.rebuild,true);refreshed=true;};
  try {
    await mosaic.select(cell);
    assert.equal(cell.element.dataset.confirm,'true');
    assert.equal(requests.length,0,'first click must not delete');
    const before = mosaic.queue.cursor;
    await mosaic.shift();
    assert.equal(mosaic.queue.cursor,before,'confirmation pauses shifts');
    await mosaic.select(other);
    assert.equal(cell.element.dataset.confirm,undefined);
    assert.equal(other.element.dataset.confirm,'true');
    handlers.keydown({key:'Escape'});
    assert.equal(other.element.dataset.confirm,undefined);
    assert.equal(other.element.attrs['aria-label'],'Remove Album B');
    await mosaic.select(cell);
    handlers.click({target:{}});
    assert.equal(cell.element.dataset.confirm,undefined,'outside click cancels');
    await mosaic.select(cell);
    await mosaic.select(cell);
    assert.equal(refreshed,false,'failed deletion keeps the collection');
    assert.equal(cell.element.disabled,false,'failed deletion allows retry');
    assert.equal(cell.element.dataset.confirm,'true');
    fail = false;
    await mosaic.select(cell);
    assert.equal(requests.at(-1).url,'/api/albums/' + cell.album);
    assert.equal(requests.at(-1).options.method,'DELETE');
    assert.equal(refreshed,true,'successful deletion refetches collection');
    assert.equal(mosaic.armedCell,null);
    console.log('Mosaic deletion checks passed: arm, cancel, pause, failure, retry, refresh.');
  } finally {mosaic.hide();}
})().catch(error => {console.error(error);process.exitCode=1;});
