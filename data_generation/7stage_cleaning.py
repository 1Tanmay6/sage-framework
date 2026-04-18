
import os
import re
from pathlib import Path


try:
    from unstructured.cleaners.core import (
        group_broken_paragraphs,
        replace_unicode_quotes,
        bytes_string_to_string,
    )
    HAS_UNSTRUCTURED = True
except ImportError:
    print("[WARNING] 'unstructured' not installed. Run: pip install unstructured")
    print("          Falling back to regex-only cleaning.\n")
    HAS_UNSTRUCTURED = False


JUNK_LINE_PATTERNS = [

    r"^(log\s?in|sign\s?in|sign\s?up|log\s?out|register|my account)$",
    r"^(home|about|contact\s?us?|contact$|support|help|faq)$",
    r"^(subscribe|newsletter|follow us|share|tweet|like|pin it)$",
    r"^(menu|navigation|sidebar|breadcrumb|search\.\.\.)$",
    r"^(skip to (main )?content|jump to).*$",


    r"^(accept (all )?cookies?|cookie (policy|settings|notice|consent)).*$",
    r"^(we use cookies|this (site|website) uses cookies).*$",
    r"^(privacy policy|terms (of (service|use))?|legal notice|disclaimer)$",


    r"^(download pdf|download article|full[- ]?text|open access|view pdf)$",
    r"^(cite this|citation|export citation|bibtex|ris|endnote).*$",
    r"^(supplementary (material|data|information))$",
    r"^(previous article|next article|back to top|top of page|\u2191 top)$",
    r"^(related articles?|recommended articles?|you may also like)$",
    r"^(metrics|altmetric|crossmark|orcid|doi:?\s*$)",
    r"^(received|accepted|published|revised):?\s*\d",
    r"^(volume|issue|pages?|journal)\s*:?\s*\d",
    r"^(copyright|©|all rights reserved).*$",
    r"^(figure \d+\.|table \d+\.|fig\.\s*\d+)$",
    r"^\s*\d{1,3}\s*$",
    r"^(advertisement|sponsored|ad\s*:).*$",


    r"^(share (on|via)|facebook|twitter|linkedin|reddit|whatsapp|email this).*$",

]

_JUNK_RE = [re.compile(p, re.IGNORECASE) for p in JUNK_LINE_PATTERNS]

MIN_LINE_LEN = 3


_MATH_SIGNALS = re.compile(
    r"""
      \\[a-zA-Z]+          
    | \$+                  
    | \\\[|\\\]            
    | \\\(|\\\)            
    | [=<>≤≥≠≈∈∉∩∪⊂⊃∑∏∫∂∇±×÷∞√]  
    | \b(sin|cos|tan|log|exp|lim|sup|inf|arg\s?max|arg\s?min)\b
    | \^[\w{]              
    | _[\w{]               
    | \d+\s*/\s*\d+        
    | [A-Za-z]\s*=\s*[-+]?\d   
    """,
    re.VERBOSE,
)


def is_math_line(line: str) -> bool:
    return bool(_MATH_SIGNALS.search(line))


def is_junk_line(line: str) -> bool:
    """Return True if the line is boilerplate and should be discarded."""
    stripped = line.strip()
    if len(stripped) < MIN_LINE_LEN and not is_math_line(stripped):
        return True
    for pat in _JUNK_RE:
        if pat.match(stripped):
            return True
    return False


def remove_junk_lines(text: str) -> str:
    """Drop every line that matches a boilerplate pattern."""
    lines = text.splitlines()
    kept = [ln for ln in lines if not is_junk_line(ln)]
    return "\n".join(kept)


def collapse_blank_lines(text: str, max_blanks: int = 2) -> str:
    """
    Reduce runs of blank lines to at most `max_blanks`.
    Equations often have excessive newlines around them — this cleans that up
    while still preserving paragraph breaks (double newline).
    """

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    pattern = re.compile(r"\n{%d,}" % (max_blanks + 1))
    return pattern.sub("\n" * max_blanks, text)


