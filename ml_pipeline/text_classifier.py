from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import pickle
import os

MODEL_PATH = 'ml_pipeline/fake_news_model.pkl'
VECTORIZER_PATH = 'ml_pipeline/tfidf_vectorizer.pkl'

FAKE_CUE_TERMS = [
    "breaking",
    "shocking",
    "exclusive",
    "miracle",
    "secret",
    "revealed",
    "you won't believe",
    "doctors hate",
    "one weird trick",
    "click here",
    "guaranteed",
]

REAL_CUE_TERMS = [
    "according to",
    "official",
    "confirmed",
    "statement",
    "report",
    "data",
    "study",
    "published",
    "researchers",
    "agency",
    "ministry",
]


def train_model():
    """Train a fresh model for fake news detection."""
    fake_samples = [
        "Breaking: Shocking news about celebrity scandal!",
        "You won't believe what happened next!",
        "Secret revealed: Government hiding truth!",
        "Miracle cure discovered by scientists!",
        "Exclusive: Celebrity admits shocking truth!",
        "UNBELIEVABLE! Scientists discover shocking secret!",
        "Click here to see what happened next!",
        "This one trick shocked doctors!",
        "You won't believe your eyes!",
        "Doctors hate this one weird trick!",
        "Breaking news: Shocking discovery!",
        "Anonymous sources reveal shocking truth!",
        "More at 11 - shocking revelation!",
        "This will shock you!",
        "Incredible discovery that will blow your mind!",
        "Urgent alert! Share this before it gets deleted.",
        "Doctors hate this miracle cure that works instantly.",
        "Anonymous insiders reveal the hidden truth they don't want you to know.",
        "Guaranteed method to reverse disease in just 24 hours.",
        "Exclusive leaked message proves the conspiracy is real.",
    ]
    real_samples = [
        "The government announced new policy changes today.",
        "Research shows correlation between diet and health.",
        "Officials confirmed the incident occurred yesterday.",
        "The study was published in a peer-reviewed journal.",
        "Experts recommend following safety guidelines.",
        "According to the latest report from researchers.",
        "The agency releases its quarterly statement.",
        "Statistical data shows a 5% increase this quarter.",
        "Meteorologists predict rain for tomorrow.",
        "The committee met to discuss new regulations.",
        "The report details findings from the study.",
        "Analysis of the data suggests a trend.",
        "The organization released official statements.",
        "Based on recent surveys of respondents.",
        "Scientists conducted research over several years.",
        "According to the ministry, the advisory was issued on Tuesday.",
        "The police department confirmed the arrest in an official statement.",
        "The journal published the study after peer review.",
        "Reuters reported the development citing two officials.",
        "The court order was uploaded to the official website.",
    ]

    texts = fake_samples + real_samples
    labels = [0] * len(fake_samples) + [1] * len(real_samples)

    vectorizer = TfidfVectorizer(
        max_features=1500,
        ngram_range=(1, 2),
        stop_words='english',
    )
    X = vectorizer.fit_transform(texts)

    model = LogisticRegression(max_iter=500, random_state=42, class_weight='balanced')
    model.fit(X, labels)

    os.makedirs(os.path.dirname(MODEL_PATH) or '.', exist_ok=True)
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    with open(VECTORIZER_PATH, 'wb') as f:
        pickle.dump(vectorizer, f)

    print("Model trained and saved successfully")


def ensure_model_artifacts():
    if not os.path.exists(MODEL_PATH) or not os.path.exists(VECTORIZER_PATH):
        train_model()


def _clamp_score(value):
    return max(0.01, min(0.99, float(value)))


def _cue_score(text, terms):
    lowered = (text or "").lower()
    return sum(lowered.count(term) for term in terms)


def _calibrate_label(real_score, fake_score):
    top_score = max(real_score, fake_score)

    if top_score < 0.55:
        return 'Uncertain', top_score

    if real_score >= fake_score:
        if real_score >= 0.75:
            return 'Real', real_score
        return 'Likely Real', real_score

    if fake_score >= 0.75:
        return 'Fake', fake_score
    return 'Likely Fake', fake_score


