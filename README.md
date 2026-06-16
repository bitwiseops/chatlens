# chatlens

Analisi **interamente locale e privata** di una chat WhatsApp a due persone, esportata in
`.txt`. Produce statistiche/pattern, riassunti e temi ricorrenti, e l'andamento
emotivo/relazionale nel tempo — più un modulo esplorativo sullo stile comunicativo.

> **Privacy prima di tutto.** Nessun dato lascia mai la macchina. L'unica connessione di
> rete è verso un'istanza **Ollama in locale** (`http://localhost:11434`). La cartella
> `data/` è ignorata da git: le tue chat non finiscono in nessun commit.

## Requisiti
- Python >= 3.11 e [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com) in locale
- GPU consigliata: RTX 3060 Ti (8 GB VRAM) — il modello di default è quantizzato per starci.

## Setup

```bash
# 1. dipendenze (uv crea .venv e usa uv.lock)
uv sync

# 2. avvia Ollama e scarica i modelli (una tantum)
ollama serve &
ollama pull qwen2.5:7b-instruct   # modello di chat di default
ollama pull nomic-embed-text      # embedding (RAG futuro)
```

Nomi modello, dimensioni delle finestre, percorsi e temperature sono in `config.yaml`.
Modelli chat alternativi: `llama3.1:8b`, `gemma2:9b`. `qwen2.5:14b` funziona con offload
parziale, ma è più lento.

## Esportare la chat da WhatsApp
Sul telefono: apri la conversazione -> **Altro / tre puntini** -> **Esporta chat** ->
**Senza media**. Ottieni un file `.txt` (formato iOS o Android). Copialo in `data/raw/`.

## Uso (CLI)

```bash
# pipeline completa
uv run chatlens all --me "Flavio" --other "NomeAltro"

# oppure passo per passo
uv run chatlens parse      data/raw/chat.txt   # -> messaggi.parquet
uv run chatlens stats                          # -> stats.json (deterministico)
uv run chatlens summarize                      # -> temi.json (LLM, map-reduce)
uv run chatlens sentiment                      # -> sentiment.csv (LLM)
uv run chatlens comm-style                     # -> comm_style.json (LLM, esplorativo)
uv run chatlens report                         # -> report.md + grafici
```

Tutti gli output finiscono in `data/processed/` (ignorata da git).

## Pseudonimizzazione
Prima di condividere qualunque output, puoi sostituire i nomi reali con pseudonimi:

```bash
uv run chatlens parse data/raw/chat.txt --anonymize
```

## Privacy e disclaimer
- Tutto gira offline tranne le chiamate a Ollama su `localhost`.
- La sezione **stile comunicativo** del report è **esplorativa e non diagnostica**: va presa
  come spunto, non come verdetto su una persona reale.

## Sviluppo
```bash
uv run pytest        # test (parse/stats non richiedono Ollama)
```
Architettura: il **deterministico** (conteggi) è separato dall'**LLM** (semantica). Vedi
`CLAUDE.md`.
