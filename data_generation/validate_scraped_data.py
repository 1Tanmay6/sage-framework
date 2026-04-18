"""
validate_scraped.py
-------------------
Checks each .txt file in cleaned_data/ and decides if it has real content.
Results are saved to validation_results.csv

Install deps:
    pip install langdetect lingua-language-detector nltk
    python -m nltk.downloader punkt
"""

import os
import re
import csv
import math
from collections import Counter
from pathlib import Path

import nltk
from langdetect import detect, LangDetectException

# ── config ────────────────────────────────────────────────────────────────────

INPUT_FOLDER = "cleaned_data"       # folder with your cleaned .txt files
OUTPUT_CSV = "validation_results.csv"
RESULTS_FOLDER = {
    "valid":      "filtered/valid",
    "suspicious": "filtered/suspicious",
    "failed":     "filtered/failed",
}

# Thresholds — tweak these if too aggressive or too lenient
MIN_WORDS = 80      # anything below this is almost certainly a failure
MIN_ALPHA_RATIO = 0.55    # at least 55% of chars should be letters/spaces
MIN_SENTENCES = 4       # real content has multiple sentences
MIN_AVG_WORD_LEN = 3.5     # very short avg = symbol soup or garbage
MAX_AVG_WORD_LEN = 12.0    # very long avg = garbled/concatenated junk
MIN_ENTROPY = 3.8     # bits per char — real prose is ~4.0–5.0
MAX_PUNCT_RATIO = 0.18    # too much punctuation = probably code/garbage
MIN_UNIQUE_WORD_RATIO = 0.10    # vocabulary diversity — repetitive pages score low

# ── helpers ───────────────────────────────────────────────────────────────────


def word_count(text):
    return len(text.split())


def alpha_ratio(text):
    if not text:
        return 0
    alpha_and_space = sum(1 for c in text if c.isalpha() or c == " ")
    return alpha_and_space / len(text)


def sentence_count(text):
    try:
        sentences = nltk.sent_tokenize(text)
        # Only count sentences with at least 4 words
        return sum(1 for s in sentences if len(s.split()) >= 4)
    except Exception:
        return text.count(".") + text.count("!") + text.count("?")


def avg_word_length(text):
    words = [w for w in text.split() if w.isalpha()]
    if not words:
        return 0
    return sum(len(w) for w in words) / len(words)


def char_entropy(text):
    if not text:
        return 0
    counts = Counter(text)
    total = len(text)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def punct_ratio(text):
    if not text:
        return 0
    punct = sum(1 for c in text if c in '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')
    return punct / len(text)


def unique_word_ratio(text):
    words = text.lower().split()
    if not words:
        return 0
    return len(set(words)) / len(words)


def detect_language(text):
    try:
        sample = text[:2000]  # langdetect only needs a sample
        return detect(sample)
    except LangDetectException:
        return "unknown"


def has_negative_signals(text):
    """Check for telltale signs of a failed scrape."""
    lowered = text.lower()
    failure_phrases = [
        "javascript is required",
        "please enable javascript",
        "access denied",
        "403 forbidden",
        "404 not found",
        "page not found",
        "subscribe to read",
        "sign in to continue",
        "login to view",
        "content is only available",
        "this content is behind",
        "create a free account",
        "paywall",
    ]
    for phrase in failure_phrases:
        if phrase in lowered:
            return True, phrase
    return False, None


# ── main validator ────────────────────────────────────────────────────────────

def validate_file(text):
    """
    Returns (verdict, reason, stats_dict)
    verdict is one of: 'valid', 'suspicious', 'failed'
    """
    stats = {
        "words":             word_count(text),
        "alpha_ratio":       round(alpha_ratio(text), 3),
        "sentences":         sentence_count(text),
        "avg_word_len":      round(avg_word_length(text), 2),
        "entropy":           round(char_entropy(text), 3),
        "punct_ratio":       round(punct_ratio(text), 3),
        "unique_word_ratio": round(unique_word_ratio(text), 3),
        "language":          detect_language(text),
    }

    # ── Stage 1: hard failures (any one = failed) ──────────────────────────
    neg, phrase = has_negative_signals(text)
    if neg:
        return "failed", f"failure phrase detected: '{phrase}'", stats

    if stats["words"] < MIN_WORDS:
        return "failed", f"too few words ({stats['words']})", stats

    if stats["alpha_ratio"] < MIN_ALPHA_RATIO:
        return "failed", f"low alpha ratio ({stats['alpha_ratio']})", stats

    if stats["sentences"] < MIN_SENTENCES:
        return "failed", f"too few real sentences ({stats['sentences']})", stats

    if stats["language"] == "unknown":
        return "failed", "language undetectable (gibberish?)", stats

    # ── Stage 2: suspicious (soft signals — might be okay, worth checking) ──
    reasons = []

    if stats["entropy"] < MIN_ENTROPY:
        reasons.append(f"low entropy ({stats['entropy']})")

    if stats["avg_word_len"] < MIN_AVG_WORD_LEN:
        reasons.append(f"very short avg word length ({stats['avg_word_len']})")

    if stats["avg_word_len"] > MAX_AVG_WORD_LEN:
        reasons.append(f"very long avg word length ({stats['avg_word_len']})")

    if stats["punct_ratio"] > MAX_PUNCT_RATIO:
        reasons.append(f"high punctuation ratio ({stats['punct_ratio']})")

    if stats["unique_word_ratio"] < MIN_UNIQUE_WORD_RATIO:
        reasons.append(
            f"low vocabulary diversity ({stats['unique_word_ratio']})")

    if stats["language"] not in ("en", "unknown") and stats["words"] < 300:
        reasons.append(f"non-English and short (lang={stats['language']})")

    if reasons:
        return "suspicious", " | ".join(reasons), stats

    return "valid", "ok", stats


# ── run ───────────────────────────────────────────────────────────────────────

def run():
    input_folder = Path(INPUT_FOLDER)
    txt_files = sorted(input_folder.glob("*.txt"))

    if not txt_files:
        print(
            f"No .txt files found in '{INPUT_FOLDER}'. Check the folder name.")
        return

    # Create output folders
    for folder in RESULTS_FOLDER.values():
        Path(folder).mkdir(parents=True, exist_ok=True)

    results = []
    counts = {"valid": 0, "suspicious": 0, "failed": 0}

    print(f"Validating {len(txt_files)} files...\n")

    for path in txt_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        verdict, reason, stats = validate_file(text)
        counts[verdict] += 1

        # Copy file to appropriate subfolder
        dest = Path(RESULTS_FOLDER[verdict]) / path.name
        dest.write_text(text, encoding="utf-8")

        # Print summary line
        icon = {"valid": "✓", "suspicious": "?", "failed": "✗"}[verdict]
        print(f"  {icon} {path.name:<45} {verdict:<12} {reason}")

        results.append({
            "file":             path.name,
            "verdict":          verdict,
            "reason":           reason,
            **stats,
        })

    # Write CSV report
    csv_path = Path(OUTPUT_CSV)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"""
─────────────────────────────────
  ✓ Valid:      {counts['valid']}
  ? Suspicious: {counts['suspicious']}
  ✗ Failed:     {counts['failed']}
─────────────────────────────────
Files sorted into:  filtered/valid|suspicious|failed
Full report saved:  {OUTPUT_CSV}
""")


run()
