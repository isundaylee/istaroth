"""Text cleanup utilities for processing game text markers."""

import re
from typing import Mapping

from istaroth.agd import localization

# ``{PLAYERAVATAR#SEXPRO[<male-branch>|<female-branch>]}`` (and the sibling
# ``{MATEAVATAR#SEXPRO[...]}`` variant) select a gendered pronoun/appellation from
# the player's chosen traveler gender. The corpus consistently renders the first
# (male-player) branch, matching the ``{M#...}{F#...}`` -> M convention below. Each
# branch is a language-neutral ``INFO_*_PRONOUN_*`` token resolved to text via
# ``pronoun_map`` (built at runtime from a pinned AGD revision, see DataRepo). The
# captured token is the first branch; the female branch is matched but discarded.
_SEXPRO_PATTERN = re.compile(r"\{(?:PLAYER|MATE)AVATAR#SEXPRO\[([^|\]]+)\|[^\]]+\]\}")


def _resolve_sexpro(match: re.Match[str], pronoun_map: Mapping[str, str]) -> str:
    """Render a SEXPRO placeholder as its first (male-player) branch's text."""
    return pronoun_map[match.group(1)]


def clean_text_markers(
    text: str,
    language: localization.Language,
    *,
    pronoun_map: Mapping[str, str],
) -> str:
    """Clean game text markers and normalize newlines.

    ``pronoun_map`` resolves the ``INFO_*_PRONOUN_*`` tokens inside SEXPRO
    placeholders; an unmapped token raises so a new one surfaces. Pass an empty
    mapping for text that cannot contain such placeholders.
    """
    if not text:
        return text

    # Get localized names for nickname replacement
    localized_names = localization.get_localized_role_names(language)

    # Replace escape sequences
    text = text.replace("\\n", "\n")

    # Resolve {PLAYERAVATAR/MATEAVATAR#SEXPRO[male|female]} to the male-branch text
    # before the {M#...}{F#...} pass below, so a branch that itself carries a nested
    # gender macro (e.g. INFO_MALE_PRONOUN_BROANDSIS) is handled too.
    text = _SEXPRO_PATTERN.sub(lambda m: _resolve_sexpro(m, pronoun_map), text)

    # Replace {NICKNAME} with appropriate traveler name
    text = re.sub(r"\{NICKNAME\}", localized_names.player, text)

    # Replace {M#option1}{F#option2} with M option
    text = re.sub(r"\{M#([^}]+)\}\{F#[^}]+\}", r"\1", text)

    # Replace <color=#RRGGBBAA>content</color> with markdown emphasis
    text = re.sub(r"<color=#[0-9A-Fa-f]{8}>([^<]*)</color>", r"*\1*", text)

    return text
