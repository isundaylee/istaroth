#!/usr/bin/env python3
"""Build the per-version first-seen delta files from AGD git history.

For each snapshot in ``_SNAPSHOTS`` (oldest first), enumerates the source ids
present in that AGD revision and writes the ids never seen in any earlier
snapshot to ``text/first_seen/<version>.json`` (committed to the ``text/``
submodule alongside the corpus regen it stamps). Reads everything
via ``git show``/``git ls-tree`` against the AGD repo's history — no checkout
switching. The default run only generates files missing on disk (ingesting a
new game version = append its ``_SNAPSHOTS`` entry and rerun); ``--rebuild-all``
regenerates every file, doubling as a determinism check of the committed data.
"""

import pathlib
import subprocess
from typing import Any

import click
import orjson

from istaroth.agd import first_seen

# The last AGD snapshot commit of each game version, oldest first. Curated by
# hand from `git log origin/master v2/main` because commit subjects are not
# reliable enough to parse blindly:
# - the 3.3 snapshot's subject is mislabeled "OSRELWin3.0.0_R11806263" (it sits
#   between the 3.2 and 3.4 snapshots and its R build number is above 3.2's);
# - hotfix snapshots repeat a version, and 1.6.1/4.0.1 normalize to 1.6/4.0;
# - no 4.1 snapshot was ever published, so 4.1 additions attribute to 4.2;
# - versions before 1.4 predate the history, so the 1.4 file is a baseline
#   ("1.4 or earlier"); CN and OS snapshots of a version are interchangeable.
_SNAPSHOTS: list[tuple[str, str]] = [
    ("1.4", "86c28c0a59526cad72d5ec6548a0d6b3a9413826"),
    ("1.5", "5ee08c0771f257ac06f37293973e6bf42302fa76"),
    ("1.6", "9eeb6591fa5de850a0486fa6c2691e1f468d3d91"),
    ("2.0", "97ec5bf557d7dd301beac19ab72cdf4edf9def0a"),
    ("2.1", "23e4d9800ee43bfc21f16a7441af18b6acf59f68"),
    ("2.2", "a92b5842daa911c095f47ef235b2bcd4b388d65a"),
    ("2.3", "3d39b3502bdcec8d936f82f32ecc36f65eaba2b2"),
    ("2.4", "27a2ca1cb72393e3b4a8420e830912f7704d4fff"),
    ("2.5", "f6b76a7c958c121e43d4612d7d54e327066d2e73"),
    ("2.6", "ecb5c64aa4fcba4ed83f69bee28103770061c189"),
    ("2.7", "ebb117f78dab56e704853b71fa60f45ee2cefe79"),
    ("2.8", "d56ed231c4513963d27051dd6f7828f0e06c2588"),
    ("3.0", "45c509efd76550b17e394774fd90bec248ccefdb"),
    ("3.1", "4c5e4f6889ee820be814c71e663bf19c2bf2275d"),
    ("3.2", "e7c944395d00f0dc1848a66703c73d9763dfc5cc"),
    ("3.3", "1a6597f5a67382119494beae22a4039a1cefc8e1"),
    ("3.4", "28662783890fd9c3a16404e1971d37a23a7045ca"),
    ("3.5", "410cafbc9ba35274b96a44f7b9e9c85be43a2334"),
    ("3.6", "9aa4937b7dddc506677617150e29803004fee964"),
    ("3.7", "23109cab0def51d4b598a91b33a1f642a83d0359"),
    ("3.8", "6b5b54aa48e0158350cd82d0732d1667140dd860"),
    ("4.0", "4f872fefab5ed8c6c6b72899e47bcb0344416a4f"),
    ("4.2", "d2a73df4ff40bd9e666f86773012a5f52b548b0f"),
    ("4.3", "ecce481664b72fa2ea1d141ed7d6d08acb80d63b"),
    ("4.4", "61eaba93568a69466951b1c2bc5efe2157963bdc"),
    ("4.5", "8c43a454992c4e339bf0b79b74cd081f8e8a2cca"),
    ("4.6", "85c2f9e54ced5df20e50065abc3db73d0d07ce87"),
    ("4.7", "c4775ae8295fa55703af9d6cd42ad39acadd508c"),
    ("4.8", "411376ae92931a04d41ae5a9386d45c0d2deb8a8"),
    ("5.0", "f90e7b375ea9a6441952c49a672f868028a9f92d"),
    ("5.1", "92931454c0f7a703c64a1e3baec83571753bc0eb"),
    ("5.2", "3847f0fc6e3119b87767508ac7471dff6a7b51d0"),
    ("5.3", "51f5e2eaab4c1a7f4692ac3454122b28024ec62c"),
    ("5.4", "dee14cc45e977782e1e93be9d3ed4b0d12e90e5a"),
    ("5.5", "0077f79f1676bad3b121017fe2098bedbe284712"),
    ("5.6", "cb46dc84d8897b49fbfbe944035fac5abc520f6f"),
    ("5.7", "de661bd09b262ce320f78a03bc0adc437f8729a3"),
    ("5.8", "13be4fd7343fe4cee8fa0096fe854b1c5b01b124"),
    ("6.0", "4f9f22c8842a9e840baa51ff579b26dd248079ba"),
    ("6.1", "f83066c8c20ced632c6fb07d8a4fb0ab8fbb4192"),
    ("6.2", "2f0f85f19885ee632d9eab37226c9e60d8f1216f"),
    ("6.3", "fe7c8592b2fd1cd3f285de5039285c99e641a5e1"),
    ("6.4", "b761e4d2e9e509eb8aa8c04c381b46d2308d7e85"),
    ("6.5", "f9a21406731cd33242defd88dfc2aa06674ab353"),
    ("6.6", "4d9593eb73a52e3fd79c30c4f22f97be4a71ba36"),
    ("6.7", "82e74382e7788e318ad41fca926739a752c0bed6"),
]

