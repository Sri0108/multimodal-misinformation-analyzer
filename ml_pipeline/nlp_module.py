import re

from textblob import TextBlob

try:
    import spacy
except ImportError:
    spacy = None

try:
    import nltk
    from nltk.stem import PorterStemmer
    from nltk.tokenize import wordpunct_tokenize
except ImportError:
    nltk = None
    PorterStemmer = None
    wordpunct_tokenize = None

try:
    import tensorflow as tf
except ImportError:
    tf = None

try:
    from transformers import pipeline
except ImportError:
    pipeline = None

SENSATIONAL_WORDS = ['shocking', 'breaking', 'exclusive', 'miracle', 'secret', 'revealed']
SUSPICIOUS_KEYWORDS = [
    'click here', 'urgent', 'act now', 'secret', 'miracle',
    'shocking', 'unbelievable', 'guaranteed', 'doctors hate',
    'one weird trick',
]

JOURNAL_KEYWORDS = [
    'journal', 'peer-reviewed', 'abstract', 'methodology',
    'references', 'findings', 'doi', 'volume', 'issue', 'conference',
]

UNIVERSITY_KEYWORDS = [
    'university', 'institute', 'college', 'department',
    'laboratory', 'lab', 'faculty', 'school of',
]

ACADEMIC_STYLE_TERMS = [
    'study', 'research', 'analysis', 'data',
    'results', 'conclusion', 'evidence', 'authors',
]

MALICIOUS_URL_HINTS = ['bit.ly', 'tinyurl', 'goo.gl', 't.co', '@', 'free-money', 'login-verify']

TRUSTED_DOMAINS = ['.gov', '.edu', '.ac.in', '.org']

SCAM_PATTERNS = [
    r'earn\s?\$\d+',
    r'win\s?\$\d+',
    r'free money',
    r'limited time',
    r'claim now',
    r'send otp',
]

DISEASE_TERMS = [
    'covid', 'covid-19', 'coronavirus', 'cancer', 'diabetes',
    'dengue', 'malaria', 'hiv', 'aids', 'flu', 'influenza',
]

MEDICAL_CLAIM_TERMS = [
    'cure', 'cures', 'prevent', 'prevents', 'treat', 'treats',
    'heal', 'heals', 'reverse', 'reverses',
]

SUPPLEMENT_REMEDY_TERMS = [
    'vitamin c', 'vitamin d', 'zinc', 'garlic', 'ginger',
    'turmeric', 'lemon', 'honey', 'herbal', 'supplement',
]

VAGUE_SOURCE_TERMS = [
    'reportedly', 'sources remain unclear', 'details are still emerging',
    'unconfirmed', 'rumors suggest', 'it is believed', 'some say',
    'sources say', 'allegedly', 'claims are circulating',
]

EXTRAORDINARY_CLAIM_TERMS = [
    'increase lifespan', 'live 50% longer', 'extend life by',
    'breakthrough', 'revolutionary method', 'scientists have reportedly discovered',
]

BERT_MODEL_NAME = "textattack/bert-base-uncased-SST-2"
_SPACY_PIPELINE = None
_BERT_SENTIMENT_PIPELINE = None
_BERT_PIPELINE_ERROR = None
_STEMMER = PorterStemmer() if PorterStemmer else None


def _count_keyword_hits(text, keywords):
    lowered = text.lower()
    return sum(lowered.count(keyword) for keyword in keywords)


def is_trusted_url(text):
    urls = re.findall(r'(https?://\S+)', text)
    return any(any(domain in url for domain in TRUSTED_DOMAINS) for url in urls)


def detect_scam_patterns(text):
    return sum(bool(re.search(pattern, text.lower())) for pattern in SCAM_PATTERNS)


def detect_medical_misinformation_signals(text):
    lowered = text.lower()
    disease_mentions = sum(1 for term in DISEASE_TERMS if term in lowered)
    medical_claim_terms = sum(1 for term in MEDICAL_CLAIM_TERMS if term in lowered)
    remedy_mentions = sum(1 for term in SUPPLEMENT_REMEDY_TERMS if term in lowered)
    has_authority_citation = any(term in lowered for term in ['cdc', 'who', 'nih', 'ministry of health'])

    unsupported_cure_claim = (
        disease_mentions > 0
        and medical_claim_terms > 0
        and remedy_mentions > 0
        and not has_authority_citation
    )

    return {
        "disease_mentions": disease_mentions,
        "medical_claim_terms": medical_claim_terms,
        "remedy_mentions": remedy_mentions,
        "has_authority_citation": has_authority_citation,
        "unsupported_cure_claim": unsupported_cure_claim,
    }


