# 🤖 GoldAI XAU Bot — Autotrade Oro (XAU/XAUT) su DeFi con AI autonoma

Bot di autotrading automatico per l'oro (XAU/USD) e il suo token DeFi (XAUT/PAXG), con **AI integrata autonoma**, operativo **H24**, **multi-trade**, gestione del rischio e **dashboard web in italiano**.

> ⚠️ **Disclaimer finanziario:** questo software è a scopo **educativo e di simulazione**. Il trading su oro e criptovalute comporta rischi elevati e puoi perdere tutto il capitale investito. Non è un consiglio finanziario. Usa esclusivamente la modalità **paper trading** (attiva di default) a meno che tu non sia un trader esperto e accetta tutti i rischi.

---

## 📁 Struttura del progetto

```
gold_ai_bot/
├── config.yaml          # Configurazione (in italiano)
├── .env.example         # Variabili d'ambiente (copia in .env)
├── requirements.txt     # Dipendenze Python
├── README.md            # Questo file
└── src/
    ├── __init__.py
    ├── main.py          # Punto d'ingresso (console)
    ├── ai/
    │   ├── __init__.py
    │   └── motore.py    # Motore AI: indicatori tecnici + ML (Random Forest)
    ├── data/
    │   ├── __init__.py
    │   └── feed.py      # Feed prezzi (CoinGecko / Binance / mock) + indicatori
    ├── defi/
    │   ├── __init__.py
    │   └── connector.py # Connettore Web3/DEX per token oro (XAUT/PAXG)
    ├── dashboard/
    │   ├── __init__.py
    │   └── app.py       # Dashboard web Flask (in italiano)
    ├── trading/
    │   ├── __init__.py
    │   ├── engine.py    # Loop H24, multi-trade, apertura/chiusura
    │   ├── portfolio.py # Portafoglio e posizioni
    │   └── risk.py      # Gestione del rischio (stop loss, take profit, drawdown)
    └── utils/
        ├── __init__.py
        ├── config.py    # Caricamento config YAML + env
        ├── logger.py    # Logging in italiano
        └── notifications.py # Notifiche Telegram (opzionale)
```

---

## 🆕 Novità in questa versione

- **USDC invece di USDT**: lo scambio su DeFi usa ora USDC come stablecoin di riferimento (modificabile in `config.yaml` sotto `trading.stablecoin`).
- **Finestra Impostazioni** (`⚙️ Impostazioni` nella dashboard):
  - Trade size fisso in USD (o calcolo automatico per rischio).
  - Strategie preimpostate: **Conservativa**, **Bilanciata**, **Aggressiva**.
  - Parametri di rischio: % per operazione, Stop Loss, Take Profit.
  - Soglia di confidenza AI e massimo posizioni concorrenti.
  - Modalità Paper Trading / Reale.
- **Finestra Wallet** (`💼 Wallet` nella dashboard):
  - Rete blockchain (Ethereum / Polygon / BSC).
  - Indirizzo wallet, RPC URL.
  - Saldo USDC e XAUT (simulato in paper trading).
- **AI LLM gratuita professionale** (`src/ai/llm_motore.py`):
  - **Ollama** (locale, gratuito): installa Ollama e un modello es. `ollama run llama3`.
  - **HuggingFace Inference API** (tier gratuito): API key gratuita da huggingface.co.
  - Il LLM analizza RSI, MACD, Bollinger, SMA e conferma o blocca i segnali tecnici.
- **Firma automatica transazioni on-chain** (`src/defi/signer.py`):
  - Firma ed invia transazioni EIP-1559 su DEX (Uniswap-style).
  - Gestione nonce automatica, gas dinamico, slippage configurabile.
  - ⚠️ Attivabile solo impostando `abilitata_firma_reale: true` e `REAL_TRADING_ENABLED=true`.
- **Sicurezza**: login dashboard, password hashata, rate limiting, headers di sicurezza, chiave privata mai salvata su disco.
- Tutte le modifiche si applicano a caldo al motore in esecuzione e vengono salvate in `impostazioni_utente.json`.

## 🚀 Installazione e avvio rapido

### 1. Clona/entra nella cartella
```bash
cd gold_ai_bot
```

### 2. Crea l'ambiente virtuale e installa le dipendenze
```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configura l'ambiente
```bash
cp .env.example .env
# Modifica .env se vuoi usare dati reali o notifiche Telegram.
# Per iniziare, lascia tutto in mock / paper trading.
```

### 4. Avvia il bot (modalità paper trading, sicura)
```bash
# Versione console
python -m src.main

