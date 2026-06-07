"""The single-page HTML/JS frontend for the Mind Meld web server."""

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Mind Meld</title>
<style>
  :root { --bg:#0e1726; --card:#16223a; --line:#26344f; --txt:#e6ecf5;
          --accent:#5ad1c0; --accent2:#7aa2ff; --warn:#ffb454; --bad:#ff6b81; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,sans-serif;
         background:radial-gradient(1200px 600px at 50% -10%,#1b2a48,#0e1726);
         color:var(--txt); min-height:100vh; }
  .wrap { max-width:680px; margin:0 auto; padding:24px 16px 60px; }
  h1 { font-weight:800; letter-spacing:.5px; margin:.2em 0 0; font-size:30px; }
  .sub { color:#9fb0c9; margin:4px 0 22px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:14px;
          padding:18px; margin:14px 0; box-shadow:0 8px 30px rgba(0,0,0,.25); }
  label { display:block; font-size:13px; color:#9fb0c9; margin:10px 0 4px; }
  select,input { width:100%; padding:10px 12px; border-radius:10px; color:var(--txt);
          background:#0f1a2e; border:1px solid var(--line); font-size:15px; }
  .row { display:flex; gap:14px; }
  .row > div { flex:1; }
  button { cursor:pointer; border:none; border-radius:10px; padding:11px 16px;
          font-size:15px; font-weight:700; color:#06121f;
          background:linear-gradient(90deg,var(--accent),var(--accent2)); }
  button.ghost { background:#23324e; color:var(--txt); font-weight:600; }
  button:disabled { opacity:.5; cursor:not-allowed; }
  .btns { display:flex; gap:10px; margin-top:16px; flex-wrap:wrap; }
  table { width:100%; border-collapse:collapse; margin-top:8px; }
  th,td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--line);
          vertical-align:top; }
  th { color:#9fb0c9; font-weight:600; font-size:12px; text-transform:uppercase; }
  .match td { color:var(--accent); }
  .match .word { font-weight:800; }
  td.rnum { color:#7e8db0; font-weight:700; }
  .word { font-weight:700; font-size:16px; }
  .think { color:#9fb0c9; font-size:12px; margin-top:3px; line-height:1.35;
           max-width:230px; font-style:italic; }
  .pill { display:inline-block; padding:2px 9px; border-radius:999px; font-size:12px;
          background:#23324e; color:#cdd9ee; }
  .banner { text-align:center; padding:16px; border-radius:12px; font-weight:800;
            font-size:20px; margin-top:8px; }
  .win { background:rgba(90,209,192,.15); color:var(--accent);
         border:1px solid rgba(90,209,192,.5); }
  .lose { background:rgba(255,107,129,.12); color:var(--bad);
          border:1px solid rgba(255,107,129,.4); }
  .err { color:var(--bad); margin-top:8px; min-height:18px; font-size:14px; }
  .used { color:#7e8db0; font-size:13px; margin-top:10px; }
  .turnbox { text-align:center; }
  .hint { color:#9fb0c9; font-size:13px; margin:6px 0 0; }
  .spin { color:var(--warn); }
  a { color:var(--accent2); }
</style>
</head>
<body>
<div class="wrap">
  <h1>🧠 Mind Meld</h1>
  <div class="sub">Think of a word. Say it together. Converge.</div>

  <!-- SETUP -->
  <div id="setup" class="card">
    <div class="row" id="playerCfgs"></div>
    <label>Max rounds</label>
    <input id="maxRounds" type="number" min="1" max="30" value="12"/>
    <div class="btns"><button id="startBtn">Start game</button></div>
    <div class="hint">Tip: pick two different AI models and watch them try to read each
      other's mind.</div>
  </div>

  <!-- GAME -->
  <div id="game" class="card" style="display:none">
    <div id="vs" class="sub" style="text-align:center;font-weight:700"></div>
    <div id="banner"></div>
    <div id="turn"></div>
    <div class="err" id="err"></div>
    <table id="board" style="display:none">
      <thead><tr><th>#</th><th id="h1"></th><th id="h2"></th><th></th></tr></thead>
      <tbody id="rows"></tbody>
    </table>
    <div class="used" id="used"></div>
    <div class="btns">
      <button id="newBtn" class="ghost" style="display:none">New game</button>
    </div>
  </div>
</div>

<script>
let MODELS = [];
let STATE = null;

const $ = s => document.querySelector(s);
const el = (t,p={}) => Object.assign(document.createElement(t), p);

function playerCfg(slot){
  const box = el('div');
  box.innerHTML = `
    <label>Player ${slot}</label>
    <select class="ptype" data-slot="${slot}">
      <option value="human">Human</option>
      <option value="ai">AI</option>
    </select>
    <label>Model</label>
    <select class="pmodel" data-slot="${slot}" disabled></select>
    <label>Name</label>
    <input class="pname" data-slot="${slot}" placeholder="Player ${slot}"/>`;
  return box;
}

function fillModels(sel){
  sel.innerHTML = '';
  MODELS.forEach(m => sel.appendChild(el('option',{value:m.id,textContent:m.name})));
}

async function init(){
  const cfgs = $('#playerCfgs');
  cfgs.appendChild(playerCfg(1));
  cfgs.appendChild(playerCfg(2));
  MODELS = await (await fetch('/api/models')).json();
  document.querySelectorAll('.pmodel').forEach(fillModels);
  document.querySelectorAll('.ptype').forEach(sel => {
    sel.addEventListener('change', e => {
      const slot = e.target.dataset.slot;
      const m = document.querySelector(`.pmodel[data-slot="${slot}"]`);
      m.disabled = e.target.value !== 'ai';
    });
  });
  $('#startBtn').addEventListener('click', startGame);
  $('#newBtn').addEventListener('click', () => location.reload());
}

function readCfg(slot){
  const type = document.querySelector(`.ptype[data-slot="${slot}"]`).value;
  const model = document.querySelector(`.pmodel[data-slot="${slot}"]`).value;
  const name = document.querySelector(`.pname[data-slot="${slot}"]`).value;
  return {type, model, name};
}

async function startGame(){
  const body = {p1: readCfg(1), p2: readCfg(2),
                max_rounds: parseInt($('#maxRounds').value)||12};
  STATE = await postJSON('/api/new', body);
  $('#setup').style.display='none';
  $('#game').style.display='block';
  $('#vs').textContent = `${STATE.p1.label}   vs   ${STATE.p2.label}`;
  $('#h1').textContent = STATE.p1.name;
  $('#h2').textContent = STATE.p2.name;
  render();
}

async function postJSON(url, body){
  const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
                            body:JSON.stringify(body)});
  return r.json();
}

function render(){
  // board
  const rows = $('#rows'); rows.innerHTML='';
  STATE.rounds.forEach(r => {
    const tr = el('tr'); if(r.matched) tr.className='match';
    const cell = (word, reason) => {
      const think = reason
        ? `<div class="think">💭 ${escapeHtml(reason)}</div>` : '';
      return `<td><div class="word">${escapeHtml(word)}</div>${think}</td>`;
    };
    tr.innerHTML = `<td class="rnum">${r.round}</td>`+
                   cell(r.w1, r.r1) + cell(r.w2, r.r2) +
                   `<td>${r.matched?'🧠 meld!':''}</td>`;
    rows.appendChild(tr);
  });
  $('#board').style.display = STATE.rounds.length ? 'table':'none';
  $('#used').textContent = STATE.used.length ? 'Used: '+STATE.used.join(', ') : '';
  $('#err').textContent = STATE.error || '';

  if(STATE.finished){ renderFinished(); return; }
  $('#banner').innerHTML='';
  renderTurn();
}

function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function renderFinished(){
  const b = $('#banner');
  if(STATE.converged){
    b.className='banner win';
    b.textContent = `🧠 MIND MELD on “${STATE.final_word}” in ${STATE.round_no} round(s)!`;
  } else {
    b.className='banner lose';
    b.textContent = `No convergence after ${STATE.round_no} rounds.`;
  }
  $('#turn').innerHTML='';
  $('#newBtn').style.display='inline-block';
}

function renderTurn(){
  const t = $('#turn');
  const n = STATE.round_no + 1;
  const humans = [];
  if(STATE.p1.human) humans.push(['p1', STATE.p1.name]);
  if(STATE.p2.human) humans.push(['p2', STATE.p2.name]);
  const lastHint = STATE.last
    ? `<p class="hint">Last round — ${STATE.p1.name}: “${STATE.last.w1}”, `+
      `${STATE.p2.name}: “${STATE.last.w2}”. Find a word that bridges them.</p>` : '';

  if(humans.length === 0){
    t.innerHTML = `<div class="turnbox"><p class="hint">Round ${n}. `+
      `Two AIs are thinking…</p>${lastHint}`+
      `<div class="btns" style="justify-content:center">`+
      `<button id="goBtn">Reveal round ${n}</button></div></div>`;
    $('#goBtn').addEventListener('click', ()=>submitRound({}));
    return;
  }
  let inputs = humans.map(([k,name]) =>
    `<label>${name}'s word (hidden)</label>`+
    `<input type="password" class="wordin" data-key="${k}" autocomplete="off"/>`
  ).join('');
  const multi = humans.length===2
    ? `<p class="hint">Both players enter a word without peeking at each other.</p>`:'';
  t.innerHTML = `<div class="turnbox"><p class="hint">Round ${n}.</p>${lastHint}${multi}`+
    `${inputs}<div class="btns" style="justify-content:center">`+
    `<button id="goBtn">Say it!</button></div></div>`;
  const go = $('#goBtn');
  const fire = ()=>{
    const words={};
    document.querySelectorAll('.wordin').forEach(i=>words[i.dataset.key]=i.value);
    submitRound(words);
  };
  go.addEventListener('click', fire);
  document.querySelectorAll('.wordin').forEach(i =>
    i.addEventListener('keydown', e=>{ if(e.key==='Enter') fire(); }));
  const first = document.querySelector('.wordin'); if(first) first.focus();
}

async function submitRound(words){
  const go = $('#goBtn'); if(go){ go.disabled=true; go.textContent='Thinking…'; }
  $('#turn').insertAdjacentHTML('beforeend',
    '<p class="hint spin" id="spin">⏳ waiting for both words…</p>');
  let res;
  try {
    res = await postJSON('/api/round', {game_id:STATE.game_id, words});
  } catch(e){
    res = {error: 'Network error contacting the server — please try again.'};
  }
  const spin = $('#spin'); if(spin) spin.remove();
  // A well-formed response carries the full game state (it has `rounds`).
  if(res && Array.isArray(res.rounds)){
    STATE = res;
    render();
  } else {
    // Error-only / malformed response: keep the previous good state, attach the
    // error, and re-render so the correct turn UI (and button) comes back. The
    // spinner never stays stuck.
    STATE.error = (res && res.error) || 'Unexpected error — try again.';
    render();
  }
}

init();
</script>
</body>
</html>
"""
