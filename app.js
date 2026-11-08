(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const networks = [
    { name: 'Bitcoin', symbol: '₿', color: '#f5b765', protocol: 'Proof of Work', yield: 2.4, load: 76 },
    { name: 'Ethereum', symbol: '◆', color: '#8da8ff', protocol: 'Proof of Stake', yield: 1.8, load: 53 },
    { name: 'Solana', symbol: '◎', color: '#bd9cff', protocol: 'Proof of History', yield: 3.2, load: 88 },
    { name: 'Polygon', symbol: '⬡', color: '#bb91ff', protocol: 'Proof of Stake', yield: 2.1, load: 63 },
    { name: 'Avalanche', symbol: '▲', color: '#ff858b', protocol: 'Proof of Stake', yield: 2.7, load: 41 },
    { name: 'Arbitrum', symbol: '◉', color: '#75c5ed', protocol: 'Layer 2', yield: 1.6, load: 58 },
  ];
  const botTemplates = [
    { name: 'Aurora-01', type: 'Ricognitore', hue: '', power: 4.8, network: 'Bitcoin', icon: '⌁' },
    { name: 'Nexus-02', type: 'Validatore', hue: 'blue', power: 4.2, network: 'Ethereum', icon: '◇' },
    { name: 'Pixel-03', type: 'Ottimizzatore', hue: 'purple', power: 3.8, network: 'Solana', icon: '✳' },
    { name: 'Nova-04', type: 'Ricognitore', hue: '', power: 5.1, network: 'Polygon', icon: '⌁' },
    { name: 'Echo-05', type: 'Validatore', hue: 'blue', power: 4.6, network: 'Avalanche', icon: '◇' },
    { name: 'Flux-06', type: 'Ottimizzatore', hue: 'purple', power: 5.4, network: 'Arbitrum', icon: '✳' },
    { name: 'Orbit-07', type: 'Ricognitore', hue: '', power: 6.1, network: 'Bitcoin', icon: '⌁' },
    { name: 'Solis-08', type: 'Validatore', hue: 'blue', power: 6.8, network: 'Ethereum', icon: '◇' },
  ];
  const defaults = { balance: 0.000126, wallet: 0.000842, lifetime: 0.001426, bots: [0, 1, 2], paused: [], route: true, autoScan: true, level: 1, scanned: 0, history: [] };
  let state;
  try { state = { ...defaults, ...JSON.parse(localStorage.getItem('mineros-save') || '{}') }; }
  catch { state = { ...defaults }; }
  state.bots = Array.isArray(state.bots) ? state.bots : defaults.bots.slice();
  state.paused = Array.isArray(state.paused) ? state.paused : [];
  state.history = Array.isArray(state.history) ? state.history : [];
  let lastTick = Date.now();
  let toastTimer;
  let isScanning = false;
  let soundOn = false;
  let audio;

  const format = (v) => Number(v || 0).toFixed(6);
  const save = () => { try { localStorage.setItem('mineros-save', JSON.stringify(state)); } catch (_) {} };
  const notify = (message) => {
    $('toastMessage').textContent = message;
    $('toast').classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => $('toast').classList.remove('show'), 2600);
  };
  function beep(freq = 650) {
    if (!soundOn) return;
    try {
      audio ||= new (window.AudioContext || window.webkitAudioContext)();
      const osc = audio.createOscillator(), gain = audio.createGain();
      osc.frequency.value = freq; osc.type = 'sine'; gain.gain.value = .035;
      osc.connect(gain); gain.connect(audio.destination); osc.start();
      gain.gain.exponentialRampToValueAtTime(.001, audio.currentTime + .12); osc.stop(audio.currentTime + .13);
    } catch (_) {}
  }
  function renderNetworks() {
    $('networkList').innerHTML = networks.map((n, i) => `
      <div class="network-row" data-network="${n.name}" style="--coin:${n.color}">
        <div class="network-logo">${n.symbol}</div>
        <div class="network-name"><b>${n.name}</b><small>${n.protocol}</small></div>
        <div class="network-meter"><i style="width:${n.load}%"></i></div>
        <div class="network-apy">${n.yield.toFixed(1)}%</div>
        <i class="network-state ${i === 4 ? 'busy' : ''}" title="${i === 4 ? 'Carico elevato' : 'Rete disponibile'}"></i>
      </div>`).join('');
  }
  function renderBots() {
    const active = state.bots.filter((id) => !state.paused.includes(id)).length;
    $('botList').innerHTML = state.bots.map((id) => {
      const b = botTemplates[id];
      const paused = state.paused.includes(id);
      return `<div class="bot-row"><div class="bot-avatar ${b.hue}">${b.icon}</div><div class="bot-name"><b>${b.name}</b><small>${b.type}</small></div><div class="bot-stat">${b.power.toFixed(1)} TH/s<small>${b.network}</small></div><div class="bot-status" style="color:${paused ? '#9299a5' : ''}"><i style="background:${paused ? '#707887' : ''}"></i>${paused ? 'PAUSA' : 'ATTIVO'}</div><button class="bot-pause" data-pause="${id}" title="${paused ? 'Riavvia' : 'Metti in pausa'}">${paused ? '▶' : 'Ⅱ'}</button></div>`;
    }).join('');
    $('activeBots').textContent = active;
    $('botLimit').textContent = botTemplates.length;
    $('capacityFill').style.width = `${state.bots.length / botTemplates.length * 100}%`;
    $('navBotCount').textContent = String(state.bots.length).padStart(2, '0');
    $('botHeadingCount').textContent = String(state.bots.length).padStart(2, '0');
    $('addBotBtn').textContent = state.bots.length >= botTemplates.length ? 'Flotta completa' : '+ Aggiungi bot';
    $('addBotBtn').disabled = state.bots.length >= botTemplates.length;
    $('addBotBtn').style.opacity = state.bots.length >= botTemplates.length ? '.55' : '';
    $('hashrate').textContent = state.bots.reduce((sum, id) => sum + (state.paused.includes(id) ? 0 : botTemplates[id].power), 0).toFixed(1);
    const level = Math.min(9, Math.floor((state.lifetime || 0) / .0008) + 1);
    state.level = level;
    $('levelSmall').textContent = String(level).padStart(2, '0');
  }
  const chartHistory = () => {
    if (state.history.length > 23) state.history = state.history.slice(-23);
    if (!state.history.length) state.history = Array.from({ length: 12 }, (_, i) => ({ t: Date.now() - (11 - i) * 3600000, v: 0 }));
  };
  function renderChart() {
    chartHistory();
    const values = state.history.map((p) => p.v);
    const max = Math.max(.0000001, ...values);
    const pts = values.map((v, i) => ({ x: values.length === 1 ? 0 : i * 720 / (values.length - 1), y: 170 - (v / max * 145) }));
    const path = pts.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
    $('chartLine').setAttribute('d', path);
    $('chartArea').setAttribute('d', `${path} L720,190 L0,190 Z`);
    $('chartDot').setAttribute('cx', pts.at(-1).x);
    $('chartDot').setAttribute('cy', pts.at(-1).y);
    const labels = $('chartRange').value === '1' ? ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', 'Ora'] : ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom'];
    $('chartLabels').innerHTML = labels.map((t) => `<span>${t}</span>`).join('');
    $('chartTooltip').textContent = `+${format(values.at(-1))} BTC`;
    $('chartTotal').textContent = `${format(state.lifetime)} BTC`;
  }
  function render() {
    $('balance').textContent = format(state.balance);
    $('walletBalance').textContent = format(state.wallet);
    $('balanceChange').textContent = `+${format(state.balance)}`;
    $('routeStatus').textContent = state.route ? 'ATTIVO' : 'IN PAUSA';
    $('routeBtn').style.opacity = state.route ? '' : '.7';
    $('routeBtn').style.borderColor = state.route ? '' : '#333945';
    $('routeBtn').style.background = state.route ? '' : '#141720';
    $('autoScanToggle').classList.toggle('on', state.autoScan);
    $('autoScanToggle').setAttribute('aria-label', state.autoScan ? 'Scansione automatica attiva' : 'Scansione automatica disattiva');
    renderBots(); renderChart(); save();
  }
  function tick() {
    const now = Date.now();
    const elapsed = Math.min(15, (now - lastTick) / 1000);
    lastTick = now;
    const active = state.bots.filter((id) => !state.paused.includes(id));
    const power = active.reduce((sum, id) => sum + botTemplates[id].power, 0);
    const reward = power * elapsed * 0.00000000046;
    if (reward > 0) {
      state.balance += reward;
      state.lifetime += reward;
      if (state.route) { state.wallet += reward; state.balance = Math.max(0, state.balance - reward); }
      const last = state.history.at(-1);
      if (!last || now - last.t > 3600000) state.history.push({ t: now, v: reward });
      else last.v += reward;
    }
    $('clock').textContent = new Date().toLocaleTimeString('it-IT', { hour12: false });
    render();
  }
  function scan() {
    if (isScanning) return;
    isScanning = true;
    $('scanBtn').disabled = true;
    $('scanBtn').innerHTML = '<span class="scan-icon">⌕</span> Scansione…';
    document.querySelectorAll('.network-row').forEach((row) => row.classList.add('scanning'));
    notify('Ricerca opportunità sulle reti simulate…');
    beep(520);
    setTimeout(() => {
      isScanning = false;
      $('scanBtn').disabled = false;
      $('scanBtn').innerHTML = '<span class="scan-icon">⌕</span> Scansiona reti <span class="button-shortcut">↵</span>';
      document.querySelectorAll('.network-row').forEach((row) => row.classList.remove('scanning'));
      networks.forEach((n) => { n.load = Math.max(25, Math.min(97, n.load + Math.floor(Math.random() * 25 - 12))); });
      state.scanned++;
      renderNetworks();
      notify(`Scansione completata · ${networks.length} reti simulate analizzate`);
      beep(780);
      save();
    }, 1400);
  }
  $('scanBtn').addEventListener('click', scan);
  $('addBotBtn').addEventListener('click', () => {
    if (state.bots.length >= botTemplates.length) return notify('La flotta è al completo.');
    const next = botTemplates.findIndex((_, id) => !state.bots.includes(id));
    state.bots.push(next); render(); notify(`${botTemplates[next].name} aggiunto alla flotta.`); beep(720);
  });
  $('botList').addEventListener('click', (event) => {
    const button = event.target.closest('[data-pause]');
    if (!button) return;
    const id = Number(button.dataset.pause);
    state.paused = state.paused.includes(id) ? state.paused.filter((x) => x !== id) : [...state.paused, id];
    render(); notify(state.paused.includes(id) ? `${botTemplates[id].name} in pausa.` : `${botTemplates[id].name} riavviato.`); beep(460);
  });
  $('routeBtn').addEventListener('click', () => {
    state.route = !state.route;
    if (state.route && state.balance > 0) {
      state.wallet += state.balance;
      state.balance = 0;
    }
    render();
    notify(state.route ? 'Instradamento attivato. Saldo e nuove ricompense inviati al wallet simulato.' : 'Instradamento in pausa. Le ricompense restano nel saldo.'); beep(620);
  });
  $('autoScanToggle').addEventListener('click', () => {
    state.autoScan = !state.autoScan; render();
    notify(state.autoScan ? 'Scansione automatica attivata.' : 'Scansione automatica disattivata.');
  });
  $('copyWallet').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText('bc1q-aurora-demo-wallet-simulato'); notify('Indirizzo demo copiato negli appunti.'); }
    catch (_) { notify('Indirizzo demo: bc1q-aurora-demo-wallet-simulato'); }
  });
  $('chartRange').addEventListener('change', () => { renderChart(); notify('Intervallo del grafico aggiornato.'); });
  $('soundToggle').addEventListener('click', () => {
    soundOn = !soundOn; $('soundToggle').style.color = soundOn ? '#b6f36b' : ''; notify(soundOn ? 'Suoni attivati.' : 'Suoni disattivati.'); beep(700);
  });
  const backdrop = $('modalBackdrop');
  const openHelp = () => { backdrop.classList.add('open'); backdrop.setAttribute('aria-hidden', 'false'); $('modalOk').focus(); };
  const closeHelp = () => { backdrop.classList.remove('open'); backdrop.setAttribute('aria-hidden', 'true'); };
  $('helpBtn').addEventListener('click', openHelp); $('modalClose').addEventListener('click', closeHelp); $('modalOk').addEventListener('click', closeHelp);
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) closeHelp(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeHelp(); if (e.key === 'Enter' && !['INPUT', 'SELECT', 'BUTTON'].includes(document.activeElement.tagName)) scan(); });
  const viewTitles = { dashboard: 'Panoramica', networks: 'Reti monitorate', bots: 'I miei bot', activity: 'Attività' };
  document.querySelectorAll('[data-view]').forEach((button) => button.addEventListener('click', () => {
    const view = button.dataset.view;
    if (!viewTitles[view]) return;
    document.querySelectorAll('.nav-item').forEach((n) => n.classList.toggle('active', n.dataset.view === view));
    $('breadcrumbCurrent').textContent = viewTitles[view];
    const target = view === 'networks' ? document.querySelector('.network-panel') : view === 'bots' ? document.querySelector('.bots-panel') : view === 'activity' ? document.querySelector('.performance-panel') : document.querySelector('.page-heading');
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    if (view === 'activity') notify(`Storico simulato · ${state.scanned} scansioni completate in questa sessione.`);
  }));

  $('dateLabel').textContent = new Intl.DateTimeFormat('it-IT', { weekday: 'short', day: '2-digit', month: 'short' }).format(new Date()).toUpperCase();
  renderNetworks(); render();
  setInterval(tick, 1000);
  if (state.autoScan) setInterval(() => { if (!document.hidden && state.autoScan) scan(); }, 30000);
  if (!sessionStorage.getItem('mineros-welcomed')) {
    sessionStorage.setItem('mineros-welcomed', '1');
    setTimeout(openHelp, 600);
  }
})();
