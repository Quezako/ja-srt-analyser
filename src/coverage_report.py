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
import sys


HERE = Path(__file__).resolve().parents[1]
VOCAB_PATH = HERE / "output" / "vocab.tsv"
ANKI_PATH = HERE / "input" / "anki-mature.txt"
OUT_DIR = HERE / "output"
MANUAL_FILE = HERE / "input" / "spoken_grammar_known.tsv"


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


def is_katakana(s: str) -> bool:
    """Return True if string is composed only of Katakana (and common punctuation like prolonged mark)."""
    if not s:
        return False
    s = s.strip()
    # Katakana Unicode block 30A0-30FF, include prolonged sound mark 'ー' and middle dot
    return bool(re.fullmatch(r"^[\u30A0-\u30FFー・･]+$", s))


def is_number(s: str) -> bool:
    """Return True if string is only numeric (ASCII or fullwidth digits)."""
    if not s:
        return False
    s = s.strip()
    return bool(re.fullmatch(r"^[0-9０-９]+$", s))


def has_hiragana_or_kanji(s: str) -> bool:
    """Return True if string contains at least one Hiragana or Kanji character."""
    if not s:
        return False
    # Hiragana \u3040-\u309F, Kanji \u4E00-\u9FFF
    return bool(re.search(r"[\u3040-\u309F\u4E00-\u9FFF]", s))


def is_hiragana_only(s: str) -> bool:
    """Return True if string is composed only of Hiragana (including iteration marks)."""
    if not s:
        return False
    # include hiragana block and iteration marks ゝ(309D) ゞ(309E)
    return bool(re.fullmatch(r"^[\u3040-\u309F\u309D\u309E]+$", s))


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
            norm = normalize(raw)
            # try to read example sentence from the known column name
            example = ""
            if "example_sentence" in row:
                example = (row.get("example_sentence") or "").strip()
            else:
                # fallback: try common alternate header names
                example = (row.get("example") or row.get("example_sentence ") or "").strip()
            # ignore pure katakana tokens and pure numbers
            if is_katakana(norm) or is_number(norm):
                continue
            # ignore tokens that do not contain hiragana or kanji (e.g. romaji, romaji+katakana+digits)
            if not has_hiragana_or_kanji(norm):
                continue
            items.append({"raw": raw, "norm": norm, "example": example})
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
            # build a list of normalized variants: the base form with bracketed readings removed
            # plus any readings that appear inside [...] (e.g. "今日は[こんにちは]" -> variants "今日は", "こんにちは")
            base_norm = normalize(first)
            bracket_vals = re.findall(r"\[([^\]]+)\]", first)
            norms = [base_norm]
            for b in bracket_vals:
                bnorm = normalize(b)
                if bnorm and bnorm not in norms:
                    norms.append(bnorm)

            # decide whether to keep this Anki entry: keep if ANY variant is acceptable
            any_katakana = all(is_katakana(n) for n in norms if n)
            any_number = all(is_number(n) for n in norms if n)
            any_has_hira_or_kanji = any(has_hiragana_or_kanji(n) for n in norms if n)

            if any_katakana or any_number:
                # skip entries that are exclusively katakana or exclusively numbers
                continue
            if not any_has_hira_or_kanji:
                # skip entries that have no hiragana/kanji in any variant (e.g. romaji-only)
                continue

            items.append({"raw": first, "norms": norms})
    return items


def load_manual(path: Path):
    """Load manual classifications from `input/spoken_grammar_known.tsv`.

    Returns a dict mapping lemma -> status string (lowercase), e.g. 'yes', 'no', 'ignore'.
    """
    manual = {}
    if not path.exists():
        return manual
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        reader = csv.reader(fh, delimiter="\t")
        # skip header if present
        first = next(reader, None)
        # if first looks like header, continue, otherwise treat it as data
        if first and len(first) >= 1 and first[0].strip().lower() == "lemma":
            pass
        else:
            # first was actual data row
            if first:
                lemma = first[0].strip()
                status = (first[1].strip().lower() if len(first) > 1 else "").strip()
                if lemma:
                    manual[lemma] = status
        for parts in reader:
            if not parts:
                continue
            lemma = parts[0].strip()
            status = (parts[1].strip().lower() if len(parts) > 1 else "").strip()
            if lemma:
                manual[lemma] = status
    return manual


def find_match(lemma_norm: str, anki_items):
    # try exact normalized match first (consider all Anki variants)
    for a in anki_items:
        norms = a.get("norms") or [a.get("norm")]
        for an in norms:
            if lemma_norm and an and lemma_norm == an:
                return a["raw"]
    # try containment (either way) across variants
    for a in anki_items:
        norms = a.get("norms") or [a.get("norm")]
        for an in norms:
            if lemma_norm and an and (lemma_norm in an or an in lemma_norm):
                return a["raw"]
    return None


def main():
    anki_items = load_anki(ANKI_PATH)
    vocab_items = load_vocab(VOCAB_PATH)
    manual_map = load_manual(MANUAL_FILE)

    matched_count = 0
    details = []

    # Incorporate manual classifications:
    # - if manual_map[lemma] == 'yes' -> treat as matched
    # - if manual_map[lemma] == 'ignore' -> exclude from total and outputs
    for v in vocab_items:
        norm = v["norm"]
        raw = v["raw"]
        example = v.get("example", "")

        # check manual decisions first
        m_status = manual_map.get(norm) or manual_map.get(raw)
        if m_status == "ignore":
            # mark as ignored: do not include in details (we'll track it but exclude later)
            details.append({"raw": raw, "norm": norm, "matched": None, "match": "(ignored)", "example": example})
            continue
        if m_status == "yes":
            # count as matched via manual file
            matched_count += 1
            details.append({"raw": raw, "norm": norm, "matched": True, "match": "(manual_known)", "example": example})
            continue

        # otherwise fall back to Anki matching
        m = find_match(norm, anki_items)
        matched = bool(m)
        if matched:
            matched_count += 1
        details.append({"raw": raw, "norm": norm, "matched": matched, "match": m or "", "example": example})

    # Exclude ignored items from total
    total = sum(1 for d in details if d.get("matched") is not None)
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
            m = d.get("matched")
            if m is True:
                status = "yes"
            elif m is False:
                status = "no"
            else:
                status = "ignored"
            w.writerow([d["raw"], d["norm"], status, d["match"]])

    missing_path = OUT_DIR / "coverage_missing.tsv"
    # prepare missing entries: include only explicit False (i.e. not matched and not ignored)
    missing_entries = [d for d in details if d.get("matched") is False]
    missing_entries.sort(key=lambda x: (x.get("norm") or x.get("raw") or ""))

    with missing_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["lemma_raw", "lemma_norm", "example_sentence"])
        for d in missing_entries:
            w.writerow([d["raw"], d["norm"], d.get("example", "")])

    # At this point we have written the missing file.
    print(f"Wrote summary to {summary_path}\nDetails to {details_path}\nMissing to {missing_path}")

    # Offer to run the manual classifier automatically when the environment variable is set.
    if os.environ.get("RUN_MANUAL") == "1":
        if sys.stdin.isatty():
            try:
                import manual_classify

                manual_classify.main()
            except Exception as exc:
                print(f"Failed to run manual classifier: {exc}")
        else:
            print("RUN_MANUAL is set but no TTY available; skipped manual classification.")
    else:
        print("To run manual classification now: python3 src/manual_classify.py")


if __name__ == "__main__":
    main()
