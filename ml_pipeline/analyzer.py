import os

from .deepfake_detector import detect_manipulation
from .document_module import extract_text_from_document
from .nlp_module import analyze_nlp
from .ocr_module import extract_text_from_image
from .source_verifier import verify_claim_with_sources
from .text_classifier import classify_text
from .url_module import fetch_and_extract_from_url
from .youtube_module import extract_youtube_content, is_youtube_url


def final_fusion_decision(result, nlp_result):
    risk = nlp_result.get("risk_score", 0)
    credibility = nlp_result.get("credibility_score", 0)
    base_conf = result.get("confidence", 0.5)
    signals = nlp_result.get("signals", {})

    if signals.get("unsupported_cure_claim"):
        risk = min(1.0, risk + 0.35)
    if signals.get("unverified_breakthrough_claim"):
        risk = min(1.0, risk + 0.25)
    if signals.get("extraordinary_claim"):
        risk = min(1.0, risk + 0.2)

    adjusted_real = base_conf + credibility - risk
    adjusted_fake = (1 - base_conf) + risk - (credibility / 2)

    adjusted_real = max(0.01, min(0.99, adjusted_real))
    adjusted_fake = max(0.01, min(0.99, adjusted_fake))

    if max(adjusted_real, adjusted_fake) < 0.55:
        return "Uncertain", max(adjusted_real, adjusted_fake)
    if adjusted_real >= adjusted_fake:
        return ("Real" if adjusted_real > 0.75 else "Likely Real"), adjusted_real
    return ("Fake" if adjusted_fake > 0.75 else "Likely Fake"), adjusted_fake


