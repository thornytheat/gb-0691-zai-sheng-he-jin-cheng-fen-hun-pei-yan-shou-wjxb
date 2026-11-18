const ledger = { busy: false };
const feedback = document.querySelector('#feedback');
const ledgerId = () => document.querySelector('#ledger-id').textContent.trim();

function setFeedback(message, bad) {
  feedback.textContent = message || '';
  feedback.style.color = bad ? 'var(--bad)' : 'var(--ok)';
}

async function call(url, options) {
  if (ledger.busy) return;
  ledger.busy = true;
  setFeedback('处理中…', false);
  document.querySelectorAll('button').forEach(b => b.disabled = true);
  try {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || '请求失败');
    return data;
  } finally {
    ledger.busy = false;
    document.querySelectorAll('button').forEach(b => b.disabled = false);
  }
}

async function postJson(url, body) {
  return call(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

async function postFile(url, field, file) {
  const form = new FormData();
  form.append(field, file);
  return call(url, { method: 'POST', body: form });
}

function render(view) {
  document.querySelector('#ledger-id').textContent = view.ledger_id;
  document.querySelector('#kpi-balance').innerHTML =
    view.conservation.balance_kg + ' <small>kg</small>';
  document.querySelector('#kpi-conserved').textContent =
    view.conservation.conserved ? '相符' : '差异';
  const lots = document.querySelector('#lots-body');
  lots.innerHTML = view.lots.map(l => `<tr class="${l.status === '隔离' ? 'sev--severe' : ''}">
    <td>${l.lot}</td><td>${l.receipt_id}</td><td>${l.arrival_batch}</td>
    <td>${l.wet_mass_kg}</td><td>${l.moisture_pct}</td><td>${l.dry_total_kg}</td>
    <td>${l.dry_balance_kg}</td><td title="${l.到货含量}">${l.到货含量}</td><td>${l.status}</td>
  </tr>`).join('');
  const issues = document.querySelector('#issues-body');
  issues.innerHTML = view.issues.map(i => `<tr>
    <td>${i.seq}</td><td>${i.request_id}</td><td>${i.lot}</td><td>${i.furnace}</td>
    <td>${i.requested_kg}</td><td>${i.remaining_kg}</td><td>${i.处理 || '已确认'}</td></tr>`).join('');
  const q = document.querySelector('#quarantine-body');
  q.innerHTML = view.quarantine.map(r => `<tr>
    <td>${r.行号 ?? '—'}</td><td>${r.回执 ?? '—'}</td><td>${r.批号 ?? '—'}</td>
    <td class="sev--severe">${r.原因码}</td><td>${r.原因}</td></tr>`).join('');
  history.replaceState(null, '', '/ledger/' + encodeURIComponent(view.ledger_id));
}

document.querySelector('#receipt-submit').addEventListener('click', async () => {
  try {
    const data = await postJson('/api/m8/ledgers',
      { csv: document.querySelector('#receipt-csv').value });
    render(data);
    setFeedback(data.reused ? '同回执已存在，复用台账（幂等）。' : '台账已建立。', false);
  } catch (e) { setFeedback(e.message, true); }
});

document.querySelector('#receipt-upload').addEventListener('click', async () => {
  const file = document.querySelector('#receipt-file').files[0];
  if (!file) return setFeedback('先选择回执 CSV。', true);
  try { render(await postFile('/api/m8/ledgers', 'receipts', file)); setFeedback('台账已建立。', false); }
  catch (e) { setFeedback(e.message, true); }
});

document.querySelector('#sample-receipts').addEventListener('click', async () => {
  try {
    const data = await postJson('/api/m8/ledgers',
      { csv: document.querySelector('#receipt-csv').value });
    render(data);
    setFeedback(data.reused ? '样例台账已存在，复用。' : '样例台账已建立。', false);
  } catch (e) { setFeedback(e.message, true); }
});

document.querySelector('#one-submit').addEventListener('click', async () => {
  try {
    const data = await postJson(`/api/m8/ledgers/${ledgerId()}/issue`, {
      request_id: document.querySelector('#one-request').value.trim(),
      lot: document.querySelector('#one-lot').value.trim(),
      furnace: document.querySelector('#one-furnace').value.trim(),
      dry_mass: document.querySelector('#one-mass').value.trim(),
      unit: document.querySelector('#one-unit').value,
    });
    render(data.ledger);
    setFeedback(data.replayed ? '请求号已确认，回放原记录，未重复扣减。' : '领用已确认。', false);
  } catch (e) { setFeedback(e.message, true); }
});

async function runBatch(csv) {
  try {
    const data = await postJson(`/api/m8/ledgers/${ledgerId()}/batch`, { csv });
    render(data.ledger);
    const b = data.batch;
    setFeedback(b.stopped_at
      ? `在 ${b.stopped_at} 中断：${b.reason}；已确认 ${b.confirmed_count} 条，修正后可续跑。`
      : `全部处理完成（确认 ${b.results.length} 条，含跳过/回放，未重复扣减）。`,
      !!b.stopped_at);
  } catch (e) { setFeedback(e.message, true); }
}

document.querySelector('#batch-submit').addEventListener('click',
  () => runBatch(document.querySelector('#batch-csv').value));

document.querySelector('#batch-upload').addEventListener('click', () => {
  const file = document.querySelector('#batch-file').files[0];
  if (!file) return setFeedback('先选择领用 CSV。', true);
  const reader = new FileReader();
  reader.onload = () => runBatch(reader.result);
  reader.readAsText(file);
});
