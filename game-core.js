(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.SongRevealCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function validatePack(pack) {
    const errors = [];
    if (!pack || typeof pack !== 'object') return { ok: false, errors: ['Datei enthält kein JSON-Objekt.'] };
    if (typeof pack.pack_id !== 'string' || !pack.pack_id.trim()) errors.push('pack_id fehlt.');
    if (typeof pack.playlist_name !== 'string' || !pack.playlist_name.trim()) errors.push('playlist_name fehlt.');
    if (pack.status && pack.status !== 'READY') errors.push('Pack ist nicht READY.');
    if (!Array.isArray(pack.songs) || pack.songs.length === 0) errors.push('songs fehlt oder ist leer.');
    if (Array.isArray(pack.songs)) {
      const ids = new Set();
      pack.songs.forEach((song, i) => {
        const n = i + 1;
        if (!song || typeof song !== 'object') { errors.push(`Song ${n} ist ungültig.`); return; }
        if (typeof song.title !== 'string' || !song.title.trim()) errors.push(`Song ${n}: title fehlt.`);
        if (typeof song.artist !== 'string' || !song.artist.trim()) errors.push(`Song ${n}: artist fehlt.`);
        if (!Number.isInteger(song.scoring_year)) errors.push(`Song ${n}: scoring_year ist ungültig.`);
        if (typeof song.amazon_play_url !== 'string' || !/^https:\/\//i.test(song.amazon_play_url)) errors.push(`Song ${n}: amazon_play_url ist ungültig.`);
        const id = song.song_id || `${song.title}__${song.artist}__${song.scoring_year}`;
        if (ids.has(id)) errors.push(`Song ${n}: doppelte Song-ID.`);
        ids.add(id);
      });
    }
    return { ok: errors.length === 0, errors };
  }

  function shuffledIndices(length, randomFn) {
    const rand = randomFn || Math.random;
    const arr = Array.from({ length }, (_, i) => i);
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(rand() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  function newProgress(pack, randomFn) {
    return { order: shuffledIndices(pack.songs.length, randomFn), cursor: 0, revealed: false };
  }

  function sanitizeProgress(pack, progress, randomFn) {
    if (!progress || !Array.isArray(progress.order) || progress.order.length !== pack.songs.length) return newProgress(pack, randomFn);
    const expected = new Set(Array.from({ length: pack.songs.length }, (_, i) => i));
    for (const i of progress.order) {
      if (!Number.isInteger(i) || !expected.delete(i)) return newProgress(pack, randomFn);
    }
    const cursor = Math.max(0, Math.min(Number.isInteger(progress.cursor) ? progress.cursor : 0, pack.songs.length - 1));
    return { order: progress.order, cursor, revealed: Boolean(progress.revealed) };
  }

  function currentSong(pack, progress) { return pack.songs[progress.order[progress.cursor]]; }
  function advance(pack, progress) {
    const cursor = progress.cursor + 1;
    return { ...progress, cursor: cursor >= pack.songs.length ? 0 : cursor, revealed: false };
  }
  return { validatePack, shuffledIndices, newProgress, sanitizeProgress, currentSong, advance };
});
