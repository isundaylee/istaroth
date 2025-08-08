#!/usr/bin/env python3
"""CLI interface for audio transcription."""

import sys
from pathlib import Path

import click

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(Path(__file__).parent.parent))

from istaroth import transcribe
from istaroth.agd import localization


@click.command()
@click.argument("audio_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--language",
    "-l",
    type=click.Choice(["CHS", "ENG"], case_sensitive=False),
    default="CHS",
    help="Language of the audio file (default: CHS)",
)
def main(audio_file: Path, language: str):
    """Transcribe an audio file and print the result to stdout."""
    lang_enum = localization.Language[language.upper()]

    try:
        transcriber = transcribe.AudioTranscriber()
        result = transcriber.transcribe(audio_file, lang_enum)
        print(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
