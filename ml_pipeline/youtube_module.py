import json
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    PoTokenRequired,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    from transformers import pipeline
except Exception:
    pipeline = None


OEMBED_URL = "https://www.youtube.com/oembed"
ENGLISH_TRANSCRIPT_LANGUAGES = ("en", "en-US", "en-GB", "en-IN", "en-CA", "en-AU", "a.en")
YOUTUBE_ASR_MODEL_NAME = "openai/whisper-small"
_ASR_PIPELINE = None
_ASR_PIPELINE_ERROR = None


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _friendly_transcript_error(error):
    message = clean_text(str(error))
    lowered = message.lower()

    if isinstance(error, TranscriptsDisabled):
        return "the video owner disabled transcripts"
    if isinstance(error, VideoUnavailable):
        return "the video is unavailable"
    if isinstance(error, (PoTokenRequired, RequestBlocked)):
        return "YouTube blocked transcript retrieval for this video on this server"
    if isinstance(error, CouldNotRetrieveTranscript):
        return "YouTube did not return a usable transcript for this video"
    if isinstance(error, NoTranscriptFound):
        return "YouTube did not return a usable transcript for this video"

    if "list_transcripts" in lowered or "transcript-list api" in lowered:
        return "the installed YouTube transcript library version changed its transcript-list API"
    if "no english transcript" in lowered:
        return "no English transcript or translatable transcript was available"
    if "transcript is disabled" in lowered:
        return "the video owner disabled transcripts"
    if "captions are available" in lowered:
        return "captions were found, but no usable English or translatable transcript could be produced"
    if "no transcripts were found" in lowered or "could not retrieve transcript" in lowered:
        return "YouTube did not return a usable transcript for this video"
    if "video unavailable" in lowered:
        return "the video is unavailable"
    if "request blocked" in lowered or "po token" in lowered:
        return "YouTube blocked transcript retrieval for this video on this server"

    return message or "the transcript could not be retrieved"


def _friendly_summary_reason(error, reason_type):
    message = clean_text(str(error))
    lowered = message.lower()

    if reason_type == "transcript":
        if "no english transcript" in lowered or "translatable transcript" in lowered:
            return "Usable English captions were not available for this video"
        if "transcript is disabled" in lowered:
            return "The video owner has disabled captions for this video"
        if "captions were found" in lowered:
            return "Captions were found, but a usable English transcript could not be produced"
        if "youtube did not return a usable transcript" in lowered or "no transcripts were found" in lowered:
            return "YouTube did not return a usable transcript for this video"
        if "video unavailable" in lowered:
            return "This video is currently unavailable"
        if "blocked transcript retrieval" in lowered or "request blocked" in lowered or "po token" in lowered:
            return "YouTube blocked transcript retrieval for this video on this server"
        if "library version changed" in lowered or "transcript-list api" in lowered:
            return "Caption retrieval is temporarily unavailable on this server"
        return "A usable transcript could not be retrieved for this video"

    if "yt-dlp is not installed" in lowered or "audio transcription fallback is unavailable" in lowered:
        return "Audio transcription is not enabled on this server"
    if "transformers is not installed" in lowered:
        return "Audio transcription support is not installed on this server"
    if "ffmpeg" in lowered:
        return "Audio transcription could not start because ffmpeg is missing on this server"
    if "empty text" in lowered:
        return "Audio transcription did not return enough speech to summarize"
    if "could not download" in lowered:
        return "The server could not download audio for transcription"
    return "Audio transcription could not be completed for this video"


def is_youtube_url(url):
    parsed = urlparse((url or "").strip())
    host = parsed.netloc.lower()
    return host in {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
    }


