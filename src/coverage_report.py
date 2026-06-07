#!/usr/bin/env python3
"""Coverage report between `output/vocab.tsv` and `input/anki-mature.txt`.

Writes three files under `output/`:
- `coverage_summary.txt` : short summary with counts and percent
- `coverage_details.tsv` : per-lemma detail (lemma, matched, matched_anki)
- `coverage_missing.tsv` : only missing lemmas

Matching strategy:
- Normalize strings by removing bracketed readings (e.g. `[いち]`), HTML tags and common annotations.
- Consider a match when normalized forms are equal or one contains the other.
"""
import csv
import os
import re
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
VOCAB_PATH = HERE / "output" / "vocab.tsv"
ANKI_PATH = HERE / "input" / "anki-mature.txt"
OUT_DIR = HERE / "output"


def normalize(s: str) -> str:
    if s is None:
        return ""
    s = s.strip()
    # remove anki-style readings like [いち]
    s = re.sub(r"\[.*?\]", "", s)
    # remove {...} annotations (e.g. {\an8})
    s = re.sub(r"\{.*?\}", "", s)
    # remove html tags
    s = re.sub(r"<.*?>", "", s)
    # remove quotes and non-breaking spaces
    s = s.replace('"', '').replace("'", '').replace('\xa0', ' ')
    s = s.strip()
    # collapse whitespace
    s = re.sub(r"\s+", " ", s)
    return s


def load_vocab(path: Path):
    items = []
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        # fallback: if no header or unexpected, use first column
        fieldnames = reader.fieldnames or []
        if not fieldnames:
            raise ValueError("vocab.tsv has no header")
        first_col = fieldnames[0]
        for row in reader:
            raw = row.get(first_col, "").strip()
            items.append({"raw": raw, "norm": normalize(raw)})
    return items


def load_anki(path: Path):
    items = []
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            ln = ln.rstrip("\n\r")
            if not ln or ln.startswith("#"):
                continue
            parts = ln.split("\t")
            if not parts:
                continue
            first = parts[0].strip()
            if first == "":
                continue
            items.append({"raw": first, "norm": normalize(first)})
    return items


def find_match(lemma_norm: str, anki_items):
    # try exact normalized match first
    for a in anki_items:
        if lemma_norm and a["norm"] and lemma_norm == a["norm"]:
            return a["raw"]
    # try containment (either way)
    for a in anki_items:
        if lemma_norm and a["norm"] and (lemma_norm in a["norm"] or a["norm"] in lemma_norm):
            return a["raw"]
    return None


def main():
    anki_items = load_anki(ANKI_PATH)
    vocab_items = load_vocab(VOCAB_PATH)

    matched_count = 0
    details = []

    for v in vocab_items:
        m = find_match(v["norm"], anki_items)
        matched = bool(m)
        if matched:
            matched_count += 1
        details.append({"raw": v["raw"], "norm": v["norm"], "matched": matched, "match": m or ""})

    total = len(vocab_items)
    percent = (matched_count / total * 100) if total else 0.0

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # summary
    summary_path = OUT_DIR / "coverage_summary.txt"
    with summary_path.open("w", encoding="utf-8") as fh:
        fh.write(f"total_vocab\t{total}\n")
        fh.write(f"matched\t{matched_count}\n")
        fh.write(f"coverage_percent\t{percent:.2f}\n")

    # details
    details_path = OUT_DIR / "coverage_details.tsv"
    with details_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["lemma_raw", "lemma_norm", "matched", "matched_anki_raw"])
        for d in details:
            w.writerow([d["raw"], d["norm"], "yes" if d["matched"] else "no", d["match"]])

    missing_path = OUT_DIR / "coverage_missing.tsv"
    with missing_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["lemma_raw", "lemma_norm"])
        for d in details:
            if not d["matched"]:
                w.writerow([d["raw"], d["norm"]])

    print(f"Wrote summary to {summary_path}\nDetails to {details_path}\nMissing to {missing_path}")


if __name__ == "__main__":
    main()
