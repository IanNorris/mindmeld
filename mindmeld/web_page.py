"""The single-page HTML/JS frontend for the Mind Meld web server.

Supports two modes:
  * Local  — both players on one screen (pick Human/AI + model each).
  * Online — matchmaking: players are paired as they join, each plays from
    their own browser and submits only their own word.

A shared game view renders the board, live AI "thinking" panes (fed by an
SSE stream), and per-round word entry.
"""

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
  .wrap { max-width:720px; margin:0 auto; padding:24px 16px 60px; }
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
           max-width:250px; font-style:italic; }
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
  /* live thinking panes */
  .panes { display:flex; gap:12px; margin:8px 0 4px; }
  .pane { flex:1; background:#0f1a2e; border:1px solid var(--line);
          border-radius:10px; padding:10px 12px; min-height:64px; }
  .pane h4 { margin:0 0 6px; font-size:13px; color:#cdd9ee; display:flex;
             justify-content:space-between; }
  .pane .status { font-size:11px; color:#7e8db0; font-weight:600; }
  .pane .live { font-size:12.5px; line-height:1.4; color:#bcd; white-space:pre-wrap;
                font-family:ui-monospace,SFMono-Regular,Menlo,monospace; min-height:20px; }
  .pane.ready { border-color:rgba(90,209,192,.55); }
  .modesel { display:flex; gap:12px; }
  .modesel button { flex:1; padding:18px; font-size:16px; }
  .tag { display:inline-block; font-size:11px; padding:2px 8px; border-radius:999px;
         background:#23324e; color:#cdd9ee; margin-left:6px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>🧠 Mind Meld</h1>
  <div class="sub">Think of a word. Say it together. Converge.</div>

  <!-- HOME -->
  <div id="home" class="card">
    <div class="modesel">
      <button id="onlineBtn">🌐 Play online<br/><span style="font-weight:500;font-size:12px">match with the next player who joins</span></button>
      <button id="localBtn" class="ghost">🖥️ Local game<br/><span style="font-weight:500;font-size:12px">two players on this screen</span></button>
    </div>
  </div>

  <!-- ONLINE SETUP -->
  <div id="onlineSetup" class="card" style="display:none">
    <label>Your name</label>
    <input id="onName" placeholder="Player"/>
    <label>Opponent</label>
    <select id="onVs">
      <option value="human">A human (wait to be matched)</option>
      <option value="ai">An AI (play right now)</option>
    </select>
    <div id="onModelWrap" style="display:none">
      <label>AI model</label>
      <select id="onModel"></select>
    </div>
    <div class="btns">
      <button id="findBtn">Find a match</button>
      <button class="ghost" onclick="location.reload()">Back</button>
    </div>
  </div>

  <!-- WAITING ROOM -->
  <div id="waiting" class="card" style="display:none">
    <div class="turnbox">
      <p class="spin" style="font-size:18px;font-weight:700">⏳ Waiting for an opponent…</p>
      <p class="hint">You'll be matched with the next player who joins.</p>
      <div class="btns" style="justify-content:center">
        <button id="cancelBtn" class="ghost">Cancel</button>
      </div>
    </div>
  </div>

  <!-- LOCAL SETUP -->
  <div id="localSetup" class="card" style="display:none">
    <div class="row" id="playerCfgs"></div>
    <label>Max rounds</label>
    <input id="maxRounds" type="number" min="1" max="30" value="12"/>
    <div class="btns">
      <button id="startBtn">Start game</button>
      <button class="ghost" onclick="location.reload()">Back</button>
    </div>
    <div class="hint">Tip: pick two different AI models and watch them try to read
      each other's mind.</div>
  </div>

  <!-- GAME -->
  <div id="game" class="card" style="display:none">
    <div id="vs" class="sub" style="text-align:center;font-weight:700"></div>
    <div id="banner"></div>
    <div id="panes" class="panes"></div>
    <div id="turn"></div>
    <div class="err" id="err"></div>
    <table id="board" style="display:none">
      <thead><tr><th>#</th><th id="h1"></th><th id="h2"></th><th></th></tr></thead>
      <tbody id="rows"></tbody>
    </table>
    <div class="used" id="used"></div>
    <div class="btns">
      <button id="newBtn" class="ghost" style="display:none"
              onclick="location.reload()">New game</button>
    </div>
  </div>
</div>

<script>
let MODELS = [];
let STATE = null;
let MODE = null;            // 'online' | 'local'
let ME = {slot:null, token:null};
let ES = null;             // (legacy) unused; live updates now use WebSocket
let WS = null;             // single WebSocket for lobby + game events
let TICKET = null;
let liveText = {p1:'', p2:''};
let pendingEnter = false;  // show game view on the next 'state' push

const $ = s => document.querySelector(s);
const el = (t,p={}) => Object.assign(document.createElement(t), p);
const show = id => ['home','onlineSetup','waiting','localSetup','game']
  .forEach(s => $('#'+s).style.display = (s===id?'block':'none'));

function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
async function postJSON(url, body){
  const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
                            body:JSON.stringify(body||{})});
  return r.json();
}

