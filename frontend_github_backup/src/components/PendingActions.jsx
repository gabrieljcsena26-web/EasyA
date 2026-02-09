import React, { useEffect, useState } from 'react';
import API from '../utils/api';

function readPending(){
  try{ const raw = localStorage.getItem('ea_pending_actions'); return raw ? JSON.parse(raw) : []; }catch(_){ return []; }
}

export default function PendingActions(){
  const [actions, setActions] = useState(() => readPending());

  useEffect(()=>{
    const onStorage = () => setActions(readPending());
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  },[]);

  function persist(arr){
    try{ localStorage.setItem('ea_pending_actions', JSON.stringify(arr)); }catch(_){ }
    setActions(arr);
  }

  async function retryAction(a, idx){
    try{
      let res;
      const method = (a.method || (a.type ? a.type.toUpperCase() : '')).toUpperCase();
      if(method === 'POST') res = await API.post(a.path, a.payload || a.body || {});
      else if(method === 'PUT') res = await API.put(a.path, a.payload || a.body || {});
      else if(method === 'DELETE') res = await API.delete(a.path);
      else throw new Error('Unknown method');
      // on success remove
      const copy = readPending();
      copy.splice(idx,1);
      persist(copy);
      return res;
    }catch(e){
      console.warn('Retry failed', e);
      throw e;
    }
  }

  async function retryAll(){
    const list = readPending();
    for(let i=0;i<list.length;i++){
      try{ await retryAction(list[i], 0); }catch(_){ /* keep going */ }
    }
  }

  function removeAt(i){
    const copy = readPending();
    copy.splice(i,1);
    persist(copy);
  }

  if(!actions || !actions.length) return (
    <div style={{padding:10,border:'1px solid #eee',borderRadius:6,background:'#fafafa'}}>
      <strong>Pending Actions</strong>
      <div style={{marginTop:8,color:'#666'}}>Nenhuma ação pendente</div>
    </div>
  );

  return (
    <div style={{padding:10,border:'1px solid #eee',borderRadius:6,background:'#fff'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
        <strong>Pending Actions</strong>
        <div>
          <button onClick={retryAll} style={{marginRight:8}}>Retry All</button>
        </div>
      </div>
      <div style={{marginTop:8}}>
        {actions.map((a,idx)=> (
          <div key={idx} style={{padding:8,borderBottom:'1px solid #eee',display:'flex',justifyContent:'space-between',gap:8}}>
            <div style={{flex:1}}>
              <div style={{fontSize:13}}><strong>{(a.method || (a.type && a.type.toUpperCase()) || '')}</strong> {a.path}</div>
              <div style={{fontSize:12,color:'#444'}}>{a.payload ? JSON.stringify(a.payload) : (a.body ? JSON.stringify(a.body) : '')}</div>
            </div>
            <div style={{display:'flex',flexDirection:'column',gap:6}}>
              <button onClick={() => retryAction(a, idx)}>Retry</button>
              <button onClick={() => removeAt(idx)}>Remove</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
