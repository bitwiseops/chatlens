"""Strato 1 — Temi e riassunti via map-reduce sull'LLM locale.

Map: ogni finestra -> {temi, riassunto}. Reduce: aggrega i temi ricorrenti su tutta la
cronologia con conteggio/trend. Il deterministico (conteggi di messaggi) resta in stats.py;
qui si usa l'LLM solo per la semantica.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from . import load_config
from .llm import OllamaClient, load_prompt
from .windows import make_windows, render_transcript


def _map_window(client: OllamaClient, transcript: str, periodo: str) -> dict:
    prompt = (
        load_prompt("theme_extraction.txt")
        .replace("<<PERIODO>>", periodo)
        .replace("<<TRANSCRIPT>>", transcript)
    )
    res = client.chat_json(prompt, fallback={"temi": [], "riassunto": ""})
    if not isinstance(res, dict):
        res = {"temi": [], "riassunto": ""}
    res.setdefault("temi", [])
    res.setdefault("riassunto", "")
    return res


def summarize(
    df: pd.DataFrame, client: OllamaClient | None = None, cfg: dict | None = None
) -> dict:
    """Esegue map (per finestra) + reduce (aggregazione temi). Ritorna un dict."""
    cfg = cfg or load_config()
    client = client or OllamaClient(cfg)

    cooldown = float(cfg["llm"].get("cooldown_s", 0))
    windows = make_windows(df, cfg=cfg)
    per_window = []
    for i, w in enumerate(windows):
        transcript = render_transcript(w, cfg)
        if not transcript.strip():
            continue
        periodo = f"{w.start:%Y-%m-%d} – {w.end:%Y-%m-%d}"
        res = _map_window(client, transcript, periodo)
        per_window.append({"finestra": w.label, "periodo": periodo, **res})
        if cooldown and i < len(windows) - 1:
            time.sleep(cooldown)  # pausa di raffreddamento GPU

    # Reduce
    reduce_prompt = load_prompt("aggregate_themes.txt").replace(
        "<<FINESTRE>>", json.dumps(per_window, ensure_ascii=False, indent=2)
    )
    aggregato = client.chat_json(
        reduce_prompt, fallback={"temi_ricorrenti": [], "panoramica": ""}
    )
    if not isinstance(aggregato, dict):
        aggregato = {"temi_ricorrenti": [], "panoramica": ""}

    return {"finestre": per_window, "aggregato": aggregato, "modalita": cfg["windows"]["mode"]}


def save_themes(result: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