/* ---------------- init / home ---------------- */
async function init(){
  MODELS = await (await fetch('/api/models')).json();
  fillModels($('#onModel'));
  buildLocalCfgs();
  $('#onlineBtn').onclick = ()=>{ MODE='online'; show('onlineSetup'); };
  $('#localBtn').onclick = ()=>{ MODE='local'; show('localSetup'); };
  $('#onVs').onchange = e =>
    $('#onModelWrap').style.display = (e.target.value==='ai'?'block':'none');
  $('#findBtn').onclick = findMatch;
  $('#cancelBtn').onclick = cancelMatch;
  $('#startBtn').onclick = startLocal;
}
function fillModels(sel){
  sel.innerHTML='';
  MODELS.forEach(m => sel.appendChild(el('option',{value:m.id,textContent:m.name})));
}

/* ---------------- WebSocket (replaces SSE + lobby polling) ---------------- */
function wsURL(){
  return (location.protocol==='https:'?'wss://':'ws://') + location.host + '/ws';
}
function openWS(subscribe){
  if(WS){ try { WS.close(); } catch(e){} }
  WS = new WebSocket(wsURL());
  WS.onopen = () => WS.send(JSON.stringify(subscribe));
  WS.onmessage = ev => {
    let m; try { m = JSON.parse(ev.data); } catch(e){ return; }
    handleWS(m);
  };
}
function handleWS(m){
  if(m.type==='error'){ $('#err').textContent = m.error||'Server error'; return; }
  if(m.type==='ticket'){            // matched after waiting
    ME = {slot:m.slot, token:m.token};
    pendingEnter = true;            // game view appears on the next 'state'
    return;
  }
  if(m.kind==='state'){
    STATE = m.state;
    if(pendingEnter || $('#game').style.display==='none'){ enterGameView(); }
    pendingEnter = false;
    render();
    return;
  }
  if(m.kind==='round_start'){ liveText = {p1:'', p2:''}; renderPanes('thinking'); return; }
  if(m.kind==='delta'){ liveText[m.slot] = (liveText[m.slot]||'') + m.text; renderPanes('thinking'); return; }
  if(m.kind==='submitted'){
    markSubmitted(m.slot);
    if(MODE==='online' && m.slot===ME.slot) render();  // show my "waiting" state
    return;
  }
  // round_done is followed by a 'state' push, so nothing to do here.
}

/* ---------------- online matchmaking ---------------- */
async function findMatch(){
  const name = $('#onName').value.trim() || 'Player';
  const vs = $('#onVs').value;
  const model = $('#onModel').value;
  const t = await postJSON('/api/join', {name, vs, model});
  TICKET = t.ticket;
  if(t.status==='matched'){ onMatched(t); return; }
  show('waiting');
  // No polling: wait for a push over the WebSocket.
  openWS({type:'watch_ticket', ticket:TICKET});
}
async function cancelMatch(){
  if(WS){ try { WS.close(); } catch(e){} WS=null; }
  if(TICKET) await postJSON('/api/cancel', {ticket:TICKET});
  location.reload();
}
function onMatched(t){
  ME = {slot:t.slot, token:t.token};
  pendingEnter = true;
  openWS({type:'watch_game', game_id:t.game_id});
}

