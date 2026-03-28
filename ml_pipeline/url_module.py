import re
from urllib.parse import urlparse, urlencode

import requests
from bs4 import BeautifulSoup
from newspaper import Article

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
]

HEADERS = {
    "User-Agent": USER_AGENTS[0],
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "DNT": "1",
}

MIN_WORDS = 50
TEXT_LIMIT = 5000
SNIPPET_LIMIT = 3000

BOILERPLATE_TERMS = [
    "toi world desk",
    "times of india world desk",
    "our dedicated team of seasoned journalists",
    "read more",
]

LOW_SIGNAL_TERMS = BOILERPLATE_TERMS + [
    "about the author",
    "follow us on social media",
    "financial calculators",
    "emi calculator",
    "sip calculator",
    "ppf calculator",
    "fd calculator",
    "nps calculator",
    "mutual fund calculator",
    "calculate now",
    "daily puzzles",
    "hot picks",
    "top trending",
    "trending stories",
    "end of article",
    "go ad free now",
]

HARD_STOP_TERMS = {
    "about the author",
    "follow us on social media",
    "end of article",
    "financial calculators",
    "daily puzzles",
    "trending stories",
    "hot picks",
}


def normalize_url(url):
    parsed = urlparse(url)
    return url if parsed.scheme else f"https://{url}"


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def ensure_terminal_punctuation(text):
    cleaned = clean_text(text)
    if not cleaned:
        return ""

    if re.search(r'[.!?]["\')\]]?$', cleaned):
        return cleaned

    return f"{cleaned}."


def join_text_blocks(blocks):
    normalized = [ensure_terminal_punctuation(block) for block in blocks if clean_text(block)]
    return " ".join(block for block in normalized if block)


def is_low_signal_block(text):
    lowered = clean_text(text).lower()
    if not lowered:
        return True

    return any(term in lowered for term in LOW_SIGNAL_TERMS)


def dedupe_blocks(blocks):
    unique = []
    seen = set()

    for block in blocks:
        normalized = clean_text(block)
        if not normalized:
            continue

        key = normalized.lower()
        if key in seen:
            continue

        seen.add(key)
        unique.append(normalized)

    return unique


def derive_intro_sentence(text):
    cleaned = clean_text(text)
    if not cleaned:
        return ""

    for marker in [" after ", " amid ", " while ", " following ", " as "]:
        marker_index = cleaned.lower().find(marker)
        if marker_index >= 40:
            candidate = cleaned[:marker_index].strip(" ,;:")
            if len(candidate.split()) >= 8:
                return ensure_terminal_punctuation(candidate)

    match = re.match(r"(.+?[.!?])(?:\s|$)", cleaned)
    if match:
        return clean_text(match.group(1))

    return ensure_terminal_punctuation(cleaned)


def trim_to_sentence_boundary(text, limit):
    cleaned = clean_text(text)
    if len(cleaned) <= limit:
        return cleaned

    truncated = cleaned[:limit]
    sentence_boundaries = [match.end() for match in re.finditer(r'[.!?]["\')\]]?(?:\s|$)', truncated)]
    if sentence_boundaries:
        last_boundary = sentence_boundaries[-1]
        if last_boundary >= int(limit * 0.6):
            return truncated[:last_boundary].strip()

    extended_match = re.search(r'[.!?]["\')\]]?(?:\s|$)', cleaned[limit:])
    if extended_match:
        boundary = limit + extended_match.end()
        if boundary <= min(len(cleaned), limit + 100):
            return cleaned[:boundary].strip()

    return truncated.rsplit(" ", 1)[0].strip()


def is_valid_article(text):
    if not text:
        return False

    t = text.lower()
    if any(term in t for term in ["emi calculator", "sip calculator", "calculate now"]):
        return False

    if len(text.split()) < MIN_WORDS:
        return False

    return True


