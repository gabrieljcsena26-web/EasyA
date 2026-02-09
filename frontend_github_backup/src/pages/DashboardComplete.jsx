/* eslint-disable no-unused-vars, react-hooks/exhaustive-deps */
import React, { useEffect, useState } from 'react';
import API from '../utils/api';
import '../styles/dashboard-complete.css';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';
import TopCards from '../components/TopCards';
import MiniCalendar from '../components/MiniCalendar';
import StaffList from '../components/StaffList';
import PendingActions from '../components/PendingActions';
import AgendaTable from '../components/AgendaTable';

export default function DashboardComplete(){
  const [appointments,setAppointments] = useState([]);
  const [loading,setLoading] = useState(false);
  const [config,setConfig] = useState(null);
  // eslint-disable-next-line no-unused-vars
  const [_professionals,setProfessionals] = useState([]);
  const [selectedProfessional,setSelectedProfessional] = useState(null);
  // eslint-disable-next-line no-unused-vars
  const [selectedDate,_setSelectedDate] = useState(() => {
    // default to today
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  });

  useEffect(()=>{
    (async function(){
      setLoading(true);
      try{
        const c = await API.get('/config');
        // normalize professionals coming from backend
        const profs = (c && c.professionals) ? c.professionals : [];
        setConfig(c);
        setProfessionals(profs);
        if(profs && profs.length){
          setSelectedProfessional(prev => prev || profs[0].id);
        }
      }catch(_){ }
      try{
        // initial load will be handled by the other effect when selectedProfessional set
      }catch(e){ }
      finally{ setLoading(false); }
    })();
  },[]);

  // Fetch appointments when professional or date changes
  useEffect(()=>{
    if(!selectedProfessional || !selectedDate) return;
    (async function(){
      setLoading(true);
      try{
        const path = `/appointments?professional_id=${selectedProfessional}&date=${selectedDate}`;
        const res = await API.get(path);
        // Map backend shape to AgendaTable shape
        const mapped = (res || []).map(r => {
          // backend fallback MOCK_APPOINTMENTS uses different keys
          if(r.start_time || r.customer_name){
            return {
              id: r.id,
              date: r.date || r.date,
              time: r.start_time || r.time,
              client: r.customer_name || r.client,
              phone: r.customer_whatsapp || r.phone,
              service: r.service_name || r.service || '',
              prof: (() => {
                if(r.professional_id && config && config.professionals){
                  const p = config.professionals.find(x => x.id === r.professional_id || String(x.id) === String(r.professional_id));
                  return p ? p.name : String(r.professional_id);
                }
                return r.prof || (r.professional_id ? String(r.professional_id) : '');
              })(),
              status: r.status || r.status || 'pendente',
              channel: r.channel || ''
            };
          }
          return r;
        });
        setAppointments(mapped);
      }catch(e){
        setAppointments(generateMockAppointments());
      }finally{ setLoading(false); }
    })();
  },[selectedProfessional, selectedDate, config]);

  function generateMockAppointments(){
    return [
      { id:1, client:'João', phone:'(11) 99999-0000', time:'09:00', status:'confirmed' },
      { id:2, client:'Maria', phone:'(11) 98888-1111', time:'10:30', status:'pending' }
    ];
  }

  return (
    <div className="page">
      <Header />
      <div className="main">
        <Sidebar />
        <div>
          <TopCards appointments={appointments} />

          <div style={{marginTop:12, display:'grid', gridTemplateColumns:'360px minmax(0,1fr)', gap:12}}>
            <div style={{display:'flex',flexDirection:'column',gap:10}}>
              <PendingActions />
              <MiniCalendar />
              <StaffList />
            </div>

            <div>
              <AgendaTable appointments={appointments} loading={loading} config={config} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
