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
    // keep track of a two-column grid; we'll create wrappers for each param
    for(const p of info.params){
      const wrapper = document.createElement('div');
      if(['image_base64','name','registration'].includes(p)) wrapper.className = 'full';
      const lbl = document.createElement('label');
      lbl.textContent = p;
      wrapper.appendChild(lbl);
      // richer input types
      if(p === 'start' || p === 'end'){
        const inp = document.createElement('input'); inp.type='date'; inp.id='param-'+p; inp.name=p; wrapper.appendChild(inp);
      } else if(p.endsWith('_id') || ['id','user_id','group_id','limit'].includes(p)){
        const inp = document.createElement('input'); inp.type='number'; inp.id='param-'+p; inp.name=p; wrapper.appendChild(inp);
      } else if(p === 'match'){
        const sel = document.createElement('select'); sel.id='param-'+p; sel.name=p; const o1=document.createElement('option');o1.value='0';o1.textContent='0 (no)'; const o2=document.createElement('option');o2.value='1';o2.textContent='1 (yes)'; sel.appendChild(o1); sel.appendChild(o2); wrapper.appendChild(sel);
      } else if(p === 'image_base64'){
        const file = document.createElement('input'); file.type='file'; file.accept='image/*'; file.id='param-'+p; file.name=p; wrapper.appendChild(file);
      } else {
        const inp = document.createElement('input'); inp.type='text'; inp.id='param-'+p; inp.name=p; wrapper.appendChild(inp);
      }
      container.appendChild(wrapper);
    }
  });
}

// Devices management and selection
async function loadDevices(){
  const res = await fetch('/api/devices');
  const devices = await res.json();
  const sel = document.getElementById('device');
  sel.innerHTML = '';
  const empty = document.createElement('option');
  empty.value = '';
  empty.textContent = '-- Seleccione dispositivo --';
  sel.appendChild(empty);
  for(const d of devices){
    const opt = document.createElement('option');
    opt.value = d.id;
    opt.textContent = d.name + ' (' + d.ip + ')';
    sel.appendChild(opt);
  }
  sel.addEventListener('change', onDeviceChange);
  renderDevicesList(devices);
}

function renderDevicesList(devices){
  const container = document.getElementById('devicesList');
  container.innerHTML = '';
  if(!devices.length) container.textContent = 'No hay dispositivos configurados.';
  devices.forEach(d=>{
    const div = document.createElement('div');
    div.style.padding = '6px 0';
    div.innerHTML = `<strong>${d.name}</strong> (${d.ip}) ` +
      `<button data-id="${d.id}" class="edit">Editar</button> ` +
      `<button data-id="${d.id}" class="del">Eliminar</button>`;
    container.appendChild(div);
  });
  container.querySelectorAll('.del').forEach(btn=>{
    btn.addEventListener('click', async (e)=>{
      const id = e.target.getAttribute('data-id');
      await fetch('/api/devices/'+id, { method:'DELETE' });
      await loadDevices();
    });
  });
  container.querySelectorAll('.edit').forEach(btn=>{
    btn.addEventListener('click', async (e)=>{
      const id = e.target.getAttribute('data-id');
      const res = await fetch('/api/devices/'+id);
      const device = await res.json();
      // open edit view
      showEditDevice(device);
    });
  });
}

function showEditDevice(device){
  document.getElementById('deviceManager').style.display = 'block';
  document.getElementById('new_name').value = device.name || '';
  document.getElementById('new_ip').value = device.ip || '';
  document.getElementById('new_login').value = device.login || '';
  document.getElementById('new_password').value = device.password || '';
  // store editing id on addDevice button temporarily
  const addBtn = document.getElementById('addDevice');
  addBtn.textContent = 'Guardar cambios';
  addBtn.dataset.editing = device.id;
  // load defaults editor
  renderDefaultsEditor(device);
}

function renderDefaultsEditor(device){
  // create area below form to manage defaults per command
  let defArea = document.getElementById('defaultsArea');
  if(!defArea){
    defArea = document.createElement('div'); defArea.id='defaultsArea';
    defArea.style.marginTop='12px';
    document.getElementById('deviceManager').appendChild(defArea);
  }
  defArea.innerHTML = '<h4>Defaults por comando</h4>';
  const cmdSel = document.createElement('select'); cmdSel.id='defaultsCommand';
  fetch('/api/commands').then(r=>r.json()).then(commands=>{
    for(const k of Object.keys(commands)){
      const o = document.createElement('option'); o.value=k; o.textContent=k; cmdSel.appendChild(o);
    }
    defArea.appendChild(cmdSel);
    const paramsContainer = document.createElement('div'); paramsContainer.id='defaultsParams'; paramsContainer.style.marginTop='8px'; defArea.appendChild(paramsContainer);
    cmdSel.addEventListener('change', ()=>{
      renderDefaultsParamsForCommand(device, cmdSel.value, paramsContainer);
    });
    // render for first
    renderDefaultsParamsForCommand(device, cmdSel.value, paramsContainer);
  });
}