def parse_html(content):
    soup = BeautifulSoup(content, "html.parser")
    candidate_blocks = []

    headline = clean_text(soup.title.get_text()) if soup.title else ""
    if headline and not is_low_signal_block(headline):
        candidate_blocks.append(headline)

    for selector in [
        {"name": "description"},
        {"property": "og:description"},
        {"name": "twitter:description"},
    ]:
        meta = soup.find("meta", attrs=selector)
        description = clean_text(meta.get("content", "")) if meta else ""
        if len(description.split()) >= 10 and not is_low_signal_block(description):
            candidate_blocks.append(description)

    scopes = [
        tag for tag in soup.find_all(["article", "main", "section"])
        if tag.find_all("p")
    ]
    if not scopes:
        scopes = [soup]

    best_paragraphs = []
    best_word_count = 0

    for scope in scopes:
        paragraphs = []
        for p in scope.find_all("p"):
            text = clean_text(p.get_text(" ", strip=True))
            if len(text.split()) <= 6:
                continue

            lowered = text.lower()
            if any(marker in lowered for marker in HARD_STOP_TERMS):
                if len(paragraphs) >= 2:
                    break
                continue

            if is_low_signal_block(text):
                continue

            paragraphs.append(text)

        word_count = sum(len(paragraph.split()) for paragraph in paragraphs)
        if word_count > best_word_count:
            best_word_count = word_count
            best_paragraphs = paragraphs

    if not candidate_blocks and best_paragraphs:
        derived_intro = derive_intro_sentence(best_paragraphs[0])
        if derived_intro and not is_low_signal_block(derived_intro):
            candidate_blocks.append(derived_intro)

    candidate_blocks.extend(best_paragraphs)
    return join_text_blocks(dedupe_blocks(candidate_blocks))


# -----------------------------
# DIRECT FETCH
# -----------------------------
def fetch_direct(url):
    for _ in range(2):
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue

            text = parse_html(r.content)

            if is_valid_article(text):
                return {"text": trim_to_sentence_boundary(text, TEXT_LIMIT), "url": url}

        except:
            continue

    return None


# -----------------------------
# AMP
# -----------------------------
def fetch_amp(url):
    try:
        parsed = urlparse(url)
        amp_url = f"https://{parsed.netloc.replace('.', '-')}.cdn.ampproject.org/v/s/{parsed.netloc}{parsed.path}"

        r = requests.get(amp_url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None

        text = parse_html(r.content)

        if is_valid_article(text):
            return {"text": trim_to_sentence_boundary(text, TEXT_LIMIT), "url": url}

    except:
        return None


# -----------------------------
# GOOGLE SNIPPET
# -----------------------------
def fetch_google(url):
    try:
        parsed = urlparse(url)
        slug = parsed.path.split("/")[-1].replace("-", " ")
        query = f"{slug} site:{parsed.netloc}"

        search_url = f"https://www.google.com/search?{urlencode({'q': query})}"

        r = requests.get(search_url, headers={"User-Agent": USER_AGENTS[1]}, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")

        snippets = []
        for s in soup.select("div.VwiC3b, div.BNeawe"):
            txt = clean_text(s.get_text())
            if len(txt.split()) > 6 and not is_low_signal_block(txt):
                snippets.append(txt)

        if snippets:
            return {"text": trim_to_sentence_boundary(join_text_blocks(snippets), SNIPPET_LIMIT), "url": url}

    except:
        return None


# -----------------------------
# NEWSPAPER (BEST FALLBACK)
# -----------------------------
def fetch_newspaper(url):
    try:
        article = Article(url)
        article.download()
        article.parse()

        if is_valid_article(article.text):
            return {"text": trim_to_sentence_boundary(article.text, TEXT_LIMIT), "url": url}

    except:
        return None


# -----------------------------
# MAIN
# -----------------------------
def fetch_and_extract_from_url(url):

    if not url:
        return {"source_type": "error", "text": "", "error": "No URL"}

    url = normalize_url(url)

    # 1. Direct
    res = fetch_direct(url)
    if res:
        return {"source_type": "webpage", **res}

    # 2. AMP
    res = fetch_amp(url)
    if res:
        return {"source_type": "amp", **res}

    # 3. Google
    res = fetch_google(url)
    if res:
        return {"source_type": "snippet", **res}

    # 4. Newspaper
    res = fetch_newspaper(url)
    if res:
        return {"source_type": "newspaper", **res}

    # FINAL SAFE FALLBACK
    return {
        "source_type": "fallback",
        "text": f"Could not extract full article. URL: {url}",
        "url": url,
    }
