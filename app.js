(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const SAVE_KEY = 'miner-aurora-save-v1';
  const networks = [
    { name: 'Luna', icon: '☾', desc: 'Orbita silenziosa', cost: 0, rate: 0.6 },
    { name: 'Nebula', icon: '✧', desc: 'Nubi di polvere stellare', cost: 180, rate: 2.4 },
    { name: 'Pulsar', icon: '◉', desc: 'Segnali ad alta energia', cost: 950, rate: 9 },
    { name: 'Cintura', icon: '◌', desc: 'Campo di asteroidi', cost: 5200, rate: 32 },
    { name: 'Quasar', icon: '✹', desc: 'Nucleo luminoso remoto', cost: 28000, rate: 115 },
    { name: 'Orizzonte', icon: '◎', desc: 'Oltre il confine noto', cost: 160000, rate: 420 },
  ];
  const upgrades = [
    { id: 'scanner', name: 'Scanner quantico', icon: '⌕', desc: 'I bot raccolgono il 50% in più.', base: 80, multiplier: 2.3, effect: 'Produzione ×1,5', max: 8 },
    { id: 'processor', name: 'Nucleo ottimizzato', icon: '⟁', desc: 'Più Aurora da ogni impulso manuale.', base: 120, multiplier: 2.15, effect: 'Impulso ×2', max: 6 },
    { id: 'relay', name: 'Relay autonomo', icon: '⌁', desc: 'Una nuova rete aumenta il rendimento globale.', base: 260, multiplier: 2.6, effect: 'Bonus rete +15%', max: 5 },
  ];
  const defaults = () => ({ credits: 0, lifetime: 0, vault: 0, bots: 1, unlocked: [0], upgrades: { scanner: 0, processor: 0, relay: 0 }, paused: false, routing: false, xp: 0, startedAt: Date.now(), lastAt: Date.now(), totalScans: 0, missionStage: 0, sound: false });
  let state = load();
  let lastScan = 0;
  let toastTimer;
  let audioContext;

  function load() {
    try {
      const saved = JSON.parse(localStorage.getItem(SAVE_KEY));
      if (!saved || typeof saved !== 'object') return defaults();
      const fresh = { ...defaults(), ...saved };
      fresh.upgrades = { ...defaults().upgrades, ...(saved.upgrades || {}) };
      fresh.unlocked = Array.isArray(saved.unlocked) ? [...new Set([0, ...saved.unlocked.filter((n) => Number.isInteger(n) && n >= 0 && n < networks.length)])].sort((a,b) => a-b) : [0];
      fresh.bots = Math.max(1, Math.min(1000, Number(fresh.bots) || 1));
      fresh.credits = Math.max(0, Number(fresh.credits) || 0);
      fresh.lifetime = Math.max(fresh.credits, Number(fresh.lifetime) || 0);
      fresh.vault = Math.max(0, Number(fresh.vault) || 0);
      fresh.xp = Math.max(0, Number(fresh.xp) || 0);
      const away = Math.min(8 * 60 * 60, Math.max(0, (Date.now() - (Number(saved.lastAt) || Date.now())) / 1000));
      if (!fresh.paused && away > 2) {
        const earned = rateFor(fresh) * away;
        fresh.credits += earned * (fresh.routing ? 0.8 : 1);
        fresh.vault += earned * (fresh.routing ? 0.2 : 0);
        fresh.lifetime += earned;
        fresh.xp += earned * 0.1;
        fresh.offlineEarned = earned;
      }
      fresh.lastAt = Date.now();
      return fresh;
    } catch { return defaults(); }
  }
  function save() {
    state.lastAt = Date.now();
    try { localStorage.setItem(SAVE_KEY, JSON.stringify(state)); } catch { toast('Salvataggio non disponibile in questo browser.'); }
  }
  function rateFor(s = state) {
    if (s.paused) return 0;
    const networkRate = s.unlocked.reduce((sum, i) => sum + networks[i].rate, 0);
    const scanner = 1 + (s.upgrades.scanner || 0) * 0.5;
    const relay = 1 + (s.upgrades.relay || 0) * 0.15;
    return networkRate * (1 + (s.bots - 1) * 0.72) * scanner * relay;
  }
  function levelFor(xp = state.xp) { return Math.floor(Math.sqrt(Math.max(0, xp) / 100)) + 1; }
  function levelProgress() { const lv = levelFor(); return { lv, current: state.xp - (lv - 1) ** 2 * 100, needed: lv ** 2 * 100 - (lv - 1) ** 2 * 100 }; }
  function fmt(value, digits = 1) {
    if (!Number.isFinite(value)) return '—';
    if (value >= 1e9) return (value / 1e9).toLocaleString('it-IT', { maximumFractionDigits: 2 }) + 'B';
    if (value >= 1e6) return (value / 1e6).toLocaleString('it-IT', { maximumFractionDigits: 2 }) + 'M';
    if (value >= 1e4) return Math.floor(value).toLocaleString('it-IT');
    return value.toLocaleString('it-IT', { maximumFractionDigits: digits });
  }
  function rankName(level) { return ['Recluta', 'Esploratore', 'Cartografo', 'Operatore', 'Pioniere', 'Comandante', 'Custode'][Math.min(6, Math.floor((level - 1) / 3))]; }
  function botCapacity() { return 8 + (levelFor() - 1) * 2; }
  function botCost() { return Math.floor(50 * Math.pow(1.48, state.bots - 1)); }
  function canAfford(cost) { return state.credits + 1e-8 >= cost; }
  function spend(amount) { if (!canAfford(amount)) return false; state.credits -= amount; return true; }
  function setText(id, text) { $(id).textContent = text; }
  function render() {
    const rate = rateFor();
    const progress = levelProgress();
    setText('credits', fmt(state.credits)); setText('lifetime', fmt(state.lifetime)); setText('rate', fmt(rate));
    setText('bots', state.bots); setText('botCap', botCapacity()); setText('networkCount', state.unlocked.length);
    setText('vault', fmt(state.vault)); setText('routeStatus', state.routing ? 'Instradamento attivo · 20%' : 'Instradamento disattivato');
    setText('rank', `${String(progress.lv).padStart(2, '0')} · ${rankName(progress.lv)}`);
    $('rankProgress').style.width = `${Math.min(100, progress.current / progress.needed * 100)}%`;
    setText('rankHint', `${fmt(progress.current, 0)} / ${fmt(progress.needed, 0)} XP al prossimo grado`);
    const elapsed = Math.max(0, Math.floor((Date.now() - state.startedAt) / 1000));
    setText('uptime', `${String(Math.floor(elapsed / 3600)).padStart(2, '0')}:${String(Math.floor(elapsed / 60) % 60).padStart(2, '0')}`);
    setText('lastSave', state.paused ? 'Partita in pausa' : 'Salvataggio locale attivo');
    $('pauseBtn').innerHTML = state.paused ? '<span>▶</span> Riprendi flotta' : '<span>Ⅱ</span> Metti in pausa';
    $('fleetStatus').classList.toggle('paused', state.paused);
    setText('fleetStatus', state.paused ? 'FLOTTA IN PAUSA' : 'FLOTTA OPERATIVA');
    setText('fleetTitle', state.paused ? 'La flotta è in attesa.' : 'La tua squadra è pronta.');
    setText('fleetMessage', state.paused ? 'La produzione riprenderà quando riattivi i bot.' : `I bot scandagliano ${state.unlocked.length} ${state.unlocked.length === 1 ? 'rete selezionata' : 'reti selezionate'} in cerca di frammenti Aurora.`);
    setText('efficiency', `${Math.round((1 + state.upgrades.scanner * 0.5) * (1 + state.upgrades.relay * 0.15) * 100)}%`);
    setText('nextBonus', fmt(100 * (1 + (state.upgrades.scanner || 0) * 0.5)) + ' Aurora');
    setText('networkTotal', `${String(state.unlocked.length).padStart(2, '0')} / 06`);
    renderNetworks(); renderUpgrades(); renderMission();
    $('routeToggle').classList.toggle('on', state.routing); $('routeToggle').setAttribute('aria-checked', String(state.routing));
    setText('routeLabel', state.routing ? 'Instradamento attivo' : 'Instradamento disattivato');
    setText('routeSub', state.routing ? 'Il 20% va all’archivio demo' : 'I crediti restano disponibili');
    const vaultPercent = Math.min(100, state.vault / 10000 * 100);
    setText('vaultPercent', `${Math.floor(vaultPercent)}%`); $('vaultMeter').style.width = `${vaultPercent}%`;
    setText('botCost', `${fmt(botCost(), 0)} ✦`);
    $('buyBotBtn').disabled = state.bots >= botCapacity() || !canAfford(botCost());
    $('buyBotBtn').classList.toggle('unavailable', $('buyBotBtn').disabled);
    $('scanBtn').disabled = state.paused || Date.now() - lastScan < 900;
    $('scanHint').textContent = state.paused ? 'Riattiva la flotta per continuare' : (Date.now() - lastScan < 900 ? 'Impulso in ricarica…' : 'Invia un impulso alla rete · pronto');
    $('soundBtn').innerHTML = state.sound ? '♫ <span>Audio on</span>' : '♫ <span>Audio off</span>';
  }
  function renderNetworks() {
    $('networkGrid').innerHTML = networks.map((network, i) => {
      const unlocked = state.unlocked.includes(i);
      const next = i === 0 || state.unlocked.includes(i - 1);
      const cost = Math.floor(network.cost * (1 + state.upgrades.relay * 0.08));
      const action = unlocked ? '<span class="network-active"><i></i> SCANSIONE</span>' : next ? `<button class="unlock-button" data-network="${i}" ${canAfford(cost) ? '' : 'disabled'}>Sblocca · ${fmt(cost, 0)} ✦</button>` : '<span class="network-locked">◌ SIGILLATA</span>';
      return `<article class="network-card ${unlocked ? 'unlocked' : 'locked'}"><div class="network-symbol">${network.icon}</div><div class="network-info"><b>${network.name}</b><small>${unlocked ? `+${fmt(network.rate * (1 + state.upgrades.scanner * 0.5) * (1 + state.upgrades.relay * 0.15))}/sec base` : network.desc}</small></div><div class="network-action">${action}</div></article>`;
    }).join('');
    $('networkGrid').querySelectorAll('[data-network]').forEach((button) => button.addEventListener('click', () => unlockNetwork(Number(button.dataset.network))));
  }
  function renderUpgrades() {
    $('upgradeList').innerHTML = upgrades.map((upgrade) => {
      const level = state.upgrades[upgrade.id] || 0;
      const cost = Math.floor(upgrade.base * upgrade.multiplier ** level);
      const maxed = level >= upgrade.max;
      return `<article class="upgrade-row"><span class="upgrade-icon">${upgrade.icon}</span><div class="upgrade-info"><b>${upgrade.name} <i>Lv.${level}/${upgrade.max}</i></b><small>${upgrade.desc}</small></div><span class="upgrade-effect">${upgrade.effect}</span><button class="upgrade-button" data-upgrade="${upgrade.id}" ${maxed || !canAfford(cost) ? 'disabled' : ''}>${maxed ? 'MAX' : `✦ ${fmt(cost, 0)}`}</button></article>`;
    }).join('');
    $('upgradeList').querySelectorAll('[data-upgrade]').forEach((button) => button.addEventListener('click', () => buyUpgrade(button.dataset.upgrade)));
  }
  function renderMission() {
    const missions = [
      { title: 'Primo contatto', text: 'Raccogli 100 Aurora per calibrare la stazione.', goal: 100, value: state.lifetime, reward: 50 },
      { title: 'Piccola flotta', text: 'Schiera 3 bot per automatizzare la ricerca.', goal: 3, value: state.bots, reward: 150 },
      { title: 'Oltre la Luna', text: 'Sblocca la rete Nebula e amplia l’orizzonte.', goal: 2, value: state.unlocked.length, reward: 300 },
      { title: 'Segnale profondo', text: 'Raggiungi 2.500 Aurora raccolte in totale.', goal: 2500, value: state.lifetime, reward: 600 },
      { title: 'Rotta tracciata', text: 'Attiva l’archivio virtuale e raccogli 1.000 Aurora.', goal: 1000, value: state.vault, reward: 1000 },
      { title: 'Cartografo stellare', text: 'Sblocca quattro reti della galassia.', goal: 4, value: state.unlocked.length, reward: 2200 },
    ];
    const stage = Math.min(state.missionStage || 0, missions.length);
    const mission = missions[stage] || { title: 'Orizzonte infinito', text: 'La galassia è tua: continua a migliorare la stazione!', goal: 100000, value: state.lifetime, reward: 0, done: true };
    setText('missionTitle', mission.title); setText('missionText', mission.text);
    setText('missionCount', `${fmt(Math.min(mission.value, mission.goal), 0)} / ${fmt(mission.goal, 0)}`);
    $('missionMeter').style.width = `${Math.min(100, mission.value / mission.goal * 100)}%`;
    if (!mission.done && mission.value >= mission.goal) {
      state.missionStage = stage + 1; state.credits += mission.reward; state.lifetime += mission.reward;
      toast(`Obiettivo completato! +${fmt(mission.reward, 0)} Aurora`); playTone(680, 0.14);
      save();
      setTimeout(render, 0);
    }
  }
  function unlockNetwork(index) {
    if (!Number.isInteger(index) || state.unlocked.includes(index) || !state.unlocked.includes(index - 1)) return;
    const cost = Math.floor(networks[index].cost * (1 + state.upgrades.relay * 0.08));
    if (!spend(cost)) return;
    state.unlocked.push(index); state.unlocked.sort((a,b) => a-b); state.xp += 18;
    toast(`${networks[index].name} ora è in scansione.`); playTone(560, 0.12); save(); render();
  }
  function buyUpgrade(id) {
    const upgrade = upgrades.find((item) => item.id === id); if (!upgrade) return;
    const level = state.upgrades[id] || 0; if (level >= upgrade.max) return;
    const cost = Math.floor(upgrade.base * upgrade.multiplier ** level); if (!spend(cost)) return;
    state.upgrades[id] = level + 1; state.xp += 12;
    toast(`${upgrade.name} potenziato al livello ${level + 1}.`); playTone(620, 0.1); save(); render();
  }
  function buyBot() {
    if (state.bots >= botCapacity()) { toast('Capacità massima raggiunta: sali di grado.'); return; }
    const cost = botCost(); if (!spend(cost)) return;
    state.bots++; state.xp += 8; toast('Nuovo bot operativo.'); playTone(520, 0.1); save(); render();
  }
  function manualScan() {
    const now = Date.now(); if (state.paused || now - lastScan < 900) return;
    lastScan = now;
    const amount = 10 * (1 + state.upgrades.processor * 1.15) * (1 + (state.unlocked.length - 1) * 0.2);
    addEarnings(amount); state.totalScans++; state.xp += amount * 0.04;
    toast(`Impulso riuscito · +${fmt(amount)} Aurora`); playTone(740, 0.08); save(); render();
  }
  function addEarnings(amount) {
    const toVault = state.routing ? amount * 0.2 : 0;
    state.credits += amount - toVault; state.vault += toVault; state.lifetime += amount;
    state.xp += amount * 0.1;
  }
  function toast(message) {
    const el = $('toast'); el.textContent = message; el.classList.add('visible');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('visible'), 2600);
  }
  function playTone(freq, duration) {
    if (!state.sound) return;
    try {
      audioContext ||= new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioContext.createOscillator(), gain = audioContext.createGain();
      oscillator.type = 'sine'; oscillator.frequency.value = freq; gain.gain.setValueAtTime(0.04, audioContext.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + duration);
      oscillator.connect(gain); gain.connect(audioContext.destination); oscillator.start(); oscillator.stop(audioContext.currentTime + duration);
    } catch { /* Audio is an optional enhancement. */ }
  }
  $('pauseBtn').addEventListener('click', () => { state.paused = !state.paused; toast(state.paused ? 'Flotta in pausa.' : 'Flotta di nuovo operativa.'); save(); render(); });
  $('scanBtn').addEventListener('click', manualScan);
  $('buyBotBtn').addEventListener('click', buyBot);
  $('routeToggle').addEventListener('click', () => { state.routing = !state.routing; toast(state.routing ? 'Instradamento demo attivato · 20% dei crediti.' : 'Instradamento demo disattivato.'); save(); render(); });
  $('soundBtn').addEventListener('click', () => { state.sound = !state.sound; if (state.sound) playTone(660, 0.1); save(); render(); });
  $('resetBtn').addEventListener('click', () => $('resetDialog').showModal());
  $('confirmReset').addEventListener('click', (event) => { event.preventDefault(); localStorage.removeItem(SAVE_KEY); state = defaults(); $('resetDialog').close(); toast('Nuova partita iniziata.'); render(); save(); });
  window.addEventListener('keydown', (event) => { if (event.code === 'Space' && !event.repeat && !['BUTTON', 'INPUT', 'TEXTAREA'].includes(document.activeElement.tagName) && !$('resetDialog').open) { event.preventDefault(); manualScan(); } });
  if (state.offlineEarned > 0) { const awayGain = state.offlineEarned; delete state.offlineEarned; toast(`Bentornato! La flotta ha raccolto ${fmt(awayGain)} Aurora offline.`); }
  render(); save();
  let previous = Date.now();
  window.setInterval(() => {
    const now = Date.now(), seconds = Math.min(2, Math.max(0, (now - previous) / 1000)); previous = now;
    const rate = rateFor();
    if (rate > 0 && seconds > 0) {
      const earned = rate * seconds, diverted = state.routing ? earned * 0.2 : 0;
      state.credits += earned - diverted; state.vault += diverted; state.lifetime += earned; state.xp += earned * 0.1;
      if (state.lifetime % 20 < earned) save();
    }
    render();
  }, 250);
  window.addEventListener('beforeunload', save);
})();
