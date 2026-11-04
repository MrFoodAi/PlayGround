"""Dashboard web Flask in italiano per il bot GoldAI XAU."""

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


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<title>GoldAI XAU Bot - Dashboard</title>
<style>
  body { font-family: system-ui, -apple-system, sans-serif; background: #0b1021; color: #e8eaf6; margin: 0; padding: 24px; }
  h1 { margin: 0 0 8px; font-size: 24px; }
  .bar { display: flex; gap: 16px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
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
  .btn { background: #2563eb; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 700; }
  .btn:hover { background: #1d4ed8; }
  .btn--danger { background: #dc2626; }
  .btn--danger:hover { background: #b91c1c; }
  .btn--success { background: #16a34a; }
  .btn--success:hover { background: #15803d; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .segnale { font-family: ui-monospace, SFMono-Regular, monospace; font-size: 13px; }
  .buy { color: #34d399; font-weight: 700; }
  .sell { color: #f87171; font-weight: 700; }
  .hold { color: #fbbf24; font-weight: 700; }
  .muted { color: #64748b; }
  .disclaimer { background: #7f1d1d1a; border: 1px solid #7f1d1d; color: #fecaca; padding: 12px; border-radius: 8px; font-size: 12px; margin-bottom: 16px; }
</style>
</head>
<body>
<h1>🤖 GoldAI XAU Bot</h1>
<div class="bar">
  <span class="badge" id="stato">Caricamento...</span>
  <span id="modalita" class="badge badge--paper">Paper Trading</span>
</div>

<div class="disclaimer">
  <b>Disclaimer finanziario:</b> questo software è a scopo educativo e di simulazione. Il trading su oro e criptovalute comporta rischi elevati e puoi perdere tutto il capitale investito. Non è un consiglio finanziario. Usa esclusivamente la modalità paper trading a meno che tu non sia un trader esperto e accetti i rischi.
</div>

<div class="card">
  <h2>Mercato</h2>
  <div class="grid">
    <div class="stat"><div class="v" id="prezzo">--</div><div class="l">Prezzo XAU/USD (USD/oncia)</div></div>
    <div class="stat"><div class="v" id="asset">--</div><div class="l">Asset DeFi</div></div>
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
  <div style="display:flex; gap:10px; flex-wrap:wrap;">
    <button class="btn btn--success" onclick="comando('/avvia')">Avvia bot</button>
    <button class="btn btn--danger" onclick="comando('/ferma')">Ferma bot</button>
    <button class="btn" onclick="comando('/stato')">Aggiorna stato</button>
  </div>
  <p class="muted" style="margin-top:10px;">Modalita attuale: <b id="mtxt">paper trading (simulazione)</b>. Per il trading reale modifica <i>config.yaml</i> e proteggi le chiavi.</p>
</div>

<div class="card">
  <h2>Ultimi segnali AI</h2>
  <div id="segnali-lista">Caricamento...</div>
</div>

<script>
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
        # Avvia il motore in un thread separato
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
