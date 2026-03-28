import atexit
import io
import importlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from youtube_transcript_api._errors import RequestBlocked


TEST_ROOT = Path(tempfile.mkdtemp(prefix="mma_case_tests_"))
TEST_DB_PATH = TEST_ROOT / "test_app.db"
TEST_UPLOAD_DIR = TEST_ROOT / "uploads"
TEST_REPORT_DIR = TEST_ROOT / "reports"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["UPLOAD_FOLDER"] = str(TEST_UPLOAD_DIR)
os.environ["REPORT_FOLDER"] = str(TEST_REPORT_DIR)
os.environ["SEED_DEFAULT_ADMIN"] = "false"
os.environ["JWT_COOKIE_SECURE"] = "false"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret"

atexit.register(lambda: shutil.rmtree(TEST_ROOT, ignore_errors=True))

backend_app_module = importlib.import_module("backend.app")
backend_app_module = importlib.reload(backend_app_module)

from ml_pipeline.analyzer import analyze_content
from ml_pipeline.deepfake_detector import detect_manipulation
from ml_pipeline.document_module import extract_text_from_document
from ml_pipeline.nlp_module import analyze_nlp
from ml_pipeline.ocr_module import extract_text_from_image
from ml_pipeline.report_generator import generate_pdf_report
from ml_pipeline.source_verifier import verify_claim_with_sources
from ml_pipeline.summary_module import summarize_text
from ml_pipeline.text_classifier import classify_text
from ml_pipeline.youtube_module import (
    _transcript_chunks_to_text,
    build_youtube_summary_unavailable_message,
    extract_youtube_text,
    get_youtube_text_for_summary,
)

app = backend_app_module.app
db = backend_app_module.db
User = backend_app_module.User
Input = backend_app_module.Input
Report = backend_app_module.Report


class InMemoryUpload(io.BytesIO):
    def __init__(self, payload, filename, mimetype):
        super().__init__(payload)
        self.filename = filename
        self.mimetype = mimetype