def analyze_content(content_type, content, file_path):
    result = {
        "prediction": "Uncertain",
        "confidence": 0.5,
        "manipulation_score": 0.0,
        "extracted_text": "",
        "sentiment": "neutral",
        "explanation": [],
        "content_source": "",
        "signals": {},
        "scores": {},
        "reason_summary": [],
        "trusted_sources": [],
        "claim_category": "general",
        "verification_mode": "classifier_fallback",
        "source_evidence_count": 0,
    }

    text = ""
    source_url = ""
    source_title = ""

    try:
        if content_type == "text":
            text = content or ""
            result["content_source"] = "direct_text"

        elif content_type == "url":
            if is_youtube_url(content or ""):
                youtube_data = extract_youtube_content(content)
                text = youtube_data.get("text", "")
                result["content_source"] = youtube_data.get("source_type", "youtube")
                source_url = youtube_data.get("url", "")
                source_title = youtube_data.get("title", "")
                if youtube_data.get("source_note"):
                    result["explanation"].append(youtube_data["source_note"])
            else:
            # FIX 1: Guard against None return from fetch_and_extract_from_url
                url_data = fetch_and_extract_from_url(content)

                if url_data is None:
                    result["prediction"] = "Error"
                    result["confidence"] = 0.0
                    result["explanation"] = [
                        "URL fetch returned no data. The page may be unreachable or blocked."
                    ]
                    return result

                # FIX 2: url_module returns "webpage" / "amp_cache" / "search_snippet" on success,
                # and "error" on failure. Accept all non-error source types as valid.
                if url_data.get("source_type") == "error":
                    raw_error = url_data.get("error", "") or url_data.get("text", "") or ""
                    raw_error_str = str(raw_error)

                    if "403" in raw_error_str:
                        friendly = (
                            "Access denied (403): This website blocks automated access. "
                            "Try pasting the article text directly instead."
                        )
                    elif "404" in raw_error_str:
                        friendly = (
                            "Page not found (404): The URL may be incorrect or the article has been removed."
                        )
                    elif "429" in raw_error_str:
                        friendly = "Rate limited (429): Too many requests to this site. Please try again shortly."
                    elif "timeout" in raw_error_str.lower() or "timed out" in raw_error_str.lower():
                        friendly = "Request timed out: The website took too long to respond."
                    elif "ssl" in raw_error_str.lower() or "certificate" in raw_error_str.lower():
                        friendly = "SSL error: Could not establish a secure connection to this website."
                    else:
                        friendly = f"Could not fetch the URL: {raw_error_str}"

                    result["prediction"] = "Error"
                    result["confidence"] = 0.0
                    result["explanation"] = [friendly]
                    return result

                # FIX 3: Even on "webpage" source_type, text can be an error string
                raw_text = url_data.get("text") or ""
                if raw_text.startswith("Unable to fetch URL:") or raw_text.startswith("Error processing URL:"):
                    result["prediction"] = "Error"
                    result["confidence"] = 0.0
                    result["explanation"] = [raw_text]
                    return result

                text = raw_text
                # Store which tier was used (webpage / amp_cache / search_snippet)
                result["content_source"] = url_data.get("source_type", "url")
                source_url = url_data.get("url", "")
                source_title = url_data.get("title", "")
                if url_data.get("source_note"):
                    result["explanation"].append(url_data["source_note"])

        elif content_type == "youtube":
            youtube_data = extract_youtube_content(content)
            text = youtube_data.get("text", "")
            result["content_source"] = youtube_data.get("source_type", "youtube")
            source_url = youtube_data.get("url", "")
            source_title = youtube_data.get("title", "")
            if youtube_data.get("source_note"):
                result["explanation"].append(youtube_data["source_note"])

        elif content_type in {"image", "screenshot"}:
            if file_path and os.path.exists(file_path):
                text = extract_text_from_image(file_path)
                result["manipulation_score"] = detect_manipulation(file_path)
                result["content_source"] = "screenshot_ocr" if content_type == "screenshot" else "image_ocr"

                if text == "No text found in image.":
                    result["prediction"] = "No Text Detected"
                    result["confidence"] = 0.0
                    result["explanation"] = [text]
                    result["reason_summary"] = [text]
                    return result

                if text.startswith("Image analysis (Tesseract not available):") or text.startswith("Image error:"):
                    result["prediction"] = "Error"
                    result["confidence"] = 0.0
                    result["explanation"] = [text]
                    result["reason_summary"] = [text]
                    return result

        elif content_type == "document":
            if file_path and os.path.exists(file_path):
                text = extract_text_from_document(file_path)

        if text and len(text.split()) > 5:
            result["extracted_text"] = text[:1600]

            if (
                text.startswith("Error ")
                or text.startswith("Unsupported file format")
                or text.startswith("File not found")
            ):
                result["prediction"] = "Error"
                result["confidence"] = 0.0
                result["explanation"] = [text]
                return result

            # FIX 4: Wrap each downstream call individually so one failure
            # doesn't crash the whole pipeline and wipe what was already computed.
            try:
                nlp_result = analyze_nlp(text)
            except Exception as nlp_error:
                nlp_result = {
                    "sentiment": "neutral",
                    "signals": {},
                    "risk_score": 0.5,
                    "credibility_score": 0.5,
                }
                result["explanation"].append(f"NLP analysis failed: {nlp_error}")

            result["sentiment"] = nlp_result.get("sentiment", "neutral")
            result["signals"] = nlp_result.get("signals", {})
            should_verify_sources = content_type in {"text", "url", "youtube"}

            if should_verify_sources:
                try:
                    verification = verify_claim_with_sources(
                        text,
                        result["signals"],
                        source_url=source_url,
                        source_title=source_title,
                    )
                except Exception as verify_error:
                    verification = {
                        "reason_summary": [f"Source verification failed: {verify_error}"],
                        "trusted_sources": [],
                        "claim_category": "general",
                        "verification_mode": "classifier_fallback",
                        "source_evidence_count": 0,
                        "source_verdict": "Uncertain",
                        "source_confidence": 0.5,
                    }

                result["reason_summary"] = verification.get("reason_summary", [])
                result["trusted_sources"] = verification.get("trusted_sources", [])
                result["claim_category"] = verification.get("claim_category", "general")
                result["verification_mode"] = verification.get("verification_mode", "classifier_fallback")
                result["source_evidence_count"] = verification.get("source_evidence_count", 0)

                if (
                    verification.get("verification_mode") == "trusted_source_first"
                    and verification.get("source_verdict", "Uncertain") != "Uncertain"
                ):
                    source_verdict = verification["source_verdict"]
                    source_confidence = verification.get("source_confidence", 0.5)
                    result["prediction"] = source_verdict
                    result["confidence"] = round(source_confidence, 2)
                    result["explanation"] = verification.get("reason_summary", [])
                    result["scores"] = {
                        "real_score": source_confidence if "Real" in source_verdict else 0.18,
                        "fake_score": source_confidence if "Fake" in source_verdict else 0.18,
                    }
                    return result

            try:
                classification = classify_text(text, nlp_result)
            except Exception as classify_error:
                classification = {
                    "prediction": "Uncertain",
                    "confidence": 0.5,
                    "explanation": [f"Classification failed: {classify_error}"],
                    "scores": {"real_score": 0.5, "fake_score": 0.5},
                }

            result.update({
                "prediction": classification.get("prediction", "Uncertain"),
                "confidence": classification.get("confidence", 0.5),
                "explanation": classification.get("explanation", []),
                "scores": classification.get("scores", {}),
            })

            final_label, final_conf = final_fusion_decision(result, nlp_result)
            result["prediction"] = final_label
            result["confidence"] = round(final_conf, 2)

            if not result["reason_summary"]:
                result["reason_summary"] = classification.get("explanation", [])

        else:
            result["explanation"] = [
                "Content too short or empty - the page may require a login or subscription."
            ]

    except Exception as error:
        result["prediction"] = "Error"
        result["confidence"] = 0.0
        result["explanation"] = [str(error)]

    return result
