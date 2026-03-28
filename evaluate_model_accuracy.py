import csv
import json
import sys
from pathlib import Path

from ml_pipeline.nlp_module import analyze_nlp
from ml_pipeline.text_classifier import classify_text


def load_rows(dataset_path):
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            raise ValueError("JSON dataset must be a list of objects")
        return data

    raise ValueError("Supported dataset formats: .csv or .json")


def normalize_label(label):
    lowered = (label or "").strip().lower()
    if "real" in lowered:
        return "real"
    if "fake" in lowered:
        return "fake"
    return "uncertain"


def evaluate_dataset(rows):
    total = 0
    exact_matches = 0
    normalized_matches = 0
    mismatches = []

    for index, row in enumerate(rows, start=1):
        text = (row.get("text") or "").strip()
        expected = (row.get("label") or "").strip()

        if not text or not expected:
            continue

        total += 1
        nlp_result = analyze_nlp(text)
        prediction = classify_text(text, nlp_result)["prediction"]

        if prediction == expected:
            exact_matches += 1

        if normalize_label(prediction) == normalize_label(expected):
            normalized_matches += 1
        else:
            mismatches.append(
                {
                    "row": index,
                    "expected": expected,
                    "predicted": prediction,
                    "text_preview": text[:160],
                }
            )

    if total == 0:
        raise ValueError("Dataset did not contain any rows with both 'text' and 'label' values")

    return {
        "samples_evaluated": total,
        "exact_match_accuracy": round(exact_matches / total, 4),
        "normalized_label_accuracy": round(normalized_matches / total, 4),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:20],
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: python evaluate_model_accuracy.py <dataset.csv|dataset.json>")
        sys.exit(1)

    dataset_path = sys.argv[1]
    rows = load_rows(dataset_path)
    report = evaluate_dataset(rows)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
