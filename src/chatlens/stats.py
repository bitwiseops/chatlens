"""Metriche puramente deterministiche, calcolate in pandas.

PRINCIPIO: qui non entra mai l'LLM. Tutto ciò che è conteggiabile (frequenze, orari,
tempi di risposta, emoji, chi inizia le conversazioni) si calcola qui ed è riproducibile.
Output serializzato in data/processed/stats.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import load_config


def _py(obj: Any) -> Any:
    """Rende ricorsivamente l'oggetto serializzabile in JSON (no tipi numpy/Timestamp)."""
    if isinstance(obj, dict):
        return {str(k): _py(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_py(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if isinstance(obj, float):
        return None if np.isnan(obj) else obj
    return obj


def _per_sender(df: pd.DataFrame, col: str, agg: str = "sum") -> dict[str, Any]:
    return df.groupby("sender")[col].agg(agg).to_dict()


def response_times(df: pd.DataFrame, gap_minutes: int) -> dict[str, dict[str, float]]:
    """Tempi di risposta (secondi) per mittente: messaggi consecutivi di mittenti diversi
    entro la soglia di sessione (gap_minutes). Restituisce mediana/media/conteggio."""
    out: dict[str, list[float]] = {}
    ts = df["timestamp"].to_numpy()
    senders = df["sender"].to_numpy()
    gap_s = gap_minutes * 60
    for i in range(1, len(df)):
        if senders[i] == senders[i - 1]:
            continue
        dt = (ts[i] - ts[i - 1]) / np.timedelta64(1, "s")
        if dt <= gap_s:
            out.setdefault(senders[i], []).append(float(dt))
    return {
        s: {"mediana": float(np.median(v)), "media": float(np.mean(v)), "n": len(v)}
        for s, v in out.items()
    }


def conversation_starters(df: pd.DataFrame, gap_minutes: int) -> dict[str, Any]:
    """Chi inizia le conversazioni: primo messaggio dopo un gap > soglia (e il primissimo)."""
    if df.empty:
        return {"sessioni": 0, "chi_inizia": {}, "gap_minuti": gap_minutes}
    ts = df["timestamp"].to_numpy()
    senders = df["sender"].to_numpy()
    gap_s = gap_minutes * 60
    starters: dict[str, int] = {}
    sessions = 0
    for i in range(len(df)):
        new_session = i == 0 or (ts[i] - ts[i - 1]) / np.timedelta64(1, "s") > gap_s
        if new_session:
            sessions += 1
            starters[senders[i]] = starters.get(senders[i], 0) + 1
    return {"sessioni": sessions, "chi_inizia": starters, "gap_minuti": gap_minutes}


def compute_stats(df: pd.DataFrame, cfg: dict | None = None) -> dict[str, Any]:
    """Calcola tutte le metriche deterministiche e restituisce un dict serializzabile."""
    cfg = cfg or load_config()
    gap_minutes = int(cfg["windows"]["session_gap_minutes"])

    df = df.sort_values("timestamp").reset_index(drop=True)
    text_df = df[~df["is_media"]]  # solo messaggi testuali per parole/caratteri

    month = df["timestamp"].dt.to_period("M").astype(str)

    stats = {
        "periodo": {
            "inizio": df["timestamp"].min(),
            "fine": df["timestamp"].max(),
            "giorni": int(df["date"].nunique()),
        },
        "totali": {
            "messaggi": int(len(df)),
            "per_mittente": _per_sender(df, "n_chars", "count"),
        },
        "media": {
            "totali": int(df["is_media"].sum()),
            "per_mittente": df[df["is_media"]].groupby("sender").size().to_dict(),
        },
        "parole": {
            "totali": int(text_df["n_words"].sum()),
            "per_mittente": _per_sender(text_df, "n_words", "sum"),
            "media_per_messaggio": _per_sender(text_df, "n_words", "mean"),
        },
        "caratteri": {
            "totali": int(text_df["n_chars"].sum()),
            "per_mittente": _per_sender(text_df, "n_chars", "sum"),
        },
        "emoji": {
            "totali": int(df["n_emoji"].sum()),
            "per_mittente": _per_sender(df, "n_emoji", "sum"),
        },
        "orari": {
            "per_ora": df.groupby("hour").size().reindex(range(24), fill_value=0).to_dict(),
            "per_giorno_settimana": df.groupby("weekday").size().to_dict(),
            "per_mese": df.groupby(month).size().to_dict(),
        },
        "tempi_risposta_secondi": {
            "per_mittente": response_times(df, gap_minutes),
        },
        "iniziativa": conversation_starters(df, gap_minutes),
    }
    return _py(stats)


def save_stats(stats: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=2)
