"""Strato 3 — Stile comunicativo (ESPLORATIVO, non diagnostico).

Questo modulo NON emette etichette cliniche o di personalità come fatti: si limita a
pattern linguistici osservabili e formula ipotesi caute con evidenze. Il report include
un disclaimer esplicito. Vedi prompts/comm_style.txt per i paletti.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import load_config
from .llm import OllamaClient, load_prompt


def _sample_transcript(df: pd.DataFrame, cfg: dict) -> str:
    """Campiona messaggi distribuiti su tutta la cronologia (no media, no vuoti)."""
    max_msgs = int(cfg["llm"]["max_messages_per_window"])
    max_chars = int(cfg["llm"]["max_chars_per_message"])

    text_df = df[(~df["is_media"]) & (df["text_clean"].str.strip() != "")]
    text_df = text_df.sort_values("timestamp")
    if len(text_df) > max_msgs:
        # Campionamento uniforme deterministico su tutta la timeline.
        idx = (pd.Series(range(max_msgs)) * (len(text_df) - 1) / (max_msgs - 1)).round().astype(int)
        text_df = text_df.iloc[idx.unique()]

    lines = [
        f"[{r['timestamp']:%Y-%m-%d}] {r['sender']}: {str(r['text_clean'])[:max_chars]}"
        for _, r in text_df.iterrows()
    ]
    return "\n".join(lines)


def analyze_comm_style(
    df: pd.DataFrame,
    me: str | None = None,
    other: str | None = None,
    client: OllamaClient | None = None,
    cfg: dict | None = None,
) -> dict:
    """Analisi esplorativa dello stile comunicativo dei due interlocutori."""
    cfg = cfg or load_config()
    client = client or OllamaClient(cfg)

    names = [n for n in (me, other) if n] or list(df["sender"].unique())
    interlocutori = " e ".join(map(str, names))

    transcript = _sample_transcript(df, cfg)
    prompt = (
        load_prompt("comm_style.txt")
        .replace("<<INTERLOCUTORI>>", interlocutori)
        .replace("<<TRANSCRIPT>>", transcript)
    )
    fallback = {
        "per_persona": [],
        "dinamica_coppia": "",
        "avvertenza": "Questa sezione è speculativa e non costituisce un giudizio sulle persone reali.",
    }
    res = client.chat_json(prompt, fallback=fallback)
    if not isinstance(res, dict):
        res = fallback
    # Garantisci sempre l'avvertenza.
    res.setdefault("avvertenza", fallback["avvertenza"])
    return res


def save_comm_style(result: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
