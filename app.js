(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const number = (value) => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value)) ? Number(value).toLocaleString('it-IT') : '—';
  const btc = (satoshis) => satoshis !== null && satoshis !== undefined && satoshis !== '' && Number.isFinite(Number(satoshis)) ? `${(Number(satoshis) / 1e8).toLocaleString('it-IT', { maximumFractionDigits: 8 })} BTC` : '—';
  const setText = (id, value) => { $(id).textContent = value ?? '—'; };

  function render(payload) {
    const { data, error, updated_at: updatedAt } = payload;
    $('errorBanner').hidden = !error;
    if (error) $('errorBanner').textContent = `Dati non aggiornati: ${error}. Nessun valore simulato viene mostrato.`;
    $('connection').classList.toggle('ok', Boolean(data));
    $('connection').classList.toggle('error', Boolean(error));
    $('connection').innerHTML = `<i></i> ${data ? 'DATI REALI' : 'NON CONNESSO'}`;
    setText('updatedAt', updatedAt ? new Date(updatedAt).toLocaleString('it-IT') : '—');

    if (data) {
      setText('height', number(data.height));
      setText('txCount', number(data.block?.tx_count));
      setText('mempoolCount', number(data.mempool?.count));
      setText('feeRate', number(data.fees?.fastestFee));
      setText('blockHash', data.block?.id || '—');
      setText('blockTime', data.block?.timestamp ? new Date(data.block.timestamp * 1000).toLocaleString('it-IT') : '—');
      setText('blockSize', Number.isFinite(data.block?.size) ? `${number(data.block.size)} byte` : '—');
      setText('mempoolFees', btc(data.mempool?.total_fee));
      const fees = data.fees || {};
      setText('feeSummary', ['fastestFee', 'halfHourFee', 'hourFee', 'economyFee'].map((key) => fees[key] == null ? '—' : `${key.replace('Fee', '')} ${number(fees[key])}`).join(' · '));
    }

  }

  let loading = false;
  async function refresh() {
    if (loading) return;
    loading = true;
    $('refreshBtn').disabled = true;
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (!response.ok) throw new Error(`server HTTP ${response.status}`);
      render(await response.json());
    } catch (error) {
      $('errorBanner').hidden = false;
      $('errorBanner').textContent = `Impossibile raggiungere il servizio locale (${error.message}). Nessun valore simulato viene mostrato.`;
      $('connection').classList.remove('ok');
      $('connection').classList.add('error');
      $('connection').innerHTML = '<i></i> NON CONNESSO';
    } finally {
      loading = false;
      $('refreshBtn').disabled = false;
    }
  }
  $('refreshBtn').addEventListener('click', refresh);
  refresh();
  window.setInterval(refresh, 60_000);
})();
