"""Test delle metriche deterministiche su dati noti della fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

from chatlens.parse import parse_chat
from chatlens.stats import compute_stats

FIXTURE = Path(__file__).parent / "fixtures" / "sample_chat.txt"


@pytest.fixture(scope="module")
def stats():
    df = parse_chat(FIXTURE)
    return compute_stats(df)


def test_totali_messaggi(stats):
    assert stats["totali"]["messaggi"] == 6
    assert stats["totali"]["per_mittente"] == {"Flavio": 3, "Giulia": 3}


def test_media_per_mittente(stats):
    assert stats["media"]["totali"] == 2
    assert stats["media"]["per_mittente"] == {"Flavio": 1, "Giulia": 1}


def test_emoji(stats):
    assert stats["emoji"]["totali"] == 2
    assert stats["emoji"]["per_mittente"]["Giulia"] == 2


def test_iniziativa(stats):
    # 3 sessioni (gap 6h): Flavio inizia 2 (09:05 e 18:00), Giulia 1 (13/01 21:30)
    assert stats["iniziativa"]["sessioni"] == 3
    assert stats["iniziativa"]["chi_inizia"] == {"Flavio": 2, "Giulia": 1}


def test_tempi_risposta(stats):
    rt = stats["tempi_risposta_secondi"]["per_mittente"]
    # Entro la sessione del 12/01 mattina:
    #   Giulia risponde a 09:05->09:06 (60s) e 09:07->09:10 (180s) -> mediana 120
    #   Flavio risponde a 09:06->09:07 (60s) -> mediana 60
    assert rt["Giulia"]["n"] == 2
    assert rt["Giulia"]["mediana"] == 120.0
    assert rt["Flavio"]["n"] == 1
    assert rt["Flavio"]["mediana"] == 60.0


def test_periodo(stats):
    assert stats["periodo"]["giorni"] == 2  # 12 e 13 gennaio (il 14 era eliminato)


def test_serializzabile(stats, tmp_path):
    import json
    from chatlens.stats import save_stats

    out = tmp_path / "stats.json"
    save_stats(stats, out)
    reloaded = json.loads(out.read_text(encoding="utf-8"))
    assert reloaded["totali"]["messaggi"] == 6