/* ---------------- local mode ---------------- */
function buildLocalCfgs(){
  const cfgs = $('#playerCfgs'); cfgs.innerHTML='';
  [1,2].forEach(slot => {
    const box = el('div');
    box.innerHTML = `
      <label>Player ${slot}</label>
      <select class="ptype" data-slot="${slot}">
        <option value="human">Human</option><option value="ai">AI</option></select>
      <label>Model</label>
      <select class="pmodel" data-slot="${slot}" disabled></select>
      <label>Name</label>
      <input class="pname" data-slot="${slot}" placeholder="Player ${slot}"/>`;
    cfgs.appendChild(box);
  });
  document.querySelectorAll('.pmodel').forEach(fillModels);
  document.querySelectorAll('.ptype').forEach(sel =>
    sel.onchange = e => {
      const m = document.querySelector(`.pmodel[data-slot="${e.target.dataset.slot}"]`);
      m.disabled = e.target.value!=='ai';
    });
}
function readLocalCfg(slot){
  return {
    type: document.querySelector(`.ptype[data-slot="${slot}"]`).value,
    model: document.querySelector(`.pmodel[data-slot="${slot}"]`).value,
    name: document.querySelector(`.pname[data-slot="${slot}"]`).value,
  };
}
async function startLocal(){
  const body = {p1:readLocalCfg(1), p2:readLocalCfg(2),
                max_rounds: parseInt($('#maxRounds').value)||12};
  const st = await postJSON('/api/new', body);
  ME = {slot:null, token:null};
  STATE = st;
  enterGameView();
  render();
  openWS({type:'watch_game', game_id:st.game_id});  // live updates via push
}

/* ---------------- shared game view ---------------- */
function enterGameView(){
  show('game');
  $('#vs').innerHTML = `${escapeHtml(STATE.p1.label)} &nbsp;vs&nbsp; ${escapeHtml(STATE.p2.label)}`
    + (MODE==='online' ? `<span class="tag">you are ${ME.slot==='p1'?STATE.p1.name:STATE.p2.name}</span>` : '');
  $('#h1').textContent = STATE.p1.name;
  $('#h2').textContent = STATE.p2.name;
}

function slotIsAI(slot){
  return slot==='p1' ? !STATE.p1.human : !STATE.p2.human;
}
function slotName(slot){ return slot==='p1'?STATE.p1.name:STATE.p2.name; }

function renderPanes(phase){
  // Show a live pane per player during/after a round.
  const wrap = $('#panes'); wrap.innerHTML='';
  if(STATE.finished && phase!=='thinking'){ wrap.style.display='none'; return; }
  wrap.style.display='flex';
  ['p1','p2'].forEach(slot => {
    const ai = slotIsAI(slot);
    const submitted = (STATE.submitted||[]).includes(slot);
    const txt = liveText[slot];
    let status = '';
    if(ai) status = txt ? 'thinking…' : 'waiting';
    else status = submitted ? '✓ ready' : 'choosing…';
    const body = ai
      ? (txt ? escapeHtml(txt) : '…')
      : (submitted ? '🔒 word locked in' : '✏️ choosing a word…');
    const pane = el('div', {className:'pane'+(submitted?' ready':'')});
    pane.innerHTML = `<h4>${escapeHtml(slotName(slot))}`+
      `<span class="status">${status}</span></h4>`+
      `<div class="live">${body}</div>`;
    wrap.appendChild(pane);
  });
}
function markSubmitted(slot){
  if(!STATE.submitted) STATE.submitted=[];
  if(!STATE.submitted.includes(slot)) STATE.submitted.push(slot);
  renderPanes('thinking');
}

