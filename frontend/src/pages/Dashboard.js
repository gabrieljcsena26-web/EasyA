import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export default function Dashboard() {
  const [overview, setOverview] = useState(null);
  const [activeTab, setActiveTab] = useState('today');
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const token = localStorage.getItem('token');

  useEffect(() => {
    fetchOverview();
  }, []);

  const fetchOverview = async () => {
    try {
      const response = await axios.get(
        `${API_URL}/api/dashboard/${user.establishment_id}/overview`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setOverview(response.data);
    } catch (error) {
      console.error('Failed to fetch overview:', error);
    }
  };

  const logout = () => {
    localStorage.clear();
    window.location.href = '/login';
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-blue-600">EasyAgenda</h1>
          <div className="flex items-center space-x-4">
            <span className="text-gray-700">{user.full_name}</span>
            <button onClick={logout} className="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600">
              Logout
            </button>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-gray-500 text-sm font-semibold">Today's Appointments</h3>
            <p className="text-3xl font-bold text-blue-600">{overview?.today?.count || 0}</p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-gray-500 text-sm font-semibold">This Week</h3>
            <p className="text-3xl font-bold text-green-600">{overview?.week_upcoming || 0}</p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-gray-500 text-sm font-semibold">Total Customers</h3>
            <p className="text-3xl font-bold text-purple-600">{overview?.total_customers || 0}</p>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4">Today's Schedule</h2>
          {overview?.today?.appointments?.length > 0 ? (
            <div className="space-y-3">
              {overview.today.appointments.map((apt) => (
                <div key={apt.id} className="border-l-4 border-blue-500 pl-4 py-2">
                  <div className="flex justify-between">
                    <div>
                      <p className="font-semibold">{apt.time} - {apt.customer_name}</p>
                      <p className="text-sm text-gray-600">{apt.customer_phone}</p>
                    </div>
                    <span className="text-sm text-green-600 font-semibold">{apt.status}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500">No appointments today</p>
          )}
        </div>
      </div>
    </div>
  );
}