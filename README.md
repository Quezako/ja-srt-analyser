# srt-analyser

Small Python tool to extract a vocabulary list from a Japanese SRT file.

Quick usage:

1. Install dependencies (recommended in a virtual environment):

```bash
python -m venv .venv
source .venv/bin/activate   # or ".\.venv\Scripts\activate" in PowerShell
pip install -r requirements.txt
```

2. Run the analysis:

```bash
python src/srt_vocab.py "input/Tora-sans Tropical Fever 1997 1080psubtitle Asian Cinema.jp.srt"
```

Output: `output/vocab.tsv` (TSV: lemma, surface_examples, pos, freq, example_sentence)

Notes:
- The script tries to use SudachiPy (recommended). If SudachiPy is not installed, it falls back to a simple built-in tokenizer.
- For better results, install `sudachidict_core` or `sudachidict_full`.
