(() => {
  'use strict';
  const get = id => document.getElementById(id);
  const fallback = '/artwork.svg';
  const mosaic = globalThis.AlbumMosaic ? new globalThis.AlbumMosaic(get('mosaic')) : null;
  if (mosaic) mosaic.show();
  let lastSuccess = performance.now();
  let lastRevision = null;
  let disconnected = false;
  let artworkSource = '';
  let artworkFallbacks = [];

  function safeArtwork(value) {
    if (value === '/demo-artwork.svg') return value;
    if (typeof value !== 'string') return fallback;
    try {
      const url = new URL(value);
      return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : fallback;
    } catch { return fallback; }
  }

  function largerArtwork(source) {
    try {
      const url = new URL(source);
      if (!url.hostname.endsWith('.mzstatic.com')) return source;
      const size = url.pathname.match(/\/(\d+)x(\d+)((?:cc|bb)\.(?:jpg|jpeg|png|webp))$/i);
      if (!size || Math.max(Number(size[1]), Number(size[2])) >= 1200) return source;
      url.pathname = url.pathname.slice(0, -size[0].length) + '/1200x1200' + size[3];
      return url.href;
    } catch { return source; }
  }

  get('artwork').addEventListener('error', () => {
    const next = artworkFallbacks.shift();
    if (next) {
      artworkSource = next;
      get('artwork').src = next;
    }
  });

  function renderActivity(state) {
    const fallbackActivity = {idle: 'listening', identifying: 'identifying', matched: 'music_detected', unavailable: 'paused'}[state.status] || 'paused';
    const activity = state.activity || fallbackActivity;
    const text = {listening: 'Listening', music_detected: 'Music detected', identifying: 'Identifying song…', paused: 'Listening paused'}[activity] || 'Listening paused';
    document.body.dataset.activity = activity;
    if (get('activity-text').textContent !== text) get('activity-text').textContent = text;
  }

  function render(state) {
    renderActivity(state);
    const status = ['idle', 'identifying', 'matched', 'unavailable'].includes(state.status) ? state.status : 'unavailable';
    const matched = status === 'matched' && state.track;
    document.body.dataset.state = status;
    get('track').hidden = !matched;
    const next = matched && state.next_track && typeof state.next_track.title === 'string';
    get('next-song').hidden = !next;
    get('next-title').textContent = next ? state.next_track.title : '';
    if (mosaic) matched ? mosaic.hide() : mosaic.show();
    if (matched) {
      get('title').textContent = (state.inferred ? '💿 ' : '') + state.track.title;
      get('artist').textContent = state.track.artist;
      get('album').textContent = state.track.album || '';
      get('album').hidden = !state.track.album;
      const original = safeArtwork(state.track.artwork_url);
      const source = largerArtwork(original);
      if (source !== artworkSource) {
        artworkFallbacks = [...new Set([original, fallback])].filter(value => value !== source);
        artworkSource = source;
        get('artwork').src = source;
      }
    }
  }

  async function poll() {
    const started = performance.now();
    try {
      const response = await fetch('/api/state', {cache: 'no-store', signal: AbortSignal.timeout(3000)});
      if (!response.ok) throw new Error('State unavailable');
      const state = await response.json();
      if (!state || !Number.isInteger(state.revision) || typeof state.status !== 'string') throw new Error('Invalid state');
      if (state.status === 'matched' && (!state.track || typeof state.track.title !== 'string' || typeof state.track.artist !== 'string')) throw new Error('Invalid track');
      lastSuccess = performance.now();
      renderActivity(state);
      if (disconnected || state.revision !== lastRevision) {
        render(state);
        lastRevision = state.revision;
      }
      disconnected = false;
    } catch {
      if (performance.now() - lastSuccess >= 10000 && !disconnected) {
        render({status: 'unavailable', track: null});
        disconnected = true;
      }
    } finally {
      setTimeout(poll, Math.max(0, 1000 - (performance.now() - started)));
    }
  }
  poll();
})();
