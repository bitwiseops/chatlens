# chatlens

**Fully local, private analysis of a two-person WhatsApp chat.** Feed it an exported `.txt` and get statistics and patterns, summaries and recurring themes, and the emotional/relational trend over time, plus an exploratory module on communication style.

> **Privacy first.** No data ever leaves your machine. The only network connection is to a **local Ollama** instance (`http://localhost:11434`). The `data/` folder is git-ignored, so your chats never end up in a commit.

## Features

- **Deterministic stats** (message counts, response times, who starts conversations) kept strictly separate from the **LLM layer** (semantics), so numbers are never hallucinated
- **Map-reduce summarisation** of long chats into recurring themes
- **Sentiment over time** and an exploratory, non-diagnostic **communication-style** analysis
- **Optional pseudonymisation** before sharing any output
- Markdown report with charts

## Requirements

- Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com) running locally
- A GPU is recommended: the default model is quantised to fit in 8 GB of VRAM

## Setup

```bash
uv sync

ollama serve &
ollama pull qwen2.5:7b-instruct   # default chat model
ollama pull nomic-embed-text      # embeddings
```

Model names, context windows, paths and temperatures live in [`config.yaml`](config.yaml).

## Usage

Export the chat from WhatsApp (*⋮ → Export chat → Without media*) and copy the `.txt` into `data/raw/`.

```bash
# full pipeline
uv run chatlens all --me "Alice" --other "Bob"

# or step by step
uv run chatlens parse data/raw/chat.txt     # -> messages.parquet
uv run chatlens stats                       # -> stats.json
uv run chatlens summarize                   # -> themes.json (LLM)
uv run chatlens sentiment                   # -> sentiment.csv (LLM)
uv run chatlens comm-style                  # -> comm_style.json (LLM, exploratory)
uv run chatlens report                      # -> report.md + charts
```

To replace real names with pseudonyms before sharing results, add `--anonymize` to `parse`.

## Disclaimer

The communication-style section is exploratory and **not diagnostic**: treat it as a prompt for reflection, not a verdict on a real person.

## Development

```bash
uv run pytest    # parse/stats tests do not need Ollama
```

## Stack

Python · Ollama (local LLMs) · pandas/Parquet · uv

## License

MIT, see [LICENSE](LICENSE).
