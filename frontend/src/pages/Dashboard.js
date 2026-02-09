import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export default function Dashboard() {
  const [overview, setOverview] = useState(null);
  const [professionals, setProfessionals] = useState([]);
  const [services, setServices] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');
  const [newProfName, setNewProfName] = useState('');
  const [newServiceName, setNewServiceName] = useState('');
  const [newServiceDuration, setNewServiceDuration] = useState(30);
  const [newServicePrice, setNewServicePrice] = useState(0);
  
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const token = localStorage.getItem('token');
  const estId = user.establishment_id;
  
  console.log('Dashboard loaded. User:', user);
  console.log('Token:', token ? 'Present' : 'Missing');
  console.log('Establishment ID:', estId);

  useEffect(() => {
    if (estId) {
      loadData();
    }
  }, [estId]);

  const loadData = async () => {
    try {
      const [overviewRes, profsRes, svcsRes, custsRes] = await Promise.all([
        axios.get(`${API}/api/dashboard/overview?establishment_id=${estId}`),
        axios.get(`${API}/api/admin/professionals?establishment_id=${estId}`),
        axios.get(`${API}/api/admin/services?establishment_id=${estId}`),
        axios.get(`${API}/api/dashboard/customers?establishment_id=${estId}`)
      ]);
      setOverview(overviewRes.data);
      setProfessionals(profsRes.data.professionals);
      setServices(svcsRes.data.services);
      setCustomers(custsRes.data.customers);
    } catch (error) {
      console.error('Failed to load data:', error);
    }
  };

  const addProfessional = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/api/admin/professionals?establishment_id=${estId}`, {
        name: newProfName,
        specialty: 'General'
      });
      setNewProfName('');
      loadData();
    } catch (error) {
      alert('Failed to add professional');
    }
  };

  const addService = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/api/admin/services?establishment_id=${estId}`, {
        name: newServiceName,
        duration_minutes: parseInt(newServiceDuration),
        price: parseFloat(newServicePrice)
      });
      setNewServiceName('');
      setNewServiceDuration(30);
      setNewServicePrice(0);
      loadData();
    } catch (error) {
      alert('Failed to add service');
    }
  };

  const logout = () => {
    localStorage.clear();
    window.location.href = '/login';
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-blue-600">EasyAgenda</h1>
          <div className="flex items-center space-x-4">
            <span className="text-gray-700">{user.full_name}</span>
            <span className="text-sm text-gray-500">({user.establishment_slug})</span>
            <button onClick={logout} className="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600 text-sm">
              Logout
            </button>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="flex space-x-2 mb-6 border-b">
          {['overview', 'professionals', 'services', 'customers'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 font-semibold capitalize ${
                activeTab === tab
                  ? 'text-blue-600 border-b-2 border-blue-600'
                  : 'text-gray-600 hover:text-blue-600'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {activeTab === 'overview' && overview && (
          <div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-sm text-gray-500 font-semibold">Today</h3>
                <p className="text-3xl font-bold text-blue-600">{overview.today.count}</p>
              </div>
              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-sm text-gray-500 font-semibold">This Week</h3>
                <p className="text-3xl font-bold text-green-600">{overview.week_upcoming}</p>
              </div>
              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-sm text-gray-500 font-semibold">This Month</h3>
                <p className="text-3xl font-bold text-purple-600">{overview.month_appointments}</p>
              </div>
              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-sm text-gray-500 font-semibold">Customers</h3>
                <p className="text-3xl font-bold text-orange-600">{overview.total_customers}</p>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-bold mb-4">Today's Schedule</h2>
              {overview.today.appointments.length > 0 ? (
                <div className="space-y-3">
                  {overview.today.appointments.map((apt) => (
                    <div key={apt.id} className="border-l-4 border-blue-500 pl-4 py-3 bg-blue-50 rounded">
                      <div className="flex justify-between items-center">
                        <div>
                          <p className="font-semibold text-lg">{new Date(apt.start_time).toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit'})} - {apt.customer_name}</p>
                          <p className="text-sm text-gray-600">{apt.customer_phone}</p>
                        </div>
                        <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-semibold">
                          {apt.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-center py-8">No appointments today</p>
              )}
            </div>
          </div>
        )}

        {activeTab === 'professionals' && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-bold mb-4">Professionals / Workers</h2>
            
            <form onSubmit={addProfessional} className="mb-6 p-4 bg-blue-50 rounded-lg">
              <h3 className="font-semibold mb-3">Add New Professional</h3>
              <div className="flex gap-3">
                <input
                  type="text"
                  placeholder="Name"
                  value={newProfName}
                  onChange={(e) => setNewProfName(e.target.value)}
                  className="flex-1 px-4 py-2 border rounded-lg"
                  required
                />
                <button type="submit" className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700">
                  Add
                </button>
              </div>
            </form>

            <div className="space-y-3">
              {professionals.map((prof) => (
                <div key={prof.id} className="border rounded-lg p-4 hover:shadow-md transition">
                  <h3 className="font-semibold text-lg">{prof.name}</h3>
                  <p className="text-sm text-gray-600">{prof.specialty || 'No specialty'}</p>
                  {prof.email && <p className="text-sm text-gray-600">{prof.email}</p>}
                  {prof.phone && <p className="text-sm text-gray-600">{prof.phone}</p>}
                </div>
              ))}
              {professionals.length === 0 && (
                <p className="text-gray-500 text-center py-8">No professionals yet. Add one above!</p>
              )}
            </div>
          </div>
        )}

        {activeTab === 'services' && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-bold mb-4">Services</h2>
            
            <form onSubmit={addService} className="mb-6 p-4 bg-green-50 rounded-lg">
              <h3 className="font-semibold mb-3">Add New Service</h3>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <input
                  type="text"
                  placeholder="Service Name"
                  value={newServiceName}
                  onChange={(e) => setNewServiceName(e.target.value)}
                  className="px-4 py-2 border rounded-lg"
                  required
                />
                <input
                  type="number"
                  placeholder="Duration (min)"
                  value={newServiceDuration}
                  onChange={(e) => setNewServiceDuration(e.target.value)}
                  className="px-4 py-2 border rounded-lg"
                  required
                />
                <input
                  type="number"
                  step="0.01"
                  placeholder="Price"
                  value={newServicePrice}
                  onChange={(e) => setNewServicePrice(e.target.value)}
                  className="px-4 py-2 border rounded-lg"
                  required
                />
                <button type="submit" className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700">
                  Add
                </button>
              </div>
            </form>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {services.map((svc) => (
                <div key={svc.id} className="border rounded-lg p-4 hover:shadow-md transition">
                  <h3 className="font-semibold text-lg">{svc.name}</h3>
                  <div className="mt-2 space-y-1">
                    <p className="text-sm text-gray-600">⏱️ Duration: {svc.duration_minutes} minutes</p>
                    <p className="text-sm text-gray-600">💰 Price: ${svc.price}</p>
                    {svc.description && <p className="text-sm text-gray-600">{svc.description}</p>}
                  </div>
                </div>
              ))}
              {services.length === 0 && (
                <p className="text-gray-500 text-center py-8 col-span-2">No services yet. Add one above!</p>
              )}
            </div>
          </div>
        )}

        {activeTab === 'customers' && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-bold mb-4">Customers</h2>
            
            <div className="mb-4">
              <input
                type="text"
                placeholder="Search customers..."
                className="w-full px-4 py-2 border rounded-lg"
                onChange={(e) => {
                  // TODO: Implement search
                }}
              />
            </div>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Name</th>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Phone</th>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Email</th>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Appointments</th>
                  </tr>
                </thead>
                <tbody>
                  {customers.map((customer) => (
                    <tr key={customer.id} className="border-t hover:bg-gray-50">
                      <td className="px-4 py-3">{customer.name}</td>
                      <td className="px-4 py-3">{customer.phone}</td>
                      <td className="px-4 py-3">{customer.email || '-'}</td>
                      <td className="px-4 py-3">{customer.appointment_count || 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {customers.length === 0 && (
                <p className="text-gray-500 text-center py-8">No customers yet</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}