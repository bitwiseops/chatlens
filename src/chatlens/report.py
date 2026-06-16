"""Report markdown autocontenuto + grafici matplotlib, tutto offline.

Legge gli artefatti deterministici e semantici da data/processed/ e produce report.md con
grafici salvati localmente: attività per mese, heatmap oraria, timeline del sentiment,
tempi di risposta. Include il disclaimer sulla sezione stile comunicativo.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # nessuna finestra/display: rendering offline su file
import matplotlib.pyplot as plt
import pandas as pd

from . import load_config, resolve_path

_WEEKDAY_ORDER = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


def _load_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# --------------------------- grafici ---------------------------

def _fig_attivita_mese(df: pd.DataFrame, out: Path) -> Path | None:
    serie = df.groupby(df["timestamp"].dt.to_period("M").astype(str)).size()
    if serie.empty:
        return None
    fig, ax = plt.subplots(figsize=(10, 4))
    serie.plot(kind="bar", ax=ax, color="#4C72B0")
    ax.set_title("Messaggi per mese")
    ax.set_xlabel("Mese")
    ax.set_ylabel("N. messaggi")
    fig.tight_layout()
    p = out / "attivita_mese.png"
    fig.savefig(p, dpi=120)
    plt.close(fig)
    return p


def _fig_heatmap_oraria(df: pd.DataFrame, out: Path) -> Path | None:
    pivot = (
        df.assign(weekday=pd.Categorical(df["weekday"], categories=_WEEKDAY_ORDER, ordered=True))
        .pivot_table(index="weekday", columns="hour", values="text", aggfunc="size", fill_value=0)
        .reindex(index=_WEEKDAY_ORDER, columns=range(24), fill_value=0)
    )
    fig, ax = plt.subplots(figsize=(11, 4))
    im = ax.imshow(pivot.values, aspect="auto", cmap="magma")
    ax.set_yticks(range(len(_WEEKDAY_ORDER)), _WEEKDAY_ORDER)
    ax.set_xticks(range(0, 24, 2), [f"{h:02d}" for h in range(0, 24, 2)])
    ax.set_title("Heatmap oraria (giorno × ora)")
    ax.set_xlabel("Ora del giorno")
    fig.colorbar(im, ax=ax, label="N. messaggi")
    fig.tight_layout()
    p = out / "heatmap_oraria.png"
    fig.savefig(p, dpi=120)
    plt.close(fig)
    return p


def _fig_sentiment(sent: pd.DataFrame, out: Path) -> Path | None:
    if sent is None or sent.empty or "valenza" not in sent:
        return None
    s = sent.copy()
    s["inizio"] = pd.to_datetime(s["inizio"])
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(s["inizio"], pd.to_numeric(s["valenza"], errors="coerce"), marker="o", color="#C44E52")
    ax.axhline(0, color="gray", lw=0.8, ls="--")
    ax.set_ylim(-1.05, 1.05)
    ax.set_title("Timeline del sentiment (valenza per finestra)")
    ax.set_xlabel("Tempo")
    ax.set_ylabel("Valenza (-1 … +1)")
    fig.tight_layout()
    p = out / "sentiment_timeline.png"
    fig.savefig(p, dpi=120)
    plt.close(fig)
    return p


def _fig_tempi_risposta(stats: dict, out: Path) -> Path | None:
    rt = stats.get("tempi_risposta_secondi", {}).get("per_mittente", {})
    if not rt:
        return None
    nomi = list(rt)
    mediane = [rt[n]["mediana"] / 60 for n in nomi]  # in minuti
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(nomi, mediane, color="#55A868")
    ax.set_title("Tempo di risposta mediano")
    ax.set_ylabel("Minuti")
    fig.tight_layout()
    p = out / "tempi_risposta.png"
    fig.savefig(p, dpi=120)
    plt.close(fig)
    return p


# --------------------------- markdown ---------------------------

def build_report(cfg: dict | None = None) -> Path:
    """Costruisce report.md + grafici a partire dagli artefatti in data/processed/."""
    cfg = cfg or load_config()
    figures_dir = resolve_path("figures_dir", cfg)
    figures_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(resolve_path("messages_parquet", cfg))
    stats = _load_json(resolve_path("stats_json", cfg)) or {}
    themes = _load_json(resolve_path("themes_json", cfg))
    comm = _load_json(resolve_path("comm_style_json", cfg))
    sent_path = resolve_path("sentiment_csv", cfg)
    sent = pd.read_csv(sent_path) if sent_path.exists() else None

    figs = {
        "attivita": _fig_attivita_mese(df, figures_dir),
        "heatmap": _fig_heatmap_oraria(df, figures_dir),
        "sentiment": _fig_sentiment(sent, figures_dir),
        "tempi": _fig_tempi_risposta(stats, figures_dir),
    }

    report_path = resolve_path("report_md", cfg)
    rel = lambda p: p.relative_to(report_path.parent).as_posix() if p else None

    md: list[str] = ["# Report chatlens\n"]
    md.append("> Analisi generata interamente in locale. I dati non hanno lasciato la macchina.\n")

    # Panoramica deterministica
    if stats:
        per = stats.get("totali", {}).get("per_mittente", {})
        periodo = stats.get("periodo", {})
        md.append("## Panoramica\n")
        md.append(f"- **Periodo:** {periodo.get('inizio','?')} → {periodo.get('fine','?')} "
                  f"({periodo.get('giorni','?')} giorni)")
        md.append(f"- **Messaggi totali:** {stats.get('totali',{}).get('messaggi','?')}")
        md.append(f"- **Per mittente:** " + ", ".join(f"{k}: {v}" for k, v in per.items()))
        md.append(f"- **Media condivisi:** {stats.get('media',{}).get('totali','?')}")
        md.append(f"- **Emoji totali:** {stats.get('emoji',{}).get('totali','?')}")
        ini = stats.get("iniziativa", {})
        if ini.get("chi_inizia"):
            md.append(f"- **Chi inizia (su {ini.get('sessioni','?')} sessioni):** "
                      + ", ".join(f"{k}: {v}" for k, v in ini["chi_inizia"].items()))
        md.append("")

    # Grafici
    md.append("## Attività nel tempo\n")
    if figs["attivita"]:
        md.append(f"![Messaggi per mese]({rel(figs['attivita'])})\n")
    if figs["heatmap"]:
        md.append("## Quando scrivete\n")
        md.append(f"![Heatmap oraria]({rel(figs['heatmap'])})\n")
    if figs["tempi"]:
        md.append("## Tempi di risposta\n")
        md.append(f"![Tempi di risposta]({rel(figs['tempi'])})\n")

    # Temi (LLM)
    if themes and themes.get("aggregato"):
        agg = themes["aggregato"]
        md.append("## Temi ricorrenti\n")
        if agg.get("panoramica"):
            md.append(agg["panoramica"] + "\n")
        for t in agg.get("temi_ricorrenti", []):
            md.append(f"- **{t.get('tema','?')}** — {t.get('occorrenze','?')} finestre "
                      f"(_{t.get('trend','')}_)")
        md.append("")

    # Sentiment (LLM)
    if figs["sentiment"]:
        md.append("## Andamento emotivo/relazionale\n")
        md.append(f"![Timeline sentiment]({rel(figs['sentiment'])})\n")
        if sent is not None and not sent.empty:
            md.append(f"- Valenza media: **{pd.to_numeric(sent['valenza'], errors='coerce').mean():.2f}** "
                      f"(scala -1…+1)\n")

    # Stile comunicativo (LLM, esplorativo) — con disclaimer
    if comm:
        md.append("## Stile comunicativo (esplorativo)\n")
        md.append("> ⚠️ **Disclaimer.** Questa sezione è **speculativa e non diagnostica**: "
                  "sono ipotesi su pattern linguistici osservabili, non un verdetto su una "
                  "persona reale. Va presa come spunto, non come giudizio.\n")
        for p in comm.get("per_persona", []):
            md.append(f"### {p.get('nome','?')}")
            md.append(f"- Registro: {p.get('registro','n/d')}")
            md.append(f"- Domande: {p.get('domande','n/d')}")
            for oss in p.get("osservazioni", []):
                md.append(f"- {oss}")
            md.append("")
        if comm.get("dinamica_coppia"):
            md.append(f"**Dinamica di coppia:** {comm['dinamica_coppia']}\n")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(md), encoding="utf-8")
    return report_path
