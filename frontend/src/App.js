import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './components/Login';
import Upload from './components/Upload';
import Result from './components/Result';
import AdminDashboard from './components/AdminDashboard';
import { apiFetch } from './api';

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
  const [sessionReady, setSessionReady] = useState(false);
  const [user, setUser] = useState(getStoredUser);
  const authenticatedHome = user?.role === 'admin' ? '/admin' : '/upload';

  useEffect(() => {
    let active = true;

    const hydrateSession = async () => {
      try {
        const response = await apiFetch('/api/session');
        const data = await response.json();

        if (!active) {
          return;
        }

        if (response.ok && data?.authenticated && data?.user) {
          localStorage.setItem('user', JSON.stringify(data.user));
          setUser(data.user);
        } else {
          localStorage.removeItem('user');
          setUser(null);
        }
      } catch (error) {
        if (active) {
          localStorage.removeItem('user');
          setUser(null);
        }
      } finally {
        if (active) {
          setSessionReady(true);
        }
      }
    };

    hydrateSession();
    return () => {
      active = false;
    };
  }, []);

  const handleLogin = (nextUser) => {
    if (nextUser === undefined || nextUser === null) {
      localStorage.removeItem('user');
      setUser(null);
    } else {
      localStorage.setItem('user', JSON.stringify(nextUser));
      setUser(nextUser);
    }
  };

  const handleLogout = async () => {
    try {
      await apiFetch('/api/logout', { method: 'POST' });
    } catch (error) {
      // Clear local state even if the request fails.
    }

    localStorage.removeItem('user');
    setUser(null);
  };

  if (!sessionReady) {
    return null;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={user ? <Navigate to={authenticatedHome} /> : <Login onLogin={handleLogin} mode="user" />}
        />
        <Route
          path="/admin/login"
          element={user ? <Navigate to={authenticatedHome} /> : <Login onLogin={handleLogin} mode="admin" />}
        />
        <Route path="/upload" element={user ? <Upload user={user} onLogout={handleLogout} /> : <Navigate to="/login" />} />
        <Route path="/result" element={user ? <Result /> : <Navigate to="/login" />} />
        <Route
          path="/admin"
          element={
            user
              ? user?.role === 'admin'
                ? <AdminDashboard onLogout={handleLogout} />
                : <Navigate to="/upload" />
              : <Navigate to="/admin/login" />
          }
        />
        <Route path="/" element={<Navigate to={user ? authenticatedHome : '/login'} />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
