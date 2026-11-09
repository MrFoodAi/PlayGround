(() => {
  'use strict';

  const STORAGE_KEY = 'miner-aurora-save-v1';
  const MAX_OFFLINE_SECONDS = 8 * 60 * 60;
  const NETWORKS = [
    { name: 'Asterion', reward: 8, risk: 'Basso', unlockCost: 0, description: 'Una rete stabile per avviare la flotta, con segnali puliti e routing leggero.', signal: 'Segnale stabile' },
    { name: 'Valkyr', reward: 14, risk: 'Medio', unlockCost: 38, description: 'Traffico intenso e ricompense più profonde: la prima vera prova per la tua flotta.', signal: 'Rondò intenso' },
    { name: 'Nyx', reward: 22, risk: 'Medio', unlockCost: 96, description: 'Una superficie distribuita: investi in bot e sincronizzazione per crescere più in fretta.', signal: 'Massa neutronica' },
    { name: 'Khepri', reward: 34, risk: 'Alto', unlockCost: 220, description: 'Cicli di scansione profondi, più redditizi per team ben coordinati.', signal: 'Sottoreticolo instabile' },
    { name: 'Rhea', reward: 52, risk: 'Alto', unlockCost: 520, description: 'Domini ad alta latenza con ricompense elevate e disturbi da monitorare.', signal: 'Campo di disturbo' },
    { name: 'Helios', reward: 80, risk: 'Estremo', unlockCost: 1300, description: 'La rete di frontiera: il traguardo della spedizione Aurora.', signal: 'Trasmissione critica' },
  ];
  const UPGRADE_DEFS = [
    { id: 'nodeArray', name: 'Node Array', description: 'Aumenta la produzione dei bot del 18% per livello.', baseCost: 20, scaling: 1.6 },
    { id: 'relaySync', name: 'Relay Sync', description: 'Riduce del 8% il costo degli sblocchi per livello.', baseCost: 35, scaling: 1.8 },
    { id: 'crystalCache', name: 'Crystal Cache', description: 'Riduce assunzioni e aumenta i depositi demo del 10% per livello.', baseCost: 60, scaling: 1.9 },
  ];
  const DEFAULT_STATE = {
    credits: 0,
    wallet: 0,
    totalEarned: 0,
    unlockedNetworks: 1,
    activeNetworkId: 0,
    routeMode: true,
    bots: [
      { id: 1, name: 'A-01', level: 1, power: 4, paused: false },
      { id: 2, name: 'C-04', level: 1, power: 4, paused: false },
    ],
    upgrades: { nodeArray: 0, relaySync: 0, crystalCache: 0 },
    lastTick: Date.now(),
  };
  const $ = (id) => document.getElementById(id);
  const els = {
    networkList: $('networkList'), networkProgress: $('networkProgress'),
    activeNetworkName: $('activeNetworkName'), scanBtn: $('scanBtn'),
    networkSignal: $('networkSignal'), networkReward: $('networkReward'),
    networkIndex: $('networkIndex'), networkDescription: $('networkDescription'),
    networkRisk: $('networkRisk'), networkPower: $('networkPower'), networkUnlock: $('networkUnlock'),
    hireBtn: $('hireBtn'), routeBtn: $('routeBtn'), routeStatus: $('routeStatus'), resetBtn: $('resetBtn'),
    botList: $('botList'), upgradeList: $('upgradeList'), creditsStat: $('creditsStat'),
    walletStat: $('walletStat'), totalStat: $('totalStat'), onlineBots: $('onlineBots'),
    unlockedCount: $('unlockedCount'), prodRate: $('prodRate'), statusBadge: $('statusBadge'), toast: $('toast'),
  };
  let toastTimer;
  let state = loadState();
  const offlineSeconds = Math.min(MAX_OFFLINE_SECONDS, Math.max(0, (Date.now() - state.lastTick) / 1000));
  const offlineGain = getProduction() * offlineSeconds;
  if (offlineSeconds > 0) {
    state.credits += offlineGain;
    state.totalEarned += offlineGain;
    if (state.routeMode) state.wallet += offlineGain * getWalletShare();
  }
  state.lastTick = Date.now();

  function loadState() {
    let saved;
    try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null'); } catch { saved = null; }
    if (!saved || typeof saved !== 'object') return structuredClone(DEFAULT_STATE);
    const numberOr = (value, fallback) => Number.isFinite(Number(value)) ? Math.max(0, Number(value)) : fallback;
    const unlocked = Math.min(NETWORKS.length, Math.max(1, Math.floor(numberOr(saved.unlockedNetworks, 1))));
    const bots = Array.isArray(saved.bots) ? saved.bots.filter((bot) => bot && typeof bot === 'object').map((bot, index) => ({
      id: bot.id ?? index + 1,
      name: String(bot.name || `B-${String(index + 1).padStart(2, '0')}`).slice(0, 20),
      level: Math.max(1, Math.floor(numberOr(bot.level, 1))),
      power: numberOr(bot.power, 4),
      paused: Boolean(bot.paused),
    })) : structuredClone(DEFAULT_STATE.bots);
    const upgrades = {};
    for (const def of UPGRADE_DEFS) upgrades[def.id] = Math.min(100, Math.floor(numberOr(saved.upgrades?.[def.id], 0)));
    return {
      credits: numberOr(saved.credits, 0), wallet: numberOr(saved.wallet, 0), totalEarned: numberOr(saved.totalEarned, 0),
      unlockedNetworks: unlocked,
      activeNetworkId: Math.min(unlocked - 1, Math.max(0, Math.floor(numberOr(saved.activeNetworkId, 0)))),
      routeMode: saved.routeMode !== false,
      bots,
      upgrades,
      lastTick: Number.isFinite(Number(saved.lastTick)) ? Number(saved.lastTick) : Date.now(),
    };
  }

  function saveState() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch { showToast('Impossibile salvare: spazio locale non disponibile.'); }
  }
  function formatCredits(value) {
    return `${Number(value || 0).toLocaleString('it-IT', { maximumFractionDigits: 1 })} cr`;
  }
  function showToast(message) {
    els.toast.textContent = message;
    els.toast.classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => els.toast.classList.remove('visible'), 2200);
  }
  function getActiveNetwork() { return NETWORKS[state.activeNetworkId] || NETWORKS[0]; }
  function getUpgradeCost(id) {
    const def = UPGRADE_DEFS.find((item) => item.id === id);
    return Math.round(def.baseCost * Math.pow(def.scaling, state.upgrades[id] || 0));
  }
  function getUnlockCost(index) {
    const baseCost = NETWORKS[index]?.unlockCost || 0;
    return Math.ceil(baseCost * Math.max(0.6, 1 - (state.upgrades.relaySync || 0) * 0.08));
  }
  function getHireCost() {
    const discount = Math.max(0.68, 1 - (state.upgrades.crystalCache || 0) * 0.08);
    return Math.ceil((24 + state.bots.length * 12) * discount);
  }
  function getProduction() {
    const network = getActiveNetwork();
    const botPower = state.bots.reduce((sum, bot) => sum + (bot.paused ? 0 : bot.power), 0);
    const botBonus = 1 + (state.upgrades.nodeArray || 0) * 0.18;
    return botPower * botBonus * (network.reward / 8);
  }
  function getWalletShare() { return Math.min(0.8, 0.3 + (state.upgrades.crystalCache || 0) * 0.1); }

  function unlockNextNetwork() {
    if (state.unlockedNetworks >= NETWORKS.length) {
      showToast('Tutte le reti sono state sbloccate: spedizione completata!');
      return;
    }
    const nextIndex = state.unlockedNetworks;
    const network = NETWORKS[nextIndex];
    const cost = getUnlockCost(nextIndex);
    if (state.credits < cost) {
      showToast(`Servono ${formatCredits(cost - state.credits)} per sbloccare ${network.name}.`);
      return;
    }
    state.credits -= cost;
    state.unlockedNetworks += 1;
    state.activeNetworkId = nextIndex;
    saveState();
    render();
    showToast(`${network.name} sbloccata: nuova rete attiva.`);
  }
  function selectNetwork(index) {
    if (index >= state.unlockedNetworks) {
      showToast(`Sblocca prima ${NETWORKS[index].name} con la scansione.`);
      return;
    }
    state.activeNetworkId = index;
    saveState();
    render();
  }
  function hireBot() {
    const cost = getHireCost();
    if (state.credits < cost) { showToast(`Servono ${formatCredits(cost - state.credits)} per assumere un bot.`); return; }
    state.credits -= cost;
    const network = getActiveNetwork();
    const power = Number((4 * network.reward / 8 * (1 + state.upgrades.nodeArray * 0.08)).toFixed(1));
    const number = state.bots.length + 1;
    state.bots.push({ id: `${Date.now()}-${Math.random()}`, name: `B-${String(number).padStart(2, '0')}`, level: 1, power, paused: false });
    saveState(); render(); showToast('Bot aggiunto alla flotta.');
  }
  function toggleBot(id) {
    const bot = state.bots.find((item) => item.id === id);
    if (!bot) return;
    bot.paused = !bot.paused;
    saveState(); render();
  }
  function buyUpgrade(id) {
    const def = UPGRADE_DEFS.find((item) => item.id === id);
    const cost = getUpgradeCost(id);
    if (state.credits < cost) { showToast(`Mancano ${formatCredits(cost - state.credits)} per ${def.name}.`); return; }
    state.credits -= cost;
    state.upgrades[id] += 1;
    saveState(); render(); showToast(`${def.name} migliorato al livello ${state.upgrades[id]}.`);
  }

  function renderNetworks() {
    els.networkList.replaceChildren();
    NETWORKS.forEach((network, index) => {
      const unlocked = index < state.unlockedNetworks;
      const card = document.createElement('button');
      card.type = 'button';
      card.className = `network-item ${index === state.activeNetworkId ? 'active' : ''} ${unlocked ? '' : 'disabled'}`;
      card.setAttribute('aria-pressed', String(index === state.activeNetworkId));
      card.innerHTML = `<div class="network-topline"><span class="network-name">${network.name}</span><span class="network-badge">${index === state.activeNetworkId ? 'Attiva' : unlocked ? 'Sbloccata' : `${formatCredits(getUnlockCost(index))}`}</span></div><div class="network-meta"><span>Indice ${network.reward}</span><span>${network.risk}</span></div>`;
      card.addEventListener('click', () => selectNetwork(index));
      els.networkList.appendChild(card);
    });
    els.networkProgress.textContent = `${state.unlockedNetworks}/${NETWORKS.length} reti`;
  }
  function renderActiveNetwork() {
    const network = getActiveNetwork();
    const nextIndex = state.unlockedNetworks;
    const finished = nextIndex >= NETWORKS.length;
    const cost = finished ? 0 : getUnlockCost(nextIndex);
    els.activeNetworkName.textContent = network.name;
    els.networkSignal.textContent = network.signal;
    els.networkReward.textContent = `+${getProduction().toFixed(1)} cr/sec`;
    els.networkIndex.textContent = String(state.activeNetworkId + 1).padStart(2, '0');
    els.networkDescription.textContent = network.description;
    els.networkRisk.textContent = network.risk;
    els.networkPower.textContent = String(network.reward);
    els.networkUnlock.textContent = state.activeNetworkId === 0 ? 'Rete iniziale' : `${formatCredits(network.unlockCost)} iniziali`;
    els.scanBtn.disabled = finished;
    els.scanBtn.textContent = finished ? 'Spedizione completata' : `Sblocca ${NETWORKS[nextIndex].name} · ${formatCredits(cost)}`;
    els.hireBtn.textContent = `Assumi bot · ${formatCredits(getHireCost())}`;
  }
  function renderBots() {
    els.botList.replaceChildren();
    state.bots.forEach((bot) => {
      const card = document.createElement('div');
      card.className = `bot-card ${bot.paused ? 'is-paused' : ''}`;
      card.innerHTML = `<div class="bot-head"><strong>${bot.name}</strong><span class="bot-status">${bot.paused ? 'In pausa' : 'Online'}</span></div><div class="bot-meta"><span class="bot-power">Potenza ${bot.power.toFixed(1)}</span><span class="bot-status">Lv ${bot.level}</span></div>`;
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'secondary-button';
      button.textContent = bot.paused ? 'Riattiva' : 'Metti in pausa';
      button.addEventListener('click', () => toggleBot(bot.id));
      card.appendChild(button); els.botList.appendChild(card);
    });
    if (!state.bots.length) els.botList.innerHTML = '<div class="bot-card"><strong>Nessun bot in servizio</strong></div>';
  }
  function renderUpgrades() {
    els.upgradeList.replaceChildren();
    UPGRADE_DEFS.forEach((upgrade) => {
      const level = state.upgrades[upgrade.id];
      const card = document.createElement('div');
      card.className = 'upgrade-card';
      card.innerHTML = `<div class="upgrade-head"><strong>${upgrade.name}</strong><span class="upgrade-level">Lv ${level}</span></div><div class="upgrade-meta"><span>${upgrade.description}</span></div>`;
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'primary-button';
      button.textContent = `Migliora · ${formatCredits(getUpgradeCost(upgrade.id))}`;
      button.addEventListener('click', () => buyUpgrade(upgrade.id));
      card.appendChild(button); els.upgradeList.appendChild(card);
    });
  }
  function updateHud() {
    const online = state.bots.filter((bot) => !bot.paused).length;
    els.creditsStat.textContent = formatCredits(state.credits);
    els.walletStat.textContent = formatCredits(state.wallet);
    els.totalStat.textContent = formatCredits(state.totalEarned);
    els.onlineBots.textContent = String(online);
    els.unlockedCount.textContent = String(state.unlockedNetworks);
    els.prodRate.textContent = `${getProduction().toFixed(1)} cr/s`;
    els.statusBadge.textContent = state.unlockedNetworks === NETWORKS.length ? 'COMPLETATO' : state.routeMode ? 'ROUTING ATTIVO' : 'ROUTING SPENTO';
    els.routeStatus.classList.toggle('route-off', !state.routeMode);
    els.routeStatus.classList.toggle('route-on', state.routeMode);
    els.routeStatus.innerHTML = `<span class="dot"></span> WALLET DEMO ${state.routeMode ? 'ON' : 'OFF'}`;
    els.routeBtn.textContent = state.routeMode ? 'Disattiva instradamento' : 'Attiva instradamento';
  }
  function render() { renderNetworks(); renderActiveNetwork(); renderBots(); renderUpgrades(); updateHud(); }
  function tick() {
    const now = Date.now();
    const elapsed = Math.min(MAX_OFFLINE_SECONDS, Math.max(0, (now - state.lastTick) / 1000));
    state.lastTick = now;
    const earned = getProduction() * elapsed;
    state.credits += earned;
    state.totalEarned += earned;
    if (state.routeMode) state.wallet += earned * getWalletShare();
    saveState(); render();
  }
  function bindEvents() {
    els.scanBtn.addEventListener('click', unlockNextNetwork);
    els.hireBtn.addEventListener('click', hireBot);
    els.routeBtn.addEventListener('click', () => {
      state.routeMode = !state.routeMode; saveState(); render();
      showToast(state.routeMode ? `Instradamento attivo: ${Math.round(getWalletShare() * 100)}% dei crediti va al wallet demo.` : 'Instradamento wallet disattivato.');
    });
    els.resetBtn.addEventListener('click', () => {
      if (!window.confirm('Vuoi davvero azzerare la spedizione e cancellare il salvataggio?')) return;
      state = structuredClone(DEFAULT_STATE); state.lastTick = Date.now(); saveState(); render(); showToast('Nuova spedizione avviata.');
    });
  }

  bindEvents();
  render();
  if (offlineGain >= 1) showToast(`Bentornato! Hai raccolto ${formatCredits(offlineGain)} offline.`);
  saveState();
  setInterval(tick, 1000);
})();
