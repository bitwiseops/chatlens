"""Pseudonimizzazione dei nomi — utility opzionale di privacy.

Da usare PRIMA di condividere qualsiasi output: sostituisce i nomi reali (mittenti e loro
menzioni nel testo) con pseudonimi stabili. La mappa reversibile resta solo in locale.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


def build_mapping(names: list[str]) -> dict[str, str]:
    """Crea una mappa stabile nome_reale -> pseudonimo (Persona A, Persona B, …)."""
    letters = (chr(ord("A") + i) for i in range(26))
    return {name: f"Persona {next(letters)}" for name in dict.fromkeys(names)}


def anonymize_df(
    df: pd.DataFrame, mapping: dict[str, str] | None = None
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Restituisce una copia del DataFrame con nomi pseudonimizzati e la mappa usata."""
    mapping = mapping or build_mapping(sorted(df["sender"].unique()))
    out = df.copy()
    out["sender"] = out["sender"].map(lambda s: mapping.get(s, s))

    # Sostituisci anche le menzioni dei nomi nel testo (match su parola intera).
    if mapping:
        pattern = re.compile(
            r"\b(" + "|".join(re.escape(n) for n in mapping) + r")\b"
        )
        repl = lambda m: mapping[m.group(0)]
        for col in ("text", "text_clean"):
            out[col] = out[col].map(
                lambda t: pattern.sub(repl, t) if isinstance(t, str) and t else t
            )
    return out, mapping


def save_mapping(mapping: dict[str, str], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(mapping, fh, ensure_ascii=False, indent=2)
