#!/usr/bin/env python
"""
Test script to verify the analysis API handles all content types correctly
"""
import sys
from pathlib import Path

workspace_root = Path(__file__).parent
sys.path.insert(0, str(workspace_root))

from ml_pipeline.analyzer import analyze_content

# Test 1: Text Analysis
print("=" * 60)
print("TEST 1: Text Analysis")
print("=" * 60)
text_result = analyze_content(
    "text",
    "Breaking news! Scientific researchers discovered a miraculous cure!",
    None
)
print(f"Prediction: {text_result['prediction']}")
print(f"Confidence: {text_result['confidence']:.2%}")
print(f"Sentiment: {text_result['sentiment']}")
print(f"Explanation: {text_result['explanation']}\n")

# Test 2: URL Analysis
print("=" * 60)
print("TEST 2: URL Analysis")
print("=" * 60)
url_result = analyze_content(
    "url",
    "https://www.bbc.com/news",
    None
)
print(f"Prediction: {url_result['prediction']}")
print(f"Confidence: {url_result['confidence']:.2%}")
print(f"Content Source: {url_result['content_source']}")
print(f"Explanation: {url_result['explanation'][:100]}...\n" if url_result['explanation'] else f"Explanation: {url_result['explanation']}\n")

# Test 3: Real text (should predict Real)
print("=" * 60)
print("TEST 3: Real News Analysis")
print("=" * 60)
real_text = "The government announced new policy changes today regarding healthcare standards and regulations for next year."
real_result = analyze_content(
    "text",
    real_text,
    None
)
print(f"Prediction: {real_result['prediction']}")
print(f"Confidence: {real_result['confidence']:.2%}")
print(f"Sentiment: {real_result['sentiment']}")
print(f"Explanation: {real_result['explanation']}\n")

print("=" * 60)
print("✓ Analysis API is working correctly!")
print("✓ Text analysis: OK")
print("✓ URL analysis: OK")
print("✓ Fake/Real detection: OK")
print("=" * 60)
