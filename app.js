(() => {
  'use strict';

  const STORAGE_KEY = 'miner-aurora-save-v1';
  const SETTINGS_KEY = 'miner-aurora-settings-v1';
  const MAX_OFFLINE_SECONDS = 8 * 60 * 60;
  const DEFAULT_SETTINGS = { currency: 'eur', walletAddress: '', hashrate: 0, power: 0, electricity: 0, poolFee: 1 };
  const settings = loadSettings();
  let marketData = { price: null, networkHashrate: null, updatedAt: null };
  let marketRefreshTimer;
  let liveRefreshSequence = 0;
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
    views: [...document.querySelectorAll('.app-view')], navButtons: [...document.querySelectorAll('.nav-button')], liveView: $('liveView'),
    liveUpdated: $('liveUpdated'), chainSearchForm: $('chainSearchForm'), chainSearchInput: $('chainSearchInput'), chainSearchResult: $('chainSearchResult'),
    cryptoSearchForm: $('cryptoSearchForm'), cryptoSearchInput: $('cryptoSearchInput'), cryptoSearchResult: $('cryptoSearchResult'),
    currencySetting: $('currencySetting'), walletAddressSetting: $('walletAddressSetting'), hashrateSetting: $('hashrateSetting'),
    powerSetting: $('powerSetting'), electricitySetting: $('electricitySetting'), poolFeeSetting: $('poolFeeSetting'),
    saveSettingsBtn: $('saveSettingsBtn'), settingsSaveStatus: $('settingsSaveStatus'), checkWalletBtn: $('checkWalletBtn'),
    walletCheckResult: $('walletCheckResult'), settingsRouteBtn: $('settingsRouteBtn'), grossEstimate: $('grossEstimate'),
    energyEstimate: $('energyEstimate'), netEstimate: $('netEstimate'), btcEstimate: $('btcEstimate'), estimateStatus: $('estimateStatus'),
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

  function loadSettings() {
    let saved;
    try { saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || 'null'); } catch { saved = null; }
    if (!saved || typeof saved !== 'object') return { ...DEFAULT_SETTINGS };
    const boundedNumber = (value, fallback, max) => {
      const number = Number(value);
      return Number.isFinite(number) ? Math.min(max, Math.max(0, number)) : fallback;
    };
    return {
      currency: saved.currency === 'usd' ? 'usd' : 'eur',
      walletAddress: typeof saved.walletAddress === 'string' ? saved.walletAddress.trim().slice(0, 90) : '',
      hashrate: boundedNumber(saved.hashrate, 0, 100000000),
      power: boundedNumber(saved.power, 0, 10000000),
      electricity: boundedNumber(saved.electricity, 0, 100000),
      poolFee: boundedNumber(saved.poolFee, 1, 100),
    };
  }
  function saveSettings() {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
      els.settingsSaveStatus.textContent = 'Impostazioni salvate in questo browser.';
      updateEstimate();
      return true;
    } catch {
      els.settingsSaveStatus.textContent = 'Impossibile salvare le impostazioni nello spazio locale.';
      return false;
    }
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
  function formatMoney(value, currency = settings.currency) {
    if (!Number.isFinite(value)) return '—';
    return new Intl.NumberFormat('it-IT', { style: 'currency', currency: currency.toUpperCase(), maximumFractionDigits: value < 1 ? 4 : 2 }).format(value);
  }
  function formatNumber(value, digits = 2) {
    return Number(value).toLocaleString('it-IT', { maximumFractionDigits: digits });
  }
  async function fetchJson(url) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(url, { signal: controller.signal, headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`Servizio non disponibile (HTTP ${response.status}).`);
      return await response.json();
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('Richiesta scaduta: riprova tra poco.');
      throw error;
    } finally { clearTimeout(timeout); }
  }
  function setResult(element, message, isError = false) {
    element.textContent = message;
    element.classList.toggle('is-error', isError);
  }
  function updateEstimate() {
    if (!els.grossEstimate) return;
    const { price, networkHashrate } = marketData;
    const hasInputs = settings.hashrate > 0 && settings.power > 0;
    if (!Number.isFinite(price) || price <= 0 || !Number.isFinite(networkHashrate) || networkHashrate <= 0 || !Number.isSafeInteger(marketData.height) || marketData.height < 0 || !hasInputs) {
      els.grossEstimate.textContent = '—';
      els.energyEstimate.textContent = settings.power > 0 ? `${formatNumber(settings.power * 24 / 1000)} kWh` : '—';
      els.netEstimate.textContent = '—';
      els.btcEstimate.textContent = '—';
      els.estimateStatus.textContent = !settings.hashrate || !settings.power
        ? 'Inserisci hashrate e consumo nelle Impostazioni; la stima usa prezzo BTC e hashrate di rete live.'
        : 'In attesa dei dati live di prezzo BTC, hashrate e altezza del blocco.';
      return;
    }
    const height = marketData.height;
    const halvingEra = Math.floor(height / 210000);
    const subsidy = 50 / Math.pow(2, halvingEra);
    const btcBeforeFee = (settings.hashrate * 1e12 / networkHashrate) * 144 * subsidy;
    const btcPerDay = btcBeforeFee * (1 - settings.poolFee / 100);
    const gross = btcBeforeFee * price;
    const electricityKwh = settings.power * 24 / 1000;
    const energyCost = electricityKwh * settings.electricity;
    els.grossEstimate.textContent = formatMoney(gross);
    els.energyEstimate.textContent = `${formatNumber(electricityKwh)} kWh · ${formatMoney(energyCost)}`;
    els.netEstimate.textContent = formatMoney(btcPerDay * price - energyCost);
    els.btcEstimate.textContent = `${formatNumber(btcPerDay, 8)} BTC`;
    const asOf = marketData.updatedAt ? new Date(marketData.updatedAt).toLocaleTimeString('it-IT') : '—';
    els.estimateStatus.textContent = `Calcolo indicativo su ${formatNumber(networkHashrate / 1e18, 2)} EH/s, sussidio ${formatNumber(subsidy, 8)} BTC/blocco e prezzo ${formatMoney(price)} · aggiornato ${asOf}. Fee pool applicata ai BTC stimati.`;
  }
  async function refreshLiveData() {
    const requestId = ++liveRefreshSequence;
    const currency = settings.currency;
    const [priceResult, hashrateResult, heightResult] = await Promise.allSettled([
      fetchJson(`https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=${currency}`).then((data) => {
        const price = Number(data?.bitcoin?.[currency]);
        if (!Number.isFinite(price) || price <= 0) throw new Error('Prezzo BTC non valido.');
        return price;
      }),
      fetchJson('https://mempool.space/api/v1/mining/hashrate/1m').then((data) => {
        const records = data?.hashrates;
        const hashrate = Number(Array.isArray(records) ? records.at(-1)?.avgHashrate : NaN);
        if (!Number.isFinite(hashrate) || hashrate <= 0) throw new Error('Hashrate della rete non valido.');
        return hashrate;
      }),
      fetch('https://mempool.space/api/blocks/tip/height').then(async (response) => {
        if (!response.ok) throw new Error('Altezza blocco non disponibile.');
        const text = (await response.text()).trim();
        if (!/^\d+$/.test(text)) throw new Error('Altezza blocco non valida.');
        const value = Number(text);
        if (!Number.isSafeInteger(value)) throw new Error('Altezza blocco non valida.');
        return value;
      }),
    ]);
    if (requestId !== liveRefreshSequence || currency !== settings.currency) return;
    marketData.price = priceResult.status === 'fulfilled' ? priceResult.value : null;
    marketData.networkHashrate = hashrateResult.status === 'fulfilled' ? hashrateResult.value : null;
    marketData.height = heightResult.status === 'fulfilled' ? heightResult.value : null;
    marketData.updatedAt = Date.now();
    const liveErrors = [priceResult, hashrateResult, heightResult].filter((result) => result.status === 'rejected');
    els.liveUpdated.textContent = liveErrors.length === 0
      ? `BTC ${formatMoney(marketData.price)} · rete ${formatNumber((marketData.networkHashrate || 0) / 1e18, 2)} EH/s · aggiornato ${new Date().toLocaleTimeString('it-IT')}`
      : `Dati live parziali · ${liveErrors.map((result) => result.reason.message).join(' ')}`;
    updateEstimate();
  }
  function validBitcoinAddress(value) {
    return /^([13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[ac-hj-np-z02-9]{11,71})$/i.test(value);
  }
  async function searchBlockchain() {
    const query = els.chainSearchInput.value.trim();
    setResult(els.chainSearchResult, 'Ricerca in corso…');
    try {
      const base = 'https://mempool.space/api';
      if (/^\d{1,9}$/.test(query)) {
        const height = Number(query);
        const hashResponse = await fetch(`${base}/block-height/${height}`);
        if (!hashResponse.ok) throw new Error('Blocco non trovato o servizio non disponibile.');
        const hash = await hashResponse.text();
        if (!/^[a-f0-9]{64}$/i.test(hash)) throw new Error('Blocco non trovato.');
        const block = await fetchJson(`${base}/block/${hash}`);
        setResult(els.chainSearchResult, `Blocco ${block.height} · ${block.tx_count} transazioni · ${formatNumber(block.size)} byte · ${new Date(block.timestamp * 1000).toLocaleString('it-IT')} · Hash ${block.id}`);
      } else if (/^[a-f0-9]{64}$/i.test(query)) {
        try {
          const block = await fetchJson(`${base}/block/${query}`);
          setResult(els.chainSearchResult, `Blocco ${block.height} · ${block.tx_count} transazioni · ${formatNumber(block.size)} byte · ${new Date(block.timestamp * 1000).toLocaleString('it-IT')} · Hash ${block.id}`);
        } catch {
          const tx = await fetchJson(`${base}/tx/${query}`);
          const status = tx.status?.confirmed ? `confermato nel blocco ${tx.status.block_height}` : 'non ancora confermato';
          setResult(els.chainSearchResult, `Transazione ${status} · Fee ${formatNumber(tx.fee)} sat · ${tx.vin?.length || 0} input · ${tx.vout?.length || 0} output · Hash ${tx.txid}`);
        }
      } else if (validBitcoinAddress(query)) {
        const data = await fetchJson(`${base}/address/${encodeURIComponent(query)}`);
        const confirmed = (data.chain_stats?.funded_txo_sum || 0) - (data.chain_stats?.spent_txo_sum || 0);
        const pending = (data.mempool_stats?.funded_txo_sum || 0) - (data.mempool_stats?.spent_txo_sum || 0);
        setResult(els.chainSearchResult, `Indirizzo ${query} · saldo confermato ${formatNumber(confirmed / 1e8, 8)} BTC · saldo non confermato ${formatNumber(pending / 1e8, 8)} BTC · transazioni confermate ${data.chain_stats?.tx_count || 0}`);
      } else {
        throw new Error('Formato non riconosciuto. Inserisci un’altezza, un hash di 64 caratteri o un indirizzo Bitcoin mainnet.');
      }
    } catch (error) { setResult(els.chainSearchResult, error.message || 'Ricerca non riuscita.', true); }
  }
  async function searchCrypto() {
    const query = els.cryptoSearchInput.value.trim();
    els.cryptoSearchResult.replaceChildren();
    const loading = document.createElement('div'); loading.className = 'result-box'; loading.textContent = 'Ricerca in corso…'; els.cryptoSearchResult.appendChild(loading);
    try {
      const search = await fetchJson(`https://api.coingecko.com/api/v3/search?query=${encodeURIComponent(query)}`);
      const coins = (search.coins || []).slice(0, 5);
      if (!coins.length) throw new Error('Nessuna criptovaluta trovata.');
      const ids = coins.map((coin) => coin.id).join(',');
      const markets = await fetchJson(`https://api.coingecko.com/api/v3/coins/markets?vs_currency=${settings.currency}&ids=${encodeURIComponent(ids)}&price_change_percentage=24h`);
      els.cryptoSearchResult.replaceChildren();
      for (const coin of markets) {
        const card = document.createElement('div'); card.className = 'market-result';
        const title = document.createElement('strong'); title.textContent = `${coin.name} (${String(coin.symbol).toUpperCase()})`;
        const price = document.createElement('span'); price.textContent = formatMoney(coin.current_price);
        const change = document.createElement('span');
        const percent = Number(coin.price_change_percentage_24h);
        change.className = `market-change ${percent >= 0 ? 'positive' : 'negative'}`;
        change.textContent = Number.isFinite(percent) ? `${percent >= 0 ? '+' : ''}${formatNumber(percent, 2)}% · 24h` : 'Variazione 24h n/d';
        card.append(title, price, change); els.cryptoSearchResult.appendChild(card);
      }
    } catch (error) {
      const message = document.createElement('div'); message.className = 'result-box is-error'; message.textContent = error.message || 'Ricerca non riuscita.';
      els.cryptoSearchResult.replaceChildren(message);
    }
  }
  async function checkWalletBalance() {
    const address = els.walletAddressSetting.value.trim();
    if (!validBitcoinAddress(address)) { setResult(els.walletCheckResult, 'Inserisci un indirizzo Bitcoin mainnet valido; non usare seed phrase o chiavi private.', true); return; }
    settings.walletAddress = address;
    saveSettings();
    els.checkWalletBtn.disabled = true;
    setResult(els.walletCheckResult, 'Lettura del saldo pubblico…');
    try {
      const data = await fetchJson(`https://mempool.space/api/address/${encodeURIComponent(address)}`);
      const sats = (data.chain_stats?.funded_txo_sum || 0) - (data.chain_stats?.spent_txo_sum || 0);
      const btc = sats / 1e8;
      const fiatValue = Number.isFinite(marketData.price) ? formatMoney(btc * marketData.price) : 'valore fiat non disponibile';
      setResult(els.walletCheckResult, `Saldo confermato: ${formatNumber(btc, 8)} BTC (${fiatValue}). Dato pubblico on-chain, non è un wallet connesso.`);
    } catch (error) { setResult(els.walletCheckResult, error.message || 'Saldo non disponibile.', true); }
    finally { els.checkWalletBtn.disabled = false; }
  }
  function loadSettingsForm() {
    els.currencySetting.value = settings.currency;
    els.walletAddressSetting.value = settings.walletAddress;
    els.hashrateSetting.value = settings.hashrate || '';
    els.powerSetting.value = settings.power || '';
    els.electricitySetting.value = settings.electricity || '';
    els.poolFeeSetting.value = settings.poolFee;
    els.settingsRouteBtn.textContent = state.routeMode ? 'Attivo' : 'Disattivato';
  }
  function collectSettingsForm() {
    const values = [els.hashrateSetting, els.powerSetting, els.electricitySetting, els.poolFeeSetting];
    if (values.some((input) => !input.checkValidity())) {
      els.settingsSaveStatus.textContent = 'Controlla i valori inseriti: devono rientrare nei limiti indicati.';
      return false;
    }
    const address = els.walletAddressSetting.value.trim();
    if (address && !validBitcoinAddress(address)) {
      els.settingsSaveStatus.textContent = 'L’indirizzo inserito non sembra un indirizzo Bitcoin mainnet valido.';
      return false;
    }
    const previousCurrency = settings.currency;
    settings.currency = els.currencySetting.value === 'usd' ? 'usd' : 'eur';
    if (previousCurrency !== settings.currency) marketData.price = null;
    settings.walletAddress = address.slice(0, 90);
    settings.hashrate = Number(els.hashrateSetting.value) || 0;
    settings.power = Number(els.powerSetting.value) || 0;
    settings.electricity = Number(els.electricitySetting.value) || 0;
    settings.poolFee = Number(els.poolFeeSetting.value) || 0;
    return saveSettings();
  }
  function setView(viewId) {
    for (const view of els.views) view.hidden = view.id !== viewId;
    for (const button of els.navButtons) {
      const active = button.dataset.view === viewId;
      button.classList.toggle('active', active);
      if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
    }
    clearInterval(marketRefreshTimer);
    if (viewId === 'liveView') {
      refreshLiveData();
      marketRefreshTimer = setInterval(refreshLiveData, 60000);
    }
  }
  function toggleRouteMode() {
    state.routeMode = !state.routeMode;
    saveState();
    render();
    loadSettingsForm();
    showToast(state.routeMode ? `Instradamento attivo: ${Math.round(getWalletShare() * 100)}% dei crediti va al wallet demo.` : 'Instradamento wallet disattivato.');
  }
  function bindEvents() {
    els.navButtons.forEach((button) => button.addEventListener('click', () => setView(button.dataset.view)));
    els.chainSearchForm.addEventListener('submit', (event) => { event.preventDefault(); searchBlockchain(); });
    els.cryptoSearchForm.addEventListener('submit', (event) => { event.preventDefault(); searchCrypto(); });
    els.saveSettingsBtn.addEventListener('click', () => {
      if (!collectSettingsForm()) return;
      if (!els.liveView?.hidden) refreshLiveData();
    });
    els.checkWalletBtn.addEventListener('click', checkWalletBalance);
    els.settingsRouteBtn.addEventListener('click', toggleRouteMode);
    els.scanBtn.addEventListener('click', unlockNextNetwork);
    els.hireBtn.addEventListener('click', hireBot);
    els.routeBtn.addEventListener('click', toggleRouteMode);
    els.resetBtn.addEventListener('click', () => {
      if (!window.confirm('Vuoi davvero azzerare la spedizione e cancellare il salvataggio?')) return;
      state = structuredClone(DEFAULT_STATE); state.lastTick = Date.now(); saveState(); render(); loadSettingsForm(); showToast('Nuova spedizione avviata.');
    });
  }

  bindEvents();
  loadSettingsForm();
  render();
  updateEstimate();
  if (offlineGain >= 1) showToast(`Bentornato! Hai raccolto ${formatCredits(offlineGain)} offline.`);
  saveState();
  setInterval(tick, 1000);
})();
