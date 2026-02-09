import React from 'react';

const STAFF = [
  { id: 'ana', name: 'Ana', role: 'Cabeleireira', meta: '6 atendimentos', status: 'online' },
  { id: 'julia', name: 'Júlia', role: 'Manicure', meta: '4 atendimentos', status: 'online' },
  { id: 'pedro', name: 'Pedro', role: 'Barbeiro', meta: 'fora hoje', status: 'off' }
];

export default function StaffList(){
  return (
    <div className="card">
      <div className="card-title">Funcionários hoje</div>
      <div className="staff-list">
        {STAFF.map(s => (
          <div key={s.id} className="staff-item">
            <div className="staff-avatar">{s.name.charAt(0)}<span className={`staff-status-dot ${s.status==='online'? 'staff-status-online':'staff-status-off'}`}></span></div>
            <div className="staff-main">
              <div className="staff-name">{s.name}</div>
              <div className="staff-role">{s.role}</div>
            </div>
            <div className="staff-meta">{s.meta}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