class BackendUnitTests(unittest.TestCase):
    def test_ut_01_allowed_file_accepts_pdf(self):
        self.assertTrue(backend_app_module.allowed_file("evidence.pdf"))

    def test_ut_02_validate_file_rejects_files_over_10mb(self):
        oversized = InMemoryUpload(b"x" * (11 * 1024 * 1024), "large.pdf", "application/pdf")

        is_valid, message = backend_app_module.validate_file(oversized)

        self.assertFalse(is_valid)
        self.assertIn("10MB", message)

    @patch("ml_pipeline.document_module.extract_from_docx", return_value="docx text")
    @patch("ml_pipeline.document_module.extract_from_pdf", return_value="pdf text")
    @patch("ml_pipeline.document_module.extract_from_txt", return_value="txt text")
    @patch("ml_pipeline.document_module.os.path.exists", return_value=True)
    def test_ut_03_extract_text_from_document_dispatches_supported_types(
        self,
        _mock_exists,
        _mock_txt,
        _mock_pdf,
        _mock_docx,
    ):
        cases = {
            "sample.docx": "docx text",
            "sample.pdf": "pdf text",
            "sample.txt": "txt text",
        }

        for file_name, expected in cases.items():
            with self.subTest(file_name=file_name):
                self.assertEqual(extract_text_from_document(file_name), expected)

    @patch("ml_pipeline.ocr_module._best_ocr_text", return_value="Visible text from image")
    @patch("ml_pipeline.ocr_module.Image.open")
    @patch("ml_pipeline.ocr_module._configure_tesseract")
    def test_ut_04_extract_text_from_image_returns_ocr_string(
        self,
        _mock_configure,
        mock_open,
        _mock_best_text,
    ):
        mock_open.return_value = object()

        result = extract_text_from_image("sample.png")

        self.assertEqual(result, "Visible text from image")

    def test_ut_05_detect_manipulation_returns_score_between_zero_and_one(self):
        image_path = TEST_ROOT / "manipulation_input.png"
        Image.new("RGB", (8, 8), color=(120, 80, 40)).save(image_path)

        score = detect_manipulation(str(image_path))

        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_ut_06_analyze_nlp_flags_scam_message_as_high_risk(self):
        result = analyze_nlp(
            "Urgent! Click here now to claim free money and send OTP immediately via bit.ly link."
        )

        self.assertGreaterEqual(result["risk_score"], 0.5)
        self.assertGreater(result["signals"]["suspicious_keywords"], 0)
        self.assertGreater(result["signals"]["malicious_url_count"], 0)

    @patch("ml_pipeline.source_verifier._brave_search", return_value=[])
    @patch("ml_pipeline.source_verifier._search_domain", return_value=[])
    def test_ut_07_verify_claim_with_sources_targets_health_domains(
        self,
        mock_search_domain,
        _mock_brave_search,
    ):
        verify_claim_with_sources(
            "Vitamin C cures covid in 24 hours.",
            {"source_unclear": False, "unsupported_cure_claim": True},
        )

        searched_domains = [call.args[1] for call in mock_search_domain.call_args_list]
        self.assertIn("cdc.gov", searched_domains)
        self.assertIn("nih.gov", searched_domains)

    def test_ut_08_classify_text_boosts_formal_academic_content(self):
        text = (
            "According to the published study, researchers reported data from a peer-reviewed journal. "
            "The methodology section and official statement support the findings."
        )

        nlp_result = analyze_nlp(text)
        result = classify_text(text, nlp_result)

        self.assertIn(result["prediction"], {"Real", "Likely Real"})
        self.assertGreater(result["scores"]["real_score"], result["scores"]["fake_score"])

    def test_ut_09_summarize_text_returns_extractive_summary(self):
        text = (
            "The ministry issued a public advisory on Tuesday. "
            "Officials said the guidance was based on a new safety review. "
            "The report recommends additional monitoring in affected areas."
        )

        summary = summarize_text(text, max_sentences=2)

        self.assertIn("The ministry issued a public advisory", summary)
        self.assertTrue(len(summary) > 20)

    def test_ut_10_generate_pdf_report_creates_file(self):
        result = {
            "prediction": "Likely Real",
            "confidence": 0.83,
            "manipulation_score": 0.08,
            "sentiment": "neutral",
            "explanation": ["Trusted sources support the claim."],
            "reason_summary": ["Found supporting evidence from trusted sources."],
            "signals": {"trusted_url": True},
            "trusted_sources": [],
            "extracted_text": "Sample extracted text for PDF generation.",
        }

        report_path = generate_pdf_report(result, 70001)

        try:
            self.assertTrue(os.path.exists(report_path))
            self.assertTrue(report_path.lower().endswith(".pdf"))
        finally:
            if os.path.exists(report_path):
                os.remove(report_path)

    @patch("ml_pipeline.youtube_module._fetch_oembed_metadata", return_value={"title": "Sample video", "author_name": "TruthCheck"})
    @patch(
        "ml_pipeline.youtube_module._fetch_transcript",
        return_value=("Transcript text from the YouTube video.", "english", "en"),
    )
    def test_ut_11_extract_youtube_text_returns_transcript_content(
        self,
        _mock_transcript,
        _mock_metadata,
    ):
        text = extract_youtube_text("https://www.youtube.com/watch?v=abc123xyz01")

        self.assertIn("Sample video", text)
        self.assertIn("Transcript text from the YouTube video.", text)

    def test_ut_12_get_youtube_text_for_summary_strips_title_and_channel_prefix(self):
        cleaned = get_youtube_text_for_summary(
            {
                "title": "Poochta Hai Bharat: Did Iran Attack First?",
                "author_name": "Republic Bharat",
                "text": (
                    "Poochta Hai Bharat: Did Iran Attack First? "
                    "Channel: Republic Bharat "
                    "Tonight we examine the available evidence and competing claims."
                ),
            }
        )

        self.assertEqual(
            cleaned,
            "Tonight we examine the available evidence and competing claims.",
        )

    def test_ut_13_build_youtube_summary_unavailable_message_explains_why(self):
        message = build_youtube_summary_unavailable_message(
            {
                "title": "Will Iran War Situation Result In Fuel Lockdown In India?",
                "transcript_error": "No English transcript or translatable transcript was available for this video.",
                "fallback_error": "audio transcription fallback is unavailable because yt-dlp is not installed.",
            }
        )

        self.assertIn('Summary unavailable for "Will Iran War Situation Result In Fuel Lockdown In India?"', message)
        self.assertIn("Usable English captions were not available for this video.", message)
        self.assertIn("Audio transcription is not enabled on this server.", message)

    def test_ut_14_build_youtube_summary_unavailable_message_avoids_false_no_captions_claim(self):
        message = build_youtube_summary_unavailable_message(
            {
                "title": "Breaking Update",
                "transcript_error": "YouTube did not return a usable transcript for this video",
            }
        )

        self.assertIn('Summary unavailable for "Breaking Update"', message)
        self.assertIn("YouTube did not return a usable transcript for this video.", message)
        self.assertNotIn("does not provide captions", message.lower())

    def test_ut_15_transcript_chunk_conversion_supports_object_snippets(self):
        text = _transcript_chunks_to_text(
            [
                SimpleNamespace(text="First line"),
                SimpleNamespace(text="Second line"),
            ]
        )

        self.assertEqual(text, "First line Second line")

    @patch("ml_pipeline.youtube_module._fetch_oembed_metadata", return_value={"title": "Render video", "author_name": "Reuters"})
    @patch("ml_pipeline.youtube_module.yt_dlp", new=object())
    @patch(
        "ml_pipeline.youtube_module._fetch_ytdlp_subtitles",
        return_value=("Recovered subtitle text from yt-dlp.", "yt_dlp_subtitles", "en"),
    )
    @patch(
        "ml_pipeline.youtube_module._fetch_transcript",
        side_effect=RequestBlocked("abc123xyz01"),
    )
    def test_ut_16_extract_youtube_text_falls_back_to_ytdlp_subtitles_when_transcript_api_is_blocked(
        self,
        _mock_transcript,
        _mock_ytdlp_subtitles,
        _mock_metadata,
    ):
        text = extract_youtube_text("https://www.youtube.com/watch?v=abc123xyz01")

        self.assertIn("Render video", text)
        self.assertIn("Recovered subtitle text from yt-dlp.", text)

    @patch("ml_pipeline.youtube_module._fetch_oembed_metadata", return_value={"title": "Documentary", "author_name": "DW"})
    @patch(
        "ml_pipeline.youtube_module._fetch_ytdlp_description_metadata",
        return_value={
            "title": "Documentary",
            "author_name": "DW Documentary",
            "description": (
                "This documentary examines how fake news, propaganda, and conspiracy theories spread online "
                "and how journalists, researchers, and fact-checkers respond to disinformation campaigns."
            ),
        },
    )
    @patch("ml_pipeline.youtube_module.yt_dlp", new=object())
    @patch(
        "ml_pipeline.youtube_module._fetch_ytdlp_subtitles",
        side_effect=ValueError("yt-dlp could not retrieve usable subtitle text for this video."),
    )
    @patch(
        "ml_pipeline.youtube_module._fetch_transcript",
        side_effect=RequestBlocked("abc123xyz01"),
    )
    def test_ut_17_extract_youtube_content_uses_description_fallback_when_transcripts_are_unavailable(
        self,
        _mock_transcript,
        _mock_ytdlp_subtitles,
        _mock_description,
        _mock_metadata,
    ):
        from ml_pipeline.youtube_module import extract_youtube_content

        result = extract_youtube_content("https://www.youtube.com/watch?v=abc123xyz01")

        self.assertEqual(result["source_type"], "youtube_metadata")
        self.assertEqual(result["metadata_basis"], "description")
        self.assertIn("fake news, propaganda, and conspiracy theories", result["summary_text"].lower())

    @patch("ml_pipeline.youtube_module._fetch_oembed_metadata", return_value={"title": "Hosted video", "author_name": "News18"})
    @patch(
        "ml_pipeline.youtube_module._fetch_watch_page_metadata",
        return_value={
            "description": (
                "This report examines whether India could play a diplomatic role in the Iran war crisis "
                "after calls between Prime Minister Narendra Modi, US President Donald Trump, and Iran's president."
            )
        },
    )
    @patch(
        "ml_pipeline.youtube_module._fetch_ytdlp_description_metadata",
        side_effect=ValueError("yt-dlp metadata extraction failed"),
    )
    @patch("ml_pipeline.youtube_module.yt_dlp", new=object())
    @patch(
        "ml_pipeline.youtube_module._fetch_ytdlp_subtitles",
        side_effect=ValueError("yt-dlp could not retrieve usable subtitle text for this video."),
    )
    @patch(
        "ml_pipeline.youtube_module._fetch_transcript",
        side_effect=RequestBlocked("abc123xyz01"),
    )
    def test_ut_18_extract_youtube_content_uses_watch_page_description_when_ytdlp_metadata_fails(
        self,
        _mock_transcript,
        _mock_ytdlp_subtitles,
        _mock_description_metadata,
        _mock_watch_page,
        _mock_metadata,
    ):
        from ml_pipeline.youtube_module import extract_youtube_content

        result = extract_youtube_content("https://www.youtube.com/watch?v=abc123xyz01")

        self.assertEqual(result["source_type"], "youtube_metadata")
        self.assertEqual(result["metadata_basis"], "description")
        self.assertIn("diplomatic role in the iran war crisis", result["summary_text"].lower())


class SystemFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def setUp(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.create_all()

    def create_user(self, email, username, password, role="user"):
        with app.app_context():
            user = User(
                email=email,
                username=username,
                password=backend_app_module.generate_password_hash(password),
                role=role,
            )
            db.session.add(user)
            db.session.commit()
            return user.id

    def auth_headers(self, user_id):
        return {"Authorization": f"Bearer {user_id}"}

    def test_st_01_register_and_login_flow_returns_token_and_user(self):
        register_response = self.client.post(
            "/api/register",
            json={"email": "caseuser@example.com", "username": "caseuser", "password": "CasePass123!"},
        )
        login_response = self.client.post(
            "/api/login",
            json={"email": "caseuser@example.com", "password": "CasePass123!"},
        )

        self.assertEqual(register_response.status_code, 200)
        self.assertEqual(login_response.status_code, 200)
        payload = login_response.get_json()
        self.assertIn("user", payload)
        self.assertIn("Set-Cookie", login_response.headers)
        self.assertIn("HttpOnly", login_response.headers["Set-Cookie"])

    def test_st_01b_login_session_and_logout_invalidate_cookie_session(self):
        self.client.post(
            "/api/register",
            json={"email": "sessionuser@example.com", "username": "sessionuser", "password": "CasePass123!"},
        )

        login_response = self.client.post(
            "/api/login",
            json={"email": "sessionuser@example.com", "password": "CasePass123!"},
        )
        self.assertEqual(login_response.status_code, 200)

        session_response = self.client.get("/api/session")
        self.assertEqual(session_response.status_code, 200)
        self.assertTrue(session_response.get_json()["authenticated"])

        logout_response = self.client.post("/api/logout")
        self.assertEqual(logout_response.status_code, 200)

        post_logout_session = self.client.get("/api/session")
        self.assertEqual(post_logout_session.status_code, 401)

    @patch("backend.app.analyze_content")
    def test_st_02_submit_suspicious_health_text_claim(self, mock_analyze):
        user_id = self.create_user("health@example.com", "healthuser", "CasePass123!")
        mock_analyze.return_value = {
            "prediction": "Likely Fake",
            "confidence": 0.88,
            "manipulation_score": 0.0,
            "explanation": ["Unsupported cure claim detected."],
            "reason_summary": ["Health claim lacks strong authority evidence."],
            "trusted_sources": [{"source": "cdc.gov", "url": "https://www.cdc.gov"}],
        }

        response = self.client.post(
            "/api/analyze",
            json={
                "content_type": "text",
                "content": "Drinking garlic water cures covid overnight.",
            },
            headers=self.auth_headers(user_id),
        )

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("reason_summary", payload["result"])
        self.assertIn("trusted_sources", payload["result"])

    @patch("backend.app.analyze_content")
    def test_st_03_submit_news_article_url(self, mock_analyze):
        user_id = self.create_user("url@example.com", "urluser", "CasePass123!")
        mock_analyze.return_value = {
            "prediction": "Likely Real",
            "confidence": 0.81,
            "manipulation_score": 0.0,
            "content_source": "webpage",
            "explanation": ["Trusted publisher source found."],
        }

        response = self.client.post(
            "/api/analyze",
            json={
                "content_type": "url",
                "content": "https://www.reuters.com/world/example-story",
            },
            headers=self.auth_headers(user_id),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["result"]["prediction"], "Likely Real")

    @patch("backend.app.analyze_content")
    def test_st_03b_submit_youtube_link(self, mock_analyze):
        user_id = self.create_user("youtube@example.com", "ytuser", "CasePass123!")
        mock_analyze.return_value = {
            "prediction": "Likely Real",
            "confidence": 0.8,
            "manipulation_score": 0.0,
            "content_source": "youtube_transcript",
            "extracted_text": "Transcript text from the linked video.",
            "explanation": ["YouTube transcript extracted successfully."],
        }

        response = self.client.post(
            "/api/analyze",
            json={
                "content_type": "youtube",
                "content": "https://www.youtube.com/watch?v=abc123xyz01",
            },
            headers=self.auth_headers(user_id),
        )

        self.assertEqual(response.status_code, 200)
        with app.app_context():
            saved_input = Input.query.order_by(Input.id.desc()).first()
            self.assertEqual(saved_input.content_type, "youtube")
            self.assertEqual(saved_input.content, "https://www.youtube.com/watch?v=abc123xyz01")

    @patch("backend.app.analyze_content")
    def test_st_04_upload_image_with_embedded_text(self, mock_analyze):
        user_id = self.create_user("image@example.com", "imageuser", "CasePass123!")
        mock_analyze.return_value = {
            "prediction": "Likely Fake",
            "confidence": 0.74,
            "manipulation_score": 0.36,
            "extracted_text": "Suspicious message extracted from screenshot.",
            "explanation": ["OCR text and manipulation score returned."],
        }

        response = self.client.post(
            "/api/analyze",
            data={
                "content_type": "image",
                "file": (io.BytesIO(b"fake image bytes"), "sample.png"),
            },
            headers=self.auth_headers(user_id),
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["result"]
        self.assertIn("extracted_text", payload)
        self.assertIn("manipulation_score", payload)

    @patch("backend.app.analyze_content")
    def test_st_04b_upload_screenshot_with_embedded_text(self, mock_analyze):
        user_id = self.create_user("screen@example.com", "screenuser", "CasePass123!")
        mock_analyze.return_value = {
            "prediction": "Likely Fake",
            "confidence": 0.76,
            "manipulation_score": 0.31,
            "content_source": "screenshot_ocr",
            "extracted_text": "Screenshot text extracted via OCR.",
            "explanation": ["Screenshot OCR and manipulation score returned."],
        }

        response = self.client.post(
            "/api/analyze",
            data={
                "content_type": "screenshot",
                "file": (io.BytesIO(b"fake screenshot bytes"), "sample.png"),
            },
            headers=self.auth_headers(user_id),
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["result"]
        self.assertEqual(payload["content_source"], "screenshot_ocr")
        with app.app_context():
            saved_input = Input.query.order_by(Input.id.desc()).first()
            self.assertEqual(saved_input.content_type, "screenshot")

    @patch("backend.app.analyze_content")
    def test_st_05_upload_pdf_document(self, mock_analyze):
        user_id = self.create_user("doc@example.com", "docuser", "CasePass123!")
        mock_analyze.return_value = {
            "prediction": "Likely Real",
            "confidence": 0.79,
            "manipulation_score": 0.0,
            "explanation": ["Document text classified successfully."],
        }

        response = self.client.post(
            "/api/analyze",
            data={
                "content_type": "document",
                "file": (io.BytesIO(b"%PDF-1.4 fake"), "sample.pdf"),
            },
            headers=self.auth_headers(user_id),
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("prediction", response.get_json()["result"])

    def test_st_06_generate_summary_for_saved_input(self):
        user_id = self.create_user("summary@example.com", "summaryuser", "CasePass123!")
        with app.app_context():
            input_record = Input(
                user_id=user_id,
                content_type="text",
                content=(
                    "Officials confirmed the advisory was issued on Tuesday. "
                    "The ministry recommended added safety checks across the corridor."
                ),
            )
            db.session.add(input_record)
            db.session.commit()
            input_id = input_record.id

        response = self.client.post(f"/api/input/{input_id}/summary", headers=self.auth_headers(user_id))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["summary"])

    @patch(
        "backend.app.extract_youtube_content",
        return_value={
            "video_id": "abc123xyz01",
            "url": "https://www.youtube.com/watch?v=abc123xyz01",
            "title": "Did Iran Attack First?",
            "author_name": "Republic Bharat",
            "text": "Did Iran Attack First? Channel: Republic Bharat",
            "summary_text": "",
            "source_type": "youtube_metadata",
            "source_note": "",
            "transcript_error": "No English transcript or translatable transcript was available for this video.",
            "fallback_error": "audio transcription fallback is unavailable because yt-dlp is not installed.",
        },
    )
    def test_st_06b_generate_summary_reports_metadata_only_youtube_honestly(self, _mock_youtube):
        user_id = self.create_user("youtube-summary@example.com", "ytsummary", "CasePass123!")
        with app.app_context():
            input_record = Input(
                user_id=user_id,
                content_type="youtube",
                content="https://www.youtube.com/watch?v=abc123xyz01",
            )
            db.session.add(input_record)
            db.session.commit()
            input_id = input_record.id

        response = self.client.post(f"/api/input/{input_id}/summary", headers=self.auth_headers(user_id))

        self.assertEqual(response.status_code, 200)
        summary = response.get_json()["summary"]
        self.assertIn('Summary unavailable for "Did Iran Attack First?"', summary)
        self.assertIn("Usable English captions were not available for this video.", summary)
        self.assertIn("Audio transcription is not enabled on this server.", summary)

    @patch(
        "backend.app.extract_youtube_content",
        return_value={
            "video_id": "abc123xyz01",
            "url": "https://www.youtube.com/watch?v=abc123xyz01",
            "title": "Fake news, propaganda, and conspiracy theories",
            "author_name": "DW Documentary",
            "text": (
                "Fake news, propaganda, and conspiracy theories Channel: DW Documentary "
                "This documentary examines how fake news, propaganda, and conspiracy theories spread online "
                "and how journalists, researchers, and fact-checkers respond to disinformation campaigns."
            ),
            "summary_text": (
                "This documentary examines how fake news, propaganda, and conspiracy theories spread online "
                "and how journalists, researchers, and fact-checkers respond to disinformation campaigns."
            ),
            "source_type": "youtube_metadata",
            "metadata_basis": "description",
            "source_note": "A usable transcript was not available, so the analysis used the video's public description as a fallback source.",
            "transcript_error": "YouTube did not return a usable transcript for this video",
            "fallback_error": "transformers is not installed for audio transcription.",
        },
    )
    def test_st_06c_generate_summary_uses_youtube_description_fallback(self, _mock_youtube):
        user_id = self.create_user("youtube-description@example.com", "ytdescription", "CasePass123!")
        with app.app_context():
            input_record = Input(
                user_id=user_id,
                content_type="youtube",
                content="https://www.youtube.com/watch?v=abc123xyz01",
            )
            db.session.add(input_record)
            db.session.commit()
            input_id = input_record.id

        response = self.client.post(f"/api/input/{input_id}/summary", headers=self.auth_headers(user_id))

        self.assertEqual(response.status_code, 200)
        summary = response.get_json()["summary"]
        self.assertIn("fake news, propaganda, and conspiracy theories spread online", summary.lower())
        self.assertIn("video's public description", summary)
        self.assertNotIn("Summary unavailable", summary)

    @patch("backend.app.analyze_content")
    def test_st_07_generate_pdf_report(self, mock_analyze):
        user_id = self.create_user("report@example.com", "reportuser", "CasePass123!")
        with app.app_context():
            input_record = Input(
                user_id=user_id,
                content_type="text",
                content="Verified sample content for report generation.",
            )
            db.session.add(input_record)
            db.session.commit()
            input_id = input_record.id

        mock_analyze.return_value = {
            "prediction": "Likely Real",
            "confidence": 0.84,
            "manipulation_score": 0.0,
            "sentiment": "neutral",
            "explanation": ["Trusted sources support the claim."],
            "reason_summary": ["Trusted sources support the claim."],
            "signals": {},
            "trusted_sources": [],
            "extracted_text": "Verified sample content for report generation.",
        }

        response = self.client.post(f"/api/input/{input_id}/report", headers=self.auth_headers(user_id))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("report_url", payload)
        self.assertTrue(payload["report_url"].startswith("/api/report/"))

    def test_st_08_admin_dashboard_endpoints_are_visible_to_admin(self):
        admin_id = self.create_user("admin@example.com", "adminuser", "CasePass123!", role="admin")
        normal_user_id = self.create_user("member@example.com", "member", "CasePass123!", role="user")

        with app.app_context():
            input_record = Input(
                user_id=normal_user_id,
                content_type="text",
                content="Saved content for admin listing.",
            )
            db.session.add(input_record)
            db.session.commit()

            report = Report(
                input_id=input_record.id,
                prediction="Likely Real",
                confidence=0.82,
                manipulation_score=0.0,
                report_path=str(TEST_REPORT_DIR / "sample.pdf"),
            )
            db.session.add(report)
            db.session.commit()

        overview_response = self.client.get("/api/admin/overview", headers=self.auth_headers(admin_id))
        inputs_response = self.client.get("/api/admin/inputs", headers=self.auth_headers(admin_id))
        reports_response = self.client.get("/api/admin/reports", headers=self.auth_headers(admin_id))

        self.assertEqual(overview_response.status_code, 200)
        self.assertEqual(inputs_response.status_code, 200)
        self.assertEqual(reports_response.status_code, 200)
        self.assertIn("stats", overview_response.get_json())
        self.assertTrue(isinstance(inputs_response.get_json(), list))
        self.assertTrue(isinstance(reports_response.get_json(), list))

    @patch("backend.app.fetch_top_fake_news")
    def test_st_09_fetch_fake_news_feed(self, mock_feed):
        mock_feed.return_value = [
            {
                "title": "Fact-check roundup",
                "url": "https://www.snopes.com/example",
                "source": "Snopes",
                "summary": "Latest fact-check items displayed in dashboard",
                "published_at": "2026-03-28T00:00:00+00:00",
            }
        ]

        response = self.client.get("/api/top-fake-news")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["source"], "Snopes")


if __name__ == "__main__":
    unittest.main()