def extract_youtube_video_id(url):
    parsed = urlparse((url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid YouTube URL")

    host = parsed.netloc.lower()
    if host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/", 1)[0]
        if video_id:
            return video_id

    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
            if video_id:
                return video_id

        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live", "v"}:
            return path_parts[1]

    raise ValueError("Invalid YouTube URL")


def _transcript_chunks_to_text(transcript_chunks):
    parts = []
    for chunk in transcript_chunks:
        if isinstance(chunk, dict):
            text = chunk.get("text", "")
        else:
            text = getattr(chunk, "text", "")
        cleaned = clean_text(text)
        if cleaned:
            parts.append(cleaned)
    return clean_text(" ".join(parts))


def _language_code_is_englishish(language_code):
    normalized = clean_text(language_code).lower()
    return normalized.startswith("en") or normalized.endswith(".en")


def _subtitle_format_priority(entry):
    ext = clean_text(entry.get("ext", "")).lower()
    preference = {
        "json3": 0,
        "json": 1,
        "vtt": 2,
        "srv3": 3,
        "srv2": 4,
        "srv1": 5,
        "ttml": 6,
        "xml": 7,
    }
    return preference.get(ext, 50), ext


def _parse_json_subtitle_payload(payload):
    try:
        data = json.loads(payload)
    except Exception:
        return ""

    if isinstance(data, dict) and isinstance(data.get("events"), list):
        parts = []
        for event in data["events"]:
            for segment in event.get("segs", []) or []:
                cleaned = clean_text(segment.get("utf8", ""))
                if cleaned:
                    parts.append(cleaned)
        return clean_text(" ".join(parts))

    if isinstance(data, list):
        parts = []
        for item in data:
            cleaned = clean_text((item or {}).get("text", ""))
            if cleaned:
                parts.append(cleaned)
        return clean_text(" ".join(parts))

    return ""


def _parse_vtt_subtitle_payload(payload):
    lines = []
    for raw_line in payload.splitlines():
        line = clean_text(raw_line)
        if not line:
            continue
        if line.upper().startswith("WEBVTT"):
            continue
        if "-->" in line:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        line = re.sub(r"<[^>]+>", " ", line)
        line = clean_text(line)
        if line:
            lines.append(line)
    return clean_text(" ".join(lines))


def _parse_xml_subtitle_payload(payload):
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return ""

    parts = []
    for element in root.iter():
        tag = element.tag.lower() if isinstance(element.tag, str) else ""
        if tag.endswith("text") or tag.endswith("p"):
            cleaned = clean_text(" ".join(element.itertext()))
            if cleaned:
                parts.append(cleaned)

    return clean_text(" ".join(parts))


def _parse_subtitle_payload(payload, entry):
    ext = clean_text(entry.get("ext", "")).lower()
    content_type = clean_text(entry.get("ext", "")).lower()

    if ext in {"json3", "json"}:
        parsed = _parse_json_subtitle_payload(payload)
        if parsed:
            return parsed

    if ext in {"vtt", "srv1", "srv2", "srv3"}:
        parsed = _parse_vtt_subtitle_payload(payload)
        if parsed:
            return parsed

    if ext in {"ttml", "xml"} or "xml" in content_type:
        parsed = _parse_xml_subtitle_payload(payload)
        if parsed:
            return parsed

    parsed = _parse_vtt_subtitle_payload(payload)
    if parsed:
        return parsed
    parsed = _parse_xml_subtitle_payload(payload)
    if parsed:
        return parsed
    return _parse_json_subtitle_payload(payload)


def _fetch_ytdlp_subtitles(url):
    if yt_dlp is None:
        raise ValueError("subtitle fallback is unavailable because yt-dlp is not installed")

    options = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
    }

    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=False)

    subtitle_sources = [
        ("yt_dlp_subtitles", info.get("subtitles") or {}),
        ("yt_dlp_auto_captions", info.get("automatic_captions") or {}),
    ]

    for mode, subtitle_map in subtitle_sources:
        if not subtitle_map:
            continue

        preferred_languages = sorted(
            subtitle_map.keys(),
            key=lambda code: (0 if _language_code_is_englishish(code) else 1, code),
        )

        for language_code in preferred_languages:
            entries = subtitle_map.get(language_code) or []
            for entry in sorted(entries, key=_subtitle_format_priority):
                subtitle_url = entry.get("url")
                if not subtitle_url:
                    continue
                try:
                    response = requests.get(subtitle_url, timeout=15)
                    response.raise_for_status()
                    transcript_text = _parse_subtitle_payload(response.text, entry)
                    if transcript_text:
                        return transcript_text, mode, language_code
                except Exception:
                    continue

    raise ValueError("yt-dlp could not retrieve usable subtitle text for this video.")


def _fetch_ytdlp_info(url):
    if yt_dlp is None:
        raise ValueError("yt-dlp is not installed")

    options = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(options) as downloader:
        return downloader.extract_info(url, download=False)


