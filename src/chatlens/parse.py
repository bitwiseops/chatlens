"""Parser degli export WhatsApp (iOS + Android) -> DataFrame conforme al contratto-dati.

Output (data/processed/messaggi.parquet), colonne esatte:
    timestamp (datetime), sender (str), text (str grezzo), text_clean (str, vuoto se media),
    is_media (bool), n_chars (int), n_words (int), n_emoji (int),
    date (date), hour (int), weekday (str)

Strategia: una riga che inizia con un header datato apre un nuovo messaggio; le righe
successive non datate sono continuazioni (multilinea). Le righe di sistema vengono scartate.
Tutto è deterministico: nessuna chiamata di rete, nessun LLM.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

# Colonne esatte del contratto-dati, nell'ordine.
COLUMNS = [
    "timestamp", "sender", "text", "text_clean", "is_media",
    "n_chars", "n_words", "n_emoji", "date", "hour", "weekday",
]

# Caratteri di formattazione invisibili che WhatsApp/iOS inseriscono.
_INVISIBLE = dict.fromkeys(map(ord, "‎‏‪‬  "), None)

# Nomi giorno in italiano (timestamp.weekday(): 0 = lunedì).
_WEEKDAYS_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]

# --- Header iOS:  [gg/mm/aaaa, hh:mm:ss] resto
_IOS_RE = re.compile(
    r"^\[(?P<date>\d{1,2}[./-]\d{1,2}[./-]\d{2,4}),\s*"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap]\.?\s?[Mm]\.?)?)\]\s*"
    r"(?P<body>.*)$"
)
# --- Header Android:  gg/mm/aaaa, hh:mm - resto
_ANDROID_RE = re.compile(
    r"^(?P<date>\d{1,2}[./-]\d{1,2}[./-]\d{2,4}),\s*"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap]\.?\s?[Mm]\.?)?)\s+-\s+"
    r"(?P<body>.*)$"
)

# Marker dei media (IT + EN), come riga intera (eventuale prefisso già ripulito).
_MEDIA_RE = re.compile(
    r"^("
    r"<media omessi?>|<media omitted>|"                       # Android
    r"<allegato:.*>|<attached:.*>|"                            # iOS
    r"(immagine|foto|video|audio|gif|sticker|adesivo|documento|contatto)\s+(omess[aoi]|non incluso|esclus[ao])|"
    r"(image|video|audio|gif|sticker|document|contact card|voice message)\s+omitted|"
    r"\.?(opus|jpg|jpeg|png|webp|mp4|m4a|pdf)\s*\(file allegato\)|"
    r".*\(file (allegato|attached)\)"
    r")\s*$",
    re.IGNORECASE,
)

# Frasi di sistema/notifica (sender-less) da scartare, IT + EN.
_SYSTEM_PATTERNS = re.compile(
    r"(crittografat|end-to-end|messaggi e (le )?chiamate|"
    r"hai creato il gruppo|ha creato il gruppo|"
    r"ha cambiato (il |l')?(oggetto|icona|numero|descrizione)|"
    r"è entrato|è uscito|ha aggiunto|ha rimosso|"
    r"messaggio eliminato|hai eliminato questo messaggio|questo messaggio è stato eliminato|"
    r"i messaggi sono effimeri|le chiamate sono|"
    r"messages and calls are end-to-end encrypted|"
    r"you (created|added|removed|left)|changed (the )?(subject|group|icon)|"
    r"this message was deleted|you deleted this message|missed (voice|video) call)",
    re.IGNORECASE,
)

# Range Unicode delle emoji (sufficiente per il conteggio).
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"   # simboli & pittogrammi, emoticon, oggetti, ecc.
    "\U00002600-\U000027BF"   # misc symbols & dingbats
    "\U0001F1E6-\U0001F1FF"   # bandiere (regional indicators)
    "\U00002190-\U000021FF"   # frecce
    "\U00002B00-\U00002BFF"   # stelle/frecce varie
    "\U0000FE00-\U0000FE0F"   # variation selectors
    "\U00002700-\U000027BF"
    "]",
    flags=re.UNICODE,
)


def _clean_line(line: str) -> str:
    """Rimuove caratteri invisibili e newline finali."""
    return line.translate(_INVISIBLE).rstrip("\n").rstrip("\r")


def _parse_datetime(date_str: str, time_str: str) -> datetime:
    """Converte (data, ora) in datetime, day-first (locale italiano), 24h o AM/PM."""
    d_norm = re.sub(r"[.\-]", "/", date_str)
    day, month, year = (int(x) for x in d_norm.split("/"))
    if year < 100:
        year += 2000
    # Day-first; se incoerente (es. mm/dd), prova a invertire.
    if day > 31 and month <= 31:
        day, month = month, day
    if month > 12 and day <= 12:
        day, month = month, day

    t = time_str.strip().lower().replace(".", "")
    ampm = None
    m = re.search(r"\b([ap])\s?m\b", t)
    if m:
        ampm = m.group(1)
        t = re.sub(r"\b[ap]\s?m\b", "", t).strip()
    parts = [int(x) for x in t.split(":")]
    hour, minute = parts[0], parts[1]
    second = parts[2] if len(parts) > 2 else 0
    if ampm == "p" and hour != 12:
        hour += 12
    elif ampm == "a" and hour == 12:
        hour = 0
    return datetime(year, month, day, hour, minute, second)


def _split_sender(body: str) -> tuple[str | None, str]:
    """Divide 'Nome: testo' al primo ': '. Ritorna (None, body) se non c'è sender."""
    idx = body.find(": ")
    # Un sender plausibile non contiene a capo e non è troppo lungo.
    if idx != -1 and "\n" not in body[:idx] and len(body[:idx]) <= 80:
        return body[:idx].strip(), body[idx + 2:]
    if body.endswith(":"):  # messaggio vuoto dopo il nome
        return body[:-1].strip(), ""
    return None, body


