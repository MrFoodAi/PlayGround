# PlayGround

<!-- omgithub:readme:start -->
## 🚀 Build, play, and remix with OMGithub

**Created using [OMGithub.com](https://go.ondev.store/).**

[![OMGithub](https://img.shields.io/badge/OMGithub-Open%20project-orange?style=for-the-badge)](https://go.ondev.store/MrFoodAi/PlayGround)
[![GitHub](https://img.shields.io/badge/GitHub-Source-181717?logo=github&style=for-the-badge)](https://github.com/MrFoodAi/PlayGround)

- 🎮 [Open the project](https://go.ondev.store/MrFoodAi/PlayGround).
- ✨ [Remix this project](https://go.ondev.store/MrFoodAi/PlayGround?remix=1).
- 💻 [Explore the source](https://github.com/MrFoodAi/PlayGround).
- 🛠️ [Check build runs](https://github.com/MrFoodAi/PlayGround/actions).
- 🐛 [Report an issue](https://github.com/MrFoodAi/PlayGround/issues).
- 👤 [Explore the creator's projects](https://go.ondev.store/MrFoodAi).
- 🌍 [Create with OMGithub](https://go.ondev.store/).
<!-- omgithub:readme:end -->

## MINER // Protocollo Aurora

Un idle game in italiano in cui gestisci una flotta di bot e scansioni sei reti immaginarie. Accumula ricompense virtuali, metti in pausa i bot e attiva/disattiva l'instradamento verso il wallet demo. I progressi e le preferenze vengono salvati localmente nel browser.

### Funzionalità

- **Gioco:** sei reti immaginarie, bot e crediti virtuali; l'instradamento modifica solo le ricompense simulate.
- **Dati live:** ricerca di criptovalute e consultazione in sola lettura di blocchi, transazioni e indirizzi Bitcoin.
- **Wallet:** verifica del saldo pubblico di un indirizzo Bitcoin, senza collegare un portafoglio.
- **Stima teorica BTC / 24 ore:** usa hashrate e prezzo Bitcoin live, hashrate dell'hardware, potenza, costo elettrico e fee del pool configurabili.
- **Impostazioni locali:** valuta, indirizzo pubblico e parametri di stima sono conservati nel `localStorage` del browser.

### Fonti e limiti

Le richieste di sola lettura usano le API pubbliche di [CoinGecko](https://www.coingecko.com/) (mercati) e [mempool.space](https://mempool.space/) (dati Bitcoin). Richiedono una connessione internet e possono essere soggette a indisponibilità o limiti del servizio.

La stima calcola i BTC teorici come quota dell'hashrate di rete × 144 blocchi al giorno × sussidio corrente per blocco. Applica la fee del pool configurata ai BTC stimati, valorizza il risultato al prezzo live e sottrae il costo energia configurato. Il valore lordo è prima della fee del pool; il netto teorico è dopo fee e costo energia. È un'approssimazione: non include fee di transazione, variabilità dei blocchi, hardware, tasse, downtime o altri costi e non garantisce ricavi.

**È solo un gioco e uno strumento informativo:** l'app non esegue mining, non invia transazioni e non trasferisce fondi. Non richiede né gestisce seed phrase o chiavi private. Inserire solo un indirizzo pubblico Bitcoin è facoltativo; la verifica mostra dati on-chain pubblici e non crea né collega un wallet.