def _build_explanation(signals, label):
    explanation = []

    if signals.get('unsupported_cure_claim'):
        explanation.append('Unsupported cure claim detected for a disease-related statement')
    if signals.get('medical_claim_terms', 0) > 0 and not signals.get('has_authority_citation'):
        explanation.append('Medical treatment claim appears without a strong authority citation')
    if signals.get('source_unclear'):
        explanation.append('Claim relies on vague or unclear sourcing language')
    if signals.get('unverified_breakthrough_claim'):
        explanation.append('Breakthrough-style claim appears before credible sources are identified')
    if signals.get('extraordinary_claim'):
        explanation.append('The claim makes an extraordinary promise that needs strong verifiable evidence')

    if signals.get('academic_style'):
        explanation.append('Formal academic writing style detected')

    if signals.get('suspicious_keywords', 0) == 0:
        explanation.append('No suspicious keywords found')
    else:
        explanation.append(
            f"Suspicious keyword count elevated: {signals.get('suspicious_keywords', 0)}"
        )

    if signals.get('malicious_url_count', 0) == 0:
        explanation.append('No phishing or malicious URLs detected')
    else:
        explanation.append('Potentially risky URL patterns detected')

    if (
        signals.get('doi_present')
        or signals.get('citation_format')
        or signals.get('journal_keywords')
        or signals.get('author_university_reference')
    ):
        explanation.append('Content structure matches legitimate publication patterns')

    if signals.get('tone') == 'neutral':
        explanation.append('Overall tone appears neutral rather than sensational')
    elif signals.get('tone') == 'negative':
        explanation.append('Tone is emotionally negative, which can increase misinformation risk')

    if not explanation:
        explanation.append(f'Content calibrated as {label} from combined linguistic signals')

    return explanation


def classify_text(text, nlp_result=None):
    """Classify text and return calibrated labels plus explainable signals."""
    ensure_model_artifacts()

    with open(MODEL_PATH, 'rb') as f:
        model = pickle.load(f)
    with open(VECTORIZER_PATH, 'rb') as f:
        vectorizer = pickle.load(f)

    X = vectorizer.transform([text])
    prediction = model.predict(X)[0]
    confidence = model.predict_proba(X)[0]

    base_fake_score = float(confidence[0])
    base_real_score = float(confidence[1])

    signals = (nlp_result or {}).get('signals', {})
    risk_score = float((nlp_result or {}).get('risk_score', 0.0))
    credibility_score = float((nlp_result or {}).get('credibility_score', 0.0))
    academic_boost = 0.2 if signals.get('academic_style') else 0.0
    suspicious_penalty = min(0.2, signals.get('suspicious_keywords', 0) * 0.04)
    malicious_penalty = min(0.2, signals.get('malicious_url_count', 0) * 0.08)
    medical_claim_penalty = 0.0
    lexical_fake_bonus = min(0.25, _cue_score(text, FAKE_CUE_TERMS) * 0.04)
    lexical_real_bonus = min(0.2, _cue_score(text, REAL_CUE_TERMS) * 0.03)
    authority_bonus = 0.08 if signals.get('has_authority_citation') else 0.0
    trusted_url_bonus = 0.08 if signals.get('trusted_url') else 0.0

    if signals.get('unsupported_cure_claim'):
        medical_claim_penalty += 0.45
    if signals.get('medical_claim_terms', 0) > 0 and not signals.get('has_authority_citation'):
        medical_claim_penalty += 0.15
    if signals.get('source_unclear'):
        medical_claim_penalty += min(0.3, signals.get('vague_source_hits', 0) * 0.12)
    if signals.get('unverified_breakthrough_claim'):
        medical_claim_penalty += 0.3
    if signals.get('extraordinary_claim'):
        medical_claim_penalty += 0.25

    real_score = _clamp_score(
        (base_real_score * 0.55)
        + (credibility_score * 0.25)
        + lexical_real_bonus
        + authority_bonus
        + trusted_url_bonus
        + academic_boost
        - suspicious_penalty
        - malicious_penalty
        - medical_claim_penalty
    )
    fake_score = _clamp_score(
        (base_fake_score * 0.45)
        + (risk_score * 0.35)
        + lexical_fake_bonus
        + suspicious_penalty
        + malicious_penalty
        + medical_claim_penalty
        - (academic_boost / 2)
        - (trusted_url_bonus / 2)
    )

    label, conf_score = _calibrate_label(real_score, fake_score)
    explanation = _build_explanation(signals, label)

    return {
        'prediction': label,
        'confidence': float(conf_score),
        'explanation': explanation,
        'signals': signals,
        'scores': {
            'real_score': real_score,
            'fake_score': fake_score,
        }
    }
