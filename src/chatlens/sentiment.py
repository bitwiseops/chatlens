"""Strato 2 — Andamento emotivo/relazionale nel tempo via LLM locale.

Per ogni finestra: valenza, toni, reciprocità/iniziativa, calore/tensione. I risultati
vengono aggregati in una serie storica (CSV) plottata poi da report.py.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import load_config
from .llm import OllamaClient, load_prompt
from .windows import make_windows, render_transcript

# Schema della serie storica (colonne del CSV).
_FIELDS = ["valenza", "reciprocita", "calore", "tensione", "iniziativa", "toni", "nota"]
_FALLBACK = {
    "valenza": 0.0, "reciprocita": 0.0, "calore": 0.0, "tensione": 0.0,
    "iniziativa": "n/d", "toni": [], "nota": "",
}


def _analyze_window(client: OllamaClient, transcript: str, periodo: str) -> dict:
    prompt = (
        load_prompt("sentiment_window.txt")
        .replace("<<PERIODO>>", periodo)
        .replace("<<TRANSCRIPT>>", transcript)
    )
    res = client.chat_json(prompt, fallback=dict(_FALLBACK))
    if not isinstance(res, dict):
        res = dict(_FALLBACK)
    out = dict(_FALLBACK)
    out.update({k: res.get(k, _FALLBACK[k]) for k in _FIELDS})
    return out


def analyze_sentiment(
    df: pd.DataFrame, client: OllamaClient | None = None, cfg: dict | None = None
) -> pd.DataFrame:
    """Calcola la serie storica di sentiment finestra per finestra."""
    cfg = cfg or load_config()
    client = client or OllamaClient(cfg)

    rows = []
    for w in make_windows(df, cfg=cfg):
        transcript = render_transcript(w, cfg)
        if not transcript.strip():
            continue
        periodo = f"{w.start:%Y-%m-%d} – {w.end:%Y-%m-%d}"
        res = _analyze_window(client, transcript, periodo)
        # 'toni' è una lista: la serializziamo in stringa per il CSV.
        toni = res.get("toni", [])
        res["toni"] = ", ".join(toni) if isinstance(toni, list) else str(toni)
        rows.append(
            {"finestra": w.label, "inizio": w.start, "fine": w.end,
             "n_messaggi": len(w.df), **res}
        )

    return pd.DataFrame(rows)


def save_sentiment(series: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    series.to_csv(path, index=False)
