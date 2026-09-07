"""CLI entry point. Only `serve` and `authors list` are implemented in M1;
the rest of SPEC section 9's command list (index, write, export, eval,
backup) lands with the milestones that give them something to do."""

from __future__ import annotations

import typer

from diary.core.style.profile import has_index, list_author_slugs, load_author_profile

app = typer.Typer(add_completion=False)


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Start the web UI."""
    import uvicorn

    uvicorn.run("diary.app.main:app", host=host, port=port, reload=reload)


authors_app = typer.Typer(add_completion=False)
app.add_typer(authors_app, name="authors")


@authors_app.command("list")
def authors_list() -> None:
    """List authors available under authors/ (data-driven, SPEC 3.1)."""
    slugs = list_author_slugs()
    if not slugs:
        typer.echo("Brak autorów w katalogu authors/.")
        raise typer.Exit(code=0)
    for slug in slugs:
        profile = load_author_profile(slug)
        index_status = "indeks: tak" if has_index(slug) else "indeks: brak (samo style card)"
        typer.echo(f"{profile.slug}\t{profile.name}\t{index_status}")


if __name__ == "__main__":
    app()