function renderDefaultsParamsForCommand(device, command, container){
  container.innerHTML = '';
  fetch('/api/commands').then(r=>r.json()).then(commands=>{
    const info = commands[command]; if(!info) return;
    info.params.forEach(p=>{
      const lbl = document.createElement('label'); lbl.textContent = p;
      const inp = document.createElement('input'); inp.id='def-'+p; inp.placeholder=p;
      // prefill from device.defaults
      const val = device.defaults && device.defaults[command] ? device.defaults[command][p] : '';
      inp.value = val || '';
      container.appendChild(lbl); container.appendChild(inp);
    });
    const saveBtn = document.createElement('button'); saveBtn.textContent = 'Guardar defaults para '+command;
    saveBtn.addEventListener('click', async ()=>{
      // construct defaults object
      const defs = device.defaults || {};
      defs[command] = {};
      info.params.forEach(p=>{ defs[command][p] = document.getElementById('def-'+p).value; });
      // PUT to update device
      const body = { name: document.getElementById('new_name').value, ip: document.getElementById('new_ip').value, login: document.getElementById('new_login').value, password: document.getElementById('new_password').value, defaults: defs };
      const res = await fetch('/api/devices/'+device.id, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
      if(res.ok) { alert('Defaults guardados'); await loadDevices(); }
      else alert('Error guardando');
    });
    container.appendChild(saveBtn);
  });
}

async function onDeviceChange(){
  const sel = document.getElementById('device');
  const id = sel.value;
  if(!id) return;
  const res = await fetch('/api/devices/' + id);
  const device = await res.json();
  // populate common fields
  const ipField = document.getElementById('param-deviceIp');
  if(ipField) ipField.value = device.ip || '';
  const loginField = document.getElementById('param-login');
  if(loginField) loginField.value = device.login || '';
  const passField = document.getElementById('param-password');
  if(passField) passField.value = device.password || '';

  // If device has command-specific defaults, merge into inputs
  const selCmd = document.getElementById('command');
  const cmd = selCmd.value;
  if(device.defaults && device.defaults[cmd]){
    const defs = device.defaults[cmd];
    Object.keys(defs).forEach(k=>{
      const el = document.getElementById('param-'+k);
      if(el) el.value = defs[k];
    });
  }
}

document.getElementById('manageDevices').addEventListener('click', ()=>{
  document.getElementById('deviceManager').style.display = 'block';
});
document.getElementById('closeManager').addEventListener('click', ()=>{
  document.getElementById('deviceManager').style.display = 'none';
});

document.getElementById('addDevice').addEventListener('click', async ()=>{
  const name = document.getElementById('new_name').value;
  const ip = document.getElementById('new_ip').value;
  const login = document.getElementById('new_login').value;
  const password = document.getElementById('new_password').value;
  if(!name || !ip) return alert('Nombre e IP obligatorios');
  const addBtn = document.getElementById('addDevice');
  if(addBtn.dataset.editing){
    const id = addBtn.dataset.editing;
    const defaults = {};
    // keep any existing defaults rendered in defaultsArea
    const defaultsArea = document.getElementById('defaultsArea');
    if(defaultsArea && window.currentEditingDefaults) Object.assign(defaults, window.currentEditingDefaults);
    await fetch('/api/devices/'+id, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ name, ip, login, password, defaults }) });
    addBtn.textContent = 'Añadir'; delete addBtn.dataset.editing;
    document.getElementById('defaultsArea').remove(); window.currentEditingDefaults = null;
  } else {
    await fetch('/api/devices', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ name, ip, login, password, defaults:{} }) });
  }
  document.getElementById('new_name').value=''; document.getElementById('new_ip').value=''; document.getElementById('new_login').value=''; document.getElementById('new_password').value='';
  await loadDevices();
});


document.getElementById('execute').addEventListener('click', async ()=>{
  const sel = document.getElementById('command');
  const command = sel.value;
  const params = {};
  // gather inputs
  document.querySelectorAll('#params input').forEach(i=>{
    const name = i.name;
    params[name] = i.value;
  });

  // include selected device id if any
  const deviceSel = document.getElementById('device');
  if(deviceSel && deviceSel.value) params.deviceId = deviceSel.value;

  // adapt date fields to ISO
  if(params.start) params.start = params.start;
  if(params.end) params.end = params.end;

  const respEl = document.getElementById('response');
  respEl.textContent = 'Ejecutando...';
  try{
    // handle file inputs: convert to base64 if any file selected
    for(const key of Object.keys(params)){
      const el = document.getElementById('param-'+key);
      if(el && el.type === 'file' && el.files && el.files[0]){
        const file = el.files[0];
        params[key] = await toBase64(file);
      }
    }

    const r = await fetch('/api/execute',{ method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ command, params }) });
    const data = await r.json();
    respEl.textContent = JSON.stringify(data, null, 2);
    addHistory(command, params, data);
  }catch(e){
    respEl.textContent = 'Error: ' + e.message;
  }
});

function toBase64(file){
  return new Promise((resolve, reject)=>{
    const reader = new FileReader();
    reader.onload = ()=> resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function addHistory(command, params, result){
  const h = document.getElementById('history');
  const el = document.createElement('div'); el.className='card small'; el.style.marginBottom='8px';
  const ts = new Date().toLocaleString();
  el.innerHTML = `<div><strong>${command}</strong> <span class="muted">${ts}</span></div><div class="small">${JSON.stringify(params)}</div><pre style="margin-top:6px">${JSON.stringify(result)}</pre>`;
  h.prepend(el);
}

document.getElementById('clearResponse').addEventListener('click', ()=>{ document.getElementById('response').textContent=''; });

async function loadSessions(){
  try{
    const res = await fetch('/api/sessions');
    const data = await res.json();
    const keys = Object.keys(data);
    document.getElementById('sessionIndicator').textContent = keys.length + ' sessions';
  }catch(e){ document.getElementById('sessionIndicator').textContent = 'error'; }
}

// Load both commands and devices and sessions
Promise.all([loadCommands(), loadDevices(), loadSessions()]).catch(e=>{ document.getElementById('response').textContent = 'Error cargando inicial: '+e.message });

// Load both commands and devices
Promise.all([loadCommands(), loadDevices()]).catch(e=>{ document.getElementById('response').textContent = 'Error cargando inicial: '+e.message });
