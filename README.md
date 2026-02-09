# 🚀 EasyAgenda - Premium Appointment Booking SaaS

**Production-Ready MVP | FastAPI + React 19 + MongoDB**

## ✨ Features

✅ Multi-tenant architecture
✅ User authentication (Signup/Login)
✅ Admin dashboard
✅ Public booking system
✅ WhatsApp notifications ready
✅ Calendar export (.ics)
✅ PDF invoices
✅ Professional & service management
✅ Availability engine
✅ Trial system (4 days)

## 🏗️ Tech Stack

**Backend:**
- FastAPI (Python)
- MongoDB (Motor)
- JWT Authentication
- Bcrypt password hashing

**Frontend:**
- React 19
- React Router 7
- Tailwind CSS
- Axios

## 🚀 Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --reload --port 8001
```

### Frontend
```bash
cd frontend
yarn install
yarn start
```

## 📦 Environment Variables

Create `backend/.env`:
```
SECRET_KEY=your-secret-key
DATABASE_URL=mongodb://localhost:27017
DB_NAME=easyagenda
CORS_ORIGINS=*
```

## 🎯 Endpoints

- `POST /api/auth/signup` - Create account
- `POST /api/auth/login` - Login
- `GET /api/booking/{slug}` - Public booking page
- `GET /ping` - Health check

## 📱 Demo

1. Access homepage
2. Click "Sign Up"
3. Create your business account
4. Access dashboard

## 🔐 Security

- JWT tokens with expiration
- Bcrypt password hashing
- CORS configuration
- Environment variables for secrets

## 📊 Database Schema

- establishments
- users
- professionals
- services
- appointments
- customers
- invoices
- notifications

## 🎨 Design

Modern, responsive design with:
- Gradient backgrounds
- Clean forms
- Professional UI
- Mobile-friendly

## 📝 License

Proprietary - All rights reserved

## 👨‍💻 Author

EasyAgenda Team