function render(){
  const rows = $('#rows'); rows.innerHTML='';
  STATE.rounds.forEach(r => {
    const tr = el('tr'); if(r.matched) tr.className='match';
    const cell = (word, reason) => {
      const think = reason ? `<div class="think">💭 ${escapeHtml(reason)}</div>`:'';
      return `<td><div class="word">${escapeHtml(word)}</div>${think}</td>`;
    };
    tr.innerHTML = `<td class="rnum">${r.round}</td>`+cell(r.w1,r.r1)+cell(r.w2,r.r2)+
                   `<td>${r.matched?'🧠 meld!':''}</td>`;
    rows.appendChild(tr);
  });
  $('#board').style.display = STATE.rounds.length ? 'table':'none';
  $('#used').textContent = STATE.used.length ? 'Used: '+STATE.used.join(', ') : '';
  $('#err').textContent = STATE.error || '';
  renderPanes('idle');
  if(STATE.finished){ renderFinished(); return; }
  $('#banner').innerHTML='';
  renderTurn();
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
  const lastHint = STATE.last
    ? `<p class="hint">Last round — ${escapeHtml(STATE.p1.name)}: “${escapeHtml(STATE.last.w1)}”, `+
      `${escapeHtml(STATE.p2.name)}: “${escapeHtml(STATE.last.w2)}”. Find a word that bridges them.</p>`
    : '';

  if(MODE==='online'){
    const mine = ME.slot;
    const already = (STATE.submitted||[]).includes(mine);
    if(already){
      t.innerHTML = `<div class="turnbox"><p class="hint">Round ${n}.</p>${lastHint}`+
        `<p class="spin">⏳ waiting for your opponent…</p></div>`;
      return;
    }
    t.innerHTML = `<div class="turnbox"><p class="hint">Round ${n}. Your word (hidden):</p>${lastHint}`+
      `<input type="password" id="wordin" autocomplete="off"/>`+
      `<div class="btns" style="justify-content:center">`+
      `<button id="goBtn">Say it!</button></div></div>`;
    wireSubmit(words => submitOnline());
    return;
  }

  // local mode: collect words for all human slots on this screen
  const humans = [];
  if(STATE.p1.human) humans.push(['p1', STATE.p1.name]);
  if(STATE.p2.human) humans.push(['p2', STATE.p2.name]);
  if(humans.length===0){
    t.innerHTML = `<div class="turnbox"><p class="hint">Round ${n}. Two AIs are thinking…</p>`+
      `${lastHint}<div class="btns" style="justify-content:center">`+
      `<button id="goBtn">Reveal round ${n}</button></div></div>`;
    $('#goBtn').onclick = ()=>submitLocal({});
    return;
  }
  const inputs = humans.map(([k,name]) =>
    `<label>${escapeHtml(name)}'s word (hidden)</label>`+
    `<input type="password" class="wordin" data-key="${k}" autocomplete="off"/>`).join('');
  const multi = humans.length===2
    ? `<p class="hint">Both players enter a word without peeking at each other.</p>`:'';
  t.innerHTML = `<div class="turnbox"><p class="hint">Round ${n}.</p>${lastHint}${multi}`+
    `${inputs}<div class="btns" style="justify-content:center">`+
    `<button id="goBtn">Say it!</button></div></div>`;
  const fire = ()=>{
    const words={};
    document.querySelectorAll('.wordin').forEach(i=>words[i.dataset.key]=i.value);
    submitLocal(words);
  };
  $('#goBtn').onclick = fire;
  document.querySelectorAll('.wordin').forEach(i =>
    i.addEventListener('keydown', e=>{ if(e.key==='Enter') fire(); }));
  const first = document.querySelector('.wordin'); if(first) first.focus();
}

function wireSubmit(fn){
  const go = $('#goBtn'), inp = $('#wordin');
  const fire = ()=>fn();
  go.onclick = fire;
  inp.addEventListener('keydown', e=>{ if(e.key==='Enter') fire(); });
  inp.focus();
}

async function submitOnline(){
  const inp = $('#wordin'), go = $('#goBtn');
  const word = inp.value.trim();
  if(!word){ $('#err').textContent='Enter a word.'; return; }
  go.disabled=true; go.textContent='Sent';
  let res;
  try { res = await postJSON('/api/move', {game_id:STATE.game_id, token:ME.token, word}); }
  catch(e){ res = {error:'Network error — try again.'}; }
  if(res && Array.isArray(res.rounds)){ STATE = res; render(); }
  else { $('#err').textContent=(res&&res.error)||'Error'; go.disabled=false; go.textContent='Say it!'; }
}

async function submitLocal(words){
  const go = $('#goBtn'); if(go){ go.disabled=true; go.textContent='Thinking…'; }
  $('#turn').insertAdjacentHTML('beforeend',
    '<p class="hint spin" id="spin">⏳ resolving round…</p>');
  let res;
  try { res = await postJSON('/api/round', {game_id:STATE.game_id, words}); }
  catch(e){ res = {error:'Network error — try again.'}; }
  if(res && Array.isArray(res.rounds)){ STATE = res; render(); }
  else { STATE.error=(res&&res.error)||'Unexpected error — try again.'; render(); }
}

init();
</script>
</body>
</html>
"""
