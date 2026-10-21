<div align="center">

# 💬 chatlens

**What does a two-person WhatsApp chat say about the conversation, without sending it to anyone?**
Statistics, themes and sentiment from an exported chat, computed entirely on your machine with a local LLM.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![Ollama](https://img.shields.io/badge/LLM-Ollama%20(local)-000000)
![uv](https://img.shields.io/badge/deps-uv-de5fe9)
![Privacy](https://img.shields.io/badge/data-never%20leaves%20your%20machine-2e7d32)

</div>

---

## Table of contents

- [Overview](#overview)
- [Highlights](#highlights)
- [Quick start](#quick-start)
- [Commands](#commands)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Privacy](#privacy)
- [Limitations](#limitations)
- [License](#license)

## Overview

chatlens analyses a WhatsApp chat between two people, exported as a `.txt` file, and produces a Markdown report with charts: activity statistics and patterns, summaries and recurring themes, and the emotional trend over time, plus an exploratory module on communication style.

> **Privacy first.** No data leaves your machine. The only network connection is to a **local Ollama** instance (`http://localhost:11434`). The `data/` folder is git-ignored, so your chats never end up in a commit.

## Highlights

- 🔒 **Fully local:** parsing, statistics and all LLM calls run on your own hardware.
- 🔢 **Deterministic numbers:** counts, response times and who starts conversations are computed in pandas, never by the LLM.
- 🧠 **LLM for meaning only:** map-reduce summarisation into themes, sentiment per time window, exploratory communication style.
- 🕶️ **Pseudonymisation:** replace real names with pseudonyms before sharing any output.
- 📈 **One-command report:** Markdown report with charts.
- ✅ **Tested:** `pytest` covers parsing and statistics without needing Ollama.

## Quick start

Requires Python 3.11 or newer, [uv](https://docs.astral.sh/uv/) and [Ollama](https://ollama.com) running locally. A GPU is recommended: the default model is quantised to fit in 8 GB of VRAM.

```bash
git clone https://github.com/bitwiseops/chatlens.git
cd chatlens
uv sync

ollama serve &
ollama pull qwen2.5:7b-instruct   # default chat model
ollama pull nomic-embed-text      # embeddings
```

Export the chat from WhatsApp (*⋮ → Export chat → Without media*), copy the `.txt` into `data/raw/`, then:

```bash
uv run chatlens all --me "Alice" --other "Bob"
```

Model names, window sizes, paths and temperatures are in [`config.yaml`](config.yaml). Alternative chat models: `llama3.1:8b`, `gemma2:9b`. `qwen2.5:14b` works with partial offload, but is slower.

## Commands

| Command | Output (in `data/processed/`) | Uses LLM |
|---|---|---|
| `chatlens parse <chat.txt> [--anonymize]` | `messaggi.parquet` | no |
| `chatlens stats` | `stats.json` | no |
| `chatlens summarize` | `temi.json` | yes |
| `chatlens sentiment` | `sentiment.csv` | yes |
| `chatlens comm-style` | `comm_style.json` (exploratory) | yes |
| `chatlens report` | `report.md` and charts | no |
| `chatlens all` | the whole pipeline | yes |

## How it works

1. **Parse** the iOS or Android export into a table of messages.
2. **Stats:** deterministic metrics (message counts, response times, conversation starters) with pandas.
3. **Windows:** the chat is cut into windows that fit the model's context.
4. **LLM passes:** themes (map-reduce), sentiment per window, communication style.
5. **Report:** everything assembled into `report.md` with matplotlib charts.

The deterministic part (counting) is kept apart from the LLM part (semantics), so numbers in the report can be trusted and only the interpretation depends on the model.

## Project structure

```
├── src/chatlens/
│   ├── cli.py            # typer entrypoint
│   ├── parse.py          # WhatsApp export → table
│   ├── anonymize.py      # pseudonymisation
│   ├── stats.py          # deterministic metrics
│   ├── windows.py        # context windows
│   ├── summarize.py      # themes (map-reduce)
│   ├── sentiment.py      # sentiment per window
│   ├── comm_style.py     # exploratory communication style
│   ├── llm.py            # Ollama client
│   └── report.py         # Markdown report and charts
├── tests/                # pytest (parse and stats need no Ollama)
├── prompts/              # LLM prompts
├── config.yaml           # models, windows, paths
└── data/                 # raw/ and processed/ (git-ignored)
```

## Privacy

Everything runs offline except calls to Ollama on `localhost`. Use `--anonymize` when parsing to replace real names with pseudonyms before sharing any output.

## Limitations

Two-person chats only. The communication-style section is **exploratory and not diagnostic**: treat it as a prompt for reflection, not a verdict on a real person. Sentiment and themes depend on the local model you choose and are not validated against human annotation.

## License

[MIT](LICENSE) © 2026 Flavio Cordari
