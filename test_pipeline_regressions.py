import os
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
