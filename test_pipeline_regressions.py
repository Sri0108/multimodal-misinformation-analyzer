import os
import unittest
from unittest.mock import patch

from ml_pipeline.analyzer import analyze_content
from ml_pipeline.report_generator import generate_pdf_report
from ml_pipeline.source_verifier import verify_claim_with_sources


class PipelineRegressionTests(unittest.TestCase):
    def test_generate_pdf_report_returns_existing_absolute_path(self):
        result = {
            "prediction": "Likely Real",
            "confidence": 0.82,
            "manipulation_score": 0.05,
            "sentiment": "neutral",
            "explanation": ["Trusted sources support the claim."],
            "reason_summary": ["Found 1 trusted source from an authoritative publisher."],
            "signals": {"trusted_url": True},
            "trusted_sources": [
                {
                    "source": "timesofindia.indiatimes.com",
                    "title": "Original analyzed article",
                    "url": "https://timesofindia.indiatimes.com/example-story",
                    "snippet": "Original source URL from the analyzed input.",
                }
            ],
            "extracted_text": "The Indian Navy deployed five warships to support merchant vessels.",
        }

        report_path = generate_pdf_report(result, 99901)

        try:
            self.assertTrue(os.path.isabs(report_path))
            self.assertTrue(os.path.exists(report_path))
        finally:
            if os.path.exists(report_path):
                os.remove(report_path)

    @patch("ml_pipeline.source_verifier._search_domain", return_value=[])
    @patch("ml_pipeline.source_verifier._brave_search", return_value=[])
    def test_verify_claim_with_sources_includes_trusted_input_url(self, _mock_brave, _mock_search):
        verification = verify_claim_with_sources(
            "Navy deploys warships to guide cargo vessels through the Strait of Hormuz.",
            {"source_unclear": False},
            source_url="https://timesofindia.indiatimes.com/india/navy-deploys-warships/articleshow/123456.cms",
            source_title="Navy deploys warships",
        )

        self.assertEqual(verification["verification_mode"], "trusted_source_first")
        self.assertGreaterEqual(verification["source_evidence_count"], 1)
        self.assertEqual(
            verification["trusted_sources"][0]["source"],
            "timesofindia.indiatimes.com",
        )

    @patch("ml_pipeline.analyzer.detect_manipulation", return_value=0.08)
    @patch("ml_pipeline.analyzer.extract_text_from_image", return_value="No text found in image.")
    @patch("ml_pipeline.analyzer.os.path.exists", return_value=True)
    def test_analyze_content_reports_when_image_has_no_text(
        self,
        _mock_exists,
        _mock_extract,
        _mock_detect,
    ):
        result = analyze_content("image", "", "uploads/blank-image.png")

        self.assertEqual(result["prediction"], "No Text Detected")
        self.assertEqual(result["confidence"], 0.0)
        self.assertEqual(result["explanation"], ["No text found in image."])
        self.assertEqual(result["reason_summary"], ["No text found in image."])

    @patch("ml_pipeline.analyzer.final_fusion_decision", return_value=("Likely Fake", 0.77))
    @patch(
        "ml_pipeline.analyzer.classify_text",
        return_value={
            "prediction": "Likely Fake",
            "confidence": 0.7,
            "explanation": ["Screenshot text looked suspicious."],
            "scores": {"real_score": 0.28, "fake_score": 0.72},
        },
    )
    @patch(
        "ml_pipeline.analyzer.analyze_nlp",
        return_value={
            "sentiment": "negative",
            "signals": {"suspicious_keywords": 2},
            "risk_score": 0.7,
            "credibility_score": 0.2,
        },
    )
    @patch("ml_pipeline.analyzer.detect_manipulation", return_value=0.26)
    @patch(
        "ml_pipeline.analyzer.extract_text_from_image",
        return_value="Urgent OTP request shown on the captured banking screen.",
    )
    @patch("ml_pipeline.analyzer.os.path.exists", return_value=True)
    def test_analyze_content_supports_screenshot_content_type(
        self,
        _mock_exists,
        _mock_extract,
        _mock_detect,
        _mock_nlp,
        _mock_classify,
        _mock_fusion,
    ):
        result = analyze_content("screenshot", "", "uploads/captured-screen.png")

        self.assertEqual(result["prediction"], "Likely Fake")
        self.assertEqual(result["content_source"], "screenshot_ocr")
        self.assertEqual(result["manipulation_score"], 0.26)
        self.assertIn("Urgent OTP request shown on the captured banking screen.", result["extracted_text"])

    @patch("ml_pipeline.analyzer.final_fusion_decision", return_value=("Likely Real", 0.86))
    @patch(
        "ml_pipeline.analyzer.classify_text",
        return_value={
            "prediction": "Likely Real",
            "confidence": 0.8,
            "explanation": ["Transcript content aligned with trusted evidence."],
            "scores": {"real_score": 0.81, "fake_score": 0.19},
        },
    )
    @patch(
        "ml_pipeline.analyzer.verify_claim_with_sources",
        return_value={
            "reason_summary": ["Found supporting evidence from trusted publishers."],
            "trusted_sources": [{"source": "apnews.com", "url": "https://apnews.com/example"}],
            "claim_category": "general",
            "verification_mode": "classifier_fallback",
            "source_evidence_count": 1,
            "source_verdict": "Uncertain",
            "source_confidence": 0.5,
        },
    )
    @patch(
        "ml_pipeline.analyzer.analyze_nlp",
        return_value={
            "sentiment": "neutral",
            "signals": {"source_unclear": False},
            "risk_score": 0.25,
            "credibility_score": 0.68,
        },
    )
    @patch(
        "ml_pipeline.analyzer.extract_youtube_content",
        return_value={
            "video_id": "abc123xyz01",
            "url": "https://www.youtube.com/watch?v=abc123xyz01",
            "title": "Sample YouTube report",
            "author_name": "TruthCheck",
            "text": "Sample YouTube report Channel: TruthCheck Transcript text from the video.",
            "source_type": "youtube_transcript",
            "source_note": "",
        },
    )
    def test_analyze_content_supports_youtube_links(
        self,
        _mock_youtube,
        _mock_nlp,
        mock_verify,
        _mock_classify,
        _mock_fusion,
    ):
        result = analyze_content("youtube", "https://www.youtube.com/watch?v=abc123xyz01", None)

        self.assertEqual(result["prediction"], "Likely Real")
        self.assertEqual(result["content_source"], "youtube_transcript")
        self.assertIn("Transcript text from the video.", result["extracted_text"])
        mock_verify.assert_called_once()


if __name__ == "__main__":
    unittest.main()
