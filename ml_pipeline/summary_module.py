import os
import re
from collections import Counter

try:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline
except ImportError:
    AutoModelForSeq2SeqLM = None
    AutoTokenizer = None
    pipeline = None


MODEL_NAME = os.getenv("SUMMARY_MODEL_NAME", "sshleifer/distilbart-cnn-12-6")
_SUMMARIZER = None
_SUMMARIZER_ERROR = None

NOISE_TERMS = {
    "advertisement",
    "subscribe",
    "sign in",
    "watch live",
    "privacy policy",
    "terms of use",
    "all rights reserved",
    "cookie policy",
    "follow us",
    "breaking news latest news",
}

IMPORTANT_TERMS = {
    "said",
    "announced",
    "confirmed",
    "reported",
    "officials",
    "government",
    "police",
    "military",
    "minister",
    "president",
    "operation",
    "investigation",
    "warning",
    "advisory",
}

OFF_TOPIC_TEASER_GROUPS = {
    "sports": {
        "ipl", "cricket", "captain", "captaincy", "run-scorer", "bowling",
        "tournament", "kohli", "cummins", "rcb", "bengaluru",
    },
    "entertainment": {
        "box office", "bollywood", "film", "movie", "actor", "actress", "trailer",
    },
}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "in", "into", "is", "it", "its", "of", "on", "or", "that", "the", "their", "this",
    "to", "was", "were", "will", "with", "after", "before", "during", "over", "under",
    "about", "than", "then", "them", "they", "he", "she", "his", "her", "you", "your",
    "we", "our", "i", "but", "if", "not", "no", "more", "most", "also", "had", "been",
    "up", "out", "who", "what", "when", "where", "why", "how",
}


