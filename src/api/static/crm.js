// Sovereign CRM - vanilla JS frontend. All calls hit the local /crm REST API.
const api = {
  async get(p) { const r = await fetch('/crm' + p); return r.json(); },
  async post(p, body) {
    const r = await fetch('/crm' + p, { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    return r.json();
  },
  async patch(p, body) {
    const r = await fetch('/crm' + p, { method: 'PATCH',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    return r.json();
  },
};
const STAGES = ['lead', 'qualified', 'proposal', 'negotiation', 'won', 'lost'];
const $ = (s) => document.querySelector(s);
const el = (h) => { const d = document.createElement('div'); d.innerHTML = h; return d.firstElementChild; };
const money = (n) => Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 0 });
const when = (ts) => ts ? new Date(ts * 1000).toLocaleDateString() : '';

// ---- navigation ----------------------------------------------------------
document.querySelectorAll('.tab[data-view]').forEach((t) => {
  t.addEventListener('click', () => switchView(t.dataset.view));
});
function switchView(name) {
  document.querySelectorAll('.tab[data-view]').forEach((t) =>
    t.classList.toggle('active', t.dataset.view === name));
  document.querySelectorAll('.view').forEach((v) =>
    v.classList.toggle('active', v.id === 'view-' + name));
  ({ dashboard: loadDashboard, contacts: loadContacts, pipeline: loadPipeline, tasks: loadTasks }[name])();
}

// ---- dashboard -----------------------------------------------------------
async function loadDashboard() {
  const d = await api.get('/dashboard');
  const s = d.summary;
  $('#dash-cards').innerHTML = '';
  const cards = [['Open deals', s.open_deals], ['Pipeline value', money(s.pipeline_value)],
    ['Due follow-ups', s.due_tasks], ['Appts (7d)', s.upcoming_appointments]];
  cards.forEach(([l, n]) => $('#dash-cards').appendChild(
    el(`<div class="card"><div class="num">${n}</div><div class="label">${l}</div></div>`)));
  $('#dash-pipeline').innerHTML = s.stages.map((st) =>
    `<div class="row"><span class="name">${st.stage}</span>
     <span class="sub">${st.count} deals · ${money(st.value)}</span></div>`).join('') || '<p class="muted">No deals.</p>';
  $('#dash-tasks').innerHTML = d.due_tasks.map((t) =>
    `<div class="row overdue"><span class="name">${t.title}</span>
     <span class="sub">${t.type}</span></div>`).join('') || '<p class="muted">Nothing due.</p>';
  $('#dash-stale').innerHTML = d.stale_contacts.map((x) =>
    `<div class="row"><span class="name">${x.contact.name}</span>
     <span class="sub">last contact ${when(x.last_interaction)}</span></div>`).join('') || '<p class="muted">None.</p>';
}

// ---- contacts ------------------------------------------------------------
async function loadContacts() {
  const q = $('#contact-search').value || '';
  const contacts = await api.get('/contacts?query=' + encodeURIComponent(q));
  const list = $('#contact-list');
  list.innerHTML = '';
  contacts.forEach((c) => {
    const row = el(`<div class="row"><span class="name">${c.name}</span>
      <div class="sub">${c.email || ''} ${c.phone || ''}</div></div>`);
    row.addEventListener('click', () => showContact(c.id));
    list.appendChild(row);
  });
  if (!contacts.length) list.innerHTML = '<p class="muted">No contacts yet.</p>';
}
async function showContact(id) {
  const d = await api.get('/contacts/' + id);
  const c = d.contact;
  const deals = d.deals.map((x) => `<div class="item">${x.title} — ${x.stage} (${money(x.value)})</div>`).join('') || '<span class="muted">none</span>';
  const acts = d.interactions.map((i) => `<div class="item"><b>${i.type}</b> ${i.summary} <span class="muted">${when(i.created_at)}</span></div>`).join('') || '<span class="muted">none</span>';
  const tasks = d.tasks.filter((t) => t.status === 'pending').map((t) =>
    `<div class="item">${t.title} <span class="muted">due ${when(t.due_date)}</span></div>`).join('') || '<span class="muted">none</span>';
  $('#contact-detail').innerHTML = `
    <h3>${c.name} <span class="pill">#${c.id}</span></h3>
    <p class="muted">${c.email || ''} · ${c.phone || ''} · ${c.tags || ''}</p>
    <p>${c.notes || ''}</p>
    <div class="toolbar">
      <button class="btn small" id="log-btn">Log activity</button>
      <button class="btn small" id="task-btn">Add follow-up</button>
    </div>
    <h4>Deals</h4>${deals}
    <h4>Activity</h4><div class="timeline">${acts}</div>
    <h4>Open follow-ups</h4>${tasks}`;
  $('#log-btn').addEventListener('click', () => logActivity(c.id));
  $('#task-btn').addEventListener('click', () => addTask(c.id));
}

// ---- pipeline ------------------------------------------------------------
async function loadPipeline() {
  const deals = await api.get('/deals?status=open');
  const board = $('#pipeline-board');
  board.innerHTML = '';
  STAGES.forEach((stage) => {
    const items = deals.filter((d) => d.stage === stage);
    const total = items.reduce((a, d) => a + (d.value || 0), 0);
    const col = el(`<div class="col"><h4>${stage}<span>${money(total)}</span></h4></div>`);
    items.forEach((d) => {
      const card = el(`<div class="deal">${d.title}<br><span class="val">${money(d.value)}</span></div>`);
      card.addEventListener('click', () => moveDeal(d));
      col.appendChild(card);
    });
    board.appendChild(col);
  });
}
async function moveDeal(d) {
  const next = prompt(`Move "${d.title}" to stage (${STAGES.join(', ')}):`, d.stage);
  if (next && STAGES.includes(next)) {
    const status = next === 'won' ? 'won' : next === 'lost' ? 'lost' : 'open';
    await api.patch('/deals/' + d.id, { stage: next, status });
    loadPipeline();
  }
}

// ---- tasks ---------------------------------------------------------------
async function loadTasks() {
  const tasks = await api.get('/tasks/due');
  const list = $('#tasks-list');
  list.innerHTML = tasks.map((t) =>
    `<div class="row" data-id="${t.id}"><span class="name overdue">${t.title}</span>
     <span class="sub">${t.type}</span>
     <button class="btn small done-btn" data-id="${t.id}">Done</button></div>`).join('')
    || '<p class="muted">No follow-ups due. Nice.</p>';
  list.querySelectorAll('.done-btn').forEach((b) =>
    b.addEventListener('click', async () => { await api.post('/tasks/' + b.dataset.id + '/complete'); loadTasks(); }));
}

// ---- modals / forms ------------------------------------------------------
function openModal(title, html) {
  $('#modal-title').textContent = title;
  $('#modal-body').innerHTML = html;
  $('#modal').classList.remove('hidden');
}
function closeModal() { $('#modal').classList.add('hidden'); }
$('#modal-close').addEventListener('click', closeModal);

function newContact() {
  openModal('New contact', `<form class="crm-form" id="f">
    <input name="name" placeholder="Name" required>
    <input name="email" placeholder="Email">
    <input name="phone" placeholder="Phone">
    <input name="source" placeholder="Source (referral, web, ...)">
    <input name="tags" placeholder="Tags (comma separated)">
    <textarea name="notes" placeholder="Notes"></textarea>
    <button class="btn primary" type="submit">Create</button></form>`);
  bindForm('/contacts', loadContacts);
}
function newDeal() {
  openModal('New deal', `<form class="crm-form" id="f">
    <input name="title" placeholder="Deal title" required>
    <input name="value" type="number" placeholder="Value">
    <input name="contact_id" type="number" placeholder="Contact id (optional)">
    <select name="stage">${STAGES.map((s) => `<option>${s}</option>`).join('')}</select>
    <button class="btn primary" type="submit">Create</button></form>`);
  bindForm('/deals', loadPipeline);
}
function newTask() { addTask(''); }
function addTask(contactId) {
  openModal('New follow-up', `<form class="crm-form" id="f">
    <input name="title" placeholder="What to do" required>
    <input name="contact_id" type="number" placeholder="Contact id" value="${contactId}">
    <input name="due_in_days" type="number" placeholder="Due in days" value="1">
    <select name="type"><option>follow_up</option><option>call</option><option>email</option>
      <option>payment_reminder</option><option>check_in</option></select>
    <button class="btn primary" type="submit">Schedule</button></form>`);
  bindForm('/tasks', loadTasks);
}
function logActivity(contactId) {
  openModal('Log activity', `<form class="crm-form" id="f">
    <input name="contact_id" type="hidden" value="${contactId}">
    <select name="type"><option>call</option><option>email</option><option>meeting</option>
      <option>message</option><option>note</option></select>
    <textarea name="summary" placeholder="What happened?"></textarea>
    <button class="btn primary" type="submit">Save</button></form>`);
  bindForm('/interactions', () => showContact(contactId));
}
function bindForm(endpoint, after) {
  $('#f').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {};
    new FormData(e.target).forEach((v, k) => { data[k] = v; });
    ['value', 'contact_id', 'due_in_days'].forEach((k) => { if (data[k] !== undefined && data[k] !== '') data[k] = Number(data[k]); });
    await api.post(endpoint, data);
    closeModal();
    after();
  });
}

// ---- wire up -------------------------------------------------------------
$('#new-contact-btn').addEventListener('click', newContact);
$('#new-deal-btn').addEventListener('click', newDeal);
$('#new-task-btn').addEventListener('click', newTask);
$('#contact-search').addEventListener('input', () => loadContacts());
$('#backup-btn').addEventListener('click', async () => {
  $('#backup-status').textContent = 'Backing up...';
  const r = await api.post('/backup');
  $('#backup-status').textContent = 'Saved snapshot + CSVs';
});
loadDashboard();
