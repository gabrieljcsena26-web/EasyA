(function(){
  // Simple static fallback app for quick sanity checks
  const API_BASE = 'http://127.0.0.1:8000'; // backend default in repo

  const el = id => document.getElementById(id);
  const configOut = el('configOut');
  const appointmentsOut = el('appointmentsOut');
  const status = el('status');
  const tokenInput = el('devtoken');
  let lastConfig = null;

  function setStatus(s){ status.textContent = s; }

  function getAuthHeaders(){
    const token = localStorage.getItem('DEV_JWT_TOKEN') || '';
    return token ? { 'Authorization': 'Bearer '+token } : {};
  }

  async function fetchJson(path){
    setStatus('Carregando '+path+'...');
    try{
      const res = await fetch(API_BASE + path, {
        headers: Object.assign({'Accept':'application/json'}, getAuthHeaders()),
      });
      const txt = await res.text();
      try{ return JSON.parse(txt); }catch(e){ return txt; }
    }catch(err){
      return { error: String(err) };
    }finally{ setStatus('Pronto'); }
  }

  el('loadConfig').addEventListener('click', async ()=>{
    configOut.textContent = '...';
    const data = await fetchJson('/admin/config');
    lastConfig = data;
    configOut.textContent = JSON.stringify(data, null, 2);
    // If we received professionals, show quick button to load today's appointments
    if (data && data.professionals && data.professionals.length>0){
      const prof = data.professionals[0];
      // add or update quick load button
      let quick = document.getElementById('quickLoadAppts');
      if(!quick){
        quick = document.createElement('button');
        quick.id = 'quickLoadAppts';
        quick.textContent = 'Carregar agendamentos (primeiro profissional hoje)';
        quick.style.marginLeft = '8px';
        document.querySelector('.controls').appendChild(quick);
        quick.addEventListener('click', async ()=>{
          const today = new Date().toISOString().slice(0,10);
          appointmentsOut.textContent = '...';
          const res = await fetchJson(`/appointments?professional_id=${prof.id}&date=${today}`);
          appointmentsOut.textContent = JSON.stringify(res, null, 2);
        });
      }
    }
  });

  el('loadAppointments').addEventListener('click', async ()=>{
    appointmentsOut.textContent = '...';
    // Fallback: if lastConfig has a professional, use it for today
    if(lastConfig && lastConfig.professionals && lastConfig.professionals.length>0){
      const prof = lastConfig.professionals[0];
      const today = new Date().toISOString().slice(0,10);
      const data = await fetchJson(`/appointments?professional_id=${prof.id}&date=${today}`);
      appointmentsOut.textContent = JSON.stringify(data, null, 2);
    }else{
      const data = await fetchJson('/appointments');
      appointmentsOut.textContent = JSON.stringify(data, null, 2);
    }
  });

  el('saveToken').addEventListener('click', ()=>{
    const v = tokenInput.value.trim();
    if(!v) return alert('Cole um token antes de salvar');
    localStorage.setItem('DEV_JWT_TOKEN', v);
    alert('Token salvo em localStorage DEV_JWT_TOKEN');
  });
  el('clearToken').addEventListener('click', ()=>{
    localStorage.removeItem('DEV_JWT_TOKEN');
    tokenInput.value = '';
    alert('Token removido');
  });

  // On load: populate token input if present
  try{ tokenInput.value = localStorage.getItem('DEV_JWT_TOKEN') || '' }catch(_){}

  // Quick info: allow opening backend in a new tab for manual checks
  const info = document.createElement('div');
  info.className = 'muted small';
  info.innerHTML = `<p>Backend base: <code>${API_BASE}</code>. Certifique-se que o backend está rodando em http://127.0.0.1:8000</p>`;
  document.querySelector('main').insertBefore(info, document.querySelector('main').firstChild);
})();