def detect_source_clarity_signals(text):
    lowered = text.lower()
    vague_source_hits = sum(1 for term in VAGUE_SOURCE_TERMS if term in lowered)
    mentions_breakthrough = any(term in lowered for term in ['discovered', 'breakthrough', 'increase lifespan'])
    source_unclear = vague_source_hits > 0
    extraordinary_claim = any(term in lowered for term in EXTRAORDINARY_CLAIM_TERMS) or bool(
        re.search(r'\b\d{2,}%\b', lowered)
    )

    return {
        "vague_source_hits": vague_source_hits,
        "source_unclear": source_unclear,
        "unverified_breakthrough_claim": source_unclear and mentions_breakthrough,
        "extraordinary_claim": extraordinary_claim,
    }


def compute_scores(signals, sensational_count, suspicious_keywords):
    risk_score = 0
    credibility_score = 0

    # Risk scoring
    risk_score += min(suspicious_keywords * 0.15, 0.6)
    risk_score += signals.get("malicious_url_count", 0) * 0.2
    risk_score += sensational_count * 0.1

    if signals.get("tone") == "negative":
        risk_score += 0.1
    if signals.get("unsupported_cure_claim"):
        risk_score += 0.45
    if signals.get("medical_claim_terms", 0) > 0 and not signals.get("has_authority_citation"):
        risk_score += 0.15
    if signals.get("source_unclear"):
        risk_score += min(0.3, signals.get("vague_source_hits", 0) * 0.12)
    if signals.get("unverified_breakthrough_claim"):
        risk_score += 0.3
    if signals.get("extraordinary_claim"):
        risk_score += 0.25

    # Credibility scoring
    if signals.get("doi_present"):
        credibility_score += 0.4
    if signals.get("citation_format"):
        credibility_score += 0.2
    if signals.get("journal_keywords"):
        credibility_score += 0.2
    if signals.get("author_university_reference"):
        credibility_score += 0.2

    return min(risk_score, 1.0), min(credibility_score, 1.0)


def _get_spacy_pipeline():
    global _SPACY_PIPELINE

    if _SPACY_PIPELINE is not None or spacy is None:
        return _SPACY_PIPELINE

    try:
        _SPACY_PIPELINE = spacy.blank("en")
        if "sentencizer" not in _SPACY_PIPELINE.pipe_names:
            _SPACY_PIPELINE.add_pipe("sentencizer")
    except Exception:
        _SPACY_PIPELINE = None

    return _SPACY_PIPELINE


def _extract_spacy_signals(text):
    pipeline_obj = _get_spacy_pipeline()
    if pipeline_obj is None:
        return {
            "sentence_count": 0,
            "entity_count": 0,
            "lexical_diversity": 0.0,
        }

    doc = pipeline_obj(text)
    alpha_tokens = [token.text.lower() for token in doc if token.is_alpha]
    unique_tokens = len(set(alpha_tokens))
    lexical_diversity = unique_tokens / max(len(alpha_tokens), 1) if alpha_tokens else 0.0

    return {
        "sentence_count": sum(1 for _ in doc.sents),
        "entity_count": len(getattr(doc, "ents", [])),
        "lexical_diversity": round(lexical_diversity, 3),
    }


def _extract_nltk_signals(text):
    if nltk is None or wordpunct_tokenize is None or _STEMMER is None:
        return {
            "stemmed_suspicious_hits": 0,
            "token_count": 0,
        }

    tokens = [token.lower() for token in wordpunct_tokenize(text) if re.search(r"[a-z]", token.lower())]
    suspicious_stems = {_STEMMER.stem(token) for token in SUSPICIOUS_KEYWORDS if " " not in token}
    token_stems = [_STEMMER.stem(token) for token in tokens]
    stemmed_suspicious_hits = sum(1 for stem in token_stems if stem in suspicious_stems)

    return {
        "stemmed_suspicious_hits": stemmed_suspicious_hits,
        "token_count": len(tokens),
    }


