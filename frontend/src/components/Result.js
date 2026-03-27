import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { buildApiUrl } from '../api';

function readStoredAnalysis() {
  const raw = localStorage.getItem('latestAnalysis');

  if (!raw || raw === 'undefined' || raw === 'null') {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch (error) {
    localStorage.removeItem('latestAnalysis');
    return null;
  }
}

function Result({ token }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState(location.state || readStoredAnalysis());
  const [summary, setSummary] = useState('');
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);

  useEffect(() => {
    if (location.state) {
      localStorage.setItem('latestAnalysis', JSON.stringify(location.state));
      setAnalysis(location.state);
    }
  }, [location.state]);

  const result = analysis?.result;
  const verificationLabel = result?.verification_mode === 'trusted_source_first'
    ? 'Trusted source first'
    : 'Classifier fallback';
  const explanationItems = Array.isArray(result?.explanation)
    ? result.explanation
    : result?.explanation
      ? [result.explanation]
      : [];
  const reasonItems = Array.isArray(result?.reason_summary)
    ? result.reason_summary
    : result?.reason_summary
      ? [result.reason_summary]
      : [];

  const verdictTone = useMemo(() => {
    if (!result?.prediction) {
      return 'warning';
    }

    const lowered = result.prediction.toLowerCase();
    if (lowered.includes('fake')) {
      return 'danger';
    }
    if (lowered.includes('real')) {
      return 'success';
    }
    return 'warning';
  }, [result?.prediction]);

  const graphItems = useMemo(() => {
    if (!result) {
      return [];
    }

    return [
      {
        label: 'Confidence',
        value: Math.round((result.confidence || 0) * 100),
        tone: 'warning',
      },
      {
        label: 'Real score',
        value: Math.round(((result.scores?.real_score) || 0) * 100),
        tone: 'success',
      },
      {
        label: 'Fake score',
        value: Math.round(((result.scores?.fake_score) || 0) * 100),
        tone: 'danger',
      },
      {
        label: 'Trusted source coverage',
        value: Math.min(100, (result.source_evidence_count || 0) * 20),
        tone: 'cool',
      },
    ];
  }, [result]);

  if (!analysis || !result) {
    return (
      <div className="app-shell workspace-pro result-shell">
        <div className="ambient ambient-one" />
        <div className="ambient ambient-two" />
        <section className="panel empty-panel">
          <h2>No analysis is available yet.</h2>
          <p>Run a fresh detection to see fake-or-not results, trusted source URLs, graphs, summary, and optional report generation.</p>
          <button className="primary-button" onClick={() => navigate('/upload')}>Go To Analyzer</button>
        </section>
      </div>
    );
  }

  const handleSummary = async () => {
    setSummaryLoading(true);

    try {
      if (!analysis.inputId) {
        throw new Error('Summary is only available for a saved analysis');
      }

      const response = await fetch(buildApiUrl(`/api/input/${analysis.inputId}/summary`), {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Failed to generate summary');
      }

      setSummary(data.summary);
      if (data.extracted_text) {
        setAnalysis((current) => {
          if (!current?.result) {
            return current;
          }

          const next = {
            ...current,
            result: {
              ...current.result,
              extracted_text: data.extracted_text,
            },
          };
          localStorage.setItem('latestAnalysis', JSON.stringify(next));
          return next;
        });
      }
    } catch (error) {
      alert(error.message);
    } finally {
      setSummaryLoading(false);
    }
  };

  const handleGenerateReport = async () => {
    setReportLoading(true);

    try {
      if (!analysis.inputId) {
        throw new Error('Detailed report is only available for a saved analysis');
      }

      const response = await fetch(buildApiUrl(`/api/input/${analysis.inputId}/report`), {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Failed to generate report');
      }

      const fileResponse = await fetch(buildApiUrl(data.report_url), {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      if (!fileResponse.ok) {
        throw new Error('Report generated but download failed');
      }

      const blob = await fileResponse.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.setAttribute('download', `report_${data.report_id}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      alert(error.message);
    } finally {
      setReportLoading(false);
    }
  };

  return (
    <div className="app-shell workspace-pro result-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <div className="page-container">
        <header className="topbar">
          <div className="brand-lockup">
            <span className="brand-mark">MM</span>
            <div>
              <p className="eyebrow">Result Workspace</p>
              <h1>multimodal misinformation analyzer</h1>
            </div>
          </div>
          <div className="topbar-actions">
            <span className="status-pill result-status-pill">{result.prediction}</span>
            <button className="ghost-button" onClick={() => navigate('/upload')}>Analyze Another Item</button>
          </div>
        </header>

        <section className="hero-panel result-hero-panel">
          <div className="hero-copy">
            <p className="eyebrow">Detection Result</p>
            <h2>{result.prediction}</h2>
            <p className="hero-lead">
              Verification mode: {verificationLabel}. Confidence is {Math.round((result.confidence || 0) * 100)}%.
              Review the reasoning, trusted sources, extracted context, and optional summary/report from one workspace.
            </p>
          </div>

          <div className="hero-metrics">
            <div className="metric-card accent-warm">
              <span className="metric-value">{Math.round((result.confidence || 0) * 100)}%</span>
              <span className="metric-label">Confidence</span>
              <small>Model confidence after verification fusion.</small>
            </div>
            <div className="metric-card accent-cool">
              <span className="metric-value">{result.source_evidence_count || 0}</span>
              <span className="metric-label">Trusted URLs Found</span>
              <small>Supporting source links identified for this input.</small>
            </div>
            <div className="metric-card accent-danger">
              <span className="metric-value">{result.claim_category || 'general'}</span>
              <span className="metric-label">Claim Type</span>
              <small>Claim category inferred from the extracted content.</small>
            </div>
          </div>
        </section>

        <div className="main-grid result-main-grid">
          <div className="left-section">
            <section className="card dashboard-card primary-panel result-primary-card">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Why The System Reached This Conclusion</p>
                  <h3>Detailed explanation</h3>
                </div>
                <span className="panel-tag">{verificationLabel}</span>
              </div>

              <div className="explanation-list">
                {explanationItems.map((item) => (
                  <div className="explanation-item" key={item}>
                    <span className="bullet-dot" />
                    <p>{item}</p>
                  </div>
                ))}
              </div>

              <div className="action-row result-actions">
                <button className="secondary-button" onClick={handleSummary} disabled={summaryLoading}>
                  {summaryLoading ? 'Generating summary...' : 'Generate Summary'}
                </button>
                <button className="primary-button" onClick={handleGenerateReport} disabled={reportLoading}>
                  {reportLoading ? 'Preparing PDF...' : 'Generate Detailed PDF Report'}
                </button>
              </div>

              {summary && (
                <div className="summary-card result-summary-block">
                  <p className="eyebrow">Summary</p>
                  <p>{summary}</p>
                </div>
              )}
            </section>

            <div className="bottom-section result-bottom-section">
              <article className="card dashboard-card info-card result-graph-card">
                <div className="info-card-header">
                  <div className="info-icon-badge workflow-badge" aria-hidden="true">GR</div>
                  <div>
                    <p className="eyebrow">Insights Graphs</p>
                    <h3>Evidence balance for this claim</h3>
                  </div>
                </div>

                <div className="graph-stack">
                  {graphItems.map((item) => (
                    <div key={item.label} className="graph-card">
                      <div className="graph-meta">
                        <span>{item.label}</span>
                        <strong>{item.value}%</strong>
                      </div>
                      <div className="graph-track">
                        <div className={`graph-fill ${item.tone}`} style={{ width: `${Math.max(item.value, 4)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>

                <div className="info-highlight">
                  Confidence, score balance, and source coverage are shown together so you can see whether the final label came from direct evidence or fallback analysis.
                </div>
              </article>

              <article className="card dashboard-card info-card result-snapshot-card">
                <div className="info-card-header">
                  <div className="info-icon-badge" aria-hidden="true">SN</div>
                  <div>
                    <p className="eyebrow">Source Snapshot</p>
                    <h3>Context from the analyzed input</h3>
                  </div>
                </div>

                <div className="snapshot-stack">
                  <div className="snapshot-card">
                    <span className="snapshot-label">Source</span>
                    <p>{analysis.sourceLabel}</p>
                  </div>

                  {result.extracted_text && (
                    <div className="snapshot-card">
                      <span className="snapshot-label">Extracted text</span>
                      <p>{result.extracted_text}</p>
                    </div>
                  )}
                </div>
              </article>
            </div>
          </div>

          <div className="right-section">
            <section className="card dashboard-card sidebar-card">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Proof And Trusted URLs</p>
                  <h3>Source-backed reasoning</h3>
                </div>
              </div>

              <div className="explanation-list">
                {reasonItems.map((item) => (
                  <div className="explanation-item" key={item}>
                    <span className="bullet-dot" />
                    <p>{item}</p>
                  </div>
                ))}
              </div>

              <div className="trusted-sources">
                {(result.trusted_sources || []).map((item) => (
                  <a
                    key={item.url}
                    className="trusted-source-card"
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <span className="snapshot-label">{item.source}</span>
                    <strong>{item.title}</strong>
                    <p>{item.snippet || item.reason}</p>
                  </a>
                ))}
              </div>
            </section>

            <section className="card dashboard-card sidebar-card">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Analyst Guidance</p>
                  <h3>Recommended next checks</h3>
                </div>
              </div>

              <ul className="workflow-steps">
                <li>Open the trusted URLs and verify they directly support the exact claim.</li>
                <li>Compare the verdict with confidence and source coverage before sharing or reporting.</li>
                <li>Use the generated summary and PDF report when you need a quick handoff or record.</li>
              </ul>

              <div className="note-box">
                <span className="note-title">Result Notes</span>
                <p className="note-body">
                  Source-first verdicts usually carry stronger evidence. Fallback classifier results should be reviewed more carefully when source coverage is limited.
                </p>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Result;
