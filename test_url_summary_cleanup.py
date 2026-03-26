import unittest
from unittest.mock import patch

from ml_pipeline.ocr_module import _is_meaningful_word
from ml_pipeline.ocr_module import _normalize_ocr_text
from ml_pipeline.ocr_module import _ocr_score
from ml_pipeline.summary_module import summarize_text
from ml_pipeline.source_verifier import detect_claim_category
from ml_pipeline.url_module import fetch_and_extract_from_url
from ml_pipeline.url_module import trim_to_sentence_boundary


TOI_STYLE_HTML = """
<html>
  <head>
    <title>TOI - Breaking News, Latest News, India News | The Times of India</title>
    <meta name="description" content="Navy deploys 5 warships to guide cargo vessels exiting the troubled Strait of Hormuz." />
  </head>
  <body>
    <header>
      <div>TOI - Breaking News, Latest News, India News, World News</div>
      <div>Edition IN IN US GCC English Sign In Subscribe</div>
    </header>
    <nav>
      <a href="/city">City</a>
      <a href="/sports">Sports</a>
      <a href="/business">Business</a>
      <a href="/politics">Politics</a>
    </nav>
    <main role="main">
      <article>
        <h1>Op Urja Suraksha: Navy deploys 5 warships to guide cargo vessels exiting troubled Strait of Hormuz</h1>
        <p>
          The Indian Navy has deployed five warships to support merchant vessels
          leaving the Strait of Hormuz after regional tensions disrupted shipping traffic.
        </p>
        <p>
          Officials said the escort mission is focused on safe passage, maritime
          awareness, and rapid response if civilian cargo routes face new threats.
        </p>
        <p>
          The operation began after repeated warnings about risks to commercial
          traffic in the area and aims to reduce delays for outbound ships.
        </p>
      </article>
      <aside class="advertisement">
        Advertisement: Buy premium access now.
      </aside>
      <section class="related-links">
        <a href="/live">Watch live updates</a>
      </section>
    </main>
    <footer>Copyright 2026 Bennett Coleman &amp; Co. Subscribe now.</footer>
  </body>
</html>
"""


class MockResponse:
    def __init__(self, html):
        self.content = html.encode("utf-8")

    def raise_for_status(self):
        return None


