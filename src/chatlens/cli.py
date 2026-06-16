"""Entrypoint CLI (typer): parse, stats, summarize, sentiment, comm-style, report, all.

Ogni comando legge/scrive da data/processed/. I comandi deterministici (parse, stats)
non richiedono Ollama; gli strati semantici sì.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from . import load_config, resolve_path
from .llm import OllamaError

app = typer.Typer(add_completion=False, help="chatlens — analisi locale di chat WhatsApp a due.")


def _find_raw(cfg: dict) -> Path:
    raw_dir = resolve_path("raw_dir", cfg)
    txts = sorted(raw_dir.glob("*.txt"))
    if not txts:
        raise typer.BadParameter(
            f"Nessun .txt in {raw_dir}. Specifica il percorso o copia l'export lì."
        )
    if len(txts) > 1:
        raise typer.BadParameter(
            f"Più .txt in {raw_dir}: specifica quale. Trovati: {[t.name for t in txts]}"
        )
    return txts[0]


@app.command()
def parse(
    path: Optional[Path] = typer.Argument(None, help="Export .txt (default: unico file in data/raw)"),
    anonymize: bool = typer.Option(False, "--anonymize", help="Pseudonimizza i nomi"),
):
    """Esegue il parsing dell'export -> messaggi.parquet (deterministico)."""
    from .parse import parse_chat, save_parquet

    cfg = load_config()
    src = path or _find_raw(cfg)
    typer.echo(f"Parsing: {src}")
    df = parse_chat(src)

    if anonymize:
        from .anonymize import anonymize_df, save_mapping
        df, mapping = anonymize_df(df)
        save_mapping(mapping, resolve_path("processed_dir", cfg) / "anonymize_map.json")
        typer.echo(f"Pseudonimizzati: {mapping}")

    out = resolve_path("messages_parquet", cfg)
    save_parquet(df, out)
    typer.echo(f"OK: {len(df)} messaggi -> {out}")


@app.command()
def stats():
    """Calcola le metriche deterministiche -> stats.json."""
    from .parse import load_parquet
    from .stats import compute_stats, save_stats

    cfg = load_config()
    df = load_parquet(resolve_path("messages_parquet", cfg))
    s = compute_stats(df, cfg)
    out = resolve_path("stats_json", cfg)
    save_stats(s, out)
    typer.echo(f"OK: statistiche -> {out}")


@app.command()
def summarize():
    """Estrae temi e riassunti (LLM, map-reduce) -> temi.json."""
    from .parse import load_parquet
    from .summarize import save_themes, summarize as run_summarize

    cfg = load_config()
    df = load_parquet(resolve_path("messages_parquet", cfg))
    typer.echo("Estrazione temi (map-reduce)… può richiedere tempo.")
    res = run_summarize(df, cfg=cfg)
    out = resolve_path("themes_json", cfg)
    save_themes(res, out)
    typer.echo(f"OK: temi -> {out}")


@app.command()
def sentiment():
    """Calcola l'andamento emotivo/relazionale (LLM) -> sentiment.csv."""
    from .parse import load_parquet
    from .sentiment import analyze_sentiment, save_sentiment

    cfg = load_config()
    df = load_parquet(resolve_path("messages_parquet", cfg))
    typer.echo("Analisi sentiment per finestra…")
    series = analyze_sentiment(df, cfg=cfg)
    out = resolve_path("sentiment_csv", cfg)
    save_sentiment(series, out)
    typer.echo(f"OK: {len(series)} finestre -> {out}")


@app.command(name="comm-style")
def comm_style(
    me: Optional[str] = typer.Option(None, "--me"),
    other: Optional[str] = typer.Option(None, "--other"),
):
    """Analisi esplorativa dello stile comunicativo (LLM) -> comm_style.json."""
    from .comm_style import analyze_comm_style, save_comm_style
    from .parse import load_parquet

    cfg = load_config()
    df = load_parquet(resolve_path("messages_parquet", cfg))
    typer.echo("Analisi stile comunicativo (esplorativa)…")
    res = analyze_comm_style(df, me=me, other=other, cfg=cfg)
    out = resolve_path("comm_style_json", cfg)
    save_comm_style(res, out)
    typer.echo(f"OK: stile comunicativo -> {out}")


@app.command()
def report():
    """Genera report.md + grafici da tutti gli artefatti disponibili."""
    from .report import build_report

    cfg = load_config()
    out = build_report(cfg)
    typer.echo(f"OK: report -> {out}")


@app.command()
def all(
    path: Optional[Path] = typer.Argument(None, help="Export .txt (default: unico file in data/raw)"),
    me: Optional[str] = typer.Option(None, "--me"),
    other: Optional[str] = typer.Option(None, "--other"),
    anonymize: bool = typer.Option(False, "--anonymize", help="Pseudonimizza i nomi"),
):
    """Pipeline completa: parse → stats → summarize → sentiment → comm-style → report.

    I passi deterministici (parse, stats) vengono sempre eseguiti. Se Ollama non è
    disponibile, i passi semantici vengono saltati con un avviso e il report viene
    comunque generato con le parti deterministiche.
    """
    from .comm_style import analyze_comm_style, save_comm_style
    from .parse import load_parquet, parse_chat, save_parquet
    from .report import build_report
    from .sentiment import analyze_sentiment, save_sentiment
    from .stats import compute_stats, save_stats
    from .summarize import save_themes, summarize as run_summarize

    cfg = load_config()

    # --- deterministico ---
    src = path or _find_raw(cfg)
    typer.echo(f"[1/6] parse: {src}")
    df = parse_chat(src)
    if anonymize:
        from .anonymize import anonymize_df, save_mapping
        df, mapping = anonymize_df(df)
        save_mapping(mapping, resolve_path("processed_dir", cfg) / "anonymize_map.json")
    save_parquet(df, resolve_path("messages_parquet", cfg))

    typer.echo("[2/6] stats")
    save_stats(compute_stats(df, cfg), resolve_path("stats_json", cfg))

    # --- semantico (LLM): tollerante ai fallimenti ---
    try:
        typer.echo("[3/6] summarize (LLM)")
        save_themes(run_summarize(df, cfg=cfg), resolve_path("themes_json", cfg))
        typer.echo("[4/6] sentiment (LLM)")
        save_sentiment(analyze_sentiment(df, cfg=cfg), resolve_path("sentiment_csv", cfg))
        typer.echo("[5/6] comm-style (LLM)")
        save_comm_style(
            analyze_comm_style(df, me=me, other=other, cfg=cfg),
            resolve_path("comm_style_json", cfg),
        )
    except OllamaError as exc:
        typer.secho(f"⚠️  Passi semantici saltati: {exc}", fg=typer.colors.YELLOW)

    typer.echo("[6/6] report")
    out = build_report(cfg)
    typer.secho(f"✅ Pipeline completata -> {out}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
