import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './components/Login';
import Upload from './components/Upload';
import Result from './components/Result';
import AdminDashboard from './components/AdminDashboard';

function getStoredToken() {
  const rawToken = localStorage.getItem('token');

  if (!rawToken || rawToken === 'undefined' || rawToken === 'null') {
    localStorage.removeItem('token');
    return null;
  }

  return rawToken;
}

function getStoredUser() {
  const rawUser = localStorage.getItem('user');

  if (!rawUser || rawUser === 'undefined' || rawUser === 'null') {
    localStorage.removeItem('user');
    return null;
  }

  try {
    return JSON.parse(rawUser);
  } catch (error) {
    localStorage.removeItem('user');
    return null;
  }
}

function App() {
  const [token, setToken] = useState(getStoredToken);
  const [user, setUser] = useState(getStoredUser);

  const handleLogin = (token, user) => {
    if (!token || token === 'undefined' || token === 'null') {
      localStorage.removeItem('token');
      setToken(null);
    } else {
      localStorage.setItem('token', token);
      setToken(token);
    }

    if (user === undefined) {
      localStorage.removeItem('user');
    } else {
      localStorage.setItem('user', JSON.stringify(user));
    }
    setUser(user ?? null);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
  };

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={token ? <Navigate to="/upload" /> : <Login onLogin={handleLogin} />} />
        <Route path="/upload" element={token ? <Upload token={token} onLogout={handleLogout} /> : <Navigate to="/login" />} />
        <Route path="/result" element={token ? <Result token={token} /> : <Navigate to="/login" />} />
        <Route path="/admin" element={token && user?.role === 'admin' ? <AdminDashboard token={token} onLogout={handleLogout} /> : <Navigate to="/login" />} />
        <Route path="/" element={<Navigate to="/login" />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
