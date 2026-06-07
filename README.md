# srt-analyser

Petit outil Python pour extraire une liste de vocabulaire depuis un fichier SRT japonais.

Usage rapide:

1. Installer dépendances (recommandé dans un virtualenv):

```bash
python -m venv .venv
source .venv/bin/activate   # ou ".\.venv\Scripts\activate" sur PowerShell
pip install -r requirements.txt
```

2. Lancer l'analyse:

```bash
python src/srt_vocab.py "input/Tora-sans Tropical Fever 1997 1080psubtitle Asian Cinema.jp.srt"
```

Sortie: `output/vocab.tsv` (TSV: lemma, surface_examples, pos, freq, example_sentence)

Notes:
- Le script essaie d'utiliser SudachiPy (recommandé). Si SudachiPy n'est pas installé, il bascule sur un tokenizer simple de secours.
- Pour un meilleur résultat, installe `sudachidict_core` ou `sudachidict_full`.
