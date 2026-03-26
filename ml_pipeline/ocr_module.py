import os
import re
from collections import defaultdict

import pytesseract
from PIL import Image, ImageFilter, ImageOps
from pytesseract import Output


_COMMON_SHORT_WORDS = {
    "a",
    "an",
    "as",
    "at",
    "be",
    "by",
    "do",
    "go",
    "he",
    "if",
    "in",
    "is",
    "it",
    "me",
    "my",
    "no",
    "of",
    "on",
    "or",
    "so",
    "to",
    "up",
    "us",
    "we",
}


def _configure_tesseract():
    tesseract_path = os.getenv("TESSERACT_PATH", "").strip()
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path


def _is_meaningful_word(word):
    letters = re.sub(r"[^A-Za-z']", "", word or "")
    if len(letters) < 2:
        return False

    lowered = letters.lower()
    has_vowel = bool(re.search(r"[aeiouy]", lowered))
    has_consonant = bool(re.search(r"[bcdfghjklmnpqrstvwxyz]", lowered))
    return has_vowel and has_consonant


def _normalize_ocr_line(line):
    line = (line or "").strip()
    if not line:
        return ""

    line = re.sub(r"^[A-Z]{1,3}\s*[\u2013\u2014\-_=|:]+\s*(?=\+\s*[A-Za-z])", "", line)
    line = re.sub(r"^[\u2022*]+\s*", "+ ", line)
    line = re.sub(r"^[+\-]{2,}\s*", "+ ", line)
    line = re.sub(r"\s{2,}", " ", line).strip()
    line = re.sub(r"^[^A-Za-z0-9+(\"']+", "", line)
    line = re.sub(r"[^A-Za-z0-9.!?'\")\]]+$", "", line).strip()
    if not line or not re.search(r"[A-Za-z]", line):
        return ""

    alpha_tokens = re.findall(r"[A-Za-z][A-Za-z'/-]*", line)
    meaningful_words = [word for word in alpha_tokens if _is_meaningful_word(word)]
    weird_chars = len(re.findall(r"[^A-Za-z0-9\s'\".,:;!?()+\-/&\[\]\u2013\u2014]", line))
    short_noise_tokens = [
        token
        for token in re.findall(r"\b[A-Za-z]{1,2}\b", line)
        if token.lower() not in _COMMON_SHORT_WORDS and not token.isupper()
    ]

    if len(alpha_tokens) == 1 and len(alpha_tokens[0]) < 8 and len(line.split()) == 1:
        return ""
    if len(meaningful_words) == 0 and len(alpha_tokens) < 2:
        return ""
    if re.search(r"([A-Za-z])\1{4,}", line):
        return ""
    if re.fullmatch(r"[A-Za-z\u2013\u2014=_-]{2,}", line) and len(meaningful_words) < 1:
        return ""
    if weird_chars >= max(3, (len(line) // 6) + 1):
        return ""
    if len(short_noise_tokens) >= 4 and len(meaningful_words) < 2:
        return ""

    return line


def _normalize_ocr_text(text):
    cleaned = (text or "").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[\u2018\u2019`]", "'", cleaned)
    cleaned = re.sub(r"[\u201c\u201d]", '"', cleaned)
    cleaned = re.sub(r"[|]{2,}", "|", cleaned)
    cleaned = re.sub(r"[\u2022\u00b7]", "- ", cleaned)
    cleaned = re.sub(r"(?<=\w)\+(?=\w)", " + ", cleaned)
    cleaned = re.sub(r"\s+\+\s+", " + ", cleaned)
    cleaned = re.sub(
        r"^.*?\bcurated by copilot\b\s*[-:]\s*\d+h\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    lines = []
    for raw_line in cleaned.split("\n"):
        line = _normalize_ocr_line(raw_line)
        if line:
            lines.append(line)

    cleaned = "\n".join(lines) if lines else cleaned
    cleaned = re.sub(r"^[^A-Za-z0-9]+", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _crop_variants(img):
    width, height = img.size
    left_panel = img.crop((0, 0, int(width * 0.53), height))
    upper_left = img.crop((0, 0, int(width * 0.58), int(height * 0.72)))
    body_left = img.crop((0, int(height * 0.14), int(width * 0.58), int(height * 0.78)))

    return [
        ("full", img),
        ("left_panel", left_panel),
        ("upper_left", upper_left),
        ("body_left", body_left),
    ]


def _preprocess_variants(img):
    original = img
    grayscale = ImageOps.grayscale(img)
    enlarged = grayscale.resize(
        (max(1, grayscale.width * 2), max(1, grayscale.height * 2)),
        Image.Resampling.LANCZOS,
    )
    autocontrast = ImageOps.autocontrast(enlarged)
    sharpened = autocontrast.filter(ImageFilter.SHARPEN)
    threshold_dark = sharpened.point(lambda value: 255 if value > 150 else 0)
    threshold_inverted = ImageOps.invert(threshold_dark)
    inverted_gray = ImageOps.invert(autocontrast)

    return [
        ("original", original),
        ("gray", grayscale),
        ("autocontrast", autocontrast),
        ("sharp", sharpened),
        ("threshold_dark", threshold_dark),
        ("threshold_inverted", threshold_inverted),
        ("inverted_gray", inverted_gray),
    ]


def _ocr_score(text):
    words = re.findall(r"\b[\w@#'+.-]{2,}\b", text or "")
    if not words:
        return 0.0

    alpha_words = [word for word in words if re.search(r"[A-Za-z]", word)]
    meaningful_words = [word for word in alpha_words if _is_meaningful_word(word)]
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    bullet_lines = text.count("\n") + text.count(" + ") + text.count("- ")
    meaningful_lines = sum(
        1
        for line in lines
        if len([word for word in re.findall(r"[A-Za-z][A-Za-z'/-]*", line) if _is_meaningful_word(word)]) >= 2
    )

    score = len(meaningful_words) * 2.2
    score += len(alpha_words) * 0.3
    score += min(bullet_lines, 10) * 0.4
    score += meaningful_lines * 0.9
    if any(char.isdigit() for char in text):
        score += 0.5

    garbage_tokens = re.findall(r"\b[a-z]{1,2}\b|\b[a-z]{8,}\b", (text or "").lower())
    weird_chars = len(re.findall(r"[^A-Za-z0-9\s'\".,:;!?()+\-/&\n\[\]\u2013\u2014]", text or ""))
    suspicious_short_tokens = [
        token
        for token in re.findall(r"\b[A-Za-z]{1,2}\b", text or "")
        if token.lower() not in _COMMON_SHORT_WORDS and not token.isupper()
    ]
    score -= len(garbage_tokens) * 0.15
    score -= weird_chars * 0.8
    score -= len(suspicious_short_tokens) * 0.45
    return score


def _is_high_confidence_ocr_text(text):
    words = re.findall(r"\b[\w'+.-]{2,}\b", text or "")
    alpha_words = [word for word in words if re.search(r"[A-Za-z]", word)]
    meaningful_words = [word for word in alpha_words if _is_meaningful_word(word)]
    weird_chars = len(re.findall(r"[^A-Za-z0-9\s'\".,:;!?()+\-/&\n\[\]\u2013\u2014]", text or ""))
    suspicious_short_tokens = [
        token
        for token in re.findall(r"\b[A-Za-z]{1,2}\b", text or "")
        if token.lower() not in _COMMON_SHORT_WORDS and not token.isupper()
    ]
    return len(meaningful_words) >= 6 and weird_chars <= 2 and len(suspicious_short_tokens) <= 2


def _attempt_bonus(crop_name, variant_name, config, method):
    bonus = 0.0

    if crop_name == "full":
        bonus += 1.2
    elif crop_name == "upper_left":
        bonus += 0.4

    if variant_name == "original":
        bonus += 1.4
    elif variant_name in {"gray", "autocontrast", "sharp"}:
        bonus += 0.8
    elif variant_name in {"threshold_dark", "threshold_inverted"}:
        bonus -= 0.2

    if "psm 4" in config:
        bonus += 1.5
    elif "psm 11" in config:
        bonus += 0.4

    if method == "string":
        bonus += 0.35

    return bonus


def _extract_lines_from_data(img, config):
    data = pytesseract.image_to_data(img, config=config, output_type=Output.DICT)
    lines = defaultdict(list)

    for i, raw_text in enumerate(data.get("text", [])):
        word = (raw_text or "").strip()
        if not word:
            continue

        conf_raw = str(data.get("conf", ["-1"])[i]).strip()
        try:
            confidence = float(conf_raw)
        except ValueError:
            confidence = -1

        if confidence < 25:
            continue

        key = (
            data["block_num"][i],
            data["par_num"][i],
            data["line_num"][i],
        )
        lines[key].append(word)

    ordered_lines = []
    for key in sorted(lines.keys()):
        line = " ".join(lines[key]).strip()
        if len(line.split()) >= 2:
            ordered_lines.append(line)

    return _normalize_ocr_text("\n".join(ordered_lines))


def _extract_with_string(img, config):
    text = pytesseract.image_to_string(img, config=config)
    return _normalize_ocr_text(text)


def _best_ocr_text(img):
    attempts = []
    configs = [
        "--oem 3 --psm 6",
        "--oem 3 --psm 11",
        "--oem 3 --psm 4",
    ]

    for config in ("--oem 3 --psm 4", "--oem 3 --psm 11"):
        try:
            text = _extract_with_string(img, config)
            if text and _is_high_confidence_ocr_text(text):
                return text
        except Exception:
            pass

    for crop_name, crop in _crop_variants(img):
        for variant_name, variant in _preprocess_variants(crop):
            for config in configs:
                try:
                    text = _extract_lines_from_data(variant, config)
                    if text:
                        attempts.append(
                            (
                                _ocr_score(text) + _attempt_bonus(crop_name, variant_name, config, "data"),
                                text,
                                crop_name,
                                variant_name,
                                "data",
                            )
                        )
                except Exception:
                    pass

                try:
                    text = _extract_with_string(variant, config)
                    if text:
                        attempts.append(
                            (
                                _ocr_score(text) + _attempt_bonus(crop_name, variant_name, config, "string"),
                                text,
                                crop_name,
                                variant_name,
                                "string",
                            )
                        )
                except Exception:
                    pass

    if not attempts:
        return ""

    attempts.sort(key=lambda item: item[0], reverse=True)
    return attempts[0][1]


def extract_text_from_image(image_path):
    try:
        _configure_tesseract()
        img = Image.open(image_path)

        try:
            text = _best_ocr_text(img)
            if text.strip():
                return text.strip()
        except Exception as tesseract_error:
            return (
                "Image analysis (Tesseract not available): "
                f"File={os.path.basename(image_path)}, Error={tesseract_error}"
            )

        return f"Image processed: {os.path.basename(image_path)} ({img.size[0]}x{img.size[1]} pixels)"

    except Exception as e:
        return f"Image error: {str(e)}"