def _get_bert_sentiment_pipeline():
    global _BERT_SENTIMENT_PIPELINE, _BERT_PIPELINE_ERROR

    if _BERT_SENTIMENT_PIPELINE is not None or _BERT_PIPELINE_ERROR is not None:
        return _BERT_SENTIMENT_PIPELINE

    if pipeline is None:
        _BERT_PIPELINE_ERROR = "transformers unavailable"
        return None

    try:
        _BERT_SENTIMENT_PIPELINE = pipeline(
            "sentiment-analysis",
            model=BERT_MODEL_NAME,
            tokenizer=BERT_MODEL_NAME,
            framework="tf",
            device=-1,
            local_files_only=True,
        )
    except Exception as error:
        _BERT_PIPELINE_ERROR = str(error)
        _BERT_SENTIMENT_PIPELINE = None

    return _BERT_SENTIMENT_PIPELINE


def _extract_bert_signals(text):
    classifier = _get_bert_sentiment_pipeline()
    if classifier is None:
        return {
            "label": "unavailable",
            "score": 0.5,
        }

    try:
        result = classifier(text[:512])[0]
        label = str(result.get("label", "neutral")).lower()
        score = float(result.get("score", 0.5))
        return {
            "label": label,
            "score": round(score, 3),
        }
    except Exception:
        return {
            "label": "unavailable",
            "score": 0.5,
        }


def _fuse_scores_with_tensorflow(risk_score, credibility_score, bert_signals, spacy_signals):
    if tf is None:
        return risk_score, credibility_score

    bert_score = bert_signals.get("score", 0.5)
    bert_is_negative = 1.0 if "neg" in bert_signals.get("label", "") else 0.0
    lexical_diversity = spacy_signals.get("lexical_diversity", 0.0)
    entity_count = min(float(spacy_signals.get("entity_count", 0)), 8.0) / 8.0

    risk_tensor = tf.sigmoid(
        tf.constant(
            1.45 * risk_score
            + 0.55 * bert_is_negative * bert_score
            + 0.10 * (1.0 - lexical_diversity),
            dtype=tf.float32,
        )
    )
    credibility_tensor = tf.sigmoid(
        tf.constant(
            1.35 * credibility_score
            + 0.25 * lexical_diversity
            + 0.15 * entity_count
            + 0.20 * (bert_score if bert_is_negative == 0.0 else 0.0),
            dtype=tf.float32,
        )
    )

    return min(float(risk_tensor.numpy()), 1.0), min(float(credibility_tensor.numpy()), 1.0)


