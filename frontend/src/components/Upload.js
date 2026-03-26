import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { buildApiUrl } from '../api';

const contentOptions = [
  { value: 'text', title: 'Text', hint: 'Paste a claim, post, or article snippet.' },
  { value: 'url', title: 'URL', hint: 'Inspect a webpage or shared article link.' },
  { value: 'document', title: 'Document', hint: 'Upload PDF, TXT, or DOCX evidence.' },
  { value: 'image', title: 'Image', hint: 'Scan screenshots, posters, and image claims.' },
];

const sampleCyberMessages = [
  {
    label: 'Bank OTP Scam',
    text: 'URGENT: Your bank account will be blocked in 2 hours. Verify now at bit.ly/secure-update and enter OTP.',
  },
  {
    label: 'Courier Fee Scam',
    text: 'Hi this is courier support. Pay Rs 25 re-delivery fee now using this link to avoid package return.',
  },
  {
    label: 'Prize Fraud',
    text: 'Congratulations! You won a cashback. Share your card number, CVV, and PIN to claim today.',
  },
];

const sampleAnalysisInputs = {
  text: [
    { label: 'Health Cure Claim', text: 'Breaking: Drinking hot lemon water cures all viral infections in 24 hours.' },
    { label: 'Cash Giveaway Link', text: 'Government announces free cash for all users who click this link and verify OTP.' },
    { label: 'AI Deepfake Claim', text: 'Scientists confirm a new AI tool can detect fake videos with 100% accuracy.' },
  ],
  url: [
    { label: 'Reuters', text: 'https://www.reuters.com' },
    { label: 'AP News', text: 'https://www.apnews.com' },
    { label: 'Snopes', text: 'https://www.snopes.com' },
  ],
};

function readAnalysisHistory() {
  const raw = localStorage.getItem('analysisHistory');
  if (!raw || raw === 'undefined' || raw === 'null') {
    return [];
  }

  try {
    return JSON.parse(raw);
  } catch (error) {
    localStorage.removeItem('analysisHistory');
    return [];
  }
}

function evaluateCyberMessage(message) {
  const text = (message || '').toLowerCase();
  const matches = [];

  const rules = [
    { key: 'phishing-link', label: 'Suspicious link request', test: /(bit\.ly|tinyurl|t\.co|shorturl|verify your account|login now|click here)/.test(text) },
    { key: 'urgent-pressure', label: 'Urgency pressure', test: /(urgent|immediately|within 24 hours|act now|last warning|final notice)/.test(text) },
    { key: 'money-request', label: 'Money transfer request', test: /(gift card|wire transfer|upi|crypto|bitcoin|send money|bank transfer)/.test(text) },
    { key: 'credential-theft', label: 'Credential/OTP request', test: /(otp|one time password|password|cvv|pin|security code)/.test(text) },
    { key: 'impersonation', label: 'Impersonation risk', test: /(bank team|tech support|customs|police|government refund|income tax)/.test(text) },
    { key: 'malware-lure', label: 'Attachment/install lure', test: /(open attachment|download app|install apk|enable macro|remote access)/.test(text) },
  ];

  for (const rule of rules) {
    if (rule.test) {
      matches.push(rule.label);
    }
  }

  let risk = 'Low';
  if (matches.length >= 4) risk = 'High';
  else if (matches.length >= 2) risk = 'Medium';

  const riskSummary = {
    High: 'High risk of scam/fraud/phishing.',
    Medium: 'Potential scam indicators detected.',
    Low: 'No strong scam indicators found, but stay cautious.',
  };

  const guidance = [
    'Do not click unknown links or open unexpected attachments.',
    'Never share OTP, PIN, password, or card details.',
    'Verify the sender using an official phone number or website.',
    'If money was sent, contact your bank/payment provider immediately.',
  ];

  const reporting = [
    'If you are in the US: Report to IC3 (ic3.gov) and FTC (reportfraud.ftc.gov).',
    'If you are in India: Report to the National Cyber Crime Reporting Portal at cybercrime.gov.in or call 1930.',
    'Report the message in-app (email/SMS/social platform) and block sender.',
    'For immediate danger or financial loss, contact local law enforcement.',
  ];

  return {
    risk,
    summary: riskSummary[risk],
    indicators: matches,
    guidance,
    reporting,
  };
}

