/* Persistent album artwork, shown whenever there is no identified track. */
(() => {
  'use strict';
  const validArtwork = value => typeof value === 'string' && (/^\/artwork\/[a-f0-9]{64}$/.test(value) || value === '/demo-artwork.svg');

  class MosaicQueue {
    constructor() { this.albums = []; this.cursor = 0; }
    update(albums) {
      const unique = new Map();
      for (const album of albums) {
        if (album && typeof album.id === 'string' && validArtwork(album.artwork_url)) unique.set(album.id, album);
      }
      const next = [...unique.values()];
      if (JSON.stringify(next) !== JSON.stringify(this.albums)) {
        const nextId = this.albums.length ? this.albums[this.cursor % this.albums.length].id : null;
        this.albums = next;
        this.cursor = Math.max(0, next.findIndex(album => album.id === nextId));
      }
    }
    next(count) {
      if (!this.albums.length) return [];
      return Array.from({length: count}, () => this.albums[this.cursor++ % this.albums.length]);
    }
  }

  class AlbumMosaic {
    constructor(root) {
      this.root = root;
      this.queue = new MosaicQueue();
      this.cells = [];
      this.broken = new Set();
      this.visible = false;
      this.generation = 0;
      this.revision = null;
      this.fetching = false;
      this.fetchSequence = 0;
      this.fetchController = null;
      this.animating = false;
      this.armedCell = null;
      this.deleting = false;
      this.motion = matchMedia('(prefers-reduced-motion: reduce)');
      this.motion.addEventListener('change', () => this.resume());
      document.addEventListener('click', event => {
        if (this.armedCell && !this.armedCell.element.contains(event.target)) this.cancelConfirmation();
      });
      document.addEventListener('keydown', event => {
        if (event.key === 'Escape') this.cancelConfirmation();
      });
      document.addEventListener('visibilitychange', () => {
        this.stopTimers();
        this.generation++;
        if (!document.hidden && this.visible) this.resume();
      });
      window.addEventListener('resize', () => {
        if (this.visible && !document.hidden) this.layout();
      });
    }
    show() {
      if (this.visible) return;
      this.visible = true;
      this.root.hidden = false;
      this.resume();
    }
    hide() {
      this.cancelConfirmation();
      this.message('');
      this.fetchSequence++;
      if (this.fetchController) this.fetchController.abort();
      this.fetching = false;
      this.visible = false;
      this.root.hidden = true;
      this.generation++;
      this.stopTimers();
    }
    stopTimers() {
      clearTimeout(this.shiftTimer);
      clearTimeout(this.refreshTimer);
    }
    message(text) {
      const status = document.getElementById('collection-message');
      if (status) { status.textContent = text; status.hidden = !text; }
    }
    cancelConfirmation() {
      if (this.armedCell) {
        delete this.armedCell.element.dataset.confirm;
        this.armedCell.element.setAttribute('aria-pressed', 'false');
        this.armedCell.element.setAttribute('aria-label', 'Remove ' + this.armedCell.label);
        this.armedCell = null;
      }
    }
    async select(cell) {
      if (this.deleting || !cell.album) return;
      this.message('');
      if (this.armedCell !== cell) {
        this.cancelConfirmation();
        this.fetchSequence++;
        if (this.fetchController) this.fetchController.abort();
        this.fetching = false;
        clearTimeout(this.refreshTimer);
        this.refreshTimer = setTimeout(() => this.refresh(), 15000);
        this.armedCell = cell;
        cell.element.dataset.confirm = 'true';
        cell.element.setAttribute('aria-pressed', 'true');
        cell.element.setAttribute('aria-label', 'Confirm removal: ' + cell.label);
        return;
      }
      const id = cell.album;
      this.deleting = true;
      cell.element.setAttribute('aria-disabled', 'true');
      cell.element.setAttribute('aria-busy', 'true');
      try {
        const response = await fetch('/api/albums/' + encodeURIComponent(id), {
          method: 'DELETE', signal: AbortSignal.timeout(5000),
        });
        if (!response.ok) throw new Error('Album deletion unavailable');
        this.cancelConfirmation();
        // Remove all copies immediately, even if the subsequent refresh fails.
        this.queue.update(this.queue.albums.filter(album => album.id !== id));
        this.deleting = false;
        if (this.visible && !document.hidden) this.layout();
        await this.refresh({force: true, rebuild: true});
      } catch {
        if (this.visible) this.message('Could not remove album. Click again to retry.');
      } finally {
        this.deleting = false;
        cell.element.removeAttribute('aria-disabled');
        cell.element.removeAttribute('aria-busy');
      }
    }
    resume() {
      this.stopTimers();
      if (!this.visible || document.hidden) return;
      // Rebuild after a hidden preload was invalidated.
      this.layout();
      this.refresh({force: true, rebuild: true});
      this.scheduleShift();
    }
    async refresh({force = false, rebuild = false} = {}) {
      if ((!force && this.fetching) || !this.visible || document.hidden) return;
      if (this.armedCell || this.deleting) {
        clearTimeout(this.refreshTimer);
        this.refreshTimer = setTimeout(() => this.refresh(), 15000);
        return;
      }
      if (this.fetchController) this.fetchController.abort();
      const sequence = ++this.fetchSequence;
      const controller = new AbortController();
      this.fetchController = controller;
      this.fetching = true;
      const deadline = setTimeout(() => controller.abort(), 3000);
      try {
        const response = await fetch('/api/albums', {cache: 'no-store', signal: controller.signal});
        if (!response.ok) throw new Error('Album collection unavailable');
        const collection = await response.json();
        if (sequence !== this.fetchSequence || !this.visible || document.hidden) return;
        if (!Array.isArray(collection.albums)) throw new Error('Invalid album collection');
        const signature = JSON.stringify(collection.albums);
        if (rebuild || collection.revision !== this.revision || signature !== this.collectionSignature || this.broken.size) {
          this.collectionSignature = signature;
          this.revision = collection.revision;
          this.broken.clear();
          this.queue.update(collection.albums);
          if (this.visible && !document.hidden) {
            if (rebuild || !this.cells.length || !this.queue.albums.length) this.layout();
            else {
              const available = new Set(this.queue.albums.map(album => album.id));
              for (const cell of this.cells) {
                if (!available.has(cell.album)) this.paint(cell, this.queue.next(1)[0], this.generation);
              }
            }
          }
        }
      } catch {
        // Keep the last successfully loaded collection through backend outages.
      } finally {
        clearTimeout(deadline);
        if (sequence === this.fetchSequence) {
          this.fetching = false;
          this.fetchController = null;
          clearTimeout(this.refreshTimer);
          if (this.visible && !document.hidden) this.refreshTimer = setTimeout(() => this.refresh(), 15000);
        }
      }
    }
    layout() {
      if (this.armedCell || this.deleting) return;
      this.generation++;
      this.animating = false;
      for (const cell of this.cells) cell.element.remove();
      this.cells = [];
      if (!this.queue.albums.length) return;
      this.columns = Math.max(1, Math.floor(Math.sqrt(24 * innerWidth / innerHeight)));
      this.size = Math.ceil(innerWidth / this.columns);
      const rows = Math.ceil(innerHeight / this.size);
      const count = Math.min(48, rows * this.columns);
      const albums = this.queue.next(count);
      const generation = this.generation;
      for (let slot = 0; slot < count; slot++) {
        const element = document.createElement('button');
        element.type = 'button';
        element.className = 'mosaic-tile';
        element.style.width = this.size + 'px';
        element.style.height = this.size + 'px';
        const cell = {element, slot, album: null};
        element.addEventListener('click', () => this.select(cell));
        this.position(cell);
        this.root.append(element);
        this.cells.push(cell);
        this.paint(cell, albums[slot], generation);
      }
    }
    position(cell) {
      cell.element.style.transform = `translate(${cell.slot % this.columns * this.size}px, ${Math.floor(cell.slot / this.columns) * this.size}px)`;
    }
    preload(album) {
      if (this.broken.has(album.id)) return Promise.resolve(null);
      return new Promise(resolve => {
        const image = new Image();
        image.alt = '';
        image.decoding = 'async';
        let finished = false;
        const done = value => {
          if (finished) return;
          finished = true;
          clearTimeout(timer);
          image.onload = image.onerror = null;
          if (!value) this.broken.add(album.id);
          resolve(value);
        };
        const timer = setTimeout(() => done(null), 5000);
        image.onload = () => done(image.naturalWidth ? image : null);
        image.onerror = () => done(null);
        image.src = album.artwork_url;
      });
    }
    async paint(cell, album, generation) {
      if (!album || cell.album === album.id) return;
      const image = await this.preload(album);
      if (!this.visible || document.hidden || generation !== this.generation) return;
      if (this.armedCell === cell || this.deleting) return;
      if (!image) {
        // Drop unavailable covers from this browser's queue instead of placeholders.
        this.queue.update(this.queue.albums.filter(item => !this.broken.has(item.id)));
        const replacement = this.queue.next(1)[0];
        if (replacement) await this.paint(cell, replacement, generation);
        return;
      }
      const previous = cell.element.firstElementChild;
      cell.element.append(image);
      cell.album = album.id;
      cell.label = [album.album || 'Album', album.artist].filter(Boolean).join(' — ');
      cell.element.setAttribute('aria-label', 'Remove ' + cell.label);
      cell.element.setAttribute('aria-pressed', 'false');
      if (previous && !this.motion.matches) {
        image.animate([{opacity: 0}, {opacity: 1}], {duration: 1000});
        setTimeout(() => previous.remove(), 1100);
      } else if (previous) previous.remove();
    }
    scheduleShift() {
      clearTimeout(this.shiftTimer);
      if (this.visible && !document.hidden && !this.motion.matches) this.shiftTimer = setTimeout(() => this.shift(), 8000);
    }
    async shift() {
      if (!this.visible || document.hidden || this.motion.matches) return;
      if (this.armedCell || this.deleting) { this.scheduleShift(); return; }
      if (this.cells.length && !this.animating) {
        this.animating = true;
        const generation = this.generation;
        // Move a small neighboring group, rather than reshuffling the entire wall.
        const start = Math.floor(Math.random() * this.cells.length);
        const group = Array.from({length: Math.min(3, this.cells.length)}, (_, i) => this.cells.find(cell => cell.slot === (start + i) % this.cells.length));
        const slots = group.map(cell => cell.slot);
        group.forEach((cell, i) => { cell.slot = slots[(i + 1) % slots.length]; this.position(cell); });
        const albums = this.queue.next(group.length);
        await Promise.all(group.map((cell, i) => this.paint(cell, albums[i], generation)));
        if (generation === this.generation) this.animating = false;
      }
      this.scheduleShift();
    }
  }
  globalThis.AlbumMosaic = AlbumMosaic;
  if (typeof module !== 'undefined') module.exports = {MosaicQueue};
})();