def analyze_nlp(text):
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity

    if polarity > 0.1:
        sentiment = 'positive'
    elif polarity < -0.1:
        sentiment = 'negative'
    else:
        sentiment = 'neutral'

    sensational_count = _count_keyword_hits(text, SENSATIONAL_WORDS)
    suspicious_keywords = _count_keyword_hits(text, SUSPICIOUS_KEYWORDS)
    journal_keyword_hits = _count_keyword_hits(text, JOURNAL_KEYWORDS)
    university_keyword_hits = _count_keyword_hits(text, UNIVERSITY_KEYWORDS)
    academic_style_hits = _count_keyword_hits(text, ACADEMIC_STYLE_TERMS)

    has_doi = bool(re.search(r'10\.\d{4,9}/[-._;()/:a-z0-9]+', text, re.IGNORECASE))
    has_citation_format = bool(
        re.search(r'\(\s*(19|20)\d{2}\s*\)', text)
        or re.search(r'\[[0-9]{1,3}\]', text)
        or re.search(r'et al\.,?\s*(19|20)\d{2}', text, re.IGNORECASE)
    )

    has_external_links = bool(re.search(r'(https?://|www\.)', text, re.IGNORECASE))
    malicious_url_count = sum(text.lower().count(hint) for hint in MALICIOUS_URL_HINTS)

    # Academic scoring
    academic_score = 0
    academic_score += 2 if has_doi else 0
    academic_score += 1 if has_citation_format else 0
    academic_score += 1 if journal_keyword_hits > 0 else 0
    academic_score += 1 if university_keyword_hits > 0 else 0
    academic_score += 1 if academic_style_hits >= 2 else 0

    academic_style = academic_score >= 2
    medical_signals = detect_medical_misinformation_signals(text)
    source_signals = detect_source_clarity_signals(text)
    spacy_signals = _extract_spacy_signals(text)
    nltk_signals = _extract_nltk_signals(text)
    bert_signals = _extract_bert_signals(text)

    signals = {
        "malicious_url_count": malicious_url_count,
        "doi_present": has_doi,
        "citation_format": has_citation_format,
        "journal_keywords": journal_keyword_hits > 0,
        "author_university_reference": university_keyword_hits > 0,
        "tone": sentiment,
        "unsupported_cure_claim": medical_signals["unsupported_cure_claim"],
        "medical_claim_terms": medical_signals["medical_claim_terms"],
        "disease_mentions": medical_signals["disease_mentions"],
        "remedy_mentions": medical_signals["remedy_mentions"],
        "has_authority_citation": medical_signals["has_authority_citation"],
        "vague_source_hits": source_signals["vague_source_hits"],
        "source_unclear": source_signals["source_unclear"],
        "unverified_breakthrough_claim": source_signals["unverified_breakthrough_claim"],
        "extraordinary_claim": source_signals["extraordinary_claim"],
        "sentence_count": spacy_signals["sentence_count"],
        "entity_count": spacy_signals["entity_count"],
        "lexical_diversity": spacy_signals["lexical_diversity"],
        "stemmed_suspicious_hits": nltk_signals["stemmed_suspicious_hits"],
        "bert_label": bert_signals["label"],
        "bert_score": bert_signals["score"],
    }

    risk_score, credibility_score = compute_scores(
        signals, sensational_count, suspicious_keywords
    )
    risk_score += min(0.15, nltk_signals["stemmed_suspicious_hits"] * 0.05)
    if spacy_signals["lexical_diversity"] >= 0.58:
        credibility_score += 0.08
    if bert_signals["label"].startswith("neg"):
        risk_score += 0.08 * bert_signals["score"]
    elif bert_signals["label"].startswith("pos"):
        credibility_score += 0.05 * bert_signals["score"]

    risk_score, credibility_score = _fuse_scores_with_tensorflow(
        min(risk_score, 1.0),
        min(credibility_score, 1.0),
        bert_signals,
        spacy_signals,
    )

    trusted_url = is_trusted_url(text)
    scam_patterns = detect_scam_patterns(text)

    return {
        'sentiment': sentiment,
        'polarity': polarity,
        'risk_score': min(risk_score + scam_patterns * 0.2, 1.0),
        'credibility_score': min(credibility_score + (0.2 if trusted_url else 0), 1.0),
        'signals': {
            'academic_style': academic_style,
            'suspicious_keywords': suspicious_keywords,
            'external_links': has_external_links,
            'trusted_url': trusted_url,
            'tone': sentiment,
            'doi_present': has_doi,
            'citation_format': has_citation_format,
            'journal_keywords': journal_keyword_hits > 0,
            'author_university_reference': university_keyword_hits > 0,
            'malicious_url_count': malicious_url_count,
            'scam_patterns': scam_patterns,
            'unsupported_cure_claim': medical_signals['unsupported_cure_claim'],
            'medical_claim_terms': medical_signals['medical_claim_terms'],
            'disease_mentions': medical_signals['disease_mentions'],
            'remedy_mentions': medical_signals['remedy_mentions'],
            'has_authority_citation': medical_signals['has_authority_citation'],
            'vague_source_hits': source_signals['vague_source_hits'],
            'source_unclear': source_signals['source_unclear'],
            'unverified_breakthrough_claim': source_signals['unverified_breakthrough_claim'],
            'extraordinary_claim': source_signals['extraordinary_claim'],
            'sentence_count': spacy_signals['sentence_count'],
            'entity_count': spacy_signals['entity_count'],
            'lexical_diversity': spacy_signals['lexical_diversity'],
            'stemmed_suspicious_hits': nltk_signals['stemmed_suspicious_hits'],
            'bert_label': bert_signals['label'],
            'bert_score': bert_signals['score'],
        }
    }
