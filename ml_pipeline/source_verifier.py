import logging
import re
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keywords & domain config
# ---------------------------------------------------------------------------

HEALTH_KEYWORDS = [
    "covid",
    "covid-19",
    "coronavirus",
    "vaccine",
    "vitamin",
    "treatment",
    "cure",
    "prevent",
    "disease",
    "nih",
    "cdc",
    "who.int",
    "world health organization",
]

SCIENCE_KEYWORDS = [
    "scientists",
    "study",
    "research",
    "lifespan",
    "breakthrough",
    "method",
    "discovery",
    "experiment",
]

NEWS_KEYWORDS = [
    "war",
    "conflict",
    "attack",
    "military",
    "troops",
    "invasion",
    "ceasefire",
    "strike",
    "missile",
    "bomb",
    "army",
    "killed",
    "government",
    "president",
    "minister",
    "election",
    "protest",
    "crisis",
    "sanctions",
    "diplomat",
]

CATEGORY_DOMAINS = {
    "health": [
        "cdc.gov",
        "nih.gov",
        "who.int",
        "pubmed.ncbi.nlm.nih.gov",
        "reuters.com",
    ],
    "science": [
        "nature.com",
        "science.org",
        "reuters.com",
        "apnews.com",
    ],
    "news": [
        "reuters.com",
        "apnews.com",
        "bbc.com",
        "theguardian.com",
        "aljazeera.com",
        "timesofindia.indiatimes.com",
        "thehindu.com",
    ],
    "general": [
        "reuters.com",
        "apnews.com",
        "snopes.com",
        "factcheck.org",
        "timesofindia.indiatimes.com",
    ],
}

TRUSTED_PUBLISHER_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "theguardian.com",
    "aljazeera.com",
    "cdc.gov",
    "nih.gov",
    "who.int",
    "pubmed.ncbi.nlm.nih.gov",
    "nature.com",
    "science.org",
    "snopes.com",
    "factcheck.org",
    "timesofindia.indiatimes.com",
    "thehindu.com",
    "indianexpress.com",
    "ndtv.com",
    "hindustantimes.com",
}

SUPPORT_TERMS = [
    "confirmed",
    "official",
    "published",
    "guideline",
    "study",
    "research",
    "evidence",
    "peer-reviewed",
    "verified",
    "reported",
]

REFUTE_TERMS = [
    "false",
    "myth",
    "misleading",
    "no evidence",
    "not recommended",
    "unsupported",
    "debunked",
    "fact check",
    "incorrect",
    "misinformation",
    "unverified",
    "rumor",
    "hoax",
]

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ---------------------------------------------------------------------------
# Category detection
# ---------------------------------------------------------------------------


def detect_claim_category(text: str) -> str:
    """Return the best-matching category for a claim."""
    lowered = (text or "").lower()
    tokens = set(re.findall(r"[a-z0-9.\-]+", lowered))

    def has_keyword(keywords):
        for keyword in keywords:
            if " " in keyword or "." in keyword or "-" in keyword:
                if keyword in lowered:
                    return True
            elif keyword in tokens:
                return True
        return False

    if has_keyword(HEALTH_KEYWORDS):
        return "health"
    if has_keyword(NEWS_KEYWORDS):
        return "news"
    if has_keyword(SCIENCE_KEYWORDS):
        return "science"
    return "general"


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def _normalize_link(href: str | None) -> str | None:
    """Resolve DuckDuckGo redirect URLs and scheme-relative URLs."""
    if not href:
        return None
    if "duckduckgo.com/l/?" in href:
        parsed = urlparse(href)
        uddg = parse_qs(parsed.query).get("uddg")
        if uddg:
            return unquote(uddg[0])
    if href.startswith("//"):
        return f"https:{href}"
    if href.startswith("http"):
        return href
    return None


