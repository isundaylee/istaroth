#!/usr/bin/env python3
"""Script to create GitHub releases with checkpoint .tar.gz files."""

import datetime
import glob
import pathlib
import re
import subprocess
import sys
import urllib.parse

import click


def _get_current_commit_hash() -> str:
    """Get the current git commit hash."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _get_current_date() -> str:
    """Get current date in YYYYMMDD format."""
    return datetime.datetime.now().strftime("%Y%m%d")


def _find_checkpoint_files(checkpoints_pattern: str) -> list[pathlib.Path]:
    """Find checkpoint files using glob pattern."""
    # Use shell expansion to find files
    checkpoint_files = [pathlib.Path(f) for f in glob.glob(checkpoints_pattern)]
    if not checkpoint_files:
        click.echo(
            f"Error: No files found matching pattern: {checkpoints_pattern}", err=True
        )
        sys.exit(1)

    # Validate all files exist and are .tar.gz files
    for f in checkpoint_files:
        if not f.exists():
            click.echo(f"Error: File does not exist: {f}", err=True)
            sys.exit(1)
        if not f.name.endswith(".tar.gz"):
            click.echo(f"Error: File is not a .tar.gz file: {f}", err=True)
            sys.exit(1)

    return sorted(checkpoint_files)


def _create_release_tag(date: str, commit_hash: str) -> str:
    """Create release tag in format checkpoint/YYYYMMDD-[commit_hash]."""
    return f"checkpoint/{date}-{commit_hash}"


def _release_exists(tag: str) -> bool:
    """Check if a release with the given tag already exists."""
    try:
        subprocess.run(["gh", "release", "view", tag], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def _git_tag_exists(tag: str) -> bool:
    """Check if a git tag already exists."""
    try:
        result = subprocess.run(
            ["git", "tag", "-l", tag], capture_output=True, text=True, check=True
        )
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        return False


def _create_and_push_git_tag(tag: str, commit_hash: str) -> None:
    """Create and push git tag."""
    # Delete existing tag if it exists
    if _git_tag_exists(tag):
        click.echo(f"⚠️  Git tag {tag} already exists. Deleting...")
        subprocess.run(["git", "tag", "-d", tag], check=True)
        # Also delete from remote
        try:
            subprocess.run(["git", "push", "origin", "--delete", tag], check=True)
        except subprocess.CalledProcessError:
            # Tag might not exist on remote, ignore error
            pass

    # Create new tag
    click.echo(f"🏷️  Creating git tag {tag}...")
    subprocess.run(["git", "tag", tag, commit_hash], check=True)

    # Push tag to remote
    click.echo(f"📤 Pushing git tag to remote...")
    subprocess.run(["git", "push", "origin", tag], check=True)


def _update_docker_entrypoint(tag: str, checkpoint_files: list[pathlib.Path]) -> None:
    """Update the default checkpoint URL in docker-entrypoint.sh."""
    # Determine the main checkpoint file (prefer chs.tar.gz, then first alphabetically)
    chs_checkpoints = [f for f in checkpoint_files if f.name == "chs.tar.gz"]
    if not chs_checkpoints:
        click.echo(f"⚠️  No chs.tar.gz checkpoint found, skipping URL update")
        return

    [main_checkpoint] = chs_checkpoints

    docker_entrypoint = pathlib.Path("scripts/docker-entrypoint.sh")
    if not docker_entrypoint.exists():
        click.echo(f"⚠️  {docker_entrypoint} not found, skipping URL update")
        return

    # Create the new URL - need to URL encode the tag for GitHub releases
    encoded_tag = urllib.parse.quote(tag, safe="")
    new_url = f"https://github.com/isundaylee/istaroth/releases/download/{encoded_tag}/{main_checkpoint.name}"

    # Read the current content
    content = docker_entrypoint.read_text()

    # Pattern to match the ISTAROTH_CHECKPOINT_URL line
    pattern = r'ISTAROTH_CHECKPOINT_URL="\${ISTAROTH_CHECKPOINT_URL:-[^}]+}"'
    replacement = f'ISTAROTH_CHECKPOINT_URL="${{ISTAROTH_CHECKPOINT_URL:-{new_url}}}"'

    # Check if pattern exists
    if not re.search(pattern, content):
        click.echo(
            "⚠️  Could not find ISTAROTH_CHECKPOINT_URL pattern in docker-entrypoint.sh"
        )
        return

    # Update the content
    new_content = re.sub(pattern, replacement, content)

    # Write back to file
    docker_entrypoint.write_text(new_content)
    click.echo(f"✅ Updated docker-entrypoint.sh with new checkpoint URL")
    click.echo(f"   New URL: {new_url}")


@click.command()
@click.argument("checkpoints")
def main(
    checkpoints: str,
) -> None:
    """Create GitHub release with checkpoint .tar.gz files.

    This script creates a GitHub release with the format 'checkpoint/YYYYMMDD-[commit_hash]'
    and uploads checkpoint files as release assets.

    It also updates the docker-entrypoint.sh file to point to the new checkpoint
    URL if chs.tar.gz is included in the checkpoint files.

    CHECKPOINTS supports shell expansion patterns.

    Examples:
        # Create release with all checkpoints
        ./scripts/release_checkpoint.py "tmp/checkpoints/*.tar.gz"

        # Create release with specific checkpoint files
        ./scripts/release_checkpoint.py "tmp/checkpoints/chs.tar.gz tmp/checkpoints/eng.tar.gz"
    """
    click.echo("🚀 Creating checkpoint release...")

    # Get current state
    commit_hash = _get_current_commit_hash()
    date_str = _get_current_date()
    checkpoint_files = _find_checkpoint_files(checkpoints)

    click.echo(f"📅 Date: {date_str}")
    click.echo(f"🔗 Commit: {commit_hash}")
    click.echo(f"📦 Found {len(checkpoint_files)} checkpoint files:")
    for f in checkpoint_files:
        click.echo(f"   - {f.name}")

    # Create release tag
    tag = _create_release_tag(date_str, commit_hash)
    click.echo(f"🏷️  Tag: {tag}")

    # Create and push git tag first
    _create_and_push_git_tag(tag, commit_hash)

    # Check if release already exists and delete it
    if _release_exists(tag):
        click.echo(f"⚠️  Release {tag} already exists. Deleting and recreating...")
        subprocess.run(["gh", "release", "delete", tag, "-y"], check=True)

    # Create the release
    click.echo("\n📤 Creating release...")
    cmd = [
        "gh",
        "release",
        "create",
        tag,
        "--title",
        tag,
        "--notes",
        f"Automated checkpoint release for commit {commit_hash}",
        "--target",
        commit_hash,
    ]

    # Add all checkpoint files as assets
    for checkpoint_file in checkpoint_files:
        cmd.append(str(checkpoint_file))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        click.echo("✅ Release created successfully!")
        click.echo(f"🔗 URL: {result.stdout.strip()}")

    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Failed to create release: {e}", err=True)
        click.echo(f"Error output: {e.stderr}", err=True)
        sys.exit(1)

    # Update docker-entrypoint.sh only if chs.tar.gz is included
    checkpoint_names = [f.name for f in checkpoint_files]
    if "chs.tar.gz" in checkpoint_names:
        click.echo("\n🐳 Updating docker-entrypoint.sh...")
        _update_docker_entrypoint(tag, checkpoint_files)
    else:
        click.echo(
            "\nℹ️  Skipping docker-entrypoint.sh update (chs.tar.gz not included)"
        )


if __name__ == "__main__":
    main()
