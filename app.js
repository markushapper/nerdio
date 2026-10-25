(() => {
  'use strict';
  const Core = window.NerdioCore;
  const DB_NAME = 'nerdio';
  const DB_VERSION = 1;
  const PACK_STORE = 'packs';
  const PROGRESS_PREFIX = 'nerdio-progress:';

  let db;
  let currentPack = null;
  let currentProgress = null;
  let deferredInstallPrompt = null;

  const els = {
    libraryScreen: document.getElementById('libraryScreen'), playScreen: document.getElementById('playScreen'),
    screenTitle: document.getElementById('screenTitle'), backButton: document.getElementById('backButton'),
    installButton: document.getElementById('installButton'), packList: document.getElementById('packList'),
    fileInput: document.getElementById('packFileInput'), libraryMessage: document.getElementById('libraryMessage'),
    roundLabel: document.getElementById('roundLabel'), shuffleButton: document.getElementById('shuffleButton'),
    mysteryState: document.getElementById('mysteryState'), revealState: document.getElementById('revealState'),
    playLink: document.getElementById('playLink'), revealButton: document.getElementById('revealButton'),
    songTitle: document.getElementById('songTitle'), songArtist: document.getElementById('songArtist'),
    songYear: document.getElementById('songYear'), nextButton: document.getElementById('nextButton'),
    skipButton: document.getElementById('skipButton'), playMessage: document.getElementById('playMessage'),
    dialog: document.getElementById('confirmDialog'), dialogTitle: document.getElementById('dialogTitle'),
    dialogText: document.getElementById('dialogText'), dialogConfirm: document.getElementById('dialogConfirm')
  };

  function openDb() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const database = req.result;
        if (!database.objectStoreNames.contains(PACK_STORE)) database.createObjectStore(PACK_STORE, { keyPath: 'pack_id' });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  function dbAllPacks() {
    return new Promise((resolve, reject) => {
      const req = db.transaction(PACK_STORE, 'readonly').objectStore(PACK_STORE).getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
  }

  function dbPutPack(pack) {
    return new Promise((resolve, reject) => {
      const tx = db.transaction(PACK_STORE, 'readwrite');
      tx.objectStore(PACK_STORE).put(pack);
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
  }

  function dbDeletePack(packId) {
    return new Promise((resolve, reject) => {
      const tx = db.transaction(PACK_STORE, 'readwrite');
      tx.objectStore(PACK_STORE).delete(packId);
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
  }

  async function loadBuiltinPack() {
    const res = await fetch('./packs/halloween.json', { cache: 'no-store' });
    if (!res.ok) throw new Error('Mitgeliefertes Halloween-Pack konnte nicht geladen werden.');
    const pack = await res.json();
    const validation = Core.validatePack(pack);
    if (!validation.ok) throw new Error(`Halloween-Pack ungültig: ${validation.errors[0]}`);
    return { ...pack, __builtin: true };
  }

  function normalizeAmazonPlayUrl(url) {
    try {
      const parsed = new URL(url);
      if (/amazon\.(de|com|co\.uk|fr|it|es)$/i.test(parsed.hostname) || /music\.amazon\./i.test(parsed.hostname)) {
        if (!parsed.searchParams.has('do')) parsed.searchParams.set('do', 'play');
      }
      return parsed.toString();
    } catch {
      if (typeof url === 'string' && url && !/[?&]do=/.test(url)) {
        return url + (url.includes('?') ? '&' : '?') + 'do=play';
      }
      return url;
    }
  }

  function progressKey(packId) { return `${PROGRESS_PREFIX}${packId}`; }
  function getProgress(pack) {
    try {
      const raw = localStorage.getItem(progressKey(pack.pack_id));
      return Core.sanitizeProgress(pack, raw ? JSON.parse(raw) : null);
    } catch { return Core.newProgress(pack); }
  }
  function saveProgress() {
    if (currentPack && currentProgress) localStorage.setItem(progressKey(currentPack.pack_id), JSON.stringify(currentProgress));
  }
  function resetProgress(pack) { localStorage.removeItem(progressKey(pack.pack_id)); }

  function setMessage(target, text, isError = false) {
    target.textContent = text || '';
    target.style.color = isError ? '#f0a0a0' : '';
  }

  async function renderLibrary() {
    let packs = [];
    try { packs = [await loadBuiltinPack(), ...(await dbAllPacks()).map(p => ({ ...p, __builtin: false }))]; }
    catch (err) { setMessage(els.libraryMessage, err.message, true); }

    const unique = new Map();
    packs.forEach(pack => { if (!unique.has(pack.pack_id) || pack.__builtin) unique.set(pack.pack_id, pack); });
    const finalPacks = [...unique.values()];
    els.packList.innerHTML = '';

    finalPacks.forEach(pack => {
      const saved = localStorage.getItem(progressKey(pack.pack_id));
      let roundText = '';
      if (saved) {
        try {
          const p = Core.sanitizeProgress(pack, JSON.parse(saved));
          if (p.cursor > 0 || p.revealed) roundText = ` · Runde ${p.cursor + 1}`;
        } catch {}
      }
      const card = document.createElement('article');
      card.className = 'pack-card';
      card.innerHTML = `
        <div class="pack-card-top">
          <div><h2 class="pack-name"></h2><p class="pack-meta"></p></div>
          <span class="pack-badge">${pack.__builtin ? 'Mitgeliefert' : 'Importiert'}</span>
        </div>
        <div class="pack-actions">
          <button class="primary-button play-pack" type="button">Spielen</button>
          <button class="secondary-button reset-pack" type="button" aria-label="Fortschritt zurücksetzen">↻</button>
          ${pack.__builtin ? '<span></span>' : '<button class="secondary-button delete-pack" type="button" aria-label="Pack löschen">🗑</button>'}
        </div>`;
      card.querySelector('.pack-name').textContent = pack.playlist_name;
      card.querySelector('.pack-meta').textContent = `${pack.songs.length} Songs${roundText}`;
      card.querySelector('.play-pack').addEventListener('click', () => openPack(pack));
      card.querySelector('.reset-pack').addEventListener('click', async () => {
        const ok = await confirmAction('Fortschritt zurücksetzen?', `„${pack.playlist_name}“ wird beim nächsten Start neu gemischt.`);
        if (ok) { resetProgress(pack); renderLibrary(); }
      });
      const del = card.querySelector('.delete-pack');
      if (del) del.addEventListener('click', async () => {
        const ok = await confirmAction('Pack löschen?', `„${pack.playlist_name}“ wird nur von diesem Gerät entfernt.`);
        if (ok) { await dbDeletePack(pack.pack_id); resetProgress(pack); renderLibrary(); }
      });
      els.packList.appendChild(card);
    });
  }

  function showScreen(name) {
    const play = name === 'play';
    els.libraryScreen.classList.toggle('active', !play);
    els.playScreen.classList.toggle('active', play);
    els.backButton.classList.toggle('hidden', !play);
    els.screenTitle.textContent = play ? currentPack.playlist_name : 'NERDIO';
  }

  function openPack(pack) {
    currentPack = pack;
    currentProgress = getProgress(pack);
    showScreen('play');
    renderRound();
  }

  function renderRound() {
    const song = Core.currentSong(currentPack, currentProgress);
    els.roundLabel.textContent = `Runde ${currentProgress.cursor + 1} / ${currentPack.songs.length}`;
    els.playLink.href = normalizeAmazonPlayUrl(song.amazon_play_url);
    els.songTitle.textContent = song.title;
    els.songArtist.textContent = song.artist;
    els.songYear.textContent = song.scoring_year;
    els.mysteryState.classList.toggle('hidden', currentProgress.revealed);
    els.revealState.classList.toggle('hidden', !currentProgress.revealed);
    setMessage(els.playMessage, '');
    saveProgress();
  }

  function reveal() { currentProgress.revealed = true; renderRound(); }
  function nextSong(skipped = false) {
    const wasLast = currentProgress.cursor === currentPack.songs.length - 1;
    currentProgress = Core.advance(currentPack, currentProgress);
    renderRound();
    if (wasLast) setMessage(els.playMessage, 'Pack einmal durchgespielt – neue Runde beginnt.', false);
    if (skipped) setMessage(els.playMessage, 'Song übersprungen.', false);
  }

  async function confirmAction(title, text) {
    els.dialogTitle.textContent = title;
    els.dialogText.textContent = text;
    els.dialog.showModal();
    return new Promise(resolve => {
      const handler = () => { els.dialog.removeEventListener('close', handler); resolve(els.dialog.returnValue === 'confirm'); };
      els.dialog.addEventListener('close', handler);
    });
  }

  async function importPack(file) {
    setMessage(els.libraryMessage, '');
    try {
      const pack = JSON.parse((await file.text()).replace(/^\uFEFF/, ''));
      const result = Core.validatePack(pack);
      if (!result.ok) throw new Error(result.errors.slice(0, 3).join(' '));
      const builtin = await loadBuiltinPack();
      if (pack.pack_id === builtin.pack_id) throw new Error('Dieser Pack ist bereits als mitgelieferter Pack vorhanden.');
      await dbPutPack(pack);
      setMessage(els.libraryMessage, `„${pack.playlist_name}“ importiert.`);
      await renderLibrary();
    } catch (err) {
      setMessage(els.libraryMessage, `Import fehlgeschlagen: ${err.message}`, true);
    } finally {
      els.fileInput.value = '';
    }
  }

  els.fileInput.addEventListener('change', e => { if (e.target.files?.[0]) importPack(e.target.files[0]); });
  els.backButton.addEventListener('click', () => { currentPack = null; currentProgress = null; showScreen('library'); renderLibrary(); });
  els.revealButton.addEventListener('click', reveal);
  els.nextButton.addEventListener('click', () => nextSong(false));
  els.skipButton.addEventListener('click', () => nextSong(true));
  els.shuffleButton.addEventListener('click', async () => {
    const ok = await confirmAction('Neu mischen?', 'Die bisherige Reihenfolge dieses Packs wird verworfen.');
    if (ok) { currentProgress = Core.newProgress(currentPack); renderRound(); }
  });

  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    deferredInstallPrompt = event;
    els.installButton.classList.remove('hidden');
  });
  els.installButton.addEventListener('click', async () => {
    if (!deferredInstallPrompt) return;
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    els.installButton.classList.add('hidden');
  });
  window.addEventListener('appinstalled', () => {
    deferredInstallPrompt = null;
    els.installButton.classList.add('hidden');
  });

  async function init() {
    try {
      db = await openDb();
      await renderLibrary();
      if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(() => {});
    } catch (err) {
      setMessage(els.libraryMessage, `Start fehlgeschlagen: ${err.message}`, true);
    }
  }
  init();
})();