def _normalize_hostname(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")


def _is_trusted_source_url(url: str | None) -> bool:
    if not url:
        return False

    hostname = _normalize_hostname(url)
    return any(
        hostname == trusted_domain or hostname.endswith(f".{trusted_domain}")
        for trusted_domain in TRUSTED_PUBLISHER_DOMAINS
    )


def _build_original_source(source_url: str | None, source_title: str | None) -> dict | None:
    if not _is_trusted_source_url(source_url):
        return None

    hostname = _normalize_hostname(source_url or "")
    return {
        "title": source_title or "Original analyzed article",
        "url": source_url,
        "source": hostname,
        "snippet": "Original source URL from the analyzed input.",
        "is_fallback": False,
    }


# ---------------------------------------------------------------------------
# DuckDuckGo search (primary)
# ---------------------------------------------------------------------------


def _extract_search_results(html: str, domain: str, limit: int = 3) -> list[dict]:
    """Parse DuckDuckGo HTML results for a given domain."""
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for result in soup.select(".result"):
        anchor = result.select_one(".result__a")
        snippet_tag = result.select_one(".result__snippet")
        if not anchor:
            continue

        url = _normalize_link(anchor.get("href"))
        if not url or domain not in url:
            continue

        title = anchor.get_text(" ", strip=True)
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

        if url.rstrip("/") in (f"https://{domain}", f"http://{domain}"):
            continue

        items.append(
            {
                "title": title,
                "url": url,
                "source": domain,
                "snippet": snippet,
            }
        )

        if len(items) >= limit:
            break

    return items


def _search_domain(claim: str, domain: str) -> list[dict]:
    """Run a DuckDuckGo site-search for one domain."""
    query = quote_plus(f"site:{domain} {claim}")
    search_url = f"https://html.duckduckgo.com/html/?q={query}"

    response = requests.get(search_url, headers=REQUEST_HEADERS, timeout=4)
    response.raise_for_status()
    return _extract_search_results(response.text, domain)


# ---------------------------------------------------------------------------
# Fallback: Brave Search (optional — set BRAVE_API_KEY env var to enable)
# Returns real article URLs, not Google search redirects.
# ---------------------------------------------------------------------------


def _brave_search(claim: str, domains: list[str]) -> list[dict]:
    """
    Optional real-time fallback using the Brave Search API.
    Set the BRAVE_API_KEY environment variable to enable.
    """
    import os

    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        return []

    results = []
    query = claim[:200]

    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            params={"q": query, "count": 10, "freshness": "pw"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("web", {}).get("results", []):
            url = item.get("url", "")
            if not any(d in url for d in domains):
                continue
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": url,
                    "source": urlparse(url).netloc.replace("www.", ""),
                    "snippet": item.get("description", ""),
                }
            )
    except Exception as error:
        logger.warning("Brave Search fallback failed: %s", error)

    return results


# ---------------------------------------------------------------------------
# Fallback: constructive direct search links (last resort)
# ---------------------------------------------------------------------------


def _build_fallback_links(claim: str, domains: list[str]) -> list[dict]:
    """
    Return direct search/site links as a last resort.
    Clearly labelled so the frontend can distinguish fallback links.
    """
    query = quote_plus(claim[:120])
    fallbacks = []

    for domain in domains[:3]:
        label = domain.split(".")[0].upper()
        fallbacks.append(
            {
                "title": f'Search "{claim[:60]}..." on {domain}',
                "url": (
                    f"https://{domain}/search?q={query}"
                    if domain
                    not in (
                        "reuters.com",
                        "apnews.com",
                        "bbc.com",
                        "theguardian.com",
                        "aljazeera.com",
                    )
                    else f"https://www.google.com/search?q=site:{domain}+{query}"
                ),
                "source": label,
                "snippet": (
                    "No direct article found automatically. "
                    "Click to search this trusted source manually."
                ),
                "is_fallback": True,
            }
        )

    return fallbacks


# ---------------------------------------------------------------------------
# Source scoring
# ---------------------------------------------------------------------------


def _score_sources(sources: list[dict]) -> tuple[int, int]:
    """Return (support_hits, refute_hits) across all source snippets + titles."""
    support_hits = 0
    refute_hits = 0

    for item in sources:
        haystack = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
        support_hits += sum(1 for term in SUPPORT_TERMS if term in haystack)
        refute_hits += sum(1 for term in REFUTE_TERMS if term in haystack)

    return support_hits, refute_hits


# ---------------------------------------------------------------------------
# Verdict helpers
# ---------------------------------------------------------------------------


