"""
Run this script to diagnose your YouTube summarization pipeline.
Place it in your project root and run: python debug_youtube_summary.py <youtube_url>
"""

import sys
import os
import re

print("=" * 60)
print("STEP 1: Checking transformers / model availability")
print("=" * 60)

try:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline as hf_pipeline
    print("[OK] transformers is installed")
except ImportError:
    print("[FAIL] transformers is NOT installed")
    print("       Fix: pip install transformers torch sentencepiece")
    hf_pipeline = None

MODEL_NAME = os.getenv("SUMMARY_MODEL_NAME", "sshleifer/distilbart-cnn-12-6")
print(f"      Model name: {MODEL_NAME}")

if hf_pipeline:
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, local_files_only=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME, local_files_only=True)
        summarizer = hf_pipeline("summarization", model=model, tokenizer=tokenizer, device=-1)
        print("[OK] Model loaded from local cache")
    except Exception as e:
        print(f"[WARN] local_files_only failed: {e}")
        print("       Trying to download model (this may take a few minutes)...")
        try:
            summarizer = hf_pipeline("summarization", model=MODEL_NAME, device=-1)
            print("[OK] Model downloaded and loaded successfully")
        except Exception as e2:
            print(f"[FAIL] Model could not load: {e2}")
            print("       Summarizer will fall back to extractive mode")
            summarizer = None
else:
    summarizer = None

print()
print("=" * 60)
print("STEP 2: Extracting YouTube content")
print("=" * 60)

url = sys.argv[1] if len(sys.argv) > 1 else None
if not url:
    print("[SKIP] No URL provided. Pass a YouTube URL as argument:")
    print("       python debug_youtube_summary.py https://youtube.com/watch?v=...")
    sys.exit(0)

try:
    from ml_pipeline.youtube_module import extract_youtube_content

    result = extract_youtube_content(url)
    print(f"[OK] video_id     : {result['video_id']}")
    print(f"[OK] title        : {result['title']}")
    print(f"[OK] author_name  : {result['author_name']}")
    print(f"[OK] source_type  : {result['source_type']}")
    print(f"[OK] source_note  : {result['source_note'] or 'none'}")
    print(f"[OK] text length  : {len(result['text'])} chars")
    print(f"[OK] word count   : {len(result['text'].split())} words")

    transcript_body = result["text"]
    title = result["title"]
    author = result["author_name"]
    if title and transcript_body.startswith(title):
        transcript_body = transcript_body[len(title):].strip()
    channel_prefix = f"Channel: {author}"
    if author and transcript_body.startswith(channel_prefix):
        transcript_body = transcript_body[len(channel_prefix):].strip()

    print()
    print("-- First 400 chars of raw transcript body --")
    print(repr(transcript_body[:400]))

except Exception as e:
    print(f"[FAIL] Could not extract YouTube content: {e}")
    sys.exit(1)

print()
print("=" * 60)
print("STEP 3: Sentence splitting on raw transcript")
print("=" * 60)

try:
    from ml_pipeline.summary_module import _split_sentences, _is_noise, _clean_text

    sentences_raw = _split_sentences(transcript_body)
    sentences_raw = [_clean_text(s) for s in sentences_raw if _clean_text(s)]
    sentences_clean = [s for s in sentences_raw if not _is_noise(s)]

    print(f"[INFO] Raw sentences found    : {len(sentences_raw)}")
    print(f"[INFO] After noise filter     : {len(sentences_clean)}")
    print()
    print("-- First 5 sentences after split+filter --")
    for i, s in enumerate(sentences_clean[:5]):
        print(f"  [{i}] ({len(s.split())} words) {s[:120]}")

except Exception as e:
    print(f"[FAIL] Sentence splitting error: {e}")

print()
print("=" * 60)
print("STEP 4: Current summarize_text() output")
print("=" * 60)

try:
    from ml_pipeline.summary_module import summarize_text

    current_summary = summarize_text(result["text"])
    print(f"[INFO] Output length: {len(current_summary)} chars")
    print()
    print("-- Current summary output --")
    print(current_summary)
except Exception as e:
    print(f"[FAIL] summarize_text() raised: {e}")

print()
print("=" * 60)
print("STEP 5: After transcript preprocessing")
print("=" * 60)


def preprocess_youtube_transcript(text):
    clean = re.sub(r"\s+", " ", (text or "")).strip()
    spoken_breaks = (
        r"\b(so |now |but |however |meanwhile |additionally |furthermore |"
        r"in fact |actually |basically |essentially |therefore |as a result |"
        r"on the other hand |at the same time |in other words )"
    )
    clean = re.sub(spoken_breaks, r". \1", clean, flags=re.IGNORECASE)
    clean = re.sub(
        r"([a-z]{3,})\s+(The |This |That |These |Those |A |An )",
        r"\1. \2",
        clean,
    )
    clean = re.sub(r"\.{2,}", ".", clean)
    clean = re.sub(r"\.\s*\.", ".", clean)
    return re.sub(r"\s+", " ", clean).strip()


try:
    from ml_pipeline.summary_module import _split_sentences, _is_noise, _clean_text

    preprocessed = preprocess_youtube_transcript(transcript_body)
    sentences_pre = _split_sentences(preprocessed)
    sentences_pre = [_clean_text(s) for s in sentences_pre if _clean_text(s)]
    sentences_pre = [s for s in sentences_pre if not _is_noise(s)]

    print(f"[INFO] Sentences after preprocessing : {len(sentences_pre)}")
    print()
    print("-- First 5 sentences after preprocessing --")
    for i, s in enumerate(sentences_pre[:5]):
        print(f"  [{i}] ({len(s.split())} words) {s[:120]}")

except Exception as e:
    print(f"[FAIL] Preprocessing test error: {e}")

print()
print("=" * 60)
print("DIAGNOSIS SUMMARY")
print("=" * 60)

issues = []
if summarizer is None:
    issues.append("Model not loaded -> falling back to extractive summarization")

if not issues:
    print("[OK] No obvious issues found.")
else:
    for issue in issues:
        print(f"[!!] {issue}")