# Filename-keyed domains scan these languages and union the stems; the sets are
# expected to match across languages, so the union just guards stragglers.
_SCAN_LANGUAGES = ("CHS", "EN")

_EXCEL_FILES: dict[first_seen.SourceDomain, tuple[str, str]] = {
    first_seen.SourceDomain.MAIN_QUEST: ("MainQuestExcelConfigData.json", "id"),
    first_seen.SourceDomain.MATERIAL: ("MaterialExcelConfigData.json", "id"),
    first_seen.SourceDomain.WEAPON: ("WeaponExcelConfigData.json", "id"),
    first_seen.SourceDomain.ACHIEVEMENT: ("AchievementExcelConfigData.json", "id"),
    first_seen.SourceDomain.AVATAR: ("AvatarExcelConfigData.json", "id"),
    first_seen.SourceDomain.ARTIFACT_SET: ("ReliquarySetExcelConfigData.json", "setId"),
    first_seen.SourceDomain.ANIMAL_CODEX: ("AnimalCodexExcelConfigData.json", "id"),
}


def _git(agd_path: pathlib.Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(agd_path), *args], capture_output=True, check=True
    ).stdout


def _ls_names(agd_path: pathlib.Path, commit: str, directory: str) -> list[str]:
    """List file names directly under ``directory`` at ``commit``."""
    out = _git(agd_path, "ls-tree", "--name-only", commit, f"{directory}/")
    return [line.rsplit("/", 1)[-1] for line in out.decode().splitlines() if line]


def _row_id(row: dict[str, Any], id_key: str) -> int:
    # Field-name style varies by era (and by file within one era): 1.x dumps
    # use PascalCase ("Id"/"SetId"), some ~2.7-3.x dumps underscore-prefixed
    # camelCase ("_id"), current dumps plain camelCase.
    for key in (id_key, id_key[0].upper() + id_key[1:], f"_{id_key}"):
        if key in row:
            return int(row[key])
    raise KeyError(f"No {id_key!r} field in excel row: {sorted(row)[:5]}...")


def _excel_ids(
    agd_path: pathlib.Path, commit: str, filename: str, id_key: str
) -> set[int | str]:
    rows = orjson.loads(_git(agd_path, "show", f"{commit}:ExcelBinOutput/{filename}"))
    return {_row_id(row, id_key) for row in rows}


