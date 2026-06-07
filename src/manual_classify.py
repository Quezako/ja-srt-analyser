#!/usr/bin/env python3
"""Interactive tool to classify hiragana-only missing items.

Reads `output/coverage_missing.tsv` and appends decisions to
`input/spoken_grammar_known.tsv`.

Choices during prompt:
- y : known (writes `yes`)
- n : unknown (writes `no`)
- i : ignore (writes `ignore`)
- s : skip (do not write)
- q : quit

This script is intended to be run in a terminal (TTY).
"""
import csv
import re
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
MISSING_PATH = HERE / "output" / "coverage_missing.tsv"
MANUAL_FILE = HERE / "input" / "spoken_grammar_known.tsv"


def is_hiragana_only(s: str) -> bool:
    if not s:
        return False
    return bool(re.fullmatch(r"^[\u3040-\u309F\u309D\u309E]+$", s))


def highlight_first(lemma: str, example: str) -> str:
    if not lemma or not example:
        return example or ""
    try:
        pattern = re.escape(lemma)
        start = "\x1b[33m"
        end = "\x1b[0m"
        return re.sub(pattern, start + lemma + end, example, count=1)
    except re.error:
        return example


def load_manual_set(path: Path):
    seen = set()
    if not path.exists():
        return seen
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        reader = csv.reader(fh, delimiter="\t")
        # skip header
        next(reader, None)
        for parts in reader:
            if not parts:
                continue
            lemma = parts[0].strip()
            if lemma:
                seen.add(lemma)
    return seen


def load_missing(path: Path):
    if not path.exists():
        raise FileNotFoundError(path)
    items = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            lemma = (row.get("lemma_norm") or row.get("lemma_raw") or "").strip()
            example = (row.get("example_sentence") or "").strip()
            if not lemma:
                continue
            if is_hiragana_only(lemma):
                items.append({"lemma": lemma, "example": example})
    return items


def main():
    if not sys.stdin.isatty():
        print("manual_classify: no TTY available, aborting interactive classification.")
        return

    MANUAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not MANUAL_FILE.exists():
        with MANUAL_FILE.open("w", encoding="utf-8", newline="") as fh:
            fh.write("lemma\tknown\tcomment\texample_sentence\n")

    manual_seen = load_manual_set(MANUAL_FILE)
    missing_hira = load_missing(MISSING_PATH)

    total = len(missing_hira)
    already = sum(1 for it in missing_hira if it["lemma"] in manual_seen)
    remaining = [it for it in missing_hira if it["lemma"] not in manual_seen]

    print(f"Found {total} hiragana-only missing items; {already} already classified, {len(remaining)} remaining.")
    if not remaining:
        return

    with MANUAL_FILE.open("a", encoding="utf-8", newline="") as fh:
        for idx, it in enumerate(remaining, start=1):
            lemma = it["lemma"]
            example = it.get("example", "")
            highlighted = highlight_first(lemma, example)
            prompt = f"[{idx}/{len(remaining)}] Know '{lemma}'? Example: {highlighted}\n[y/n/i/s/q]: "
            while True:
                ans = input(prompt).strip().lower()
                if ans in ("y", "n", "i", "s", "q"):
                    break
            if ans == "q":
                print("Quitting -- progress saved.")
                break
            if ans == "s":
                continue
            if ans == "y":
                status = "yes"
            elif ans == "n":
                status = "no"
            else:
                status = "ignore"
            safe_example = example.replace("\t", " ")
            fh.write(f"{lemma}\t{status}\t\t{safe_example}\n")
            # progress report
            done = idx + already
            left = total - done
            print(f"Recorded {status} for '{lemma}'. Progress: {done}/{total} (remaining {max(0,left)})")

    print(f"Finished. Manual file: {MANUAL_FILE}")


if __name__ == "__main__":
    main()
