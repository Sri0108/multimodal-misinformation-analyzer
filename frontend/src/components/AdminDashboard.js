import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { buildApiUrl } from '../api';

function AdminDashboard({ token, onLogout }) {
  const [inputs, setInputs] = useState([]);
  const [reports, setReports] = useState([]);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const inputsRes = await axios.get(buildApiUrl('/api/admin/inputs'), {
        headers: { Authorization: `Bearer ${token}` }
      });
      const reportsRes = await axios.get(buildApiUrl('/api/admin/reports'), {
        headers: { Authorization: `Bearer ${token}` }
      });
      setInputs(inputsRes.data);
      setReports(reportsRes.data);
    } catch (err) {
      alert('Failed to fetch admin data');
    }
  };

  return (
    <div className="container mt-4">
      <nav className="navbar navbar-light bg-light mb-4">
        <div className="container-fluid">
          <span className="navbar-brand">Admin Dashboard</span>
          <button className="btn btn-outline-danger" onClick={onLogout}>Logout</button>
        </div>
      </nav>
      
      <div className="row">
        <div className="col-md-6">
          <div className="card">
            <div className="card-body">
              <h4>Recent Inputs ({inputs.length})</h4>
              <table className="table table-sm">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>User ID</th>
                    <th>Type</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {inputs.slice(0, 10).map(input => (
                    <tr key={input.id}>
                      <td>{input.id}</td>
                      <td>{input.user_id}</td>
                      <td>{input.content_type}</td>
                      <td>{new Date(input.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
        
        <div className="col-md-6">
          <div className="card">
            <div className="card-body">
              <h4>Recent Reports ({reports.length})</h4>
              <table className="table table-sm">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Prediction</th>
                    <th>Confidence</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.slice(0, 10).map(report => (
                    <tr key={report.id}>
                      <td>{report.id}</td>
                      <td><span className={`badge bg-${report.prediction === 'Fake' ? 'danger' : report.prediction === 'Real' ? 'success' : 'warning'}`}>{report.prediction}</span></td>
                      <td>{(report.confidence * 100).toFixed(1)}%</td>
                      <td>{new Date(report.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminDashboard;
