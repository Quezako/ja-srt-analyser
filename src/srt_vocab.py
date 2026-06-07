#!/usr/bin/env python3
"""srt_vocab.py

Petit script pour extraire vocabulaire depuis un fichier SRT japonais.
Il tente d'utiliser SudachiPy; s'il n'est pas disponible, il utilise un tokenizer de secours.

Sortie: `output/vocab.tsv`
"""

import sys
import os
import re
from collections import defaultdict
from pathlib import Path


def parse_srt(path):
    text_blocks = []
    data = Path(path).read_text(encoding='utf-8', errors='ignore')
    # Split blocks by blank lines
    blocks = re.split(r"\n\s*\n", data)
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        # lines[0] could be index, lines[1] could be time range
        # collect remaining lines that look like text
        text_lines = []
        for i, ln in enumerate(lines):
            if i == 0 and re.fullmatch(r"\d+", ln):
                continue
            if i == 1 and ('-->' in ln):
                continue
            text_lines.append(ln)
        if text_lines:
            text_blocks.append(' '.join(text_lines))
    return text_blocks


def simple_tokenize(text):
    # Improved fallback tokenizer: extract runs by script to avoid mixing
    # - kanji block: \u4E00-\u9FFF
    # - katakana block: \u30A0-\u30FF (include 'ー' prolonged sound mark and middle dot)
    # - hiragana block: \u3040-\u309F
    # - latin/number: A-Za-z0-9
    pattern = re.compile(
        r"(?P<kanji>[\u4E00-\u9FFF]+)|(?P<katakana>[\u30A0-\u30FFー・･]+)|(?P<hiragana>[\u3040-\u309F]+)|(?P<latin>[A-Za-z0-9]+)",
        re.UNICODE,
    )
    # collect typed runs
    runs = [(m.lastgroup, m.group(0)) for m in pattern.finditer(text)]

    tokens = []
    i = 0
    while i < len(runs):
        typ, seg = runs[i]
        # merge Kanji + Hiragana (okurigana) sequences into one token, e.g. 互 + い -> 互い
        if typ == 'kanji' and i + 1 < len(runs) and runs[i + 1][0] == 'hiragana':
            merged = seg + runs[i + 1][1]
            tokens.append(merged)
            i += 2
            continue
        tokens.append(seg)
        i += 1
    return tokens


def try_sudachi_tokenize(text, tokenizer, Mode):
    tokens = tokenizer.tokenize(text, Mode.A)
    out = []
    for m in tokens:
        surface = m.surface()
        try:
            lemma = m.dictionary_form()
        except Exception:
            lemma = surface
        try:
            pos = '/'.join(m.part_of_speech())
        except Exception:
            pos = ''
        try:
            reading = m.reading_form()
        except Exception:
            reading = ''
        out.append({'surface': surface, 'lemma': lemma, 'pos': pos, 'reading': reading})
    return out


def build_vocab(blocks, use_sudachi=False, tokenizer=None, Mode=None):
    vocab = defaultdict(lambda: {'freq': 0, 'surfaces': set(), 'pos': set(), 'example': ''})
    for b in blocks:
        if use_sudachi:
            toks = try_sudachi_tokenize(b, tokenizer, Mode)
            for t in toks:
                lemma = t['lemma'] or t['surface']
                vocab[lemma]['freq'] += 1
                vocab[lemma]['surfaces'].add(t['surface'])
                if t['pos']:
                    vocab[lemma]['pos'].add(t['pos'])
                if not vocab[lemma]['example']:
                    vocab[lemma]['example'] = b
        else:
            toks = simple_tokenize(b)
            for s in toks:
                lemma = s
                vocab[lemma]['freq'] += 1
                vocab[lemma]['surfaces'].add(s)
                if not vocab[lemma]['example']:
                    vocab[lemma]['example'] = b
    return vocab


def save_tsv(vocab, out_path, top_n=None):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    items = sorted(vocab.items(), key=lambda kv: kv[1]['freq'], reverse=True)
    if top_n:
        items = items[:top_n]
    with out_path.open('w', encoding='utf-8') as f:
        f.write('lemma\tsurface_examples\tpos\tfreq\texample_sentence\n')
        for lemma, info in items:
            surfaces = ','.join(list(info['surfaces'])[:5])
            pos = ','.join(list(info['pos'])[:3]) if info['pos'] else ''
            freq = str(info['freq'])
            example = info['example'].replace('\t', ' ').replace('\n', ' ')[:200]
            f.write(f"{lemma}\t{surfaces}\t{pos}\t{freq}\t{example}\n")


def main():
    if len(sys.argv) < 2:
        print('Usage: srt_vocab.py path/to/file.srt [top_n]')
        sys.exit(1)
    srt_path = Path(sys.argv[1])
    top_n = int(sys.argv[2]) if len(sys.argv) >= 3 else None
    blocks = parse_srt(srt_path)
    use_sudachi = False
    tokenizer = None
    Mode = None
    try:
        from sudachipy import dictionary, tokenizer as _tokenizer
        Mode = _tokenizer.Tokenizer.SplitMode
        tokenizer = dictionary.Dictionary().create()
        use_sudachi = True
        print('SudachiPy disponible : utilisation pour tokenisation.')
    except Exception:
        print('SudachiPy non disponible : utilisation d\'un tokenizer de secours.')

    vocab = build_vocab(blocks, use_sudachi=use_sudachi, tokenizer=tokenizer, Mode=Mode)
    out = Path('output') / 'vocab.tsv'
    save_tsv(vocab, out, top_n=top_n)
    print(f'Saved {len(vocab)} entries to {out}')


if __name__ == '__main__':
    main()
