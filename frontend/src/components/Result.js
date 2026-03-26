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
      <div className="app-shell result-shell">
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
    <div className="app-shell result-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <header className="topbar">
        <div>
          <p className="eyebrow">Detection Result</p>
          <h1>Trusted-source evidence first, classification fallback second.</h1>
        </div>
        <button className="ghost-button" onClick={() => navigate('/upload')}>Analyze Another Item</button>
      </header>

      <section className="result-hero">
        <div className={`verdict-card ${verdictTone}`}>
          <p className="eyebrow">Primary Verdict</p>
          <h2>{result.prediction}</h2>
          <p>
            Verification mode: <strong>{result.verification_mode === 'trusted_source_first' ? 'Trusted source first' : 'Classifier fallback'}</strong>
          </p>
        </div>

        <div className="metrics-strip">
          <div className="metric-card accent-warning">
            <span className="metric-value">{Math.round((result.confidence || 0) * 100)}%</span>
            <span className="metric-label">Confidence</span>
          </div>
          <div className="metric-card accent-cool">
            <span className="metric-value">{result.source_evidence_count || 0}</span>
            <span className="metric-label">Trusted URLs found</span>
          </div>
          <div className="metric-card accent-success">
            <span className="metric-value">{result.claim_category || 'general'}</span>
            <span className="metric-label">Claim type</span>
          </div>
        </div>
      </section>

      <main className="result-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Why the system reached this conclusion</p>
              <h3>Detailed explanation</h3>
            </div>
          </div>

          <div className="explanation-list">
            {explanationItems.map((item) => (
              <div className="explanation-item" key={item}>
                <span className="bullet-dot" />
                <p>{item}</p>
              </div>
            ))}
          </div>

          <div className="action-row">
            <button className="secondary-button" onClick={handleSummary} disabled={summaryLoading}>
              {summaryLoading ? 'Generating summary...' : 'Generate Summary'}
            </button>
            <button className="primary-button" onClick={handleGenerateReport} disabled={reportLoading}>
              {reportLoading ? 'Preparing PDF...' : 'Generate Detailed PDF Report'}
            </button>
          </div>

          {summary && (
            <div className="summary-card">
              <p className="eyebrow">Summary</p>
              <p>{summary}</p>
            </div>
          )}
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Proof and trusted URLs</p>
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

        <section className="panel">
          <div className="panel-header">
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

          <div className="tips-card">
            <h4>Recommended next checks</h4>
            <p>Open the trusted URLs above, compare whether they directly support the claim, and note whether the app used source-first evidence or classifier fallback.</p>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Source Snapshot</p>
              <h3>Context from the analyzed input</h3>
            </div>
          </div>

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
        </section>
      </main>
    </div>
  );
}

export default Result;
