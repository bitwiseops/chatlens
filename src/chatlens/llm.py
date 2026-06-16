"""Client Ollama (locale): chat + embeddings, retry e parsing JSON robusto.

PRIVACY: l'unico endpoint contattato è l'host Ollama in config (default localhost:11434).
Nessun'altra rete. Se Ollama non risponde, gli errori sono espliciti.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import httpx

from . import load_config

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


class OllamaError(RuntimeError):
    """Errore di comunicazione con Ollama (server spento, modello assente, ecc.)."""


def load_prompt(name: str) -> str:
    """Carica un template di prompt versionato da prompts/<name>."""
    path = _PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt non trovato: {path}")
    return path.read_text(encoding="utf-8")


def _extract_json(text: str) -> Any | None:
    """Estrae il primo oggetto/array JSON da un testo, con riparazioni minime."""
    # Rimuovi eventuali fence ```json ... ```
    text = re.sub(r"```(?:json)?", "", text).strip()
    # Trova il primo blocco bilanciato { } o [ ]
    start = min(
        [i for i in (text.find("{"), text.find("[")) if i != -1],
        default=-1,
    )
    if start == -1:
        return None
    open_ch = text[start]
    close_ch = "}" if open_ch == "{" else "]"
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                candidate = text[start: i + 1]
                # Riparazione: rimuovi virgole pendenti prima di } o ]
                candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None
    return None


class OllamaClient:
    """Client minimale per l'API HTTP di Ollama."""

    def __init__(self, cfg: dict | None = None):
        cfg = cfg or load_config()
        oc = cfg["ollama"]
        self.host: str = oc["host"].rstrip("/")
        self.chat_model: str = oc["chat_model"]
        self.embed_model: str = oc["embed_model"]
        self.temperature: float = float(oc["temperature"])
        self.timeout: float = float(oc["timeout_s"])
        self.max_retries: int = int(oc["max_retries"])
        self.lingua: str = cfg.get("lingua", "it")

    # --- infrastruttura ---
    def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.host}{endpoint}"
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = httpx.post(url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                raise OllamaError(
                    f"Impossibile contattare Ollama su {self.host}. "
                    "Avvia il server con `ollama serve` e scarica i modelli "
                    "(`ollama pull <modello>`)."
                ) from exc
            except (httpx.HTTPStatusError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                time.sleep(1.5 * (attempt + 1))  # backoff lineare deterministico
        raise OllamaError(f"Ollama ha fallito dopo {self.max_retries} tentativi: {last_exc}")

    # --- chat ---
    def chat(self, prompt: str, system: str | None = None) -> str:
        """Una singola richiesta di chat; restituisce il testo della risposta."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        data = self._post(
            "/api/chat",
            {
                "model": self.chat_model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": self.temperature},
            },
        )
        return data.get("message", {}).get("content", "")

    def chat_json(
        self, prompt: str, system: str | None = None, fallback: Any | None = None
    ) -> Any:
        """Come chat(), ma forza output JSON e lo parsa in modo robusto.

        Se il modello non restituisce JSON valido, ritorna `fallback`.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        data = self._post(
            "/api/chat",
            {
                "model": self.chat_model,
                "messages": messages,
                "stream": False,
                "format": "json",  # Ollama vincola l'output a JSON
                "options": {"temperature": self.temperature},
            },
        )
        raw = data.get("message", {}).get("content", "")
        parsed = _extract_json(raw)
        return parsed if parsed is not None else fallback

    # --- embeddings ---
    def embed(self, text: str) -> list[float]:
        """Embedding di un testo (per RAG futuro)."""
        data = self._post(
            "/api/embeddings",
            {"model": self.embed_model, "prompt": text},
        )
        return data.get("embedding", [])

    def health(self) -> bool:
        """True se il server Ollama risponde."""
        try:
            httpx.get(f"{self.host}/", timeout=5).raise_for_status()
            return True
        except httpx.HTTPError:
            return False