def _clean_youtube_description(description):
    cleaned = description or ""
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"\bwww\.\S+", " ", cleaned)
    cleaned = re.sub(r"[#@]\w+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _fetch_ytdlp_description_metadata(url):
    info = _fetch_ytdlp_info(url)
    description = _clean_youtube_description(info.get("description", ""))
    return {
        "title": clean_text(info.get("title", "")),
        "author_name": clean_text(info.get("uploader", "") or info.get("channel", "")),
        "description": description,
    }


def _fetch_transcript_object_text(transcript, mode):
    transcript_chunks = transcript.fetch()
    return _transcript_chunks_to_text(transcript_chunks), mode, getattr(transcript, "language_code", "")


def _fetch_transcript(video_id):
    transcript_api = YouTubeTranscriptApi()
    try:
        fetched = transcript_api.fetch(video_id, languages=ENGLISH_TRANSCRIPT_LANGUAGES)
        return _transcript_chunks_to_text(fetched), "english", getattr(fetched, "language_code", "")
    except NoTranscriptFound:
        pass

    if hasattr(transcript_api, "list"):
        transcript_list = transcript_api.list(video_id)
    elif hasattr(YouTubeTranscriptApi, "list_transcripts"):
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    else:
        raise ValueError("The installed YouTube transcript library version changed its transcript-list API.")

    transcripts = list(transcript_list)

    english_candidates = sorted(
        [transcript for transcript in transcripts if _language_code_is_englishish(getattr(transcript, "language_code", ""))],
        key=lambda transcript: (getattr(transcript, "is_generated", False), getattr(transcript, "language_code", "")),
    )
    for transcript in english_candidates:
        try:
            return _fetch_transcript_object_text(transcript, "english")
        except Exception:
            continue

    for transcript in transcripts:
        if getattr(transcript, "is_translatable", False):
            try:
                translated = transcript.translate("en")
                translated_text, _, _ = _fetch_transcript_object_text(translated, "translated_to_english")
                return translated_text, "translated_to_english", getattr(transcript, "language_code", "")
            except Exception:
                continue

    if transcripts:
        raise ValueError("Captions are available for this video, but no usable English or translatable transcript could be produced.")

    raise ValueError("No English transcript or translatable transcript was available for this video.")


def _fetch_oembed_metadata(url):
    response = requests.get(
        OEMBED_URL,
        params={"url": url, "format": "json"},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    return {
        "title": clean_text(payload.get("title", "")),
        "author_name": clean_text(payload.get("author_name", "")),
    }


def get_youtube_text_for_summary(youtube_result):
    text = clean_text(youtube_result.get("text", ""))
    title = clean_text(youtube_result.get("title", ""))
    author = clean_text(youtube_result.get("author_name", ""))

    if title and text.startswith(title):
        text = text[len(title):].strip()

    channel_prefix = f"Channel: {author}"
    if author and text.startswith(channel_prefix):
        text = text[len(channel_prefix):].strip()

    return clean_text(text)


def _audio_fallback_enabled():
    return False if not yt_dlp else True


def _get_audio_asr_pipeline():
    global _ASR_PIPELINE, _ASR_PIPELINE_ERROR

    if _ASR_PIPELINE is not None or _ASR_PIPELINE_ERROR is not None:
        return _ASR_PIPELINE

    if pipeline is None:
        _ASR_PIPELINE_ERROR = "transformers is not installed for audio transcription."
        return None

    try:
        _ASR_PIPELINE = pipeline(
            "automatic-speech-recognition",
            model=YOUTUBE_ASR_MODEL_NAME,
            device=-1,
        )
    except Exception as error:
        _ASR_PIPELINE_ERROR = str(error)
        _ASR_PIPELINE = None

    return _ASR_PIPELINE


def _download_audio_for_transcription(url):
    if yt_dlp is None:
        raise ValueError(
            "optional audio transcription fallback is unavailable because yt-dlp is not installed"
        )

    temp_dir = tempfile.mkdtemp(prefix="youtube_audio_")
    output_template = str(Path(temp_dir) / "audio.%(ext)s")
    options = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)
        downloaded_path = Path(downloader.prepare_filename(info))
        if downloaded_path.exists():
            return downloaded_path

        stem_matches = list(Path(temp_dir).glob("audio.*"))
        if stem_matches:
            return stem_matches[0]

    raise ValueError("yt-dlp could not download an audio stream for this video.")


def _transcribe_audio_fallback(url):
    recognizer = _get_audio_asr_pipeline()
    if recognizer is None:
        raise ValueError(_ASR_PIPELINE_ERROR or "Audio transcription model is unavailable.")

    audio_path = _download_audio_for_transcription(url)
    try:
        result = recognizer(str(audio_path), generate_kwargs={"task": "translate"})
        transcript_text = clean_text(result.get("text", ""))
        if not transcript_text:
            raise ValueError("Audio transcription returned empty text.")
        return transcript_text
    finally:
        try:
            audio_path.unlink(missing_ok=True)
            audio_path.parent.rmdir()
        except Exception:
            pass


def build_youtube_summary_unavailable_message(youtube_result):
    title = clean_text(youtube_result.get("title", "")) or "this video"
    reasons = []

    transcript_error = clean_text(youtube_result.get("transcript_error", ""))
    fallback_error = clean_text(youtube_result.get("fallback_error", ""))

    if transcript_error:
        reasons.append(_friendly_summary_reason(transcript_error, "transcript"))
    if fallback_error:
        reasons.append(_friendly_summary_reason(fallback_error, "fallback"))
    if not reasons:
        reasons.append("A usable English transcript was not available for this video")

    unique_reasons = []
    seen = set()
    for reason in reasons:
        lowered = reason.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique_reasons.append(reason)

    reason_text = " ".join(
        f"{reason.rstrip('.')}." for reason in unique_reasons
    )

    return (
        f'Summary unavailable for "{title}". '
        f"{reason_text} "
        f'The current analysis uses only the video title and channel name, so it may miss important context.'
    )


def extract_youtube_content(url):
    normalized_url = (url or "").strip()
    video_id = extract_youtube_video_id(normalized_url)

    transcript_text = ""
    transcript_error = None
    transcript_mode = ""
    transcript_language = ""
    fallback_error = None
    try:
        transcript_text, transcript_mode, transcript_language = _fetch_transcript(video_id)
    except Exception as error:
        transcript_error = _friendly_transcript_error(error)

    subtitle_error = None
    if not transcript_text and yt_dlp is not None:
        try:
            transcript_text, transcript_mode, transcript_language = _fetch_ytdlp_subtitles(normalized_url)
            transcript_error = None
        except Exception as error:
            subtitle_error = clean_text(str(error))

    if not transcript_text and _audio_fallback_enabled():
        try:
            transcript_text = _transcribe_audio_fallback(normalized_url)
            transcript_mode = "audio_transcribed_to_english"
            transcript_language = transcript_language or "unknown"
        except Exception as error:
            fallback_error = str(error)
    elif not transcript_text and yt_dlp is None:
        fallback_error = "optional audio transcription fallback is unavailable because yt-dlp is not installed"

    metadata = {"title": "", "author_name": ""}
    metadata_error = None
    try:
        metadata = _fetch_oembed_metadata(normalized_url)
    except Exception as error:
        metadata_error = str(error)

    rich_metadata = {}
    rich_metadata_error = None
    if yt_dlp is not None:
        try:
            rich_metadata = _fetch_ytdlp_description_metadata(normalized_url)
        except Exception as error:
            rich_metadata_error = clean_text(str(error))

    if not metadata.get("title") and rich_metadata.get("title"):
        metadata["title"] = rich_metadata.get("title", "")
    if not metadata.get("author_name") and rich_metadata.get("author_name"):
        metadata["author_name"] = rich_metadata.get("author_name", "")

    description_text = ""
    if not transcript_text:
        candidate_description = clean_text(rich_metadata.get("description", ""))
        if len(candidate_description.split()) >= 18:
            description_text = candidate_description

    content_blocks = []
    if metadata.get("title"):
        content_blocks.append(metadata["title"])
    if metadata.get("author_name"):
        content_blocks.append(f"Channel: {metadata['author_name']}")
    if transcript_text:
        content_blocks.append(transcript_text)
    elif description_text:
        content_blocks.append(description_text)

    combined_text = clean_text(" ".join(content_blocks))
    if not combined_text:
        error_bits = [bit for bit in [transcript_error, metadata_error, rich_metadata_error] if bit]
        message = error_bits[0] if error_bits else "Unable to extract transcript or metadata from this YouTube URL."
        raise ValueError(message)

    source_type = "youtube_transcript" if transcript_text else "youtube_metadata"
    source_note = ""
    if source_type == "youtube_metadata":
        if description_text:
            source_note = (
                "A usable transcript was not available, so the analysis used the video's public description "
                "as a fallback source."
            )
        else:
            source_note = build_youtube_summary_unavailable_message(
                {
                    "title": metadata.get("title", ""),
                    "transcript_error": transcript_error or "",
                    "fallback_error": fallback_error or "",
                }
            )
    elif transcript_mode == "translated_to_english":
        source_note = (
            f"An English transcript was unavailable, so the analysis used an auto-translated English transcript "
            f"from {transcript_language or 'the original language'}."
        )
    elif transcript_mode == "yt_dlp_subtitles":
        source_note = "The standard transcript API was unavailable, so the analysis used subtitle text recovered through yt-dlp."
    elif transcript_mode == "yt_dlp_auto_captions":
        source_note = "The standard transcript API was unavailable, so the analysis used auto-generated captions recovered through yt-dlp."
    elif transcript_mode == "audio_transcribed_to_english":
        source_note = "No caption transcript was available, so the analysis used an English audio transcription fallback."

    return {
        "video_id": video_id,
        "url": normalized_url,
        "title": metadata.get("title", ""),
        "author_name": metadata.get("author_name", ""),
        "text": combined_text,
        "summary_text": get_youtube_text_for_summary(
            {
                "text": combined_text,
                "title": metadata.get("title", ""),
                "author_name": metadata.get("author_name", ""),
            }
        ) if transcript_text else description_text,
        "source_type": source_type,
        "source_note": source_note,
        "transcript_mode": transcript_mode,
        "transcript_language": transcript_language,
        "metadata_basis": "description" if description_text and not transcript_text else "",
        "transcript_error": transcript_error or "",
        "subtitle_error": subtitle_error or "",
        "fallback_error": fallback_error or "",
    }


def extract_youtube_text(url):
    return extract_youtube_content(url)["text"]
