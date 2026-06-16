"""chatlens — analisi locale e privata di chat WhatsApp a due.

Tutto è locale: l'unico endpoint di rete ammesso è Ollama su localhost.
Vedi CLAUDE.md per i vincoli di privacy e il principio deterministico/LLM.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

__version__ = "0.1.0"

# Radice del progetto (…/chat-analysis), risalendo da src/chatlens/__init__.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


@lru_cache(maxsize=None)
def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Carica config.yaml (single source of truth). Cache-ata per processo."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"config.yaml non trovato in {cfg_path}. "
            "Esegui i comandi dalla radice del progetto."
        )
    with cfg_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def resolve_path(key: str, cfg: dict[str, Any] | None = None) -> Path:
    """Restituisce un percorso da config['paths'][key] relativo alla radice progetto."""
    cfg = cfg or load_config()
    rel = cfg["paths"][key]
    p = Path(rel)
    return p if p.is_absolute() else PROJECT_ROOT / p
