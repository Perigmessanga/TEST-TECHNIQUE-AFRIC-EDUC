const form = document.querySelector('#login');
const out = document.querySelector('#out');
const loginView = document.querySelector('#loginView');
const appView = document.querySelector('#appView');
const loginError = document.querySelector('#loginError');
const queueKey = 'passage-offline-queue-v1';

if ('serviceWorker' in navigator) navigator.serviceWorker.register('/static/sw.js');

function queue() {
  return JSON.parse(localStorage.getItem(queueKey) || '[]');
}

function saveQueue(items) {
  localStorage.setItem(queueKey, JSON.stringify(items));
  document.querySelector('#queueCount').textContent = items.length;
  document.querySelector('#queueList').textContent = items.length
    ? items.map(x => `${x.local_event_id.slice(0, 8)} · ${x.point_id}`).join('\n')
    : 'Aucun passage en attente';
}

window.addEventListener('online', () => updateNetwork());
window.addEventListener('offline', () => updateNetwork());
function updateNetwork() {
  const badge = document.querySelector('#network');
  badge.textContent = navigator.onLine ? 'En ligne' : 'Hors ligne';
  badge.className = navigator.onLine ? 'online' : 'offline';
}
updateNetwork();

document.querySelector('#login').addEventListener('submit', async event => {
  event.preventDefault();
  loginError.textContent = '';
  const data = Object.fromEntries(new FormData(event.target));
  const response = await fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  if (!response.ok) { loginError.textContent = 'Identifiants invalides'; return; }
  const result = await response.json();
  loginView.classList.add('hidden'); appView.classList.remove('hidden');
  document.querySelector('#welcome').textContent = `Rôle : ${result.role}`;
  document.querySelector(`#${result.role === 'responsable' ? 'responsable' : result.role}Panel`).classList.remove('hidden');
  if (result.role === 'agent') loadPoints();
});

document.querySelector('#logout').addEventListener('click', async () => {
  await fetch('/api/logout', {method:'POST'});
  location.reload();
});

async function loadPoints() {
  const response = await fetch('/api/control-points');
  if (!response.ok) return;
  const points = await response.json();
  const select = document.querySelector('#point');
  select.innerHTML = points.map(p => `<option value="${p.id}">${p.label}</option>`).join('');
  saveQueue(queue());
}

document.querySelector('#queueScan').addEventListener('click', () => {
  const token = document.querySelector('#badgeToken').value.trim();
  if (token.length < 20) { document.querySelector('#scanStatus').textContent = 'Jeton temporaire requis.'; return; }
  const items = queue();
  items.push({
    point_id: Number(document.querySelector('#point').value),
    local_time: new Date().toISOString(),
    device_id: localStorage.deviceId || (localStorage.deviceId = crypto.randomUUID()),
    badge_token: token,
    local_event_id: crypto.randomUUID()
  });
  saveQueue(items);
  document.querySelector('#badgeToken').value = '';
  document.querySelector('#scanStatus').textContent = 'Passage conservé dans la file locale.';
});

async function syncQueue() {
  const items = queue();
  if (!items.length) return;
  const response = await fetch('/api/sync', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({items})});
  if (!response.ok) return;
  const result = await response.json();
  // La clé unique serveur empêche les doublons si cette synchronisation reprend après coupure.
  const duplicateEvents = new Set((result.rejected || []).map(r => r.event));
  const handled = new Set([...(result.accepted_events || []), ...(result.duplicate_events || [])]);
  saveQueue(items.filter(x => !handled.has(x.local_event_id) && !duplicateEvents.has(x.local_event_id)));
  document.querySelector('#scanStatus').textContent = `${result.accepted} accepté · ${result.duplicates} doublon(s) · ${result.rejected.length} rejet(s)`;
}

document.querySelector('#syncNow').addEventListener('click', syncQueue);
window.addEventListener('online', () => syncQueue());

// Détecter les absences clôturées
const detectButton = document.querySelector('#detect');
if (detectButton) detectButton.addEventListener('click', async () => {
  const response = await fetch('/api/anomalies/detect', {method:'POST'});
  document.querySelector('#anomalies').textContent = response.ok ? JSON.stringify(await response.json()) : 'Accès refusé';
});

const summaryButton = document.querySelector('#summary');
if (summaryButton) {
  document.querySelector('#summaryDate').value = new Date().toISOString().slice(0,10);
  summaryButton.addEventListener('click', async () => {
    const response = await fetch('/api/summaries', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({class_name:document.querySelector('#className').value,date:document.querySelector('#summaryDate').value})});
    if (!response.ok) { document.querySelector('#summaryText').textContent = 'Synthèse indisponible'; return; }
    const result = await response.json();
    document.querySelector('#summaryText').textContent = `${result.text} — origine: ${result.origin}`;
  });
}

const loadStudent = document.querySelector('#loadStudent');
if (loadStudent) loadStudent.addEventListener('click', async () => {
  const id = document.querySelector('#studentId').value;
  const response = await fetch(`/api/students/${encodeURIComponent(id)}`);
  document.querySelector('#studentResult').textContent = response.ok ? JSON.stringify(await response.json(), null, 2) : 'Accès refusé';
});
