async function loadCommands(){
  const res = await fetch('/api/commands');
  const commands = await res.json();
  const sel = document.getElementById('command');
  sel.innerHTML = '';
  for(const key of Object.keys(commands)){
    const opt = document.createElement('option');
    opt.value = key;
    opt.textContent = key + ' — ' + (commands[key].desc || '');
    sel.appendChild(opt);
  }
  sel.addEventListener('change', renderParams);
  renderParams();
}

function renderParams(){
  const sel = document.getElementById('command');
  const command = sel.value;
  fetch('/api/commands').then(r=>r.json()).then(commands=>{
    const info = commands[command];
    const container = document.getElementById('params');
    container.innerHTML = '';
    if(!info) return;
    for(const p of info.params){
      const lbl = document.createElement('label');
      lbl.textContent = p;
      const inp = document.createElement('input');
      inp.id = 'param-'+p;
      inp.name = p;
      inp.placeholder = p;
      if(p === 'start' || p === 'end') inp.type = 'date';
      container.appendChild(lbl);
      container.appendChild(inp);
    }
  });
}

document.getElementById('execute').addEventListener('click', async ()=>{
  const sel = document.getElementById('command');
  const command = sel.value;
  const params = {};
  // gather inputs
  document.querySelectorAll('#params input').forEach(i=>{
    const name = i.name;
    params[name] = i.value;
  });

  // adapt date fields to ISO
  if(params.start) params.start = params.start;
  if(params.end) params.end = params.end;

  const respEl = document.getElementById('response');
  respEl.textContent = 'Ejecutando...';
  try{
    const r = await fetch('/api/execute',{ method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ command, params }) });
    const data = await r.json();
    respEl.textContent = JSON.stringify(data, null, 2);
  }catch(e){
    respEl.textContent = 'Error: ' + e.message;
  }
});

loadCommands().catch(e=>{ document.getElementById('response').textContent = 'No se pudieron cargar comandos: '+e.message });