def _compute_verdict(
    signals: dict,
    support_hits: int,
    refute_hits: int,
    real_source_count: int,
) -> tuple[str, float]:
    """
    Derive verdict and confidence.
    Returns (verdict, confidence) where verdict is Likely Real/Fake/Uncertain.
    """
    if signals.get("unsupported_cure_claim") or signals.get("unverified_breakthrough_claim"):
        return ("Likely Fake", 0.82) if real_source_count > 0 else ("Uncertain", 0.55)

    if refute_hits > support_hits and refute_hits > 0:
        return "Likely Fake", min(0.55 + 0.05 * refute_hits, 0.92)

    if support_hits > refute_hits and support_hits > 0 and not signals.get("source_unclear"):
        return "Likely Real", min(0.55 + 0.05 * support_hits, 0.90)

    if real_source_count == 0:
        return "Uncertain", 0.0

    return "Uncertain", 0.52


def _build_reason_summary(
    verdict: str,
    signals: dict,
    verification_mode: str,
    source_count: int,
) -> list[str]:
    reasons = []

    if verification_mode == "trusted_source_first" and source_count > 0:
        reasons.append(f"Found {source_count} trusted source(s) from authoritative domains.")

    if signals.get("unsupported_cure_claim"):
        reasons.append("The claim links a remedy to curing a disease without strong authority evidence.")
    if signals.get("source_unclear"):
        reasons.append('The wording uses vague sourcing like "reportedly" or "sources remain unclear".')
    if signals.get("unverified_breakthrough_claim"):
        reasons.append(
            "It makes a breakthrough-style claim without naming credible institutions or evidence."
        )
    if signals.get("extraordinary_claim"):
        reasons.append("The statement makes an extraordinary promise that requires strong proof.")
    if signals.get("academic_style") and not signals.get("source_unclear"):
        reasons.append("The content uses research-style wording, but that alone is not sufficient proof.")

    if not reasons:
        reasons.append(f'Assessed as "{verdict}" after combining source evidence and classifier signals.')

    return reasons


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _deduplicate(sources: list[dict]) -> list[dict]:
    seen_urls = set()
    unique = []
    for source in sources:
        url = source.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(source)
    return unique


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------


def verify_claim_with_sources(
    text: str,
    signals: dict,
    source_url: str | None = None,
    source_title: str | None = None,
) -> dict:
    """
    Verify a claim by searching trusted sources and scoring evidence.

    Returns a dict ready to be serialized as JSON API response.
    """
    category = detect_claim_category(text)
    domains = CATEGORY_DOMAINS[category]
    search_claim = " ".join((text or "").split()[:12])

    sources: list[dict] = []
    verification_mode = "classifier_fallback"

    duckduckgo_available = True

    for domain in domains:
        if not duckduckgo_available:
            break
        try:
            results = _search_domain(search_claim, domain)
            sources.extend(results)
        except requests.exceptions.Timeout:
            logger.warning("DuckDuckGo search timed out; falling back to alternate source lookup.")
            duckduckgo_available = False
        except requests.exceptions.RequestException as error:
            logger.warning("DuckDuckGo search failed for %s", domain)
            logger.debug("DuckDuckGo error for %s: %s", domain, error)

    if not sources:
        sources = _brave_search(search_claim, domains)

    original_source = _build_original_source(source_url, source_title)
    if original_source:
        sources.insert(0, original_source)

    if sources:
        verification_mode = "trusted_source_first"
    else:
        sources = _build_fallback_links(search_claim, domains)
        verification_mode = "fallback_links_only"

    sources = _deduplicate(sources)

    real_sources = [source for source in sources if not source.get("is_fallback")]
    support_hits, refute_hits = _score_sources(real_sources)
    verdict, confidence = _compute_verdict(signals, support_hits, refute_hits, len(real_sources))

    return {
        "verdict": verdict,
        "confidence": round(confidence, 2),
        "source_verdict": verdict,
        "source_confidence": round(confidence, 2),
        "claim_category": category,
        "verification_mode": verification_mode,
        "source_evidence_count": len(real_sources),
        "support_signal_count": support_hits,
        "refute_signal_count": refute_hits,
        "trusted_sources": [
            {
                "title": source["title"],
                "url": source["url"],
                "source": source["source"],
                "snippet": source["snippet"],
                "is_fallback": source.get("is_fallback", False),
            }
            for source in sources
        ],
        "reason_summary": _build_reason_summary(verdict, signals, verification_mode, len(real_sources)),
    }
