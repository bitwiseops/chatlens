"""Test del parser: schema, formati iOS/Android, multilinea, righe di sistema, media."""

from __future__ import annotations

from pathlib import Path

import pytest

from chatlens.parse import COLUMNS, parse_chat

FIXTURE = Path(__file__).parent / "fixtures" / "sample_chat.txt"


@pytest.fixture(scope="module")
def df():
    return parse_chat(FIXTURE)


def test_schema_colonne_esatte(df):
    assert list(df.columns) == COLUMNS


def test_scarta_sistema_e_eliminati(df):
    # Riga crittografia (sender-less) e "messaggio eliminato" devono sparire.
    assert len(df) == 6
    assert df["text"].str.contains("crittografati").sum() == 0
    assert df["text"].str.contains("è stato eliminato").sum() == 0


def test_solo_due_mittenti(df):
    assert set(df["sender"]) == {"Flavio", "Giulia"}


def test_multilinea_collassata(df):
    msg = df[df["text"].str.startswith("Tutto bene")].iloc[0]
    assert msg["text"] == "Tutto bene grazie\nOggi giornata piena"
    assert msg["n_words"] == 6
    assert msg["sender"] == "Flavio"


def test_media_flag_it_en(df):
    media = df[df["is_media"]]
    assert len(media) == 2  # <Media omessi> (IT) + image omitted (EN)
    assert (media["text_clean"] == "").all()
    assert (media["n_chars"] == 0).all()


def test_emoji_contate(df):
    # Giulia: 😊 e 🌙 -> 2; Flavio: 0
    per_sender = df.groupby("sender")["n_emoji"].sum().to_dict()
    assert per_sender["Giulia"] == 2
    assert per_sender["Flavio"] == 0


def test_colonne_derivate(df):
    riga = df.iloc[0]
    assert riga["hour"] == 9
    assert riga["weekday"] == "venerdì"  # 12/01/2024 è venerdì
    assert str(riga["date"]) == "2024-01-12"


def test_fallisce_senza_messaggi(tmp_path):
    bad = tmp_path / "vuoto.txt"
    bad.write_text("nessun messaggio qui\nsolo testo libero\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Nessun messaggio riconosciuto"):
        parse_chat(bad)


def test_formato_ios(tmp_path):
    # Formato iOS: [gg/mm/aaaa, hh:mm:ss] Nome: testo, con AM/PM e multilinea.
    ios = tmp_path / "ios.txt"
    ios.write_text(
        "[12/01/2024, 9:05:00 AM] Flavio: Buongiorno\n"
        "[12/01/2024, 2:00:30 PM] Giulia: Ciao\nseconda riga\n"
        "[12/01/2024, 2:01:00 PM] Flavio: ‎<allegato: IMG-001.jpg>\n",
        encoding="utf-8",
    )
    d = parse_chat(ios)
    assert list(d.columns) == COLUMNS
    assert len(d) == 3
    # AM/PM convertiti correttamente
    assert d.iloc[0]["hour"] == 9
    assert d.iloc[1]["hour"] == 14
    # multilinea
    assert d.iloc[1]["text"] == "Ciao\nseconda riga"
    # allegato iOS riconosciuto come media
    assert bool(d.iloc[2]["is_media"]) is True


def test_separatori_data(tmp_path):
    # Android con separatori '.' e '-'
    f = tmp_path / "sep.txt"
    f.write_text(
        "12.01.2024, 09:05 - Flavio: punto\n"
        "12-01-2024, 09:06 - Giulia: trattino\n",
        encoding="utf-8",
    )
    d = parse_chat(f)
    assert len(d) == 2
    assert str(d.iloc[0]["date"]) == "2024-01-12"
    assert str(d.iloc[1]["date"]) == "2024-01-12"
