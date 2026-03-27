import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { buildApiUrl } from '../api';

function formatDate(value) {
  if (!value) return 'N/A';
  try {
    return new Date(value).toLocaleString();
  } catch (error) {
    return value;
  }
}

function predictionTone(label) {
  const lowered = (label || '').toLowerCase();
  if (lowered.includes('fake')) return 'high';
  if (lowered.includes('real')) return 'low';
  return 'medium';
}

function AdminDashboard({ token, onLogout }) {
  const navigate = useNavigate();
  const [overview, setOverview] = useState(null);
  const [inputs, setInputs] = useState([]);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;

    const loadAdminData = async () => {
      setLoading(true);
      setError('');

      try {
        const [overviewRes, inputsRes, reportsRes] = await Promise.all([
          fetch(buildApiUrl('/api/admin/overview'), { headers: { Authorization: `Bearer ${token}` } }),
          fetch(buildApiUrl('/api/admin/inputs'), { headers: { Authorization: `Bearer ${token}` } }),
          fetch(buildApiUrl('/api/admin/reports'), { headers: { Authorization: `Bearer ${token}` } }),
        ]);

        const [overviewData, inputsData, reportsData] = await Promise.all([
          overviewRes.json(),
          inputsRes.json(),
          reportsRes.json(),
        ]);

        if (!overviewRes.ok) throw new Error(overviewData.error || 'Failed to load admin overview');
        if (!inputsRes.ok) throw new Error(inputsData.error || 'Failed to load admin inputs');
        if (!reportsRes.ok) throw new Error(reportsData.error || 'Failed to load admin reports');

        if (mounted) {
          setOverview(overviewData);
          setInputs(Array.isArray(inputsData) ? inputsData : []);
          setReports(Array.isArray(reportsData) ? reportsData : []);
        }
      } catch (loadError) {
        if (mounted) {
          setError(loadError.message || 'Unable to load admin dashboard.');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    loadAdminData();
    return () => {
      mounted = false;
    };
  }, [token]);

  const stats = overview?.stats || {};
  const contentMix = overview?.content_mix || [];
  const predictionMix = overview?.prediction_mix || [];
  const recentUsers = overview?.recent_users || [];

  const statCards = [
    {
      title: 'Total Users',
      value: stats.total_users || 0,
      caption: `${stats.admin_users || 0} admin accounts`,
      tone: 'accent-warm',
    },
    {
      title: 'Analyses Logged',
      value: stats.total_inputs || 0,
      caption: `${stats.today_inputs || 0} created today`,
      tone: 'accent-cool',
    },
    {
      title: 'Reports Generated',
      value: stats.total_reports || 0,
      caption: `${Math.round((stats.average_confidence || 0) * 100)}% avg confidence`,
      tone: 'accent-danger',
    },
  ];

  const topContentTypes = useMemo(() => contentMix.slice(0, 4), [contentMix]);
  const topPredictions = useMemo(() => predictionMix.slice(0, 4), [predictionMix]);

  if (loading) {
    return (
      <div className="app-shell workspace-pro admin-shell">
        <div className="ambient ambient-one" />
        <div className="ambient ambient-two" />
        <div className="page-container">
          <section className="card dashboard-card primary-panel admin-loading-card">
            <p className="eyebrow">Admin Workspace</p>
            <h3>Loading dashboard data...</h3>
          </section>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app-shell workspace-pro admin-shell">
        <div className="ambient ambient-one" />
        <div className="ambient ambient-two" />
        <div className="page-container">
          <section className="card dashboard-card primary-panel admin-loading-card">
            <p className="eyebrow">Admin Workspace</p>
            <h3>Unable to load dashboard</h3>
            <p className="admin-empty-copy">{error}</p>
            <div className="action-row">
              <button className="secondary-button" onClick={() => window.location.reload()}>Retry</button>
              <button className="ghost-button" onClick={() => navigate('/upload')}>Back To Analyzer</button>
            </div>
          </section>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell workspace-pro admin-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <div className="page-container">
        <header className="topbar">
          <div className="brand-lockup">
            <span className="brand-mark">MM</span>
            <div>
              <p className="eyebrow">Admin Workspace</p>
              <h1>multimodal misinformation analyzer</h1>
            </div>
          </div>
          <div className="topbar-actions">
            <button className="ghost-button" onClick={() => navigate('/upload')}>Open Analyzer</button>
            <button className="ghost-button" onClick={onLogout}>Logout</button>
          </div>
        </header>

        <section className="hero-panel admin-hero-panel">
          <div className="hero-copy">
            <p className="eyebrow">Admin Dashboard</p>
            <h2>Monitor usage, review outputs, and track system activity.</h2>
            <p className="hero-lead">
              This workspace gives admins a quick operational view of registered users, analysis traffic,
              generated reports, and recent verification outcomes across the platform.
            </p>
          </div>

          <div className="hero-metrics">
            {statCards.map((card) => (
              <div key={card.title} className={`metric-card ${card.tone}`}>
                <span className="metric-value">{card.value}</span>
                <span className="metric-label">{card.title}</span>
                <small>{card.caption}</small>
              </div>
            ))}
          </div>
        </section>

        <div className="main-grid admin-main-grid">
          <div className="left-section">
            <section className="card dashboard-card primary-panel admin-table-card">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Recent Inputs</p>
                  <h3>Latest analysis submissions</h3>
                </div>
                <span className="panel-tag">{inputs.length} total</span>
              </div>

              {inputs.length === 0 ? (
                <p className="admin-empty-copy">No analysis inputs have been recorded yet.</p>
              ) : (
                <div className="admin-table-wrap">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>User</th>
                        <th>Type</th>
                        <th>Prediction</th>
                        <th>Report</th>
                        <th>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {inputs.slice(0, 12).map((input) => (
                        <tr key={input.id}>
                          <td>#{input.id}</td>
                          <td>
                            <strong>{input.username || `User ${input.user_id}`}</strong>
                            <span>{input.email || 'No email'}</span>
                          </td>
                          <td className="admin-cell-cap">{input.content_type}</td>
                          <td>
                            <span className={`news-risk-pill ${predictionTone(input.prediction)}`}>
                              {input.prediction || 'Pending'}
                            </span>
                          </td>
                          <td>{input.has_report ? 'Available' : 'Not generated'}</td>
                          <td>{formatDate(input.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <div className="bottom-section admin-bottom-section">
              <article className="card dashboard-card info-card">
                <div className="info-card-header">
                  <div className="info-icon-badge" aria-hidden="true">US</div>
                  <div>
                    <p className="eyebrow">Recent Users</p>
                    <h3>Latest registered accounts</h3>
                  </div>
                </div>

                <div className="admin-user-list">
                  {recentUsers.map((user) => (
                    <div key={user.id} className="admin-user-item">
                      <div>
                        <strong>{user.username || user.email || `User ${user.id}`}</strong>
                        <span>{user.email || 'No email'}</span>
                      </div>
                      <div className="admin-user-meta">
                        <span className={`news-risk-pill ${user.role === 'admin' ? 'medium' : 'low'}`}>{user.role}</span>
                        <small>{formatDate(user.created_at)}</small>
                      </div>
                    </div>
                  ))}
                </div>
              </article>

              <article className="card dashboard-card info-card">
                <div className="info-card-header">
                  <div className="info-icon-badge workflow-badge" aria-hidden="true">MX</div>
                  <div>
                    <p className="eyebrow">Mix Snapshot</p>
                    <h3>What the system is processing</h3>
                  </div>
                </div>

                <div className="admin-mix-grid">
                  <div className="admin-mix-block">
                    <span className="snapshot-label">Content Types</span>
                    {topContentTypes.map((item) => (
                      <div key={item.label} className="admin-mix-row">
                        <span>{item.label}</span>
                        <strong>{item.count}</strong>
                      </div>
                    ))}
                  </div>
                  <div className="admin-mix-block">
                    <span className="snapshot-label">Predictions</span>
                    {topPredictions.map((item) => (
                      <div key={item.label} className="admin-mix-row">
                        <span>{item.label}</span>
                        <strong>{item.count}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              </article>
            </div>
          </div>

          <div className="right-section">
            <section className="card dashboard-card sidebar-card admin-table-card">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Recent Reports</p>
                  <h3>Generated report activity</h3>
                </div>
                <span className="panel-tag">{reports.length} total</span>
              </div>

              {reports.length === 0 ? (
                <p className="admin-empty-copy">No PDF reports have been generated yet.</p>
              ) : (
                <div className="admin-report-list">
                  {reports.slice(0, 10).map((report) => (
                    <div key={report.id} className="admin-report-card">
                      <div className="admin-report-head">
                        <strong>Report #{report.id}</strong>
                        <span className={`news-risk-pill ${predictionTone(report.prediction)}`}>{report.prediction}</span>
                      </div>
                      <p className="admin-report-meta">
                        Input #{report.input_id} • {report.content_type || 'unknown'} • {report.username || `User ${report.user_id || 'N/A'}`}
                      </p>
                      <div className="admin-report-stats">
                        <span>Confidence: {Math.round((report.confidence || 0) * 100)}%</span>
                        <span>Manipulation: {((report.manipulation_score || 0) * 100).toFixed(0)}%</span>
                      </div>
                      <small>{formatDate(report.created_at)}</small>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="card dashboard-card sidebar-card">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Admin Guidance</p>
                  <h3>Operational next checks</h3>
                </div>
              </div>

              <ul className="workflow-steps">
                <li>Review unusual spikes in fake verdicts, uncertain results, or missing reports.</li>
                <li>Check whether admin-only access is limited to verified admin accounts.</li>
                <li>Use recent users and inputs to spot suspicious activity or heavy misuse patterns.</li>
              </ul>

              <div className="note-box">
                <span className="note-title">Admin Notes</span>
                <p className="note-body">
                  This dashboard reads live data from protected admin endpoints. If access fails, verify the logged-in account still has the admin role.
                </p>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminDashboard;
