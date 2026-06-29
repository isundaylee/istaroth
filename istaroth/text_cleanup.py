"""Text cleanup utilities for processing game text markers."""

import re
from typing import Callable

from istaroth.agd import localization

# ``{PLAYERAVATAR#SEXPRO[<male-branch>|<female-branch>]}`` (and the sibling
# ``{MATEAVATAR#SEXPRO[...]}`` variant) select a gendered pronoun/appellation from
# the player's chosen traveler gender. The corpus consistently renders the first
# (male-player) branch, matching the ``{M#...}{F#...}`` -> M convention. Each branch
# is a language-neutral ``INFO_*_PRONOUN_*`` token; the captured group is the first
# branch, the female branch is matched but discarded.
_SEXPRO_PATTERN = re.compile(r"\{(?:PLAYER|MATE)AVATAR#SEXPRO\[([^|\]]+)\|[^\]]+\]\}")


def resolve_sexpro(text: str, resolve_token: Callable[[str], str]) -> str:
    """Replace SEXPRO placeholders with their first (male-player) branch's text.

    ``resolve_token`` maps an ``INFO_*_PRONOUN_*`` token to its raw text; it should
    raise on an unknown token so a new one surfaces. Run this before
    ``clean_text_markers`` so a branch that itself carries a nested gender macro
    (e.g. INFO_MALE_PRONOUN_BROANDSIS) is then handled by its ``{M#...}{F#...}`` pass.
    """
    return _SEXPRO_PATTERN.sub(lambda m: resolve_token(m.group(1)), text)


def clean_text_markers(text: str, language: localization.Language) -> str:
    """Clean game text markers and normalize newlines.

    Does not resolve SEXPRO pronoun placeholders (those need TextMap access); run
    ``resolve_sexpro`` first where they may appear.
    """
    if not text:
        return text

    # Get localized names for nickname replacement
    localized_names = localization.get_localized_role_names(language)

    # Replace escape sequences
    text = text.replace("\\n", "\n")

    # Replace {NICKNAME} with appropriate traveler name
    text = re.sub(r"\{NICKNAME\}", localized_names.player, text)

    # Replace {M#option1}{F#option2} with M option
    text = re.sub(r"\{M#([^}]+)\}\{F#[^}]+\}", r"\1", text)

    # Replace <color=#RRGGBBAA>content</color> with markdown emphasis
    text = re.sub(r"<color=#[0-9A-Fa-f]{8}>([^<]*)</color>", r"*\1*", text)

    return text