class UrlSummaryCleanupTests(unittest.TestCase):
    @patch("ml_pipeline.url_module.requests.get")
    def test_fetch_and_extract_from_url_prefers_article_text_over_page_chrome(self, mock_get):
        mock_get.return_value = MockResponse(TOI_STYLE_HTML)

        result = fetch_and_extract_from_url("timesofindia.indiatimes.com/sample-story")

        self.assertEqual(result["source_type"], "webpage")
        self.assertIn("Navy deploys 5 warships", result["text"])
        self.assertIn("escort mission is focused on safe passage", result["text"])
        self.assertNotIn("Edition IN IN US GCC English Sign In Subscribe", result["text"])
        self.assertNotIn("Advertisement: Buy premium access now.", result["text"])
        self.assertNotIn("Watch live updates", result["text"])

    def test_summarize_text_filters_boilerplate_sentences(self):
        text = (
            "Subscribe to our newsletter for live updates. "
            "The Indian Navy deployed five warships to support merchant vessels leaving the Strait of Hormuz. "
            "Officials said the mission is focused on safe passage and rapid response for civilian cargo traffic. "
            "Advertisement: premium membership available now."
        )

        summary = summarize_text(text, max_sentences=2)

        self.assertIn("The Indian Navy deployed five warships", summary)
        self.assertIn("mission is focused on safe passage", summary)
        self.assertNotIn("Subscribe", summary)
        self.assertNotIn("Advertisement", summary)

    def test_summarize_text_avoids_raw_boilerplate_fallback(self):
        text = (
            "TOI Breaking News Latest News India News World News | Sign In | Subscribe\n"
            "The Indian Navy deployed five warships to support merchant vessels leaving the Strait of Hormuz\n"
            "Officials said the mission is focused on safe passage and rapid response for civilian cargo traffic\n"
        )

        summary = summarize_text(text)

        self.assertIn("The Indian Navy deployed five warships", summary)
        self.assertNotIn("TOI Breaking News", summary)
        self.assertNotIn("Subscribe", summary)

    def test_summarize_text_avoids_unrelated_late_teaser(self):
        text = (
            "Iran has opened the Strait of Hormuz for friendly nations like India, China, Russia, Iraq, and Pakistan. "
            "This comes as the United Nations urged an end to the conflict and the reopening of the vital waterway. "
            "The strait is a crucial oil route, and its volatility affects global energy flows amid regional tensions. "
            "Indian officials said the naval operation is aimed at keeping merchant traffic moving safely. "
            "Australia captain Pat Cummins is targeting a mid-IPL return after resuming bowling following a back injury."
        )

        summary = summarize_text(text, max_sentences=4)

        self.assertIn("Strait of Hormuz", summary)
        self.assertIn("naval operation", summary)
        self.assertNotIn("Pat Cummins", summary)

    def test_summarize_text_can_return_more_detailed_summary(self):
        text = (
            "The Indian Navy deployed five warships to support merchant vessels leaving the Strait of Hormuz after regional tensions disrupted shipping. "
            "Officials said the escort mission is focused on safe passage, maritime awareness, and rapid response for civilian cargo traffic. "
            "The operation began after repeated warnings about risks to commercial traffic in the area and aims to reduce outbound shipping delays. "
            "Government officials are coordinating with shipping operators to track vulnerable routes and share live advisories. "
            "Analysts said volatility in the strait can affect global energy flows because a large share of oil trade moves through the corridor. "
            "The latest deployment is intended to reassure commercial operators while the broader regional conflict remains unresolved."
        )

        summary = summarize_text(text, max_sentences=6)

        self.assertIn("escort mission is focused on safe passage", summary)
        self.assertIn("reduce outbound shipping delays", summary)
        self.assertIn("global energy flows", summary)

    def test_trim_to_sentence_boundary_does_not_return_half_sentence(self):
        text = (
            "Dhurandhar 2's massive success has sparked a stir, with Pakistani politician "
            "Nabeel Gabol finding himself in the spotlight. Initially enjoying the attention, "
            "he later clarified his remarks after the controversy grew."
        )

        trimmed = trim_to_sentence_boundary(text, 120)

        self.assertTrue(trimmed.endswith("."))
        self.assertNotIn("Initially enjoying", trimmed)

    def test_detect_claim_category_does_not_treat_plain_who_as_health(self):
        text = (
            "The actor praised the politician who found himself in the spotlight after the film's success."
        )

        category = detect_claim_category(text)

        self.assertEqual(category, "general")

    def test_summarize_text_is_dynamic_for_longer_inputs(self):
        short_text = (
            "Officials confirmed the advisory was issued late Tuesday evening. "
            "The operation focuses on safe passage for merchant vessels in the strait."
        )
        long_text = (
            "Officials confirmed the advisory was issued late Tuesday evening. "
            "The operation focuses on safe passage for merchant vessels in the strait. "
            "Naval teams are coordinating route updates, vessel guidance, and emergency responses across the corridor. "
            "Government officials said the deployment followed repeated warnings about attacks on commercial traffic. "
            "Energy analysts warned that prolonged disruption in the waterway could affect global oil flows and insurance costs. "
            "Shipping operators were told to follow revised transit guidance and maintain close communication with authorities. "
            "Regional diplomats meanwhile continued talks aimed at reducing the risk of further escalation in the area."
        )

        short_summary = summarize_text(short_text)
        long_summary = summarize_text(long_text)

        self.assertLess(len(short_summary), len(long_summary))
        self.assertIn("global oil flows", long_summary)

    def test_summarize_text_handles_headline_fragments_from_ocr(self):
        text = (
            "Netanyahu orders 48-hour blitz on Iran + Netanyahu's urgent strike order + "
            "Why Israel distrusts the US plan + Iran's outright rejection and counter-demands + "
            "Diverging endgames and long-term risks"
        )

        summary = summarize_text(text)

        self.assertIn("Netanyahu orders 48-hour blitz on Iran", summary)
        self.assertIn("Key points include", summary)
        self.assertIn("Iran's outright rejection", summary)

    def test_normalize_ocr_text_preserves_headline_delimiters(self):
        raw = "Curated by Copilot  -  15h   Netanyahu orders 48-hour blitz on Iran+Why Israel distrusts the US plan"

        normalized = _normalize_ocr_text(raw)

        self.assertIn("Netanyahu orders 48-hour blitz on Iran + Why Israel distrusts the US plan", normalized)

    def test_normalize_ocr_text_removes_ui_prefix_noise(self):
        raw = "M@ os +47 - Curated by Copilot - 15h Netanyahu orders 48-hour blitz on Iran"

        normalized = _normalize_ocr_text(raw)

        self.assertEqual(normalized, "Netanyahu orders 48-hour blitz on Iran")

    def test_normalize_ocr_text_drops_symbol_heavy_noise_lines(self):
        raw = (
            "'@~ +7 - Curated by Copilot - 15h\n"
            "Netanyahu orders 48-hour blitz on Iran\n"
            "SS \u2014$________________y\n"
            "+ Netanyahu's urgent strike order\n"
            "Why Israel distrusts the US plan\n"
            "__\u2014S\u2014=EEEEEEE\n"
        )

        normalized = _normalize_ocr_text(raw)

        self.assertIn("Netanyahu orders 48-hour blitz on Iran", normalized)
        self.assertIn("Why Israel distrusts the US plan", normalized)
        self.assertNotIn("SS", normalized)
        self.assertNotIn("EEEEEEE", normalized)

    def test_is_meaningful_word_filters_gibberish(self):
        self.assertTrue(_is_meaningful_word("Netanyahu"))
        self.assertFalse(_is_meaningful_word("Syyse"))
        self.assertFalse(_is_meaningful_word("ec"))

    def test_ocr_score_prefers_clean_headline_block_over_noisy_candidate(self):
        clean = (
            "Netanyahu orders 48-hour blitz on Iran\n"
            "+ Netanyahu's urgent strike order\n"
            "+ Why Israel distrusts the US plan\n"
            "+ Iran's outright rejection and counter-demands\n"
            "+ Diverging endgames and long-term risks"
        )
        noisy = (
            "Why Israel distrusts the US plan a ee \u2014 ie\n"
            "Iran's outright rejection and counter-demands be \u2014 *\n"
            "Diverging endgames and long-term risks ha os = ee (tae See weit PI] ie RT aie: a. SRR."
        )

        self.assertGreater(_ocr_score(clean), _ocr_score(noisy))

    def test_summarize_text_drops_noisy_ocr_prefix_and_gibberish_fragment(self):
        text = (
            "M@ os +47 - Curated by Copilot - 15h Netanyahu orders 48-hour blitz on Iran + "
            "Netanyahu's urgent strike order + iaiacathaiie ona aa ae + "
            "Iran's outright rejection and counter-demands + Diverging endgames and long-term risks"
        )

        summary = summarize_text(text)

        self.assertIn("Netanyahu orders 48-hour blitz on Iran", summary)
        self.assertIn("Iran's outright rejection and counter-demands", summary)
        self.assertNotIn("Curated by Copilot", summary)
        self.assertNotIn("iaiacathaiie", summary)

    def test_summarize_text_trims_ocr_garbage_before_real_headline(self):
        text = (
            "owe oe ec, Yam Syyse3 Netanyahu orders 48-hour blitz on Iran + "
            "Netanyahu's urgent strike order + Why Israel distrusts the US plan"
        )

        summary = summarize_text(text)

        self.assertTrue(summary.startswith("Netanyahu orders 48-hour blitz on Iran"))
        self.assertNotIn("owe oe ec", summary)
        self.assertNotIn("Yam Syyse3", summary)


if __name__ == "__main__":
    unittest.main()
