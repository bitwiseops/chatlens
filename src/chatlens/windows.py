"""Segmentazione della cronologia in finestre temporali per il map-reduce semantico.

Ogni strato LLM (summarize, sentiment, comm_style) lavora finestra per finestra: non si
assume mai che l'intera chat entri nel context del modello.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import load_config


@dataclass
class Window:
    """Una finestra di conversazione."""
    label: str            # etichetta leggibile, es. "2024-W02" o "2024-01-12"
    start: pd.Timestamp
    end: pd.Timestamp
    df: pd.DataFrame      # sottoinsieme dei messaggi nella finestra


def _session_ids(df: pd.DataFrame, gap_minutes: int) -> pd.Series:
    gap = pd.Timedelta(minutes=gap_minutes)
    new_session = df["timestamp"].diff() > gap
    new_session.iloc[0] = True
    return new_session.cumsum()


def make_windows(
    df: pd.DataFrame, mode: str | None = None, cfg: dict | None = None
) -> list[Window]:
    """Segmenta il DataFrame in finestre secondo `mode` (weekly | daily | session)."""
    cfg = cfg or load_config()
    mode = mode or cfg["windows"]["mode"]
    df = df.sort_values("timestamp").reset_index(drop=True)
    if df.empty:
        return []

    if mode == "weekly":
        iso = df["timestamp"].dt.isocalendar()
        keys = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    elif mode == "daily":
        keys = df["timestamp"].dt.date.astype(str)
    elif mode == "session":
        keys = "S" + _session_ids(df, int(cfg["windows"]["session_gap_minutes"])).astype(str)
    else:
        raise ValueError(f"Modalità finestra sconosciuta: {mode!r} (weekly|daily|session)")

    windows: list[Window] = []
    for label, sub in df.groupby(keys, sort=False):
        windows.append(
            Window(
                label=str(label),
                start=sub["timestamp"].min(),
                end=sub["timestamp"].max(),
                df=sub.reset_index(drop=True),
            )
        )
    return windows


def render_transcript(window: Window, cfg: dict | None = None) -> str:
    """Rende una finestra come trascrizione compatta 'Nome: testo' per l'LLM.

    Applica i limiti di config (max messaggi/finestra, max caratteri/messaggio).
    È l'UNICO punto in cui il testo della chat viene passato al modello.
    """
    cfg = cfg or load_config()
    max_msgs = int(cfg["llm"]["max_messages_per_window"])
    max_chars = int(cfg["llm"]["max_chars_per_message"])

    rows = window.df
    truncated = len(rows) > max_msgs
    if truncated:
        # Mantieni inizio e fine della finestra (dove c'è più segnale).
        head = rows.iloc[: max_msgs // 2]
        tail = rows.iloc[-max_msgs // 2:]
        rows = pd.concat([head, tail])

    lines: list[str] = []
    for _, r in rows.iterrows():
        ts = r["timestamp"].strftime("%Y-%m-%d %H:%M")
        if r["is_media"]:
            body = "[media]"
        else:
            body = str(r["text_clean"])[:max_chars]
        lines.append(f"[{ts}] {r['sender']}: {body}")

    if truncated:
        lines.insert(len(lines) // 2, "[…finestra troncata…]")
    return "\n".join(lines)
