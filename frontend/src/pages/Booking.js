import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export default function Booking() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [step, setStep] = useState(1);
  const [selectedService, setSelectedService] = useState(null);
  const [selectedProfessional, setSelectedProfessional] = useState(null);
  const [selectedDate, setSelectedDate] = useState('');
  const [slots, setSlots] = useState([]);
  const [selectedTime, setSelectedTime] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    fetchEstablishment();
  }, [slug]);

  useEffect(() => {
    if (selectedDate && selectedProfessional) {
      fetchAvailability();
    }
  }, [selectedDate, selectedProfessional]);

  const fetchEstablishment = async () => {
    try {
      const response = await axios.get(`${API}/api/booking/${slug}`);
      setData(response.data);
    } catch (error) {
      alert('Business not found');
    }
  };

  const fetchAvailability = async () => {
    try {
      const response = await axios.get(
        `${API}/api/availability?establishment_id=${data.establishment.id}&professional_id=${selectedProfessional.id}&date=${selectedDate}`
      );
      setSlots(response.data.slots || []);
    } catch (error) {
      console.error('Failed to fetch availability:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const startTime = new Date(`${selectedDate}T${selectedTime}:00`);
      const response = await axios.post(
        `${API}/api/booking/book?establishment_id=${data.establishment.id}`,
        {
          service_id: selectedService.id,
          professional_id: selectedProfessional.id,
          start_time: startTime.toISOString(),
          customer_name: customerName,
          customer_phone: customerPhone,
          customer_email: customerEmail
        }
      );
      setSuccess(response.data);
      setStep(5);
    } catch (error) {
      alert(error.response?.data?.detail || 'Booking failed');
    }
  };

  if (!data) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p>Loading...</p>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50">
      <div className="max-w-4xl mx-auto py-12 px-4">
        <div className="bg-white rounded-lg shadow-xl p-8">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-800">{data.establishment.name}</h1>
            <p className="text-gray-600">Book your appointment</p>
          </div>

          <div className="flex justify-center mb-8">
            {[1, 2, 3, 4].map((s) => (
              <div key={s} className="flex items-center">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                  step >= s ? 'bg-blue-600 text-white' : 'bg-gray-300 text-gray-600'
                }`}>
                  {s}
                </div>
                {s < 4 && <div className="w-12 h-1 bg-gray-300"></div>}
              </div>
            ))}
          </div>

          {step === 1 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">Select Service</h2>
              <div className="space-y-3">
                {data.services.map((service) => (
                  <button
                    key={service.id}
                    onClick={() => { setSelectedService(service); setStep(2); }}
                    className="w-full p-4 border-2 rounded-lg hover:border-blue-500 hover:shadow-lg transition text-left"
                  >
                    <h3 className="font-semibold text-lg">{service.name}</h3>
                    <p className="text-sm text-gray-600">{service.duration_minutes} minutes · ${service.price}</p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">Select Professional</h2>
              <div className="space-y-3">
                {data.professionals.map((prof) => (
                  <button
                    key={prof.id}
                    onClick={() => { setSelectedProfessional(prof); setStep(3); }}
                    className="w-full p-4 border-2 rounded-lg hover:border-blue-500 hover:shadow-lg transition text-left"
                  >
                    <h3 className="font-semibold text-lg">{prof.name}</h3>
                    <p className="text-sm text-gray-600">{prof.specialty || 'Professional'}</p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 3 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">Select Date & Time</h2>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                min={new Date().toISOString().split('T')[0]}
                className="w-full p-3 border rounded-lg mb-4"
              />
              {slots.length > 0 && (
                <div className="grid grid-cols-4 gap-2">
                  {slots.filter(s => s.available).map((slot) => (
                    <button
                      key={slot.time}
                      onClick={() => { setSelectedTime(slot.time); setStep(4); }}
                      className="p-3 border-2 rounded-lg hover:bg-blue-500 hover:text-white hover:border-blue-500 transition"
                    >
                      {slot.time}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {step === 4 && (
            <form onSubmit={handleSubmit} className="space-y-4">
              <h2 className="text-xl font-semibold mb-4">Your Information</h2>
              <input
                type="text"
                placeholder="Full Name"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                className="w-full p-3 border rounded-lg"
                required
              />
              <input
                type="tel"
                placeholder="Phone Number"
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                className="w-full p-3 border rounded-lg"
                required
              />
              <input
                type="email"
                placeholder="Email (optional)"
                value={customerEmail}
                onChange={(e) => setCustomerEmail(e.target.value)}
                className="w-full p-3 border rounded-lg"
              />
              <button
                type="submit"
                className="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 font-semibold text-lg"
              >
                Confirm Booking
              </button>
            </form>
          )}

          {step === 5 && success && (
            <div className="text-center">
              <div className="text-6xl mb-4">✅</div>
              <h2 className="text-2xl font-bold text-green-600 mb-4">Booking Confirmed!</h2>
              <p className="text-gray-600 mb-6">Your appointment has been successfully booked.</p>
              <a
                href={`${API}${success.actions.calendar}`}
                className="inline-block bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700"
              >
                📅 Add to Calendar
              </a>
            </div>
          )}

          {step > 1 && step < 5 && (
            <button
              onClick={() => setStep(step - 1)}
              className="mt-6 text-blue-600 hover:underline font-semibold"
            >
              ← Back
            </button>
          )}
        </div>
      </div>
    </div>
  );
}