# Oppure con dashboard web (consigliato)
python -m src.dashboard.app
```

Quando avvii la dashboard, apri il browser su:
```
http://localhost:8080
```

La dashboard mostra in italiano: prezzo XAU/USD, ultimo segnale AI, portafoglio, PnL, rischio e pulsanti Avvia/Ferma.

---

## ⚙️ Configurazione (`config.yaml`)

Tutte le opzioni sono commentate in italiano. Le sezioni principali:

| Sezione | Descrizione |
|---------|-------------|
| `bot.modalita_paper_trading` | `true` = simulazione sicura (consigliato), `false` = trading reale |
| `ai.attivo` | Attiva/disattiva il motore AI |
| `ai.soglia_confidenza_minima` | Soglia di confidenza per aprire una posizione (es. 0.65 = 65%) |
| `trading.asset_defi` | Token oro su blockchain (es. XAUT, PAXG) |
| `trading.rete_blockchain` | ethereum, polygon o bsc |
| `risk_management.capitale_totale_usd` | Capitale simulato totale |
| `risk_management.stop_loss_percent` | Stop loss in % |
| `risk_management.take_profit_percent` | Take profit in % |
| `dati.prezzo_reale_api` | coingecko, binance o mock |

---

## 🧠 Come funziona l'AI

Il motore combina tre componenti:

1. **Analisi tecnica:** RSI, MACD, Bollinger Bands, SMA (breve e lunga).
2. **Modello ML:** Random Forest addestrato sullo storico per prevedere se il prezzo salirà o scenderà nei prossimi periodi.
3. **Decisione autonoma:** punteggio combinato → segnale **BUY / SELL / HOLD** con confidenza.

Se la confidenza è sotto la soglia configurata, il bot resta in **HOLD** (non apre posizioni).

---

## 🧠 AI LLM gratuita professionale

Il bot può avvalersi di un LLM gratuito per confermare i segnali tecnici:

| Provider | Costo | Requisiti |
|----------|-------|-----------|
| **Ollama** (locale) | Gratuito | `ollama` installato + modello es. `llama3` |
| **HuggingFace** | Tier gratuito | API key gratuita da huggingface.co |

### Attivare Ollama (consigliato, privato e gratuito)
```bash
# Installa Ollama: https://ollama.ai
ollama run llama3
```
Poi in `config.yaml`:
```yaml
llm:
  usa_llm: true
  provider: "ollama"
  modello: "llama3"
  endpoint: "http://localhost:11434"
```

### Attivare HuggingFace
```yaml
llm:
  usa_llm: true
  provider: "hf"
  modello: "meta-llama/Meta-Llama-3-8B-Instruct"
  api_key: "TUA_HF_API_KEY"
```

Il LLM riceve i dati tecnici (RSI, MACD, Bollinger, SMA) e può:
- Confermare un segnale BUY/SELL tecnico.
- Bloccare l'operazione se ritiene il rischio ALTO.
- Forzare HOLD se i segnali sono contrastanti.

## ⚠️ Firma automatica transazioni on-chain

Il modulo `src/defi/signer.py` può firmare e inviare automaticamente transazioni su DEX:

- **EIP-1559**: maxFeePerGas e maxPriorityFeePerGas dinamici.
- **Nonce automatico**: evita doppio invio o nonce errato.
- **Slippage configurabile**: protezione contro esecuzioni a prezzo sfavorevole.
- **Chain ID**: Ethereum (1), Polygon (137), BSC (56).

### Attivare trading reale (pericoloso)
1. Imposta `REAL_TRADING_ENABLED=true` in `.env`.
2. Imposta `abilitata_firma_reale: true` in `config.yaml` o nella dashboard.
3. Configura `PRIVATE_KEY` e `RPC_URL` corretti.
4. Testa prima su **testnet** con fondi che puoi perdere.

> La chiave privata **NON viene mai salvata su disco** dal backend: passa solo in memoria dalla variabile d'ambiente.

## 🛡️ Gestione del rischio

- Dimensione posizione calcolata sul rischio per operazione (% del capitale).
- Stop loss e take profit automatici per ogni posizione.
- Blocco giornaliero se raggiunto il max drawdown.
- Blocco dopo N perdite consecutive.
- Massimo numero di posizioni concorrenti (multi-trade).

---

## 🔗 DeFi (token oro)

Il connettore `defi/connector.py` supporta l'interazione con DEX (es. Uniswap) su Ethereum/Polygon/BSC per token come **XAUT** (Tether Gold) o **PAXG**.

- In **paper trading** (default) tutte le operazioni sono simulate: nessun rischio reale.
- Per il trading reale devi configurare `rpc_url`, `indirizzo_wallet` e `chiave_privata` in `.env` e `config.yaml`, e implementare la firma delle transazioni (placeholder presente nel codice).

---

## 📢 Notifiche (opzionale)

Attiva Telegram in `config.yaml` e inserisci `telegram_bot_token` e `telegram_chat_id` in `.env` per ricevere avvisi su aperture, chiusure e PnL.

---

## 🧪 Test veloce (senza dipendenze esterne)

Per verificare che i moduli si importino correttamente:
```bash
cd gold_ai_bot
python -c "
from src.utils.config import carica_config
cfg = carica_config('config.yaml')
print('Config OK:', cfg['bot']['nome'])
from src.data.feed import FeedPrezzi
fp = FeedPrezzi(fonte='mock')
print('Prezzo mock:', fp.prezzo_attuale())
from src.trading.engine import TradingEngine
print('Tutti i moduli importati correttamente.')
"
```

---

## 📄 Licenza

Uso personale ed educativo. Non redistribuire come consulenza finanziaria.
