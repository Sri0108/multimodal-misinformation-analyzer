import React, { useState } from 'react';
import axios from 'axios';
import { buildApiUrl } from '../api';

function Login({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const url = isRegister ? buildApiUrl('/api/register') : buildApiUrl('/api/login');
      const data = isRegister ? { email, password, username } : { email, password };
      const response = await axios.post(url, data);
      
      if (isRegister) {
        setIsRegister(false);
        alert('Registration successful! Please login.');
      } else {
        if (!response.data.token || !response.data.user) {
          throw new Error('Login response is missing token or user data');
        }
        onLogin(response.data.token, response.data.user);
      }
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'An error occurred');
    }
  };

  return (
    <div className="container mt-5">
      <div className="row justify-content-center">
        <div className="col-md-6">
          <div className="card">
            <div className="card-body">
              <h2 className="card-title text-center">{isRegister ? 'Register' : 'Login'}</h2>
              {error && <div className="alert alert-danger">{error}</div>}
              <form onSubmit={handleSubmit}>
                {isRegister && (
                  <div className="mb-3">
                    <label className="form-label">Username</label>
                    <input type="text" className="form-control" value={username} onChange={(e) => setUsername(e.target.value)} required />
                  </div>
                )}
                <div className="mb-3">
                  <label className="form-label">Email</label>
                  <input type="email" className="form-control" value={email} onChange={(e) => setEmail(e.target.value)} required />
                </div>
                <div className="mb-3">
                  <label className="form-label">Password</label>
                  <input type="password" className="form-control" value={password} onChange={(e) => setPassword(e.target.value)} required />
                </div>
                <button type="submit" className="btn btn-primary w-100">{isRegister ? 'Register' : 'Login'}</button>
              </form>
              <div className="text-center mt-3">
                <button className="btn btn-link" onClick={() => setIsRegister(!isRegister)}>
                  {isRegister ? 'Already have an account? Login' : "Don't have an account? Register"}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Login;