def _clean_text(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def _split_sentences(text):
    normalized = re.sub(r"[\r\n]+", " ", text or "")
    normalized = re.sub(
        r"(?<=[a-z0-9]) (?=[A-Z][a-z]+ [A-Z][a-z]+(?:,|\s(?:is|has|was|will)\b))",
        ". ",
        normalized,
    )
    normalized = re.sub(r'([.!?]["\']) (?=[A-Z])', r"\1 ", normalized)
    normalized = re.sub(r'([.!?])(?=[A-Z][a-z])', r"\1 ", normalized)
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    return [part.strip() for part in parts if part.strip()]


def _is_noise(sentence):
    lowered = sentence.lower()
    if any(term in lowered for term in NOISE_TERMS):
        return True
    if sentence.count("|") >= 2:
        return True
    if len(sentence.split()) > 18 and not re.search(r"[.!?]", sentence):
        return True
    return False


def _sentence_tokens(sentence):
    tokens = re.findall(r"[A-Za-z]{3,}", sentence.lower())
    return [token for token in tokens if token not in STOPWORDS]


def _build_anchor_terms(sentences):
    anchor_source = " ".join(sentences[:3])
    counts = Counter(_sentence_tokens(anchor_source))
    return {word for word, _ in counts.most_common(10)}


def _is_off_topic_teaser(sentence, anchor_text):
    lowered = sentence.lower()

    for terms in OFF_TOPIC_TEASER_GROUPS.values():
        anchor_hits = sum(1 for term in terms if term in anchor_text)
        sentence_hits = sum(1 for term in terms if term in lowered)
        if anchor_hits == 0 and sentence_hits >= 2:
            return True

    return False


def _sentence_similarity(tokens_a, tokens_b):
    if not tokens_a or not tokens_b:
        return 0.0
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    return len(set_a & set_b) / max(1, len(set_a | set_b))


def _build_candidate_window(sentences, anchor_terms):
    candidates = []
    anchor_tokens = _sentence_tokens(" ".join(sentences[:3]))
    off_topic_run = 0

    for index, sentence in enumerate(sentences[:24]):
        tokens = _sentence_tokens(sentence)
        anchor_overlap = len(set(tokens) & anchor_terms)
        anchor_similarity = _sentence_similarity(tokens, anchor_tokens)

        if index < 2:
            candidates.append((index, sentence, tokens, anchor_overlap, anchor_similarity))
            continue

        if anchor_overlap >= 1 or anchor_similarity >= 0.08:
            candidates.append((index, sentence, tokens, anchor_overlap, anchor_similarity))
            off_topic_run = 0
            continue

        off_topic_run += 1
        if off_topic_run >= 2:
            break

    return candidates


def _fallback_summary(sentences, max_sentences):
    selected = []
    for sentence in sentences:
        if len(sentence.split()) < 8:
            continue
        selected.append(sentence)
        if len(selected) >= max_sentences:
            break

    if selected:
        return "\n\n".join(
            " ".join(selected[index:index + 2]) for index in range(0, len(selected), 2)
        )

    return "Could not generate a meaningful summary."


def _clean_headline_fragment(fragment):
    candidate = _clean_text(fragment)
    candidate = re.sub(
        r"^.*?\bcurated by copilot\b\s*-\s*\d+h\s*",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(r"^\d+\s*-\s*", "", candidate)
    candidate = re.sub(r"^\d+h\s*", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"^[^A-Za-z0-9'\"(]+", "", candidate)
    candidate = re.sub(r"\s{2,}", " ", candidate)
    return candidate.strip(" -|,;:")


def _trim_unreadable_prefix(fragment):
    words = fragment.split()
    if len(words) < 4:
        return fragment

    for start in range(len(words)):
        window = words[start:start + 5]
        if len(window) < 3:
            break

        letter_words = [re.sub(r"[^A-Za-z']", "", word) for word in window]
        readable = 0
        titled = 0
        for word in letter_words:
            if len(word) < 2:
                continue
            lowered = word.lower()
            if re.search(r"[aeiouy]", lowered) and re.search(r"[bcdfghjklmnpqrstvwxyz]", lowered):
                readable += 1
            if word[:1].isupper():
                titled += 1

        if readable >= 3 and (titled >= 1 or any(char.isdigit() for char in " ".join(window))):
            trimmed = " ".join(words[start:])
            return trimmed

    return fragment


def _is_readable_headline_fragment(fragment):
    words = re.findall(r"[A-Za-z']+", fragment)
    if len(words) < 3:
        return False

    meaningful = 0
    short_words = 0
    for word in words:
        lowered = word.lower()
        if len(lowered) <= 2:
            short_words += 1
        if re.search(r"[aeiouy]", lowered) and re.search(r"[bcdfghjklmnpqrstvwxyz]", lowered):
            meaningful += 1
        elif word.isupper() and len(word) <= 4:
            meaningful += 1

    if meaningful / max(len(words), 1) < 0.6:
        return False
    if short_words > max(2, len(words) // 2):
        return False

    return True


def _headline_fragment_summary(text):
    normalized = _clean_text(text)
    if not normalized:
        return ""

    parts = re.split(r"\s+\+\s+|\s+[|]\s+|\s+[•]\s+|\n+", normalized)
    cleaned_parts = []
    seen_lower = set()

    for part in parts:
        candidate = _clean_headline_fragment(part)
        candidate = _trim_unreadable_prefix(candidate)
        if not candidate or _is_noise(candidate):
            continue
        if not _is_readable_headline_fragment(candidate):
            continue
        lowered = candidate.lower()
        if lowered in seen_lower:
            continue
        seen_lower.add(lowered)
        cleaned_parts.append(candidate.rstrip(" ,;:"))

    if len(cleaned_parts) < 2:
        return ""

    lead = cleaned_parts[0]
    details = cleaned_parts[1:5]
    summary_sentences = [lead if re.search(r"[.!?]$", lead) else f"{lead}."]
    if details:
        summary_sentences.append(
            "Key points include " + "; ".join(details) + "."
        )

    return "\n\n".join(summary_sentences)


def _target_sentence_count(sentences, max_sentences=None):
    informative = [sentence for sentence in sentences if len(sentence.split()) >= 8]
    sentence_count = len(informative)
    word_count = sum(len(sentence.split()) for sentence in informative)
    upper_bound = max(4, min(max_sentences if max_sentences is not None else 10, 10))

    if sentence_count <= 4:
        return min(sentence_count or 1, upper_bound)

    dynamic_count = max(4, round(sentence_count * 0.55))
    if word_count >= 280:
        dynamic_count += 1
    if word_count >= 420:
        dynamic_count += 1

    return min(dynamic_count, upper_bound, sentence_count)


def _extractive_summary(sentences, max_sentences=None):
    anchor_terms = _build_anchor_terms(sentences)
    anchor_text = " ".join(sentences[:3]).lower()
    ranked = []

    target_count = _target_sentence_count(sentences, max_sentences=max_sentences)
    candidate_window = _build_candidate_window(sentences, anchor_terms)

    for index, sentence, tokens, anchor_overlap, anchor_similarity in candidate_window:
        words = sentence.split()
        if len(words) < 7:
            continue

        important_hits = sum(1 for term in IMPORTANT_TERMS if term in sentence.lower())

        if _is_off_topic_teaser(sentence, anchor_text):
            continue

        score = 2.2 - (index * 0.12)
        score += min(anchor_overlap, 5) * 0.35
        score += anchor_similarity * 1.6
        score += important_hits * 0.2
        if any(char.isdigit() for char in sentence):
            score += 0.2
        if 12 <= len(words) <= 34:
            score += 0.25
        if len(sentence) > 260:
            score -= 0.4

        ranked.append((score, index, sentence, tokens))

    if not ranked:
        return _fallback_summary(sentences, target_count)

    ranked.sort(key=lambda item: (-item[0], item[1]))
    chosen = []

    for score, index, sentence, tokens in ranked:
        if chosen and score < 0.95:
            continue
        if any(_sentence_similarity(tokens, existing_tokens) > 0.72 for _, _, existing_tokens in chosen):
            continue
        chosen.append((index, sentence, tokens))
        if len(chosen) >= target_count:
            break

    ordered = [sentence for index, sentence, tokens in sorted(chosen, key=lambda item: item[0])]
    if not ordered:
        return _fallback_summary(sentences, target_count)

    paragraphs = []
    group_size = 2 if target_count <= 6 else 3
    for index in range(0, len(ordered), group_size):
        paragraphs.append(" ".join(ordered[index:index + group_size]))

    return "\n\n".join(paragraphs)


def _get_summarizer():
    global _SUMMARIZER, _SUMMARIZER_ERROR

    if _SUMMARIZER is not None or _SUMMARIZER_ERROR is not None:
        return _SUMMARIZER

    if pipeline is None:
        _SUMMARIZER_ERROR = "transformers is not installed"
        return None

    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, local_files_only=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME, local_files_only=True)
        _SUMMARIZER = pipeline(
            "summarization",
            model=model,
            tokenizer=tokenizer,
            device=-1,
        )
    except Exception as error:
        _SUMMARIZER_ERROR = str(error)
        _SUMMARIZER = None

    return _SUMMARIZER


def _chunk_sentences(sentences, max_words=220):
    chunks = []
    current = []
    current_words = 0

    for sentence in sentences:
        sentence_words = len(sentence.split())
        if current and current_words + sentence_words > max_words:
            chunks.append(" ".join(current))
            current = [sentence]
            current_words = sentence_words
            continue

        current.append(sentence)
        current_words += sentence_words

    if current:
        chunks.append(" ".join(current))

    return chunks


def _generated_summary_cleanup(summary_text):
    cleaned = _clean_text(summary_text)
    if not cleaned:
        return ""

    sentences = [sentence for sentence in _split_sentences(cleaned) if not _is_noise(sentence)]
    if not sentences:
        return cleaned

    paragraphs = []
    for index in range(0, len(sentences), 2):
        paragraphs.append(" ".join(sentences[index:index + 2]))

    return "\n\n".join(paragraphs)


def _model_summary(sentences, max_sentences=None):
    summarizer = _get_summarizer()
    if summarizer is None:
        return None

    target_count = _target_sentence_count(sentences, max_sentences=max_sentences)
    target_words = max(90, min(220, target_count * 28))
    candidate_text = " ".join(sentences)
    chunks = _chunk_sentences(sentences, max_words=220)
    chunk_summaries = []

    for chunk in chunks:
        chunk_words = len(chunk.split())
        max_length = max(80, min(200, int(chunk_words * 0.7)))
        min_length = max(35, min(max_length - 15, int(chunk_words * 0.28)))

        try:
            result = summarizer(
                chunk,
                max_length=max_length,
                min_length=min_length,
                do_sample=False,
                truncation=True,
            )
        except Exception:
            return None

        generated = result[0].get("summary_text", "").strip()
        cleaned_generated = _generated_summary_cleanup(generated)
        if cleaned_generated:
            chunk_summaries.append(cleaned_generated)

    if not chunk_summaries:
        return None

    combined = " ".join(chunk_summaries)
    combined_words = len(combined.split())

    if len(chunk_summaries) > 1 and combined_words > target_words:
        max_length = max(90, min(220, int(combined_words * 0.7)))
        min_length = max(45, min(max_length - 15, int(combined_words * 0.35)))
        try:
            refined = summarizer(
                combined,
                max_length=max_length,
                min_length=min_length,
                do_sample=False,
                truncation=True,
            )[0].get("summary_text", "").strip()
            combined = refined or combined
        except Exception:
            pass

    cleaned_final = _generated_summary_cleanup(combined)
    return cleaned_final if cleaned_final else None


def summarize_text(text, max_sentences=None, prefer_model=True):
    clean = _clean_text(text)
    if not clean:
        return "No content available to summarize."

    headline_style_summary = _headline_fragment_summary(clean)
    if headline_style_summary:
        return headline_style_summary

    sentences = _split_sentences(clean)
    sentences = [sentence for sentence in sentences if not _is_noise(sentence)]

    if not sentences:
        return "Could not generate a meaningful summary."

    if prefer_model:
        model_summary = _model_summary(sentences, max_sentences=max_sentences)
        if model_summary:
            return model_summary

    return _extractive_summary(sentences, max_sentences=max_sentences)
