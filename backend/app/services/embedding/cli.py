"""typer-based CLI for the embedding + rerank service (REQ-048 T017 — skeleton)."""
from __future__ import annotations

import typer

app = typer.Typer(help="Embedding + Rerank service CLI")


@app.command()
def health() -> None:
    """Probe the embedding service /health endpoint."""
    typer.echo('{"status": "ok", "models_loaded": []}')


@app.command()
def embed(text: str = typer.Option(..., "--text")) -> None:
    """Encode a single text and print a 512-dim vector (Phase 4 body)."""
    typer.echo("[0.0] * 512  # skeleton — Phase 4 implementation")


@app.command()
def embed_batch(file: str = typer.Option(..., "--file")) -> None:
    """Encode a batch of texts from a JSON-lines file (Phase 4 body)."""
    typer.echo(f"# skeleton — Phase 4 implementation. file={file}")


__all__ = ["app"]