def _talk_ids(agd_path: pathlib.Path, commit: str) -> set[int | str]:
    """Talk ids from TalkExcelConfigData.json, or its recent _N-split files."""
    split_names = sorted(
        name
        for name in _ls_names(agd_path, commit, "ExcelBinOutput")
        if name.startswith("TalkExcelConfigData_")
    )
    names = split_names if split_names else ["TalkExcelConfigData.json"]
    ids: set[int | str] = set()
    for name in names:
        ids |= _excel_ids(agd_path, commit, name, "id")
    return ids


def _stem_keys(
    agd_path: pathlib.Path, commit: str, directory: str, *, allow_missing: bool
) -> set[int | str]:
    """Language-neutral filename stems under ``directory``'s language subdirs."""
    keys: set[int | str] = set()
    found = False
    for language in _SCAN_LANGUAGES:
        names = _ls_names(agd_path, commit, f"{directory}/{language}")
        found = found or bool(names)
        keys |= {
            first_seen.strip_language_suffix(pathlib.PurePosixPath(name).stem)
            for name in names
        }
    if not found and not allow_missing:
        raise FileNotFoundError(f"No {directory} files at {commit}")
    return keys


def _scan_snapshot(
    agd_path: pathlib.Path, commit: str
) -> dict[first_seen.SourceDomain, set[int | str]]:
    """Enumerate all source ids present in one AGD snapshot."""
    present = {
        domain: _excel_ids(agd_path, commit, filename, id_key)
        for domain, (filename, id_key) in _EXCEL_FILES.items()
    }
    present[first_seen.SourceDomain.TALK] = _talk_ids(agd_path, commit)
    present[first_seen.SourceDomain.READABLE] = _stem_keys(
        agd_path, commit, "Readable", allow_missing=False
    )
    # Subtitles only exist from 1.6 onward.
    present[first_seen.SourceDomain.SUBTITLE] = _stem_keys(
        agd_path, commit, "Subtitle", allow_missing=True
    )
    return present


def _delta_path(version: str) -> pathlib.Path:
    return first_seen.DATA_DIR / f"{version}.json"


def _write_delta(
    version: str, commit: str, new: dict[first_seen.SourceDomain, set[int | str]]
) -> None:
    payload = {
        "version": version,
        "commit": commit,
        "new": {
            domain.value: sorted(new[domain]) for domain in first_seen.SourceDomain
        },
    }
    _delta_path(version).write_bytes(
        orjson.dumps(payload, option=orjson.OPT_INDENT_2) + b"\n"
    )


@click.command()
@click.option(
    "--agd-path",
    envvar="AGD_PATH",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=pathlib.Path),
    help="AGD repo whose git history holds the snapshots.",
)
@click.option(
    "--rebuild-all",
    is_flag=True,
    help="Regenerate every delta file instead of only the missing ones.",
)
def main(agd_path: pathlib.Path, rebuild_all: bool) -> None:
    """Generate missing first-seen delta files (or all with --rebuild-all)."""
    first_seen.DATA_DIR.mkdir(parents=True, exist_ok=True)
    seen: dict[first_seen.SourceDomain, set[int | str]] = {
        domain: set() for domain in first_seen.SourceDomain
    }
    missing_earlier: list[str] = []
    for version, commit in _SNAPSHOTS:
        if not rebuild_all and _delta_path(version).exists():
            if missing_earlier:
                raise RuntimeError(
                    f"Delta file for {version} exists but earlier versions "
                    f"{missing_earlier} are missing; run with --rebuild-all"
                )
            data = orjson.loads(_delta_path(version).read_bytes())
            if data["commit"] != commit:
                raise RuntimeError(
                    f"Committed {version}.json was built from {data['commit']}, "
                    f"but _SNAPSHOTS lists {commit}; run with --rebuild-all"
                )
            for domain_name, keys in data["new"].items():
                seen[first_seen.SourceDomain(domain_name)].update(keys)
            click.echo(f"{version}: kept existing delta")
            continue
        missing_earlier.append(version)
        present = _scan_snapshot(agd_path, commit)
        new = {domain: present[domain] - seen[domain] for domain in seen}
        for domain in seen:
            seen[domain] |= present[domain]
        _write_delta(version, commit, new)
        click.echo(
            f"{version}: wrote {sum(len(ids) for ids in new.values())} new ids "
            f"({', '.join(f'{d.value}={len(new[d])}' for d in seen if new[d])})"
        )


if __name__ == "__main__":
    main()