function cleanNewsSummary(summary) {
  if (!summary) return '';
  return summary
    .replace(/&lt;[^&]*&gt;/g, ' ')
    .replace(/&nbsp;|&amp;|&quot;|&#39;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function getNewsRisk(item) {
  const text = `${item?.title || ''} ${item?.summary || ''}`.toLowerCase();
  const highTerms = ['scam', 'fraud', 'phishing', 'hoax', 'misinformation', 'debunk', 'fake news', 'alert', 'danger'];
  const mediumTerms = ['rumor', 'myth', 'controversy', 'viral', 'claim', 'lockdown', 'warning'];

  const highHits = highTerms.filter((t) => text.includes(t)).length;
  const mediumHits = mediumTerms.filter((t) => text.includes(t)).length;

  if (highHits >= 2 || (highHits >= 1 && mediumHits >= 1)) {
    return { label: 'High', tone: 'high' };
  }
  if (highHits >= 1 || mediumHits >= 2) {
    return { label: 'Medium', tone: 'medium' };
  }
  return { label: 'Low', tone: 'low' };
}

function Upload({ token, onLogout }) {
  const [contentType, setContentType] = useState('text');
  const [content, setContent] = useState('');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [topFakeNews, setTopFakeNews] = useState([]);
  const [newsLoading, setNewsLoading] = useState(true);
  const [newsError, setNewsError] = useState('');
  const [newsRiskFilter, setNewsRiskFilter] = useState('all');
  const [newsPage, setNewsPage] = useState(0);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState([
    {
      role: 'assistant',
      text:
        'Scam Bot: Paste a suspicious message. I will return Fake/Real verdict, reasons, safety measures, and reporting links when needed.',
    },
  ]);
  const navigate = useNavigate();

  useEffect(() => {
    setHistory(readAnalysisHistory());
  }, []);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = chatOpen ? 'hidden' : previousOverflow || '';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [chatOpen]);

  useEffect(() => {
    let mounted = true;

    const loadTopFakeNews = async () => {
      setNewsLoading(true);
      setNewsError('');
      try {
        const response = await fetch(buildApiUrl('/api/top-fake-news'), {
          headers: {
            Authorization: `Bearer ${token}`
          }
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || 'Failed to fetch top fake news');
        }
        if (mounted) {
          setTopFakeNews(Array.isArray(data.items) ? data.items : []);
        }
      } catch (error) {
        if (mounted) {
          setNewsError(error.message || 'Unable to load top fake news.');
        }
      } finally {
        if (mounted) {
          setNewsLoading(false);
        }
      }
    };

    loadTopFakeNews();
    return () => {
      mounted = false;
    };
  }, [token]);

  const activeOption = contentOptions.find((option) => option.value === contentType);

  const dashboardStats = useMemo(() => {
    const today = new Date().toDateString();
    const todaysItems = history.filter((item) => new Date(item.createdAt).toDateString() === today);
    const total = todaysItems.length || 1;
    const fakeCount = todaysItems.filter((item) => (item.prediction || '').toLowerCase().includes('fake')).length;
    const realCount = todaysItems.filter((item) => (item.prediction || '').toLowerCase().includes('real')).length;
    const avgConfidence = todaysItems.reduce((sum, item) => sum + (item.confidence || 0), 0) / total;
    const sourceBacked = todaysItems.filter((item) => item.verificationMode === 'trusted_source_first').length;

    return {
      todaysCount: todaysItems.length,
      fakePercent: Math.round((fakeCount / total) * 100),
      realPercent: Math.round((realCount / total) * 100),
      avgConfidence: Math.round(avgConfidence * 100),
      sourceBackedPercent: Math.round((sourceBacked / total) * 100),
    };
  }, [history]);

  const handleContentTypeChange = (nextType) => {
    setContentType(nextType);
    setContent('');
    setFile(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!contentType) {
      alert('Please select a content type');
      return;
    }

    if ((contentType === 'text' || contentType === 'url') && !content.trim()) {
      alert(`Please enter ${contentType === 'text' ? 'text content' : 'a URL'}`);
      return;
    }

    if ((contentType === 'image' || contentType === 'document') && !file) {
      alert('Please select a file');
      return;
    }

    setLoading(true);

    const formData = new FormData();
    formData.append('content_type', contentType);

    if (contentType === 'text' || contentType === 'url') {
      formData.append('content', content.trim());
    }

    if (file && (contentType === 'image' || contentType === 'document')) {
      formData.append('file', file);
    }

    try {
      const analyzeUrl = buildApiUrl('/api/analyze');
      const response = await fetch(analyzeUrl, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`
        },
        body: formData
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Analysis failed');
      }

      const payload = {
        inputId: data.input_id,
        result: data.result,
        contentType,
        sourceLabel: file?.name || content.slice(0, 60) || activeOption?.title || 'Analysis input',
      };

      const nextHistory = [
        {
          prediction: data.result?.prediction,
          confidence: data.result?.confidence,
          verificationMode: data.result?.verification_mode,
          sourceEvidenceCount: data.result?.source_evidence_count,
          createdAt: new Date().toISOString(),
        },
        ...history,
      ].slice(0, 20);

      localStorage.setItem('analysisHistory', JSON.stringify(nextHistory));
      localStorage.setItem('latestAnalysis', JSON.stringify(payload));
      setHistory(nextHistory);
      navigate('/result', { state: payload });
    } catch (err) {
      console.error('Error:', err);
      const message = err.message === 'Failed to fetch'
        ? `Cannot reach backend API at ${buildApiUrl('/api/analyze')}. Ensure Flask is running and reachable on port 5000.`
        : err.message;
      alert(`Analysis failed: ${message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleChatSubmit = (e) => {
    e.preventDefault();
    const trimmed = chatInput.trim();
    if (!trimmed) {
      return;
    }

    const review = evaluateCyberMessage(trimmed);
    const isFake = review.risk === 'High' || review.risk === 'Medium';
    const verdict = isFake ? 'Fake' : 'Real';
    const reasons = review.indicators.length
      ? review.indicators.join(', ')
      : 'No major scam indicators were detected in this text.';
    const measures = isFake
      ? review.guidance
      : [
        'Still verify sender identity before sharing information.',
        'Avoid opening unexpected links or attachments.',
        'Keep monitoring for follow-up suspicious messages.',
      ];

    const reportLinks = isFake
      ? ['https://cybercrime.gov.in/', 'https://reportfraud.ftc.gov/', 'https://www.ic3.gov/']
      : [];

    setChatMessages((prev) => [
      ...prev,
      { role: 'user', text: trimmed },
      {
        role: 'assistant',
        risk: review.risk.toLowerCase(),
        verdict,
        reason: reasons,
        measures,
        links: reportLinks,
      },
    ]);
    setChatInput('');
  };

  const trendCards = [
    {
      title: "Today's Checks",
      value: dashboardStats.todaysCount,
      caption: 'Analyses completed today in this workspace',
      colorClass: 'accent-warm',
    },
    {
      title: 'Fake Signal Share',
      value: `${dashboardStats.fakePercent}%`,
      caption: 'Recent results leaning fake or likely fake',
      colorClass: 'accent-danger',
    },
    {
      title: 'Source-Backed Results',
      value: `${dashboardStats.sourceBackedPercent}%`,
      caption: 'Claims that found trusted-source links before fallback',
      colorClass: 'accent-cool',
    },
  ];

  const workflowItems = [
    'Source lookup runs before classifier fallback.',
    'Evidence links and reason summary are generated per claim.',
    'Cyber chat assistant supports scam/phishing triage and reporting.',
    'PDF report and summary endpoints remain available for each analysis.',
  ];

  const howItWorks = [
    'Choose an input type: text, URL, document, or image.',
    'The platform extracts content and checks trusted evidence first.',
    'NLP and classifier signals are combined when source evidence is limited.',
    'You get verdict, confidence, source links, and cyber safety guidance.',
  ];

  const filteredTopFakeNews = topFakeNews.filter((item) => {
    if (newsRiskFilter === 'all') return true;
    return getNewsRisk(item).tone === newsRiskFilter;
  });
  const NEWS_PAGE_SIZE = 3;
  const totalNewsPages = Math.max(1, Math.ceil(filteredTopFakeNews.length / NEWS_PAGE_SIZE));
  const activeNewsPage = Math.min(newsPage, totalNewsPages - 1);
  const pagedTopFakeNews = filteredTopFakeNews.slice(
    activeNewsPage * NEWS_PAGE_SIZE,
    activeNewsPage * NEWS_PAGE_SIZE + NEWS_PAGE_SIZE
  );

  useEffect(() => {
    setNewsPage(0);
  }, [newsRiskFilter]);

  useEffect(() => {
    if (newsPage > totalNewsPages - 1) {
      setNewsPage(0);
    }
  }, [newsPage, totalNewsPages]);

  return (
    <div className="app-shell workspace-pro">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <div className="page-container">
        <header className="topbar">
          <div className="brand-lockup">
            <span className="brand-mark">MM</span>
            <div>
              <h1>multimodal misinformation analyzer</h1>
            </div>
          </div>
          <div className="topbar-actions">
            <button className="ghost-button" onClick={onLogout}>Logout</button>
          </div>
        </header>

        <section className="hero-panel">
          <div className="hero-copy">
            <p className="eyebrow">Investigation Dashboard</p>
            <h2>Verify first. Act fast.</h2>
            <p className="hero-lead">
              Built for serious workflows: analyze suspicious claims, validate with trusted sources,
              and quickly assess scam, fraud, phishing, or malicious messages with actionable reporting steps.
            </p>
          </div>

          <div className="hero-metrics">
            {trendCards.map((card) => (
              <div key={card.title} className={`metric-card ${card.colorClass}`}>
                <span className="metric-value">{card.value}</span>
                <span className="metric-label">{card.title}</span>
                <small>{card.caption}</small>
              </div>
            ))}
          </div>
        </section>

        {/* ── MAIN GRID: two columns with gap ── */}
        <div className="main-grid">

          {/* ── LEFT COLUMN: stacked with gap ── */}
          <div className="left-section">

            <section className="card primary-panel dashboard-card">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Analysis Input</p>
                  <h3>Choose a channel and run a professional verification pass</h3>
                </div>
                <span className="panel-tag">{activeOption?.title}</span>
              </div>

              <div className="mode-tabs">
                {contentOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    className={`mode-tab ${contentType === option.value ? 'active' : ''}`}
                    onClick={() => handleContentTypeChange(option.value)}
                  >
                    <strong>{option.title}</strong>
                    <span>{option.hint}</span>
                  </button>
                ))}
              </div>

              <form className="analysis-form" onSubmit={handleSubmit}>
                {(contentType === 'text' || contentType === 'url') && (
                  <div className="input-samples-inline">
                    <strong className="input-samples-title">Sample {contentType === 'text' ? 'claims' : 'links'}:</strong>
                    <div className="input-samples-list">
                      {sampleAnalysisInputs[contentType].map((sample) => (
                        <span
                          key={sample.label}
                          role="button"
                          tabIndex={0}
                          className="input-sample-label"
                          onMouseEnter={() => setContent(sample.text)}
                          onFocus={() => setContent(sample.text)}
                        >
                          {sample.label}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {(contentType === 'text' || contentType === 'url') && (
                  <label className="field">
                    <span>{contentType === 'text' ? 'Paste text to inspect' : 'Paste the URL to inspect'}</span>
                    <textarea
                      className="rich-input"
                      rows="8"
                      value={content}
                      onChange={(e) => setContent(e.target.value)}
                      placeholder={
                        contentType === 'text'
                          ? 'Paste a post, article paragraph, or suspicious claim here...'
                          : 'https://example.com/article'
                      }
                      required
                    />
                  </label>
                )}

                {(contentType === 'image' || contentType === 'document') && (
                  <label className="field upload-dropzone">
                    <span>{contentType === 'image' ? 'Upload image evidence' : 'Upload a document for analysis'}</span>
                    <input
                      type="file"
                      className="file-input"
                      onChange={(e) => setFile(e.target.files[0])}
                      required
                    />
                    <small>{file ? `Selected: ${file.name}` : 'Supported: PNG, JPG, PDF, TXT, DOCX'}</small>
                  </label>
                )}

                <div className="action-row">
                  <button type="submit" className="primary-button" disabled={loading}>
                    {loading ? 'Running verification...' : 'Start Verification'}
                  </button>
                  <p className="action-note">
                    Trusted-source verification runs first. The classifier backs it up only when direct evidence is weak.
                  </p>
                </div>
              </form>
            </section>

            {/* ── BOTTOM SECTION: gap handled by parent flex column ── */}
            <div className="bottom-section">
              <article className="card info-card dashboard-card about-card-modern">
                <div className="info-card-header">
                  <div className="info-icon-badge" aria-hidden="true">TC</div>
                  <div>
                    <p className="eyebrow">About This Tool</p>
                    <h3>What TruthCheck helps you do</h3>
                  </div>
                </div>
                <p className="card-copy">
                  TruthCheck is a combined misinformation and cyber safety platform. It helps teams verify claims,
                  inspect suspicious content, and reduce harm from scam or phishing campaigns with evidence-backed workflows.
                </p>
                <div className="info-highlight">
                  Built for fast review when teams need evidence, risk context, and recommended next actions in one place.
                </div>
                <div className="about-tags">
                  <span>Source-first verification</span>
                  <span>NLP risk signals</span>
                  <span>Cybercrime guidance</span>
                  <span>Report-ready outputs</span>
                </div>
              </article>

              <article className="card info-card dashboard-card workflow-card-modern">
                <div className="info-card-header">
                  <div className="info-icon-badge workflow-badge" aria-hidden="true">01</div>
                  <div>
                    <p className="eyebrow">How It Works</p>
                    <h3>End-to-end workflow</h3>
                  </div>
                </div>
                <ol className="steps-list">
                  {howItWorks.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
              </article>
            </div>
          </div>
          {/* end .left-section */}

          {/* ── RIGHT COLUMN ── */}
          <div className="right-section">

            <section className="card dashboard-card sidebar-card">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Operational Insights</p>
                  <h3>Verification Workflow</h3>
                </div>
              </div>

              <ul className="workflow-steps">
                {workflowItems.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>

              <div className="workflow-status status-row">
                <span className="status-chip live">Source-First: Active</span>
                <span className="status-chip ready">Classifier: Standby</span>
                <span className="status-chip protect">Cyber Chat: Online</span>
              </div>

              <div className="note-box">
                <span className="note-title">Analyst Notes</span>
                <p className="note-body">
                  Prioritize trusted links, confidence, and risk signals for faster, cleaner decisions.
                </p>
              </div>
            </section>

            <section className="card dashboard-card sidebar-card">
              <div className="panel-header">
                <div>
                  <h3>Global Fake News</h3>
                </div>
                <button
                  type="button"
                  className="ghost-button"
                  onClick={async () => {
                    setNewsLoading(true);
                    setNewsError('');
                    try {
                      const response = await fetch(buildApiUrl('/api/top-fake-news'), {
                        headers: { Authorization: `Bearer ${token}` }
                      });
                      const data = await response.json();
                      if (!response.ok) {
                        throw new Error(data.error || 'Failed to refresh news');
                      }
                      setTopFakeNews(Array.isArray(data.items) ? data.items : []);
                    } catch (error) {
                      setNewsError(error.message || 'Unable to refresh news.');
                    } finally {
                      setNewsLoading(false);
                    }
                  }}
                >
                  Refresh
                </button>
              </div>

              <div className="news-filter-row">
                <button
                  type="button"
                  className={`news-filter ${newsRiskFilter === 'all' ? 'active' : ''}`}
                  onClick={() => setNewsRiskFilter('all')}
                >
                  All
                </button>
                <button
                  type="button"
                  className={`news-filter high ${newsRiskFilter === 'high' ? 'active' : ''}`}
                  onClick={() => setNewsRiskFilter('high')}
                >
                  High
                </button>
                <button
                  type="button"
                  className={`news-filter medium ${newsRiskFilter === 'medium' ? 'active' : ''}`}
                  onClick={() => setNewsRiskFilter('medium')}
                >
                  Medium
                </button>
                <button
                  type="button"
                  className={`news-filter low ${newsRiskFilter === 'low' ? 'active' : ''}`}
                  onClick={() => setNewsRiskFilter('low')}
                >
                  Low
                </button>
              </div>

              {newsLoading && <p className="news-meta">Loading latest fact-check headlines...</p>}
              {!newsLoading && newsError && <p className="news-meta news-error">{newsError}</p>}
              {!newsLoading && !newsError && filteredTopFakeNews.length === 0 && (
                <p className="news-meta">No daily fake-news headlines found right now.</p>
              )}

              {!newsLoading && !newsError && filteredTopFakeNews.length > 0 && (
                <div className="news-list">
                  {pagedTopFakeNews.map((item, idx) => {
                    const risk = getNewsRisk(item);
                    return (
                      <a
                        key={`${item.url}-${idx}`}
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="news-item"
                      >
                        <div className="news-item-top">
                          <span className="news-rank-circle">{activeNewsPage * NEWS_PAGE_SIZE + idx + 1}</span>
                          <span className="news-title">{item.title}</span>
                          <span className={`news-risk-pill ${risk.tone}`}>{risk.label}</span>
                        </div>
                        <p className="news-snippet">
                          {cleanNewsSummary(item.summary) || 'Open to read full fact-check details.'}
                        </p>
                      </a>
                    );
                  })}
                </div>
              )}

              {!newsLoading && !newsError && filteredTopFakeNews.length > NEWS_PAGE_SIZE && (
                <div className="news-pager">
                  <button
                    type="button"
                    className="news-nav-btn"
                    onClick={() => setNewsPage((prev) => Math.max(0, prev - 1))}
                    disabled={activeNewsPage === 0}
                  >
                    &#8249;
                  </button>
                  <span>{`${activeNewsPage + 1}/${totalNewsPages}`}</span>
                  <button
                    type="button"
                    className="news-nav-btn"
                    onClick={() => setNewsPage((prev) => Math.min(totalNewsPages - 1, prev + 1))}
                    disabled={activeNewsPage >= totalNewsPages - 1}
                  >
                    &#8250;
                  </button>
                </div>
              )}
            </section>

          </div>
          {/* end .right-section */}

        </div>
        {/* end .main-grid */}

      </div>

      <button
        type="button"
        className="chat-launcher"
        onClick={() => setChatOpen((prev) => !prev)}
      >
        {chatOpen ? 'Close Scam Bot' : 'Open Scam Bot'}
      </button>

      {chatOpen && (
        <div className="chat-overlay">
          <section className="chat-page-window" aria-label="Cyber Safety Chat Window">
            <div className="chat-window-header">
              <div>
                <p className="eyebrow">Scam Bot</p>
                <h4>Scam / Fraud / Phishing Assistant</h4>
              </div>
              <button type="button" className="ghost-button" onClick={() => setChatOpen(false)}>Close</button>
            </div>

            <div className="sample-message-list compact labels-only">
              {sampleCyberMessages.map((sample) => (
                <button
                  key={`${sample.label}-chat`}
                  type="button"
                  className="sample-message label-chip"
                  onClick={() => setChatInput(sample.text)}
                >
                  {sample.label}
                </button>
              ))}
            </div>

            <div className="chatbot-messages">
              {chatMessages.map((msg, idx) => (
                <div key={`${msg.role}-${idx}`} className={`chat-msg ${msg.role}`}>
                  <div className="chat-msg-head">
                    <strong>{msg.role === 'assistant' ? 'Bot' : 'You'}</strong>
                    {msg.risk && <span className={`risk-chip ${msg.risk}`}>{msg.risk}</span>}
                  </div>
                  {msg.role === 'assistant' && msg.verdict ? (
                    <div className="bot-response">
                      <div className={`bot-verdict ${msg.verdict.toLowerCase()}`}>{`Verdict: ${msg.verdict}`}</div>
                      <p><strong>Reason:</strong> {msg.reason}</p>
                      <div>
                        <strong>Measures to take:</strong>
                        <ul>
                          {msg.measures.map((measure) => (
                            <li key={measure}>{measure}</li>
                          ))}
                        </ul>
                      </div>
                      {msg.links && msg.links.length > 0 && (
                        <div>
                          <strong>Cyber Report Links:</strong>
                          <div className="bot-links">
                            {msg.links.map((link) => (
                              <a key={link} href={link} target="_blank" rel="noreferrer">{link}</a>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p>{msg.text}</p>
                  )}
                </div>
              ))}
            </div>

            <form className="chatbot-form chat-form-sticky" onSubmit={handleChatSubmit}>
              <textarea
                rows="4"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Paste suspicious message here..."
              />
              <button type="submit" className="secondary-button">Check Message</button>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}

export default Upload;