def rejoin_broken_lines(text: str) -> str:
    """
    Merge lines that were artificially wrapped mid-sentence.
    Strategy: within a paragraph block (separated by blank lines),
    if a line does NOT end with sentence-ending punctuation and the next line
    does NOT look like a new sentence / heading / math, merge them.

    Math lines are left as-is.
    """
    paragraphs = re.split(r"\n{2,}", text)
    rejoined_paragraphs = []

    for para in paragraphs:
        lines = para.splitlines()
        if len(lines) <= 1:
            rejoined_paragraphs.append(para)
            continue

        merged_lines = []
        i = 0
        while i < len(lines):
            current = lines[i].rstrip()

            if is_math_line(current):
                merged_lines.append(current)
                i += 1
                continue

            while i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if not next_line:
                    break
                if is_math_line(next_line):
                    break

                if re.search(r"[.!?:]\s*$", current):
                    break

                if re.match(r"^[A-Z\d\[]", next_line) and re.search(r"[.!?]\s*$", current):
                    break

                words = next_line.split()
                if (len(words) <= 6 and
                        next_line == next_line.title() and
                        not re.search(r"[,;]", next_line)):
                    break

                current = current.rstrip() + " " + next_line
                i += 1

            merged_lines.append(current)
            i += 1

        rejoined_paragraphs.append("\n".join(merged_lines))

    return "\n\n".join(rejoined_paragraphs)


def normalise_whitespace_in_lines(text: str) -> str:
    """
    Within each line, collapse multiple spaces to one.
    Preserves indentation on math lines (some authors indent equations).
    """
    lines = []
    for line in text.splitlines():
        if is_math_line(line):

            leading = len(line) - len(line.lstrip(" "))
            core = re.sub(r" {2,}", " ", line.lstrip(" "))
            lines.append(" " * leading + core)
        else:
            lines.append(re.sub(r" {2,}", " ", line))
    return "\n".join(lines)


def apply_unstructured_cleaners(text: str) -> str:
    """Apply unstructured library cleaning passes (if available)."""
    if not HAS_UNSTRUCTURED:
        return text

    try:
        text = bytes_string_to_string(text, encoding="utf-8")
    except Exception:
        pass

    try:
        text = replace_unicode_quotes(text)
    except Exception:
        pass

    try:
        para_split_re = re.compile(r"(\s*\n\s*){2,}")
        text = group_broken_paragraphs(text, paragraph_split=para_split_re)
    except Exception:
        pass

    return text


def clean_file(text: str) -> str:
    """Full cleaning pipeline for one research-paper .txt file."""

    text = apply_unstructured_cleaners(text)

    text = remove_junk_lines(text)

    text = collapse_blank_lines(text, max_blanks=2)

    text = rejoin_broken_lines(text)

    text = normalise_whitespace_in_lines(text)

    text = collapse_blank_lines(text, max_blanks=2)

    text = text.strip() + "\n"

    return text


def get_all_txt_files(root_dir):
    txt_files = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        for file in filenames:
            if file.lower().endswith(".txt"):
                full_path = os.path.join(dirpath, file)
                txt_files.append(full_path)

    return txt_files


def run():
    from pathlib import Path

    input_dir = "./scraped_data"
    output_dir = Path("./cleaned_data")
    output_dir.mkdir(parents=True, exist_ok=True)

    dry_run = False
    suffix = "_cleaned"

    txt_files = get_all_txt_files(input_dir)

    for i, src_path in enumerate(txt_files):
        src_path = Path(src_path)

        raw_text = src_path.read_text(encoding="utf-8", errors="replace")
        cleaned_text = clean_file(raw_text)

        if dry_run:
            print(f"{'='*70}")
            print(f"DRY RUN — {src_path.name}")
            print(f"{'='*70}\n")
            print(cleaned_text[:3000])
            if len(cleaned_text) > 3000:
                print(f"\n… [truncated — {len(cleaned_text)} chars total]")
            break

        stem = src_path.stem + suffix
        dst_path = output_dir / (stem + ".txt")
        dst_path.write_text(cleaned_text, encoding="utf-8")

        raw_lines = raw_text.count("\n")
        clean_lines = cleaned_text.count("\n")

        print(f"[{i+1}/{len(txt_files)}] {src_path.name} → {dst_path.name}  "
              f"({raw_lines} → {clean_lines} lines)")

    if not dry_run:
        print(f"\n✓ Done. Cleaned files written to '{output_dir}/'")


if __name__ == "__main__":
    run()
