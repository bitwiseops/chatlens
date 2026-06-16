# CLAUDE.md — chatlens

Guida per agenti/sviluppatori che lavorano su questa codebase.

## Cos'è
Sistema **interamente locale** per analizzare una chat WhatsApp privata a due (export `.txt`):
statistiche deterministiche, temi/riassunti, andamento emotivo/relazionale, stile comunicativo.

## Vincoli di privacy (NON negoziabili)
- **Nessuna chiamata di rete** eccetto verso Ollama in locale (`http://localhost:11434`).
  Nessuna API esterna, nessuna telemetria, nessun logging che esca dalla macchina.
- La cartella `data/` è in `.gitignore`. **Mai committare contenuti di chat** (né export,
  né parquet, né report). Sono tracciati solo i `.gitkeep`.
- `anonymize.py` offre pseudonimizzazione dei nomi: usarla prima di condividere output.
- Se aggiungi codice di rete, l'unico host ammesso resta `localhost:11434`.

## Principio architetturale centrale: deterministico ≠ LLM
- **Tutto ciò che è conteggiabile** (frequenze, orari, tempi di risposta, emoji, chi inizia
  le conversazioni) si calcola in **pandas** (`stats.py`) e **NON** viene mai dato al modello.
- L'**LLM** serve solo per ciò che richiede comprensione semantica (temi, riassunti,
  sentiment, stile) — `summarize.py`, `sentiment.py`, `comm_style.py`.
- I contenuti semantici usano sempre **map-reduce**: si segmenta la cronologia in finestre
  (`windows.py`), si analizza ogni finestra, poi si aggrega. Non assumere mai che l'intera
  chat entri nel context.
- **Output in italiano**, temperature bassa (≈0.15) per riproducibilità.

## Contratto dati (DataFrame / Parquet)
`parse.py` produce `data/processed/messaggi.parquet` con esattamente queste colonne:
`timestamp` (datetime), `sender` (str), `text` (str grezzo), `text_clean` (str, vuoto se
media), `is_media` (bool), `n_chars` (int), `n_words` (int), `n_emoji` (int), `date` (date),
`hour` (int), `weekday` (str).

## Ambiente: uv
Questo progetto usa **uv** (no pip/venv manuale, no requirements.txt).
```bash
uv sync                 # crea .venv e installa da pyproject.toml + uv.lock
uv run pytest           # test
uv run chatlens --help  # CLI
```

## Ollama: avvio e modelli
```bash
# avvia il server (lascialo in esecuzione)
ollama serve
# scarica i modelli (una tantum)
ollama pull qwen2.5:7b-instruct   # chat di default (8 GB VRAM, quantizzato)
ollama pull nomic-embed-text      # embedding (RAG futuro)
```
Nomi modello, finestre, percorsi e temperature sono in `config.yaml`.

## Test
```bash
uv run pytest          # tutti
uv run pytest -q tests/test_parse.py
```
I test deterministici (`parse`/`stats`) **non** richiedono Ollama.

## CLI
Sottocomandi: `parse`, `stats`, `summarize`, `sentiment`, `comm-style`, `report`, `all`.
Flag `--me` / `--other` per i nomi degli interlocutori.
```bash
uv run chatlens all --me "Flavio" --other "NomeAltro"
```