def _count_emoji(text: str) -> int:
    return len(_EMOJI_RE.findall(text))


def _is_media(text: str) -> bool:
    return bool(_MEDIA_RE.match(text.strip()))


def _match_header(line: str):
    """Ritorna (datetime, body) se la riga è un header datato, altrimenti None."""
    m = _IOS_RE.match(line) or _ANDROID_RE.match(line)
    if not m:
        return None
    try:
        ts = _parse_datetime(m.group("date"), m.group("time"))
    except (ValueError, IndexError):
        return None
    return ts, m.group("body")


def parse_chat(path: str | Path) -> pd.DataFrame:
    """Esegue il parsing di un export WhatsApp e restituisce il DataFrame del contratto-dati.

    Solleva ValueError se nessun messaggio viene riconosciuto.
    """
    path = Path(path)
    raw = path.read_text(encoding="utf-8", errors="replace")

    records: list[dict] = []
    cur: dict | None = None  # messaggio in costruzione (per multilinea)

    def _flush():
        if cur is not None:
            records.append(cur)

    for raw_line in raw.splitlines():
        line = _clean_line(raw_line)
        header = _match_header(line)

        if header is None:
            # Riga non datata: continuazione del messaggio corrente (multilinea).
            if cur is not None and line:
                cur["text"] = f"{cur['text']}\n{line}"
            continue

        ts, body = header
        sender, text = _split_sender(body)

        # Nuovo header -> chiudi il precedente.
        _flush()
        cur = None

        if sender is None or _SYSTEM_PATTERNS.search(body):
            # Riga di sistema/notifica: scartata, e non apre un messaggio.
            continue

        cur = {"timestamp": ts, "sender": sender, "text": text}

    _flush()

    if not records:
        raise ValueError(
            f"Nessun messaggio riconosciuto in {path}. "
            "Verifica che sia un export WhatsApp (.txt) iOS o Android non modificato."
        )

    df = pd.DataFrame.from_records(records)
    return _finalize(df)


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Aggiunge le colonne derivate del contratto-dati e ordina per timestamp."""
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    is_media = df["text"].map(_is_media)
    df["is_media"] = is_media
    df["text_clean"] = df["text"].where(~is_media, "")
    df["n_chars"] = df["text_clean"].str.len().astype("int64")
    df["n_words"] = df["text_clean"].str.split().map(len).astype("int64")
    df["n_emoji"] = df["text_clean"].map(_count_emoji).astype("int64")
    df["date"] = df["timestamp"].dt.date
    df["hour"] = df["timestamp"].dt.hour.astype("int64")
    df["weekday"] = df["timestamp"].dt.weekday.map(lambda i: _WEEKDAYS_IT[i])

    return df[COLUMNS]


def save_parquet(df: pd.DataFrame, path: str | Path) -> None:
    """Salva il DataFrame in Parquet (crea la cartella se serve)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def load_parquet(path: str | Path) -> pd.DataFrame:
    """Ricarica il DataFrame dei messaggi dal Parquet."""
    return pd.read_parquet(path)
