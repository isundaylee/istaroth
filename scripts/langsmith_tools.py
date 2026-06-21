#!/usr/bin/env python3
"""Query LangSmith tracing data from the production RAG service."""

from __future__ import annotations

import itertools
import json
import os
import sys
from datetime import UTC, datetime, timedelta

import click
import langsmith


def _make_client() -> langsmith.Client:
    api_key = os.environ.get("LANGSMITH_API_KEY")
    endpoint = os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    if not api_key:
        sys.exit("LANGSMITH_API_KEY not set; source .env.common first")
    return langsmith.Client(api_url=endpoint, api_key=api_key)


def _project_name() -> str:
    name = os.environ.get("LANGSMITH_PROJECT")
    if not name:
        sys.exit("LANGSMITH_PROJECT not set; source .env.common first")
    return name


def _format_run(run: langsmith.schemas.Run, *, verbose: bool) -> dict:
    out: dict = {
        "id": str(run.id),
        "name": run.name,
        "start_time": run.start_time.isoformat() if run.start_time else None,
        "status": run.status,
        "run_type": run.run_type,
    }
    if run.inputs:
        out["inputs"] = run.inputs
    if run.outputs:
        out["outputs"] = run.outputs
    if run.error:
        out["error"] = run.error
    if verbose:
        out["tags"] = run.tags
        out["total_tokens"] = run.total_tokens
        out["total_cost"] = str(run.total_cost) if run.total_cost else None
    return out


@click.group()
def cli() -> None:
    """LangSmith production trace tools."""


@cli.command("list-queries")
@click.option("--hours", default=24.0, show_default=True, help="Look back N hours.")
@click.option("--limit", default=50, show_default=True, help="Max runs to return.")
@click.option("--verbose", "-v", is_flag=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
def list_queries(hours: float, limit: int, verbose: bool, as_json: bool) -> None:
    """List recent top-level pipeline_query runs."""
    client = _make_client()
    since = datetime.now(UTC) - timedelta(hours=hours)

    run_iter = client.list_runs(
        project_name=_project_name(),
        run_type="chain",
        filter='eq(name, "pipeline_query")',
        is_root=True,
        start_time=since,
    )

    results = [
        _format_run(r, verbose=verbose) for r in itertools.islice(run_iter, limit)
    ]

    if as_json:
        click.echo(json.dumps(results, indent=2, default=str))
        return

    for r in results:
        ts = r["start_time"] or "?"
        status = r.get("status") or "?"
        q = (r.get("inputs") or {}).get("question", "")
        click.echo(f"[{ts}] {status:10s}  {q}")
        if verbose and (answer := ((r.get("outputs") or {}).get("answer") or "")[:120]):
            click.echo(f"  -> {answer}")
        if r.get("error"):
            click.echo(f"  ERROR: {r['error'][:200]}")


@cli.command("trace")
@click.argument("trace_id")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
def show_trace(trace_id: str, as_json: bool) -> None:
    """Show the full span tree for a single trace."""
    client = _make_client()

    runs = sorted(
        client.list_runs(project_name=_project_name(), trace_id=trace_id),
        key=lambda r: r.dotted_order or "",
    )

    if as_json:
        click.echo(
            json.dumps(
                [_format_run(r, verbose=True) for r in runs], indent=2, default=str
            )
        )
        return

    for r in runs:
        depth = len((r.dotted_order or "").split(".")) - 1
        indent = "  " * depth
        elapsed = (
            f" ({(r.end_time - r.start_time).total_seconds():.2f}s)"
            if r.start_time and r.end_time
            else ""
        )
        click.echo(f"{indent}{r.run_type:10s}  {r.name}{elapsed}")
        if r.error:
            click.echo(f"{indent}  ERROR: {r.error[:200]}")


@cli.command("errors")
@click.option("--hours", default=24.0, show_default=True)
@click.option("--limit", default=20, show_default=True)
@click.option("--json", "as_json", is_flag=True)
def list_errors(hours: float, limit: int, as_json: bool) -> None:
    """Show recent errored runs."""
    client = _make_client()
    since = datetime.now(UTC) - timedelta(hours=hours)

    results = [
        _format_run(r, verbose=True)
        for r in client.list_runs(
            project_name=_project_name(),
            error=True,
            is_root=True,
            start_time=since,
            limit=limit,
        )
    ]

    if as_json:
        click.echo(json.dumps(results, indent=2, default=str))
        return

    for r in results:
        click.echo(f"[{r['start_time']}]  {r['name']}")
        click.echo(f"  ERROR: {r.get('error', '')[:300]}")
        if q := (r.get("inputs") or {}).get("question", ""):
            click.echo(f"  query: {q}")


@cli.command("projects")
def list_projects() -> None:
    """List available LangSmith projects."""
    client = _make_client()
    for p in client.list_projects():
        click.echo(f"{p.id}  {p.name}")


if __name__ == "__main__":
    cli()
