"""Workflow Automator — embedded web dashboard UI.

The entire frontend (HTML + CSS + JS) lives here as a single string so the
dashboard command needs zero external dependencies: no npm, no frameworks,
no build step. The server in :mod:`src.dashboard` serves this page at ``/``
and exposes a small JSON API the page talks to.
"""

# Metadata shared by the GTK editor and the web editor. Kept in sync with
# src/gui/workflow_editor.py — the web dashboard edits the same data model.
TRIGGER_TYPES = ["bluetooth", "power", "schedule", "network", "shell"]
ACTION_TYPES = ["shell", "launch", "notify", "media"]
MEDIA_ACTIONS = ["Play", "Pause", "Play-Pause", "Next", "Previous", "Stop", "Open URI"]
KNOWN_PLAYERS = [
    "spotify", "vlc", "firefox", "chromium", "mpv",
    "audacious", "clementine", "rhythmbox", "amarok",
    "plasma-browser-integration", "strawberry", "tauon",
]

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Workflow Automator — Dashboard</title>
<style>
  :root {
    --bg: #0f1115;
    --panel: #171a21;
    --panel-2: #1e222b;
    --border: #2a2f3a;
    --text: #e8eaf0;
    --muted: #9aa3b2;
    --accent: #6366f1;
    --accent-2: #22d3ee;
    --green: #34d399;
    --red: #f87171;
    --amber: #fbbf24;
    --radius: 12px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    min-height: 100vh;
  }
  header {
    display: flex; align-items: center; gap: 14px;
    padding: 16px 28px;
    border-bottom: 1px solid var(--border);
    background: linear-gradient(180deg, #14171f, #10131a);
    position: sticky; top: 0; z-index: 50;
    backdrop-filter: blur(6px);
  }
  header .logo { font-size: 24px; }
  header h1 { font-size: 18px; font-weight: 700; letter-spacing: .2px; }
  header h1 .accent { background: linear-gradient(90deg, var(--accent), var(--accent-2));
    -webkit-background-clip: text; background-clip: text; color: transparent; }
  .badge {
    font-size: 11px; font-weight: 600; letter-spacing: .4px; text-transform: uppercase;
    padding: 3px 10px; border-radius: 999px;
    background: rgba(99, 102, 241, .15); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, .35);
  }
  .meta { margin-left: auto; display: flex; align-items: center; gap: 10px; font-size: 12px; color: var(--muted); }
  .meta code { background: var(--panel-2); padding: 3px 8px; border-radius: 6px; font-size: 11px; }
  .btn {
    appearance: none; border: 1px solid var(--border); cursor: pointer;
    background: var(--panel-2); color: var(--text);
    padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 600;
    transition: transform .06s ease, background .15s ease, border-color .15s ease;
  }
  .btn:hover { border-color: #3a4150; background: #242936; }
  .btn:active { transform: scale(.97); }
  .btn.primary {
    background: linear-gradient(90deg, var(--accent), #4f46e5);
    border-color: transparent; color: #fff;
  }
  .btn.primary:hover { filter: brightness(1.1); }
  .btn.danger { color: var(--red); border-color: rgba(248, 113, 113, .3); }
  .btn.danger:hover { background: rgba(248, 113, 113, .1); border-color: var(--red); }
  .btn.small { padding: 5px 10px; font-size: 12px; }
  main { max-width: 1080px; margin: 0 auto; padding: 28px; }
  .toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
  .toolbar .count { color: var(--muted); font-size: 13px; }
  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
  .card {
    background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 18px; display: flex; flex-direction: column; gap: 12px;
    transition: border-color .15s ease, transform .1s ease;
  }
  .card:hover { border-color: #383f4d; transform: translateY(-1px); }
  .card.disabled { opacity: .55; }
  .card-top { display: flex; align-items: flex-start; gap: 10px; }
  .card-top .name { font-size: 15px; font-weight: 700; flex: 1; word-break: break-word; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip {
    font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 999px;
    background: rgba(99, 102, 241, .12); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, .25);
  }
  .chip.off { background: rgba(154, 163, 178, .1); color: var(--muted); border-color: var(--border); }
  .card-foot { display: flex; align-items: center; gap: 8px; margin-top: auto; }
  .card-foot .spacer { flex: 1; }
  .switch { position: relative; width: 40px; height: 22px; flex-shrink: 0; }
  .switch input { opacity: 0; width: 0; height: 0; }
  .switch .slider {
    position: absolute; inset: 0; border-radius: 999px; background: #333a47;
    transition: background .18s ease; cursor: pointer;
  }
  .switch .slider::before {
    content: ""; position: absolute; width: 16px; height: 16px; border-radius: 50%;
    left: 3px; top: 3px; background: #fff; transition: transform .18s ease;
  }
  .switch input:checked + .slider { background: linear-gradient(90deg, var(--accent), var(--accent-2)); }
  .switch input:checked + .slider::before { transform: translateX(18px); }
  .empty {
    text-align: center; padding: 70px 20px; color: var(--muted);
    border: 1px dashed var(--border); border-radius: var(--radius);
  }
  .empty .big { font-size: 44px; margin-bottom: 12px; }
  .empty p { font-size: 14px; line-height: 1.6; }
  /* Modal */
  .overlay {
    position: fixed; inset: 0; background: rgba(5, 7, 10, .7);
    display: none; align-items: flex-start; justify-content: center;
    padding: 40px 16px; z-index: 100; overflow-y: auto;
  }
  .overlay.open { display: flex; }
  .modal {
    background: var(--panel); border: 1px solid var(--border); border-radius: 16px;
    width: 100%; max-width: 640px; padding: 24px; box-shadow: 0 24px 60px rgba(0,0,0,.5);
  }
  .modal h2 { font-size: 16px; margin-bottom: 18px; display: flex; align-items: center; gap: 10px; }
  .field { margin-bottom: 14px; }
  .field label { display: block; font-size: 12px; font-weight: 600; color: var(--muted); margin-bottom: 6px; text-transform: uppercase; letter-spacing: .3px; }
  input[type=text], select, textarea {
    width: 100%; padding: 9px 12px; border-radius: 8px;
    background: var(--panel-2); border: 1px solid var(--border); color: var(--text);
    font-size: 13px; font-family: inherit;
  }
  input[type=text]:focus, select:focus, textarea:focus { outline: none; border-color: var(--accent); }
  .section-title {
    display: flex; align-items: center; justify-content: space-between;
    margin: 20px 0 10px; padding-top: 16px; border-top: 1px solid var(--border);
    font-size: 13px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .4px;
  }
  .subrow {
    background: var(--panel-2); border: 1px solid var(--border); border-radius: 10px;
    padding: 12px; margin-bottom: 10px;
  }
  .subrow .row-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
  .subrow .row-head select { width: auto; min-width: 130px; }
  .subrow .row-head .lbl { font-size: 12px; color: var(--muted); }
  .subrow .fields { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .subrow .fields .full { grid-column: 1 / -1; }
  .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
  /* Toast */
  #toasts { position: fixed; bottom: 20px; right: 20px; display: flex; flex-direction: column; gap: 8px; z-index: 200; }
  .toast {
    background: var(--panel-2); border: 1px solid var(--border); color: var(--text);
    padding: 10px 16px; border-radius: 10px; font-size: 13px;
    box-shadow: 0 8px 24px rgba(0,0,0,.4); animation: slidein .18s ease;
  }
  .toast.ok { border-color: rgba(52, 211, 153, .5); }
  .toast.err { border-color: rgba(248, 113, 113, .5); }
  @keyframes slidein { from { transform: translateX(20px); opacity: 0; } to { transform: none; opacity: 1; } }
  @media (max-width: 640px) {
    .meta .hide-sm { display: none; }
    main { padding: 16px; }
  }
</style>
</head>
<body>
<header>
  <span class="logo">⚡</span>
  <h1>Workflow <span class="accent">Automator</span></h1>
  <span class="badge">Web Dashboard</span>
  <div class="meta">
    <span class="hide-sm">v<span id="ver">–</span></span>
    <code class="hide-sm" id="dbpath" title="Database">–</code>
    <span class="hide-sm">localhost:<span id="port">–</span></span>
  </div>
</header>

<main>
  <div class="toolbar">
    <span class="count" id="count">Loading…</span>
    <button class="btn primary" onclick="openEditor(null)">＋ New Workflow</button>
  </div>
  <div class="cards" id="cards"></div>
  <div class="empty" id="empty" style="display:none">
    <div class="big">⚡</div>
    <p><b>No Workflows Yet</b><br>Click <b>＋ New Workflow</b> to create your first automation.</p>
  </div>
</main>

<div class="overlay" id="overlay">
  <div class="modal">
    <h2 id="modalTitle">New Workflow</h2>
    <div class="field">
      <label>Name</label>
      <input type="text" id="f_name" placeholder="My workflow…">
    </div>

    <div class="section-title"><span>Triggers</span>
      <button class="btn small" onclick="addTrigger()">＋ Add trigger</button>
    </div>
    <div id="triggers"></div>

    <div class="section-title"><span>Actions</span>
      <button class="btn small" onclick="addAction()">＋ Add action</button>
    </div>
    <div id="actions"></div>

    <div class="modal-actions">
      <button class="btn" onclick="closeEditor()">Cancel</button>
      <button class="btn primary" onclick="saveEditor()">Save Workflow</button>
    </div>
  </div>
</div>

<div id="toasts"></div>

<script>
"use strict";
const TRIGGERS = {
  bluetooth: { icon: "🎧", label: "When Bluetooth connects",
    fields: [["device_name", "Device name", "text", "e.g. Sony WH-1000XM4"],
             ["mac_pattern", "MAC pattern (optional)", "text", "e.g. 00:11:22:33:44:55"]] },
  power:    { icon: "🔌", label: "When power changes",
    fields: [["state", "State", "select", ["plugged", "unplugged"]]] },
  schedule: { icon: "🕐", label: "Scheduled",
    fields: [["cron_expr", "Cron expression", "text", "e.g. 0 8 * * *"]] },
  network:  { icon: "🌐", label: "When network changes",
    fields: [["ssid", "SSID", "text", "Network name"],
             ["interface", "Interface (optional)", "text", "e.g. wlan0"]] },
  shell:    { icon: "⌨️", label: "When command matches",
    fields: [["command", "Command to watch", "text", "e.g. battery-low"]] },
};
const ACTIONS = {
  shell:  { icon: "🖥️", label: "Run command",
    fields: [["command", "Command", "text", "e.g. spotify --start-playback"]] },
  launch: { icon: "🚀", label: "Launch app",
    fields: [["command", "App path", "text", "e.g. /usr/bin/spotify"]] },
  notify: { icon: "🔔", label: "Notification",
    fields: [["subject", "Subject", "text", "Notification subject"],
             ["body", "Body", "text", "Notification body"]] },
  media:  { icon: "🎵", label: "Media control", media: true },
};
const MEDIA_ACTIONS = ["Play", "Pause", "Play-Pause", "Next", "Previous", "Stop", "Open URI"];
const KNOWN_PLAYERS = ["spotify", "vlc", "firefox", "chromium", "mpv", "audacious",
  "clementine", "rhythmbox", "amarok", "plasma-browser-integration", "strawberry", "tauon"];
const $ = (id) => document.getElementById(id);
let workflows = [];
let meta = {};

/* ---------- API ---------- */
async function api(path, opts) {
  opts = opts || {};
  opts.headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
  const res = await fetch(path, opts);
  if (res.status === 204) return null;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || ("HTTP " + res.status));
  return body;
}

/* ---------- Toast ---------- */
function toast(msg, ok) {
  const el = document.createElement("div");
  el.className = "toast " + (ok ? "ok" : "err");
  el.textContent = msg;
  $("toasts").appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

/* ---------- Render list ---------- */
function chipLabel(t) {
  const info = TRIGGERS[t.type];
  if (!info) return { icon: "❔", label: "When " + t.type, known: false };
  return { icon: info.icon, label: info.label, known: true };
}
function renderCards() {
  const cards = $("cards");
  cards.innerHTML = "";
  const on = workflows.filter(w => w.enabled).length;
  $("count").textContent = workflows.length + (workflows.length === 1 ? " workflow" : " workflows")
      + " · " + on + " enabled";
  $("empty").style.display = workflows.length ? "none" : "block";
  for (const wf of workflows) {
    const card = document.createElement("div");
    card.className = "card" + (wf.enabled ? "" : " disabled");

    const top = document.createElement("div");
    top.className = "card-top";
    const name = document.createElement("div");
    name.className = "name";
    name.textContent = wf.name || "(untitled)";
    top.appendChild(name);
    card.appendChild(top);

    const chips = document.createElement("div");
    chips.className = "chips";
    const trigs = wf.triggers || [];
    if (trigs.length === 0) {
      const c = document.createElement("span");
      c.className = "chip off";
      c.textContent = "no trigger";
      chips.appendChild(c);
    }
    for (const t of trigs) {
      const c = document.createElement("span");
      const info = chipLabel(t);
      c.className = "chip" + (t.enabled ? "" : " off");
      c.textContent = info.icon + " " + info.label;
      chips.appendChild(c);
    }
    const nAct = (wf.actions || []).length;
    const c = document.createElement("span");
    c.className = "chip off";
    c.textContent = nAct === 1 ? "1 action" : nAct + " actions";
    chips.appendChild(c);
    card.appendChild(chips);

    const foot = document.createElement("div");
    foot.className = "card-foot";
    const sw = document.createElement("label");
    sw.className = "switch";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !!wf.enabled;
    cb.addEventListener("change", () => toggleWorkflow(wf, cb.checked));
    const slider = document.createElement("span");
    slider.className = "slider";
    sw.appendChild(cb); sw.appendChild(slider);
    foot.appendChild(sw);
    const spacer = document.createElement("span");
    spacer.className = "spacer";
    foot.appendChild(spacer);
    const edit = document.createElement("button");
    edit.className = "btn small";
    edit.textContent = "Edit";
    edit.onclick = () => openEditor(wf.id);
    const del = document.createElement("button");
    del.className = "btn small danger";
    del.textContent = "Delete";
    del.onclick = () => deleteWorkflow(wf);
    foot.appendChild(edit); foot.appendChild(del);
    card.appendChild(foot);
    cards.appendChild(card);
  }
}

/* ---------- Mutations ---------- */
async function toggleWorkflow(wf, enabled) {
  try {
    await api("/api/workflows/" + wf.id, { method: "PUT", body: JSON.stringify({ enabled: enabled }) });
    wf.enabled = enabled;
    renderCards();
    toast(enabled ? "Workflow enabled" : "Workflow paused", true);
  } catch (e) { toast(e.message, false); loadAll(); }
}
async function deleteWorkflow(wf) {
  if (!confirm("Delete workflow \u201c" + wf.name + "\u201d? Its triggers and actions go too.")) return;
  try {
    await api("/api/workflows/" + wf.id, { method: "DELETE" });
    toast("Workflow deleted", true);
    loadAll();
  } catch (e) { toast(e.message, false); }
}

/* ---------- Editor ---------- */
let editingId = null;
let editor = { name: "", triggers: [], actions: [] };

function openEditor(id) {
  editingId = id;
  if (id == null) {
    editor = { name: "", triggers: [], actions: [] };
    $("modalTitle").textContent = "New Workflow";
  } else {
    const wf = workflows.find(w => w.id === id);
    if (!wf) return;
    editor = {
      name: wf.name,
      triggers: (wf.triggers || []).map(t => Object.assign({}, t, { config: Object.assign({}, t.config) })),
      actions: (wf.actions || []).map(a => Object.assign({}, a, { args: (a.args || []).slice() })),
    };
    $("modalTitle").textContent = "Edit Workflow";
  }
  $("f_name").value = editor.name;
  renderTriggers();
  renderActions();
  $("overlay").classList.add("open");
}
function closeEditor() { $("overlay").classList.remove("open"); }

function renderTriggers() {
  const box = $("triggers");
  box.innerHTML = "";
  editor.triggers.forEach((t, i) => box.appendChild(triggerRow(t, i)));
}
function triggerRow(t, i) {
  const wrap = document.createElement("div");
  wrap.className = "subrow";
  const head = document.createElement("div");
  head.className = "row-head";
  const sel = document.createElement("select");
  for (const k of Object.keys(TRIGGERS)) {
    const opt = document.createElement("option");
    opt.value = k; opt.textContent = TRIGGERS[k].icon + " " + TRIGGERS[k].label;
    if (k === t.type) opt.selected = true;
    sel.appendChild(opt);
  }
  sel.onchange = () => {
    t.type = sel.value;
    t.config = {};
    renderTriggers();
  };
  head.appendChild(sel);
  const lbl = document.createElement("span");
  lbl.className = "lbl";
  lbl.textContent = "Trigger " + (i + 1);
  head.appendChild(lbl);
  const rm = document.createElement("button");
  rm.className = "btn small danger";
  rm.textContent = "✕";
  rm.onclick = () => { editor.triggers.splice(i, 1); renderTriggers(); };
  head.appendChild(rm);
  wrap.appendChild(head);
  const fields = document.createElement("div");
  fields.className = "fields";
  for (const [key, label, kind, extra] of TRIGGERS[t.type].fields) {
    const holder = document.createElement("div");
    holder.className = key === "mac_pattern" || key === "interface" || key === "cron_expr" ? "full" : "";
    const lab = document.createElement("label");
    lab.textContent = label;
    holder.appendChild(lab);
    let input;
    if (kind === "select") {
      input = document.createElement("select");
      for (const optVal of extra) {
        const opt = document.createElement("option");
        opt.value = optVal; opt.textContent = optVal;
        if (optVal === t.config[key]) opt.selected = true;
        input.appendChild(opt);
      }
    } else {
      input = document.createElement("input");
      input.type = "text";
      input.placeholder = extra || "";
      input.value = t.config[key] || "";
    }
    input.onchange = () => { t.config[key] = input.value; };
    holder.appendChild(input);
    fields.appendChild(holder);
  }
  wrap.appendChild(fields);
  return wrap;
}

function renderActions() {
  const box = $("actions");
  box.innerHTML = "";
  editor.actions.forEach((a, i) => box.appendChild(actionRow(a, i)));
}
function actionRow(a, i) {
  const wrap = document.createElement("div");
  wrap.className = "subrow";
  const head = document.createElement("div");
  head.className = "row-head";
  const sel = document.createElement("select");
  for (const k of Object.keys(ACTIONS)) {
    const opt = document.createElement("option");
    opt.value = k; opt.textContent = ACTIONS[k].icon + " " + ACTIONS[k].label;
    if (k === a.type) opt.selected = true;
    sel.appendChild(opt);
  }
  sel.onchange = () => {
    a.type = sel.value;
    a.command = ""; a.args = [];
    renderActions();
  };
  head.appendChild(sel);
  const lbl = document.createElement("span");
  lbl.className = "lbl";
  lbl.textContent = "Action " + (i + 1);
  head.appendChild(lbl);
  const rm = document.createElement("button");
  rm.className = "btn small danger";
  rm.textContent = "✕";
  rm.onclick = () => { editor.actions.splice(i, 1); renderActions(); };
  head.appendChild(rm);
  wrap.appendChild(head);

  const fields = document.createElement("div");
  fields.className = "fields";
  if (a.type === "media") {
    const p = document.createElement("div");
    p.className = "full";
    const labP = document.createElement("label");
    labP.textContent = "Player";
    p.appendChild(labP);
    const player = document.createElement("input");
    player.type = "text";
    player.setAttribute("list", "players-datalist");
    const [cmdPlayer, cmdAct] = (a.command || "|").split("|");
    player.value = cmdPlayer;
    player.onchange = () => { a.command = player.value + "|" + actSel.value; };
    p.appendChild(player);
    fields.appendChild(p);

    const d = document.createElement("div");
    d.className = "full";
    const labD = document.createElement("label");
    labD.textContent = "Action";
    d.appendChild(labD);
    const actSel = document.createElement("select");
    for (const m of MEDIA_ACTIONS) {
      const opt = document.createElement("option");
      opt.value = m; opt.textContent = m;
      if (m === (cmdAct || "Play")) opt.selected = true;
      actSel.appendChild(opt);
    }
    actSel.onchange = () => {
      a.command = player.value + "|" + actSel.value;
      uriRow.style.display = actSel.value === "Open URI" ? "" : "none";
      a.args = actSel.value === "Open URI" ? [uri.value] : [];
    };
    d.appendChild(actSel);
    fields.appendChild(d);

    const uriRow = document.createElement("div");
    uriRow.className = "full";
    const labU = document.createElement("label");
    labU.textContent = "URI";
    uriRow.appendChild(labU);
    const uri = document.createElement("input");
    uri.type = "text";
    uri.placeholder = "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M";
    uri.value = (a.args || [])[0] || "";
    uri.onchange = () => { a.args = [uri.value]; };
    uriRow.appendChild(uri);
    fields.appendChild(uriRow);
    uriRow.style.display = actSel.value === "Open URI" ? "" : "none";
  } else {
    const spec = ACTIONS[a.type];
    for (const [key, label, kind, extra] of spec.fields) {
      const holder = document.createElement("div");
      holder.className = "full";
      const lab = document.createElement("label");
      lab.textContent = label;
      holder.appendChild(lab);
      const input = document.createElement("input");
      input.type = "text";
      input.placeholder = extra || "";
      if (a.type === "notify") {
        input.value = key === "subject" ? a.command : ((a.args || [])[0] || "");
        input.onchange = () => {
          if (key === "subject") a.command = input.value;
          else a.args = [input.value];
        };
      } else {
        input.value = a.command || "";
        input.onchange = () => { a.command = input.value; };
      }
      holder.appendChild(input);
      fields.appendChild(holder);
    }
  }
  wrap.appendChild(fields);
  return wrap;
}

function addTrigger() {
  editor.triggers.push({ type: "schedule", config: {}, enabled: true });
  renderTriggers();
}
function addAction() {
  editor.actions.push({ type: "shell", command: "", args: [], enabled: true });
  renderActions();
}

async function saveEditor() {
  const name = $("f_name").value.trim() || "New Workflow";
  let id = editingId;
  try {
    if (id == null) {
      const created = await api("/api/workflows", { method: "POST", body: JSON.stringify({ name: name, enabled: true }) });
      id = created.id;
    } else {
      await api("/api/workflows/" + id, { method: "PUT", body: JSON.stringify({ name: name }) });
    }
    await syncChildren(id);
    closeEditor();
    toast("Workflow saved", true);
    loadAll();
  } catch (e) { toast(e.message, false); }
}

async function syncChildren(wfId) {
  const detail = await api("/api/workflows/" + wfId);
  const liveTrigs = new Set((detail.triggers || []).map(t => t.id));
  const liveActs = new Set((detail.actions || []).map(a => a.id));
  const keepTrigs = new Set(), keepActs = new Set();

  for (const t of editor.triggers) {
    if (t.id != null) {
      await api("/api/triggers/" + t.id, { method: "PUT", body: JSON.stringify({ type: t.type, config: t.config, enabled: true }) });
      keepTrigs.add(t.id);
    } else {
      await api("/api/workflows/" + wfId + "/triggers", { method: "POST", body: JSON.stringify({ type: t.type, config: t.config }) });
    }
  }
  for (const a of editor.actions) {
    if (a.id != null) {
      await api("/api/actions/" + a.id, { method: "PUT", body: JSON.stringify({ type: a.type, command: a.command, args: a.args, enabled: true }) });
      keepActs.add(a.id);
    } else {
      await api("/api/workflows/" + wfId + "/actions", { method: "POST", body: JSON.stringify({ type: a.type, command: a.command, args: a.args }) });
    }
  }
  for (const tid of liveTrigs) if (!keepTrigs.has(tid)) await api("/api/triggers/" + tid, { method: "DELETE" });
  for (const aid of liveActs) if (!keepActs.has(aid)) await api("/api/actions/" + aid, { method: "DELETE" });
}

/* ---------- Boot ---------- */
async function loadAll() {
  try {
    const [wf, m] = await Promise.all([api("/api/workflows"), api("/api/meta")]);
    workflows = wf;
    meta = m;
    $("ver").textContent = m.version;
    $("dbpath").textContent = m.db_path;
    $("port").textContent = m.port;
    renderCards();
  } catch (e) { toast("Failed to load: " + e.message, false); }
}

const dl = document.createElement("datalist");
dl.id = "players-datalist";
for (const p of KNOWN_PLAYERS) {
  const opt = document.createElement("option");
  opt.value = p;
  dl.appendChild(opt);
}
document.body.appendChild(dl);

loadAll();
setInterval(loadAll, 15000);
window.addEventListener("keydown", (e) => { if (e.key === "Escape") closeEditor(); });
</script>
</body>
</html>
"""
