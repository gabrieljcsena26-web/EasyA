import React, { useEffect, useState } from 'react';

function statusClass(s){
  if(!s) return '';
  const m = s.toLowerCase();
  if(m.includes('confirm')) return 'st-confirmed';
  if(m.includes('pend') || m.includes('aguard')) return 'st-pending';
  if(m.includes('cancel') || m.includes('não') || m.includes('no-show') || m.includes('noshow')) return 'st-cancel';
  if(m.includes('criado') || m.includes('created')) return 'st-created';
  return '';
}

export default function AgendaTable({ appointments = [], loading = false, config = null }){
  const [rows, setRows] = useState(appointments || []);

  useEffect(()=>{
    setRows(appointments || []);
  },[appointments]);

  if(loading) return <div>Carregando agenda...</div>;

  return (
    <div className="agenda-card">
      <div className="agenda-header">
        <div>
          <div className="agenda-title-main">Agenda</div>
          <div className="agenda-substatus">Agenda do dia · <span className="state-tag">exemplo</span></div>
        </div>
      </div>
      <div className="agenda-table-wrapper">
        <div className="agenda-horizontal-wrapper">
          <table className="agenda">
            <thead>
              <tr>
                <th>Hora</th>
                <th>Cliente</th>
                <th>Serviço</th>
                <th>Profissional</th>
                <th>Status</th>
                <th>Canal</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} data-date={r.date} data-status={r.status} data-prof={r.prof}>
                  <td style={{width:90}}>{r.time}</td>
                  <td><div className="client-cell"><span className="client-name">{r.client}</span><span className="client-phone">{r.phone}</span></div></td>
                  <td style={{minWidth:160}}>{r.service}</td>
                  <td style={{width:120}}>{r.prof}</td>
                  <td style={{width:140}}><span className={`status-pill-table ${statusClass(r.status)}`}>{r.status}</span></td>
                  <td style={{width:120}}><span className="channel-link">{r.channel}</span></td>
                  <td className="action-cell" style={{width:120}}>
                    <div style={{display:'flex',gap:8}}>
                      <button className="btn-action" title="Confirmar">✓</button>
                      <button className="btn-action" title="Histórico">ℹ</button>
                      <button className="btn-action" title="Cancelar">✕</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

