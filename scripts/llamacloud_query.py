#!/usr/bin/env python3
"""Test script for querying LlamaCloud index."""

import os
import sys

import click
from llama_index.indices.managed.llama_cloud import LlamaCloudIndex


@click.command()  # type: ignore[misc]
@click.argument("query", type=str)  # type: ignore[misc]
def main(query: str) -> None:
    """Query the LlamaCloud index.

    QUERY: The query string to search for
    """
    api_key = os.getenv("LLAMACLOUD_API_KEY")
    if not api_key:
        click.echo("Error: LLAMACLOUD_API_KEY environment variable not set", err=True)
        sys.exit(1)

    index = LlamaCloudIndex(
        name="Istorath-test1",
        project_name="Default",
        organization_id="fe7da418-1bfb-4751-9083-b1324dd1b8b2",
        api_key=api_key,
    )

    # Perform the query
    response = index.as_query_engine().query(query)
    click.echo(str(response))


if __name__ == "__main__":
    main()
