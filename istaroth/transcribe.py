"""Audio transcription module using OpenAI's API."""

import os
from pathlib import Path
from typing import ClassVar

import openai

from istaroth.agd import localization


class AudioTranscriber:
    """Transcribe audio files using OpenAI's GPT-4 transcription model."""

    _LANGUAGE_MAP: ClassVar[dict[localization.Language, str]] = {
        localization.Language.CHS: "zh",
        localization.Language.ENG: "en",
    }
    """Map Language enum to OpenAI language codes."""

    def __init__(self, model: str = "gpt-4o-transcribe"):
        """Initialize the transcriber with model."""
        self.model = model
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable."
            )
        self.client = openai.OpenAI(api_key=api_key)

    def transcribe(
        self, audio_file_path: str | Path, language: localization.Language
    ) -> str:
        """Transcribe an audio file."""
        audio_path = Path(audio_file_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if language not in self._LANGUAGE_MAP:
            raise ValueError(f"Unsupported language: {language}")

        openai_language = self._LANGUAGE_MAP[language]

        with audio_path.open("rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model=self.model,
                file=audio_file,
                language=openai_language,
                response_format="text",
            )
            return transcript
