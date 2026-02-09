import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export default function Booking() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [step, setStep] = useState(1);
  const [selectedService, setSelectedService] = useState(null);
  const [selectedProfessional, setSelectedProfessional] = useState(null);
  const [selectedDate, setSelectedDate] = useState('');
  const [selectedTime, setSelectedTime] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');

  useEffect(() => {
    fetchEstablishment();
  }, [slug]);

  const fetchEstablishment = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/booking/${slug}`);
      setData(response.data);
    } catch (error) {
      alert('Business not found');
    }
  };

  const handleServiceSelect = (service) => {
    setSelectedService(service);
    setStep(2);
  };

  const handleProfessionalSelect = (professional) => {
    setSelectedProfessional(professional);
    setStep(3);
  };

  const handleTimeSelect = (time) => {
    setSelectedTime(time);
    setStep(4);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const startTime = new Date(`${selectedDate}T${selectedTime}`);
      const response = await axios.post(
        `${API_URL}/api/booking/${data.establishment.id}/book`,
        {
          service_id: selectedService.id,
          professional_id: selectedProfessional.id,
          start_time: startTime.toISOString(),
          customer_name: customerName,
          customer_phone: customerPhone,
          customer_email: customerEmail,
          customer_language: 'en'
        }
      );
      alert('Appointment confirmed! Check your email.');
      window.location.reload();
    } catch (error) {
      alert(error.response?.data?.detail?.message || 'Booking failed');
    }
  };

  if (!data) return <div className="flex items-center justify-center min-h-screen">Loading...</div>;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50">
      <div className="max-w-4xl mx-auto py-12 px-4">
        <div className="bg-white rounded-lg shadow-xl p-8">
          <h1 className="text-3xl font-bold text-center mb-2">{data.establishment.name}</h1>
          <p className="text-center text-gray-600 mb-8">Book your appointment</p>

          {step === 1 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">Select Service</h2>
              <div className="grid gap-4">
                {data.services.map((service) => (
                  <button
                    key={service.id}
                    onClick={() => handleServiceSelect(service)}
                    className="p-4 border rounded-lg hover:border-blue-500 hover:shadow text-left"
                  >
                    <h3 className="font-semibold">{service.name}</h3>
                    <p className="text-sm text-gray-600">{service.duration_minutes} min - ${service.price}</p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">Select Professional</h2>
              <div className="grid gap-4">
                {data.professionals.map((prof) => (
                  <button
                    key={prof.id}
                    onClick={() => handleProfessionalSelect(prof)}
                    className="p-4 border rounded-lg hover:border-blue-500 hover:shadow text-left"
                  >
                    <h3 className="font-semibold">{prof.name}</h3>
                    <p className="text-sm text-gray-600">{prof.specialty}</p>
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
                className="w-full p-2 border rounded mb-4"
              />
              <div className="grid grid-cols-4 gap-2">
                {['09:00', '10:00', '11:00', '14:00', '15:00', '16:00', '17:00'].map((time) => (
                  <button
                    key={time}
                    onClick={() => handleTimeSelect(time)}
                    className="p-2 border rounded hover:bg-blue-500 hover:text-white"
                  >
                    {time}
                  </button>
                ))}
              </div>
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
                className="w-full p-2 border rounded"
                required
              />
              <input
                type="tel"
                placeholder="Phone"
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                className="w-full p-2 border rounded"
                required
              />
              <input
                type="email"
                placeholder="Email (optional)"
                value={customerEmail}
                onChange={(e) => setCustomerEmail(e.target.value)}
                className="w-full p-2 border rounded"
              />
              <button
                type="submit"
                className="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700"
              >
                Confirm Booking
              </button>
            </form>
          )}

          {step > 1 && (
            <button
              onClick={() => setStep(step - 1)}
              className="mt-4 text-blue-600 hover:underline"
            >
              ← Back
            </button>
          )}
        </div>
      </div>
    </div>
  );
}