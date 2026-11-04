"""Dashboard web Flask in italiano per il bot GoldAI XAU.

Include:
- Stato in tempo reale e ultimi segnali
- Finestra Impostazioni (trade size, strategie preimpostate, rischio, AI, app)
- Finestra Wallet (indirizzo, rete, stablecoin USDC, saldi simulati)
- Autenticazione, headers di sicurezza, rate limiting
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from functools import wraps
from typing import Optional

# Path del progetto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import (
    Flask,
    render_template_string,
    jsonify,
    request,
    session,
    redirect,
    url_for,
    make_response,
)

from src.trading.engine import TradingEngine
from src.utils.config import carica_config
from src.utils.logger import logger

try:
    from werkzeug.security import check_password_hash, generate_password_hash
except Exception:  # werkzeug non installato
    check_password_hash = None  # type: ignore
    generate_password_hash = None  # type: ignore

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

_engine: Optional[TradingEngine] = None
_engine_lock = threading.Lock()

# File di persistenza impostazioni utente (separato da config.yaml)
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
        # Rimuovi chiave privata se presente per sicurezza
        dati_sicuri = {k: v for k, v in dati.items() if k != "chiave_privata"}
        with open(IMPOSTAZIONI_FILE, "w", encoding="utf-8") as f:
            json.dump(dati_sicuri, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.error(f"Errore salvataggio impostazioni: {exc}")


# --------------------------------------------------------------------------- #
# Sicurezza: autenticazione e rate limiting
# --------------------------------------------------------------------------- #
RATE_LIMIT_STORE: dict[str, list[float]] = {}


def _verifica_modalita_reale_consentita(cfg: dict) -> bool:
    """Se la modalità reale è richiesta ma non abilitata via env, blocca."""
    sec = cfg.get("sicurezza", {})
    if bool(sec.get("blocca_modalita_reale_senza_env", True)):
        return os.getenv("REAL_TRADING_ENABLED", "false").lower() == "true"
    return True


def _rate_limited(chiave: str, limite: int, finestra_secondi: int = 60) -> bool:
    now = time.time()
    tempi = RATE_LIMIT_STORE.get(chiave, [])
    tempi = [t for t in tempi if now - t < finestra_secondi]
    if len(tempi) >= limite:
        RATE_LIMIT_STORE[chiave] = tempi
        return True
    tempi.append(now)
    RATE_LIMIT_STORE[chiave] = tempi
    return False


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        cfg = carica_config("config.yaml")
        sec_cfg = cfg.get("dashboard", {})
        if not bool(sec_cfg.get("autenticazione_attiva", True)):
            return f(*args, **kwargs)
        if not session.get("autenticato"):
            return jsonify({"errore": "Autenticazione richiesta", "login_required": True}), 401
        return f(*args, **kwargs)
    return decorated


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
  width: 92vw; max-width: 640px; max-height: 92vh; overflow-y: auto; padding: 18px;
  position: relative; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
}
.modal .close {
  position: absolute; top: 10px; right: 14px; background: transparent; border: none;
  color: #94a3b8; font-size: 26px; cursor: pointer; line-height: 1;
}
.modal .close:hover { color: #fff; }
.modal h3 { margin: 0 0 14px; color: #93c5fd; font-size: 18px; }
.modal label { display: block; font-size: 12px; color: #94a3b8; margin: 9px 0 4px; }
.modal input, .modal select {
  width: 100%; background: #0f172a; border: 1px solid #334155; border-radius: 6px;
  color: #e8eaf6; padding: 8px 10px; box-sizing: border-box;
}
.modal input:focus, .modal select:focus { outline: none; border-color: #2563eb; }
.modal .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 8px; }
@media (max-width: 480px) { .modal .row { grid-template-columns: 1fr; } }
.modal .strategie { display: grid; gap: 8px; margin-top: 6px; }
.modal .strategia-btn {
  background: #0f172a; border: 1px solid #334155; color: #e8eaf6;
  padding: 10px; border-radius: 6px; text-align: left; cursor: pointer; font-size: 13px;
}
.modal .strategia-btn:hover { border-color: #2563eb; }
.modal .strategia-btn.active { background: #1e3a8a; border-color: #2563eb; color: #bfdbfe; }
.modal .btn-salva { width: 100%; padding: 10px; background: #2563eb; color: #fff; border: none; border-radius: 6px; font-weight: 700; margin-top: 14px; cursor: pointer; }
.modal .btn-salva:hover { background: #1d4ed8; }
.modal .btn-salva:disabled { opacity: 0.6; cursor: not-allowed; }
.modal .hint { font-size: 11px; color: #64748b; margin-top: 4px; }
.modal .wallet-saldo { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px; margin-top: 10px; }
.modal .wallet-saldo .riga { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #1f2937; }
.modal .wallet-saldo .riga:last-child { border-bottom: none; }
.modal .wallet-saldo .v { font-weight: 700; color: #22d3ee; }
.modal .pericolo { color: #f87171; font-size: 12px; font-weight: 600; }
.modal .okmsg { color: #34d399; font-size: 13px; margin-top: 8px; }
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GoldAI XAU - Accesso</title>
<style>
  body { font-family: system-ui, -apple-system, sans-serif; background: #0b1021; color: #e8eaf6; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
  .card { background: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 32px 28px; width: 90vw; max-width: 360px; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); }
  h1 { margin: 0 0 8px; font-size: 20px; color: #93c5fd; }
  .p { font-size: 13px; color: #94a3b8; margin-bottom: 20px; }
  label { display: block; font-size: 12px; color: #94a3b8; margin: 12px 0 5px; }
  input { width: 100%; background: #0f172a; border: 1px solid #334155; border-radius: 6px; color: #e8eaf6; padding: 10px; box-sizing: border-box; }
  input:focus { outline: none; border-color: #2563eb; }
  .btn { width: 100%; padding: 10px; background: #2563eb; color: #fff; border: none; border-radius: 6px; font-weight: 700; margin-top: 18px; cursor: pointer; }
  .btn:hover { background: #1d4ed8; }
  .err { color: #f87171; font-size: 12px; margin-top: 10px; display: none; }
  .muted { font-size: 11px; color: #64748b; margin-top: 16px; }
</style>
</head>
<body>
<div class="card">
  <h1>🔐 Accesso GoldAI</h1>
  <div class="p">Inserisci le credenziali per accedere alla dashboard.</div>
  <form id="loginForm">
    <label>Username</label>
    <input type="text" id="username" required>
    <label>Password</label>
    <input type="password" id="password" required>
    <div id="err" class="err">Username o password errati.</div>
    <button type="submit" class="btn">Entra</button>
  </form>
  <div class="muted">Modalità: <b id="modaltxt">--</b></div>
</div>
<script>
async function init(){
  try{
    const r = await fetch('/stato_pubblico');
    const d = await r.json();
    document.getElementById('modaltxt').textContent = d.modalita;
  }catch(e){}
}
document.getElementById('loginForm').onsubmit = async (e)=>{
  e.preventDefault();
  const fd = new FormData(e.target);
  const r = await fetch('/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({username: fd.get('username'), password: fd.get('password')})});
  const d = await r.json();
  if(d.ok){ window.location.href = '/'; } else {
    document.getElementById('err').style.display = 'block';
  }
};
init();
</script>
</body>
</html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GoldAI XAU Bot - Dashboard</title>
<style>
  body { font-family: system-ui, -apple-system, sans-serif; background: #0b1021; color: #e8eaf6; margin: 0; padding: 16px; }
  h1 { margin: 0 0 8px; font-size: 22px; }
  .bar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
  .badge { padding: 3px 8px; border-radius: 16px; font-size: 12px; font-weight: 700; }
  .badge--paper { background: #166534; color: #fff; }
  .badge--live { background: #b91c1c; color: #fff; }
  .badge--stopped { background: #454156; color: #fff; }
  .btn-logout { background: transparent; border: 1px solid #334155; color: #cbd5e1; padding: 4px 10px; border-radius: 6px; font-size: 12px; cursor: pointer; margin-left: auto; }
  .btn-logout:hover { border-color: #2563eb; color: #fff; }
  .card { background: #111827; border: 1px solid #1f2937; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
  .card h2 { font-size: 15px; margin: 0 0 10px; color: #93c5fd; text-transform: uppercase; letter-spacing: 0.05em; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
  .stat { background: #0f172a; border-radius: 7px; padding: 10px; }
  .stat .v { font-size: 18px; font-weight: 700; color: #22d3ee; }
  .stat .l { font-size: 11px; color: #94a3b8; }
  .row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #1f2937; }
  .row:last-child { border-bottom: none; }
  .btn { background: #2563eb; color: #fff; border: none; padding: 7px 14px; border-radius: 6px; cursor: pointer; font-weight: 700; font-size: 13px; }
  .btn:hover { background: #1d4ed8; }
  .btn--danger { background: #dc2626; }
  .btn--danger:hover { background: #b91c1c; }
  .btn--success { background: #16a34a; }
  .btn--success:hover { background: #15803d; }
  .btn--ghost { background: transparent; border: 1px solid #334155; color: #cbd5e1; }
  .btn--ghost:hover { border-color: #2563eb; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .segnale { font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px; }
  .buy { color: #34d399; font-weight: 700; }
  .sell { color: #f87171; font-weight: 700; }
  .hold { color: #fbbf24; font-weight: 700; }
  .muted { color: #64748b; font-size: 12px; }
  .disclaimer { background: #7f1d1d1a; border: 1px solid #7f1d1d; color: #fecaca; padding: 10px; border-radius: 7px; font-size: 11px; margin-bottom: 12px; }
""" + CSS_MODAL + """
</style>
</head>
<body>
<header style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
  <h1>🤖 GoldAI XAU Bot</h1>
  <a href="/logout" class="btn btn--ghost" style="padding:4px 12px;">Esci</a>
</header>

<div class="bar">
  <span class="badge" id="stato">Caricamento...</span>
  <span id="modalita" class="badge badge--paper">Paper Trading</span>
  <button class="btn btn--ghost" onclick="apriModal('impostazioni')">⚙️ Impostazioni</button>
  <button class="btn btn--ghost" onclick="apriModal('wallet')">💼 Wallet</button>
  <button class="btn btn--success" onclick="comando('/avvia')">Avvia</button>
  <button class="btn btn--danger" onclick="comando('/ferma')">Ferma</button>
  <button class="btn" onclick="caricaTutto()">Aggiorna</button>
</div>

<div class="disclaimer">
  <b>Disclaimer finanziario:</b> software a scopo educativo/simulativo. Il trading su oro e criptovalute comporta rischi elevati e puoi perdere tutto il capitale. Non è un consiglio finanziario. Usa la modalità paper trading a meno che tu non sia esperto e accetti i rischi.
</div>

<div class="card">
  <h2>Mercato</h2>
  <div class="grid">
    <div class="stat"><div class="v" id="prezzo">--</div><div class="l">Prezzo XAU/USD</div></div>
    <div class="stat"><div class="v" id="asset">--</div><div class="l">Asset DeFi</div></div>
    <div class="stat"><div class="v" id="stablecoin">--</div><div class="l">Stablecoin</div></div>
    <div class="stat"><div class="v" id="seg-azione">--</div><div class="l">Segnale AI</div></div>
    <div class="stat"><div class="v" id="seg-conf">--</div><div class="l">Confidenza</div></div>
  </div>
  <div class="segnale" id="seg-motivo" style="margin-top:8px;">--</div>
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
  <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:8px;">
    <button class="btn btn--success" onclick="comando('/avvia')">Avvia bot</button>
    <button class="btn btn--danger" onclick="comando('/ferma')">Ferma bot</button>
    <button class="btn" onclick="caricaTutto()">Aggiorna stato</button>
  </div>
  <p class="muted" style="margin-top:8px;">Modalita: <b id="mtxt">paper trading (simulazione)</b>. Usa <b>Impostazioni</b> per cambiare trade size, strategia e parametri di rischio.</p>
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
        <label>Trade size fisso (USD) <span class="hint">vuoto = calcolo automatico</span></label>
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
    <div style="display:flex; gap:8px; margin-top:12px;">
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
      <div class="hint">NON salvata su disco. Usa solo variabili d'ambiente in produzione.</div>
    </div>
    <div class="wallet-saldo">
      <div class="riga"><span>Saldo USDC (simulato)</span><span class="v" id="saldo-usdc">--</span></div>
      <div class="riga"><span>Saldo XAUT (simulato)</span><span class="v" id="saldo-xaut">--</span></div>
      <div class="riga"><span>Valore totale</span><span class="v" id="valore-totale">--</span></div>
    </div>
    <div style="margin-top:12px; display:flex; gap:8px;">
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
    const r = await fetch(path, {method:'POST', credentials:'same-origin'});
    const d = await r.json();
    if(d.ok) caricaTutto();
    else if(d.login_required) { window.location.href = '/login'; }
    else alert(d.errore || 'Errore');
  }catch(e){ console.error(e); }
}

async function caricaTutto(){
  try{
    const r = await fetch('/stato', {credentials:'same-origin'});
    if(r.status === 401){ window.location.href = '/login'; return; }
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
    const r = await fetch('/segnali', {credentials:'same-origin'});
    if(r.status === 401){ window.location.href = '/login'; return; }
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
    const r = await fetch('/impostazioni', {credentials:'same-origin'});
    if(r.status === 401){ window.location.href = '/login'; return; }
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
    const r = await fetch('/impostazioni', {method:'POST', headers:{'Content-Type':'application/json', 'Credentials':'include'}, body: JSON.stringify(dati), credentials:'same-origin'});
    const res = await r.json();
    document.getElementById('msg-impostazioni').textContent = res.ok ? 'Impostazioni salvate e applicate.' : (res.errore || 'Errore salvataggio.');
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
    const r = await fetch('/wallet', {credentials:'same-origin'});
    if(r.status === 401){ window.location.href = '/login'; return; }
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
    const r = await fetch('/wallet', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(dati), credentials:'same-origin'});
    const res = await r.json();
    document.getElementById('msg-wallet').textContent = res.ok ? 'Impostazioni wallet salvate (chiave privata NON scritta su disco).' : (res.errore || 'Errore salvataggio wallet.');
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

    # --- Caricamento config per sicurezza ---
    cfg = carica_config("config.yaml")
    dash_cfg = cfg.get("dashboard", {})
    app.secret_key = os.getenv("SESSION_SECRET", os.urandom(24).hex())

    @app.after_request
    def headers_sicurezza(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

    # --- Route pubbliche ---
    @app.get("/login")
    def login_page():
        if session.get("autenticato"):
            return redirect(url_for("home"))
        modalita = "PAPER TRADING"
        if not _verifica_modalita_reale_consentita(cfg):
            modalita = "REALE (bloccato da env)"
        return render_template_string(LOGIN_HTML).replace("--", modalita)

    @app.post("/login")
    def login():
        dati = request.get_json(force=True, silent=True) or {}
        user = dati.get("username", "")
        pwd = dati.get("password", "")
        user_cfg = dash_cfg.get("username", "admin")
        hash_cfg = dash_cfg.get("password_hash", "") or ""

        # Considera non configurato se è vuoto o è ancora il placeholder ${...}
        hash_non_configurato = (not hash_cfg) or hash_cfg.startswith("${") or hash_cfg.endswith("}")

        ok = False
        if hash_non_configurato:
            # Primo avvio: senza hash configurato, consenti accesso (solo sviluppo / prima configurazione)
            ok = (user == user_cfg)
            logger.warning("password_hash non configurato: login consentito con username corretto. Configura DASHBOARD_PASSWORD_HASH in produzione.")
        elif check_password_hash:
            ok = (user == user_cfg and check_password_hash(hash_cfg, pwd))

        if ok:
            session["autenticato"] = True
            session.permanent = True
            return jsonify({"ok": True})
        return jsonify({"ok": False, "errore": "Credenziali non valide"}), 401

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login_page"))

    @app.get("/stato_pubblico")
    def stato_pubblico():
        return jsonify({"modalita": "PAPER TRADING" if engine.paper_trading else "REALE"})

    # --- Route protette ---
    @app.get("/stato")
    @login_required
    def stato():
        return jsonify(_engine.stato())

    @app.get("/segnali")
    @login_required
    def segnali():
        return jsonify(_engine.ultimi_segnali(n=10))

    @app.post("/avvia")
    @login_required
    def avvia():
        if _rate_limited(request.remote_addr or "anon", int(cfg.get("sicurezza", {}).get("richieste_al_minuto", 60))):
            return jsonify({"ok": False, "errore": "Rate limit superato"}), 429
        threading.Thread(target=lambda: asyncio.run(_engine.avvia()), daemon=True).start()
        return jsonify({"ok": True})

    @app.post("/ferma")
    @login_required
    def ferma():
        if _rate_limited(request.remote_addr or "anon", int(cfg.get("sicurezza", {}).get("richieste_al_minuto", 60))):
            return jsonify({"ok": False, "errore": "Rate limit superato"}), 429
        threading.Thread(target=lambda: asyncio.run(_engine.ferma()), daemon=True).start()
        return jsonify({"ok": True})

    # --- Impostazioni ---
    @app.get("/impostazioni")
    @login_required
    def get_impostazioni():
        imp = carica_impostazioni_file()
        return jsonify(imp)

    @app.post("/impostazioni")
    @login_required
    def post_impostazioni():
        if _rate_limited(request.remote_addr or "anon", int(cfg.get("sicurezza", {}).get("richieste_al_minuto", 60))):
            return jsonify({"ok": False, "errore": "Rate limit superato"}), 429
        dati = request.get_json(force=True, silent=True) or {}
        salva_impostazioni_file(dati)
        with _engine_lock:
            if _engine is not None:
                _engine.applica_impostazioni(dati)
        return jsonify({"ok": True, "applicato": True})

    # --- Wallet ---
    @app.get("/wallet")
    @login_required
    def get_wallet():
        imp = carica_impostazioni_file()
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
    @login_required
    def post_wallet():
        if _rate_limited(request.remote_addr or "anon", int(cfg.get("sicurezza", {}).get("richieste_al_minuto", 60))):
            return jsonify({"ok": False, "errore": "Rate limit superato"}), 429
        dati = request.get_json(force=True, silent=True) or {}
        # Non salvare mai la chiave privata in chiaro su disco
        dati.pop("chiave_privata", None)
        imp = carica_impostazioni_file()
        imp.update(dati)
        salva_impostazioni_file(imp)
        return jsonify({"ok": True})

    @app.get("/")
    def home():
        if not session.get("autenticato"):
            return redirect(url_for("login_page"))
        return render_template_string(HTML_TEMPLATE)

    logger.info(f"Dashboard sicura avviata su http://{host}:{porta}")
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
