"""Dashboard web Flask in italiano per il bot GoldAI XAU.

Include:
- Stato in tempo reale e ultimi segnali
- Finestra Impostazioni (trade size, strategie preimpostate, rischio, AI, app)
- Finestra Wallet (indirizzo, rete, stablecoin USDC, saldi simulati)
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from typing import Optional

# Path del progetto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template_string, jsonify, request

from src.trading.engine import TradingEngine
from src.utils.config import carica_config
from src.utils.logger import logger

app = Flask(__name__)

_engine: Optional[TradingEngine] = None
_engine_lock = threading.Lock()

# File di persistenza impostazioni utente (separato da config.yaml per non sovrascrivere commenti)
IMPOSTAZIONI_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "impostazioni_utente.json")
IMPOSTAZIONI_FILE = os.path.abspath(IMPOSTAZIONI_FILE)

# Strategie preimpostate
STRATEGIE_PREIMPOSTATE = {
    "conservativa": {
        "nome": "Conservativa",
        "descrizione": "Rischio contenuto, adatta a capitali piccoli o prudenti.",
        "rischio_per_operazione_percent": 0.5,
        "stop_loss_percent": 1.0,
        "take_profit_percent": 2.0,
        "soglia_confidenza_minima": 0.75,
        "max_posizioni_concorrenti": 3,
        "trade_size_usd": None,
    },
    "bilanciata": {
        "nome": "Bilanciata",
        "descrizione": "Equilibrio tra rischio e rendimento (default).",
        "rischio_per_operazione_percent": 1.0,
        "stop_loss_percent": 2.0,
        "take_profit_percent": 4.0,
        "soglia_confidenza_minima": 0.65,
        "max_posizioni_concorrenti": 5,
        "trade_size_usd": None,
    },
    "aggressiva": {
        "nome": "Aggressiva",
        "descrizione": "Rischio elevato, per trader esperti e capitali adeguati.",
        "rischio_per_operazione_percent": 2.0,
        "stop_loss_percent": 3.0,
        "take_profit_percent": 6.0,
        "soglia_confidenza_minima": 0.55,
        "max_posizioni_concorrenti": 8,
        "trade_size_usd": None,
    },
}


# --------------------------------------------------------------------------- #
# Gestione impostazioni utente
# --------------------------------------------------------------------------- #
def _impostazioni_default() -> dict:
    return {
        "strategia": "bilanciata",
        "trade_size_usd": None,
        "rischio_per_operazione_percent": 1.0,
        "stop_loss_percent": 2.0,
        "take_profit_percent": 4.0,
        "soglia_confidenza_minima": 0.65,
        "max_posizioni_concorrenti": 5,
        "modalita_paper_trading": True,
        "intervallo_aggiornamento_secondi": 60,
        "lingua": "it",
        "tema": "scuro",
        "notifiche_attive": False,
    }


def carica_impostazioni_file() -> dict:
    if os.path.exists(IMPOSTAZIONI_FILE):
        try:
            with open(IMPOSTAZIONI_FILE, "r", encoding="utf-8") as f:
                dati = json.load(f)
            base = _impostazioni_default()
            base.update(dati)
            return base
        except Exception as exc:
            logger.warning(f"Impossibile caricare impostazioni ({exc}), uso default.")
    return _impostazioni_default()


def salva_impostazioni_file(dati: dict) -> None:
    try:
        with open(IMPOSTAZIONI_FILE, "w", encoding="utf-8") as f:
            json.dump(dati, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.error(f"Errore salvataggio impostazioni: {exc}")


# --------------------------------------------------------------------------- #
# HTML Template
# --------------------------------------------------------------------------- #
CSS_MODAL = """
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
  display: none; z-index: 50; align-items: center; justify-content: center;
}
.modal-overlay.aperto { display: flex; }
.modal {
  background: #111827; border: 1px solid #1f2937; border-radius: 12px;
  width: 90vw; max-width: 640px; max-height: 90vh; overflow-y: auto; padding: 20px;
  position: relative; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
}
.modal .close {
  position: absolute; top: 10px; right: 14px; background: transparent; border: none;
  color: #94a3b8; font-size: 24px; cursor: pointer; line-height: 1;
}
.modal .close:hover { color: #fff; }
.modal h3 { margin: 0 0 16px; color: #93c5fd; font-size: 18px; }
.modal label { display: block; font-size: 12px; color: #94a3b8; margin: 10px 0 4px; }
.modal input, .modal select {
  width: 100%; background: #0f172a; border: 1px solid #334155; border-radius: 6px;
  color: #e8eaf6; padding: 8px 10px; box-sizing: border-box;
}
.modal input:focus, .modal select:focus { outline: none; border-color: #2563eb; }
.modal .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 10px; }
.modal .strategie { display: grid; gap: 8px; margin-top: 6px; }
.modal .strategia-btn {
  background: #0f172a; border: 1px solid #334155; color: #e8eaf6;
  padding: 10px; border-radius: 6px; text-align: left; cursor: pointer; font-size: 13px;
}
.modal .strategia-btn:hover { border-color: #2563eb; }
.modal .strategia-btn.active { background: #1e3a8a; border-color: #2563eb; color: #bfdbfe; }
.modal .btn-salva { width: 100%; padding: 10px; background: #2563eb; color: #fff; border: none; border-radius: 6px; font-weight: 700; margin-top: 16px; cursor: pointer; }
.modal .btn-salva:hover { background: #1d4ed8; }
.modal .btn-salva:disabled { opacity: 0.6; cursor: not-allowed; }
.modal .hint { font-size: 11px; color: #64748b; margin-top: 4px; }
.modal .wallet-saldo { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px; margin-top: 10px; }
.modal .wallet-saldo .riga { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #1f2937; }
.modal .wallet-saldo .riga:last-child { border-bottom: none; }
.modal .wallet-saldo .v { font-weight: 700; color: #22d3ee; }
.modal .pericolo { color: #f87171; font-size: 12px; font-weight: 600; }
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<title>GoldAI XAU Bot - Dashboard</title>
<style>
  body { font-family: system-ui, -apple-system, sans-serif; background: #0b1021; color: #e8eaf6; margin: 0; padding: 24px; }
  h1 { margin: 0 0 8px; font-size: 24px; }
  .bar { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
  .badge { padding: 4px 10px; border-radius: 20px; font-size: 13px; font-weight: 700; }
  .badge--paper { background: #166534; color: #fff; }
  .badge--live { background: #b91c1c; color: #fff; }
  .badge--stopped { background: #454156; color: #fff; }
  .card { background: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
  .card h2 { font-size: 16px; margin: 0 0 12px; color: #93c5fd; text-transform: uppercase; letter-spacing: 0.05em; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
  .stat { background: #0f172a; border-radius: 8px; padding: 12px; }
  .stat .v { font-size: 20px; font-weight: 700; color: #22d3ee; }
  .stat .l { font-size: 12px; color: #94a3b8; }
  .row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #1f2937; }
  .row:last-child { border-bottom: none; }
  .btn { background: #2563eb; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 700; font-size: 13px; }
  .btn:hover { background: #1d4ed8; }
  .btn--danger { background: #dc2626; }
  .btn--danger:hover { background: #b91c1c; }
  .btn--success { background: #16a34a; }
  .btn--success:hover { background: #15803d; }
  .btn--ghost { background: transparent; border: 1px solid #334155; color: #cbd5e1; }
  .btn--ghost:hover { border-color: #2563eb; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .segnale { font-family: ui-monospace, SFMono-Regular, monospace; font-size: 13px; }
  .buy { color: #34d399; font-weight: 700; }
  .sell { color: #f87171; font-weight: 700; }
  .hold { color: #fbbf24; font-weight: 700; }
  .muted { color: #64748b; }
  .disclaimer { background: #7f1d1d1a; border: 1px solid #7f1d1d; color: #fecaca; padding: 12px; border-radius: 8px; font-size: 12px; margin-bottom: 16px; }
""" + CSS_MODAL + """
</style>
</head>
<body>
<h1>🤖 GoldAI XAU Bot</h1>
<div class="bar">
  <span class="badge" id="stato">Caricamento...</span>
  <span id="modalita" class="badge badge--paper">Paper Trading</span>
  <button class="btn btn--ghost" onclick="apriModal('impostazioni')">⚙️ Impostazioni</button>
  <button class="btn btn--ghost" onclick="apriModal('wallet')">💼 Wallet</button>
  <button class="btn btn--success" onclick="comando('/avvia')">Avvia bot</button>
  <button class="btn btn--danger" onclick="comando('/ferma')">Ferma bot</button>
  <button class="btn" onclick="caricaTutto()">Aggiorna</button>
</div>

<div class="disclaimer">
  <b>Disclaimer finanziario:</b> software a scopo educativo/simulativo. Il trading su oro e criptovalute comporta rischi elevati e puoi perdere tutto il capitale. Non è un consiglio finanziario. Usa la modalità paper trading a meno che tu non sia esperto e accetti i rischi.
</div>

<div class="card">
  <h2>Mercato</h2>
  <div class="grid">
    <div class="stat"><div class="v" id="prezzo">--</div><div class="l">Prezzo XAU/USD (USD/oncia)</div></div>
    <div class="stat"><div class="v" id="asset">--</div><div class="l">Asset DeFi</div></div>
    <div class="stat"><div class="v" id="stablecoin">--</div><div class="l">Stablecoin di scambio</div></div>
    <div class="stat"><div class="v" id="seg-azione">--</div><div class="l">Ultimo segnale AI</div></div>
    <div class="stat"><div class="v" id="seg-conf">--</div><div class="l">Confidenza</div></div>
  </div>
  <div class="segnale" id="seg-motivo" style="margin-top:10px;">--</div>
</div>

<div class="card">
  <h2>Portafoglio</h2>
  <div class="grid">
    <div class="stat"><div class="v" id="pf-disponibile">--</div><div class="l">Disponibile (USD)</div></div>
    <div class="stat"><div class="v" id="pf-pnl">--</div><div class="l">PnL totale (USD)</div></div>
    <div class="stat"><div class="v" id="pf-aperte">--</div><div class="l">Posizioni aperte</div></div>
    <div class="stat"><div class="v" id="pf-chiusi">--</div><div class="l">Trade chiusi</div></div>
  </div>
</div>

<div class="card">
  <h2>Rischio</h2>
  <div class="grid">
    <div class="stat"><div class="v" id="risk-perdite">--</div><div class="l">Perdite consecutive</div></div>
    <div class="stat"><div class="v" id="risk-bloccato">--</div><div class="l">Blocco drawdown</div></div>
  </div>
</div>

<div class="card">
  <h2>Controlli</h2>
  <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:8px;">
    <button class="btn btn--success" onclick="comando('/avvia')">Avvia bot</button>
    <button class="btn btn--danger" onclick="comando('/ferma')">Ferma bot</button>
    <button class="btn" onclick="caricaTutto()">Aggiorna stato</button>
  </div>
  <p class="muted" style="margin-top:10px;">Modalita: <b id="mtxt">paper trading (simulazione)</b>. Usa <b>Impostazioni</b> per cambiare trade size, strategia e parametri di rischio.</p>
</div>

<div class="card">
  <h2>Ultimi segnali AI</h2>
  <div id="segnali-lista">Caricamento...</div>
</div>

<!-- Overlay modal -->
<div id="modal-overlay" class="modal-overlay" onclick="chiudiModal(event)"></div>

<!-- Modal Impostazioni -->
<div id="modal-impostazioni" class="modal">
  <button class="close" onclick="chiudiModal('impostazioni')">&times;</button>
  <h3>⚙️ Impostazioni Trading & App</h3>
  <form id="form-impostazioni" onsubmit="salvaImpostazioni(event); return false;">
    <div class="row">
      <div>
        <label>Strategia preimpostata</label>
        <div class="strategie" id="lista-strategie"></div>
        <input type="hidden" id="strategia" name="strategia" value="bilanciata">
      </div>
      <div>
        <label>Tema</label>
        <select id="tema" name="tema">
          <option value="scuro">Scuro</option>
          <option value="chiaro">Chiaro</option>
        </select>
      </div>
    </div>
    <div class="row">
      <div>
        <label>Trade size fisso (USD) <span class="hint">lascia vuoto per calcolo automatico per rischio</span></label>
        <input type="number" id="trade_size_usd" name="trade_size_usd" step="0.01" min="0" placeholder="es. 50">
      </div>
      <div>
        <label>Modalità</label>
        <select id="modalita_paper_trading" name="modalita_paper_trading">
          <option value="true">Paper Trading (simulato)</option>
          <option value="false">Reale (pericoloso)</option>
        </select>
      </div>
    </div>
    <div class="row">
      <div>
        <label>Rischio per operazione (%)</label>
        <input type="number" id="rischio_per_operazione_percent" name="rischio_per_operazione_percent" step="0.1" min="0.1" max="10">
      </div>
      <div>
        <label>Stop Loss (%)</label>
        <input type="number" id="stop_loss_percent" name="stop_loss_percent" step="0.1" min="0.1" max="20">
      </div>
    </div>
    <div class="row">
      <div>
        <label>Take Profit (%)</label>
        <input type="number" id="take_profit_percent" name="take_profit_percent" step="0.1" min="0.1" max="50">
      </div>
      <div>
        <label>Soglia confidenza AI (%)</label>
        <input type="number" id="soglia_confidenza_minima" name="soglia_confidenza_minima" step="0.05" min="0.1" max="1">
      </div>
    </div>
    <div class="row">
      <div>
        <label>Max posizioni concorrenti</label>
        <input type="number" id="max_posizioni_concorrenti" name="max_posizioni_concorrenti" step="1" min="1" max="20">
      </div>
      <div>
        <label>Intervallo aggiornamento (s)</label>
        <input type="number" id="intervallo_aggiornamento_secondi" name="intervallo_aggiornamento_secondi" step="5" min="5" max="3600">
      </div>
    </div>
    <div style="display:flex; gap:8px; margin-top:14px;">
      <button type="button" class="btn btn--ghost" onclick="resetImpostazioni()">Ripristina default</button>
      <button type="submit" class="btn btn-salva">Salva impostazioni</button>
    </div>
  </form>
  <div id="msg-impostazioni" class="muted" style="margin-top:10px;"></div>
</div>

<!-- Modal Wallet -->
<div id="modal-wallet" class="modal">
  <button class="close" onclick="chiudiModal('wallet')">&times;</button>
  <h3>💼 Wallet & Impostazioni Blockchain</h3>
  <form id="form-wallet" onsubmit="salvaWallet(event); return false;">
    <div class="row">
      <div>
        <label>Rete blockchain</label>
        <select id="rete_blockchain" name="rete_blockchain">
          <option value="ethereum">Ethereum</option>
          <option value="polygon">Polygon</option>
          <option value="bsc">BSC</option>
        </select>
      </div>
      <div>
        <label>Stablecoin di scambio</label>
        <select id="stablecoin" name="stablecoin" disabled>
          <option value="USDC">USDC</option>
        </select>
      </div>
    </div>
    <div style="margin-bottom:4px;">
      <label>Indirizzo wallet</label>
      <input type="text" id="indirizzo_wallet" name="indirizzo_wallet" placeholder="0x...">
      <div class="hint">Usato per collegarsi al DEX (solo trading reale).</div>
    </div>
    <div style="margin-bottom:4px;">
      <label>RPC URL</label>
      <input type="text" id="rpc_url" name="rpc_url" placeholder="https://mainnet.infura.io/v3/...">
      <div class="hint">Nodo Ethereum/Polygon per lettura e invio transazioni.</div>
    </div>
    <div style="margin-bottom:4px;">
      <label>Chiave privata</label>
      <input type="password" id="chiave_privata" name="chiave_privata" placeholder="••••••••">
      <div class="hint">NON salvare chiavi reali qui in produzione. Usa solo variabili d'ambiente.</div>
    </div>
    <div class="wallet-saldo">
      <div class="riga"><span>Saldo USDC (simulato)</span><span class="v" id="saldo-usdc">--</span></div>
      <div class="riga"><span>Saldo XAUT (simulato)</span><span class="v" id="saldo-xaut">--</span></div>
      <div class="riga"><span>Valore totale</span><span class="v" id="valore-totale">--</span></div>
    </div>
    <div style="margin-top:14px; display:flex; gap:8px;">
      <button type="button" class="btn btn--ghost" onclick="caricaWallet()">Aggiorna saldi</button>
      <button type="submit" class="btn btn-salva">Salva wallet</button>
    </div>
  </form>
  <div id="msg-wallet" class="muted" style="margin-top:10px;"></div>
  <p class="pericolo" style="margin-top:10px;">⚠️ Trading reale disabilitato di default. Attivalo solo in Impostazioni se sai esattamente cosa fai.</p>
</div>

<script>
let strategiaSelezionata = "bilanciata";

async function comando(path){
  try{
    const r = await fetch(path, {method:'POST'});
    const d = await r.json();
    if(d.ok) caricaTutto();
  }catch(e){ console.error(e); }
}

async function caricaTutto(){
  try{
    const r = await fetch('/stato');
    const d = await r.json();
    document.getElementById('stato').textContent = d.in_esecuzione ? 'IN ESECUZIONE' : 'FERMO';
    document.getElementById('stato').className = 'badge ' + (d.in_esecuzione ? 'badge--live' : 'badge--stopped');
    document.getElementById('modalita').textContent = d.modalita;
    document.getElementById('modalita').className = 'badge ' + (d.modalita.includes('REALE') ? 'badge--live' : 'badge--paper');
    document.getElementById('prezzo').textContent = (d.prezzo_attuale_usd??0).toFixed(2) + ' USD';
    document.getElementById('asset').textContent = d.asset_defi;
    document.getElementById('stablecoin').textContent = 'USDC';
    const s = d.ultimo_segnale;
    if(s){
      document.getElementById('seg-azione').textContent = s.azione;
      document.getElementById('seg-azione').className = s.azione==='BUY'?'buy':(s.azione==='SELL'?'sell':'hold');
      document.getElementById('seg-conf').textContent = (s.confidenza*100).toFixed(0) + '%';
      document.getElementById('seg-motivo').textContent = s.motivo;
    }
    const pf = d.portafoglio || {};
    document.getElementById('pf-disponibile').textContent = (pf.disponibile_usd??0).toFixed(2) + ' USD';
    document.getElementById('pf-pnl').textContent = (pf.pnl_totale_usd??0).toFixed(2) + ' USD';
    document.getElementById('pf-aperte').textContent = pf.posizioni_aperte??0;
    document.getElementById('pf-chiusi').textContent = pf.trade_chiusi??0;
    const risk = d.rischio || {};
    document.getElementById('risk-perdite').textContent = risk.perdite_consecutive??0;
    document.getElementById('risk-bloccato').textContent = risk.bloccato_drawdown ? 'Sì' : 'No';
  }catch(e){ console.error(e); }
}

async function caricaSegnali(){
  try{
    const r = await fetch('/segnali');
    const lista = await r.json();
    const el = document.getElementById('segnali-lista');
    el.innerHTML = lista.map(s => `
      <div class="row">
        <span class="segnale ${s.azione==='BUY'?'buy':(s.azione==='SELL'?'sell':'hold')}">${s.azione}</span>
        <span>${s.confidenza.toFixed(0)}% @ ${s.prezzo}</span>
        <span class="muted">${s.motivo}</span>
      </div>`).join('') || 'Nessun segnale.';
  }catch(e){ console.error(e); }
}

// --- Impostazioni ---
async function caricaImpostazioni(){
  try{
    const r = await fetch('/impostazioni');
    const imp = await r.json();
    strategiaSelezionata = imp.strategia || 'bilanciata';
    document.getElementById('strategia').value = strategiaSelezionata;
    document.getElementById('trade_size_usd').value = imp.trade_size_usd ?? '';
    document.getElementById('modalita_paper_trading').value = imp.modalita_paper_trading ? 'true' : 'false';
    document.getElementById('rischio_per_operazione_percent').value = imp.rischio_per_operazione_percent ?? 1;
    document.getElementById('stop_loss_percent').value = imp.stop_loss_percent ?? 2;
    document.getElementById('take_profit_percent').value = imp.take_profit_percent ?? 4;
    document.getElementById('soglia_confidenza_minima').value = imp.soglia_confidenza_minima ?? 0.65;
    document.getElementById('max_posizioni_concorrenti').value = imp.max_posizioni_concorrenti ?? 5;
    document.getElementById('intervallo_aggiornamento_secondi').value = imp.intervallo_aggiornamento_secondi ?? 60;
    document.getElementById('tema').value = imp.tema ?? 'scuro';
    document.getElementById('msg-impostazioni').textContent = '';
    renderStrategie();
  }catch(e){
    document.getElementById('msg-impostazioni').textContent = 'Errore caricamento impostazioni.';
    console.error(e);
  }
}

function renderStrategie(){
  const container = document.getElementById('lista-strategie');
  const strategie = {
    conservativa: {nome:'Conservativa', rischio:'0.5%', SL:'1%', TP:'2%', conf:'75%'},
    bilanciata: {nome:'Bilanciata', rischio:'1%', SL:'2%', TP:'4%', conf:'65%'},
    aggressiva: {nome:'Aggressiva', rischio:'2%', SL:'3%', TP:'6%', conf:'55%'},
  };
  container.innerHTML = Object.entries(strategie).map(([key, s]) => `
    <label class="strategia-btn ${key===strategiaSelezionata?'active':''}" onclick="selezionaStrategia('${key}')" title="${s.nome} - Rischio ${s.rischio}, SL ${s.SL}, TP ${s.TP}, Conf ${s.conf}">
      <strong>${s.nome}</strong> · Rischio ${s.rischio} · SL ${s.SL} · TP ${s.TP} · Conf ${s.conf}
      <input type="radio" name="strategia" value="${key}" ${key===strategiaSelezionata?'checked':''} style="display:none;">
    </label>
  `).join('');
}

function selezionaStrategia(key){
  strategiaSelezionata = key;
  document.getElementById('strategia').value = key;
  const valori = {
    conservativa: {rischio:0.5, sl:1, tp:2, conf:0.75, max:3},
    bilanciata: {rischio:1, sl:2, tp:4, conf:0.65, max:5},
    aggressiva: {rischio:2, sl:3, tp:6, conf:0.55, max:8},
  }[key];
  document.getElementById('rischio_per_operazione_percent').value = valori.rischio;
  document.getElementById('stop_loss_percent').value = valori.sl;
  document.getElementById('take_profit_percent').value = valori.tp;
  document.getElementById('soglia_confidenza_minima').value = valori.conf;
  document.getElementById('max_posizioni_concorrenti').value = valori.max;
  renderStrategie();
}

function resetImpostazioni(){
  if(confirm('Ripristinare le impostazioni predefinite (Bilanciata)?')) {
    strategiaSelezionata = 'bilanciata';
    caricaImpostazioni();
  }
}

async function salvaImpostazioni(e){
  e.preventDefault();
  const form = document.getElementById('form-impostazioni');
  const fd = new FormData(form);
  const dati = {
    strategia: fd.get('strategia'),
    trade_size_usd: fd.get('trade_size_usd') ? parseFloat(fd.get('trade_size_usd')) : null,
    modalita_paper_trading: fd.get('modalita_paper_trading') === 'true',
    rischio_per_operazione_percent: parseFloat(fd.get('rischio_per_operazione_percent')),
    stop_loss_percent: parseFloat(fd.get('stop_loss_percent')),
    take_profit_percent: parseFloat(fd.get('take_profit_percent')),
    soglia_confidenza_minima: parseFloat(fd.get('soglia_confidenza_minima')),
    max_posizioni_concorrenti: parseInt(fd.get('max_posizioni_concorrenti')),
    intervallo_aggiornamento_secondi: parseInt(fd.get('intervallo_aggiornamento_secondi')),
    lingua: 'it',
    tema: fd.get('tema'),
    notifiche_attive: false,
  };
  try{
    const r = await fetch('/impostazioni', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(dati)});
    const res = await r.json();
    document.getElementById('msg-impostazioni').textContent = res.ok ? 'Impostazioni salvate e applicate.' : 'Errore salvataggio.';
    document.getElementById('msg-impostazioni').style.color = res.ok ? '#34d399' : '#f87171';
    if(res.ok) caricaTutto();
  }catch(err){
    document.getElementById('msg-impostazioni').textContent = 'Errore di rete.';
    console.error(err);
  }
}

// --- Wallet ---
async function caricaWallet(){
  try{
    const r = await fetch('/wallet');
    const w = await r.json();
    document.getElementById('rete_blockchain').value = w.rete_blockchain || 'ethereum';
    document.getElementById('indirizzo_wallet').value = w.indirizzo_wallet || '';
    document.getElementById('rpc_url').value = w.rpc_url || '';
    document.getElementById('saldo-usdc').textContent = (w.saldo_usdc ?? 0).toFixed(2) + ' USDC';
    document.getElementById('saldo-xaut').textContent = (w.saldo_xaut ?? 0).toFixed(6) + ' XAUT';
    document.getElementById('valore-totale').textContent = (w.valore_totale_usd ?? 0).toFixed(2) + ' USD';
    document.getElementById('msg-wallet').textContent = '';
  }catch(e){
    document.getElementById('msg-wallet').textContent = 'Errore caricamento wallet.';
    console.error(e);
  }
}

async function salvaWallet(e){
  e.preventDefault();
  const form = document.getElementById('form-wallet');
  const fd = new FormData(form);
  const dati = {
    rete_blockchain: fd.get('rete_blockchain'),
    indirizzo_wallet: fd.get('indirizzo_wallet'),
    rpc_url: fd.get('rpc_url'),
    chiave_privata: fd.get('chiave_privata'),
  };
  try{
    const r = await fetch('/wallet', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(dati)});
    const res = await r.json();
    document.getElementById('msg-wallet').textContent = res.ok ? 'Impostazioni wallet salvate.' : 'Errore salvataggio wallet.';
    document.getElementById('msg-wallet').style.color = res.ok ? '#34d399' : '#f87171';
  }catch(err){
    document.getElementById('msg-wallet').textContent = 'Errore di rete.';
    console.error(err);
  }
}

// --- Modal UI ---
function apriModal(id){
  document.getElementById('modal-overlay').classList.add('aperto');
  const m = document.getElementById('modal-'+id);
  if(m) m.style.display = 'block';
  if(id === 'impostazioni') caricaImpostazioni();
  if(id === 'wallet') caricaWallet();
}

function chiudiModal(target){
  if(target && target !== 'overlay'){
    document.getElementById('modal-'+target).style.display = 'none';
  }
  document.getElementById('modal-overlay').classList.remove('aperto');
}
// Chiudi premendo ESC
document.addEventListener('keydown', (e)=>{
  if(e.key === 'Escape') chiudiModal();
});

setInterval(()=>{ caricaTutto(); caricaSegnali(); }, 4000);
caricaTutto(); caricaSegnali();
</script>
</body>
</html>
"""


def avvia_dashboard(engine: TradingEngine, host: str = "0.0.0.0", porta: int = 8080):
    global _engine
    with _engine_lock:
        _engine = engine

    @app.get("/stato")
    def stato():
        return jsonify(_engine.stato())

    @app.get("/segnali")
    def segnali():
        return jsonify(_engine.ultimi_segnali(n=10))

    @app.post("/avvia")
    def avvia():
        threading.Thread(target=lambda: asyncio.run(_engine.avvia()), daemon=True).start()
        return jsonify({"ok": True})

    @app.post("/ferma")
    def ferma():
        threading.Thread(target=lambda: asyncio.run(_engine.ferma()), daemon=True).start()
        return jsonify({"ok": True})

    # --- Impostazioni ---
    @app.get("/impostazioni")
    def get_impostazioni():
        imp = carica_impostazioni_file()
        return jsonify(imp)

    @app.post("/impostazioni")
    def post_impostazioni():
        dati = request.get_json(force=True, silent=True) or {}
        salva_impostazioni_file(dati)
        with _engine_lock:
            if _engine is not None:
                _engine.applica_impostazioni(dati)
        return jsonify({"ok": True, "applicato": True})

    # --- Wallet ---
    @app.get("/wallet")
    def get_wallet():
        imp = carica_impostazioni_file()
        # Saldi simulati in paper trading; in futuro leggere da Web3
        saldo_usdc = 1000.0
        saldo_xaut = 0.0
        return jsonify({
            "rete_blockchain": imp.get("rete_blockchain", "ethereum"),
            "stablecoin": "USDC",
            "indirizzo_wallet": imp.get("indirizzo_wallet", ""),
            "rpc_url": imp.get("rpc_url", ""),
            "saldo_usdc": saldo_usdc,
            "saldo_xaut": saldo_xaut,
            "valore_totale_usd": round(saldo_usdc, 2),
        })

    @app.post("/wallet")
    def post_wallet():
        dati = request.get_json(force=True, silent=True) or {}
        # Non salvare mai la chiave privata in chiaro su disco in produzione
        dati.pop("chiave_privata", None)
        imp = carica_impostazioni_file()
        imp.update(dati)
        salva_impostazioni_file(imp)
        return jsonify({"ok": True})

    @app.get("/")
    def home():
        return render_template_string(HTML_TEMPLATE)

    logger.info(f"Dashboard avviata su http://{host}:{porta}")
    app.run(host=host, port=porta, debug=False, use_reloader=False)


def avvia_bot_e_dashboard(cfg: dict):
    """Avvia il motore di trading e la dashboard nello stesso processo."""
    engine = TradingEngine(cfg)

    dashboard_cfg = cfg.get("dashboard", {})
    host = dashboard_cfg.get("host", "0.0.0.0")
    porta = int(dashboard_cfg.get("porta", 8080))
    attiva = bool(dashboard_cfg.get("attiva", True))

    if attiva:
        def run_engine():
            asyncio.run(engine.avvia())

        t = threading.Thread(target=run_engine, daemon=True)
        t.start()
        avvia_dashboard(engine, host=host, porta=porta)
    else:
        asyncio.run(engine.avvia())

    return engine


if __name__ == "__main__":
    cfg = carica_config("config.yaml")
    avvia_bot_e_dashboard(cfg)
