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


def normalize_url(url):
    parsed = urlparse(url)
    return url if parsed.scheme else f"https://{url}"


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def trim_to_sentence_boundary(text, limit):
    cleaned = clean_text(text)
    if len(cleaned) <= limit:
        return cleaned

    truncated = cleaned[:limit]
    last_boundary = max(
        truncated.rfind(". "),
        truncated.rfind("! "),
        truncated.rfind("? "),
    )

    if last_boundary >= int(limit * 0.6):
        return truncated[: last_boundary + 1].strip()

    return truncated.rsplit(" ", 1)[0].strip()


def is_valid_article(text):
    if not text:
        return False

    t = text.lower()

    if any(term in t for term in BOILERPLATE_TERMS):
        return False

    if len(text.split()) < MIN_WORDS:
        return False

    return True


def parse_html(content):
    soup = BeautifulSoup(content, "html.parser")

    paragraphs = []
    for p in soup.find_all("p"):
        text = clean_text(p.get_text())
        if len(text.split()) > 6:
            if not any(term in text.lower() for term in BOILERPLATE_TERMS):
                paragraphs.append(text)

    return " ".join(paragraphs)


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
            if len(txt.split()) > 6:
                snippets.append(txt)

        if snippets:
            return {"text": trim_to_sentence_boundary(" ".join(snippets), SNIPPET_LIMIT), "url": url}

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
