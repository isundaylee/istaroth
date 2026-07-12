//! Port of istaroth.text_cleanup for the CHS language.

use anyhow::{Context, Result};
use regex::Regex;
use std::sync::LazyLock;

// `{PLAYERAVATAR#SEXPRO[<male-branch>|<female-branch>]}` (and the sibling
// `{MATEAVATAR#SEXPRO[...]}` variant) select a gendered pronoun/appellation
// from the player's chosen traveler gender. The corpus consistently renders
// the first (male-player) branch, matching the `{M#...}{F#...}` -> M
// convention. Each branch is a language-neutral `INFO_*_PRONOUN_*` token; the
// captured group is the first branch, the female branch is matched but
// discarded.
static SEXPRO: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\{(?:PLAYER|MATE)AVATAR#SEXPRO\[([^|\]]+)\|[^\]]+\]\}").unwrap());
// `#{REALNAME[ID(n)|...]}` placeholders: player-chosen names for specific
// characters that the game swaps in at runtime; replaced with hardcoded names,
// erroring on unmapped IDs so future additions surface instead of leaking.
static REALNAME: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"#\{REALNAME\[ID\((\d+)\)[^\]]*\]\}").unwrap());
// `{M#option1}{F#option2}` traveler-gender branch; the M option is kept.
static GENDER_BRANCH: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\{M#([^}]+)\}\{F#[^}]+\}").unwrap());
// <center>/<right> structural wrappers are stripped, keeping their content.
static CENTER: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?s)<center>(.*?)</center>").unwrap());
static RIGHT: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?s)<right>(.*?)</right>").unwrap());
static ITALIC: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?si)<i>(.*?)</i>").unwrap());
// `<color=#RRGGBB[AA]>content</color>` -> markdown emphasis (6-8 hex digits:
// the corpus has RGB, RGBA, and a handful of truncated 7-digit values).
static COLOR: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"<color=#[0-9A-Fa-f]{6,8}>([^<]*)</color>").unwrap());
// Standalone `<image name=.../>` placeholders (always alone on their line).
static IMAGE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"<image name=[^>]*/>\n?").unwrap());

/// Replace SEXPRO placeholders with their first (male-player) branch's text.
///
/// `resolve_token` maps an `INFO_*_PRONOUN_*` token to its raw text; it
/// errors on an unknown token so a new one surfaces. Run this before
/// `clean_text_markers` so a branch that itself carries a nested gender macro
/// (e.g. INFO_MALE_PRONOUN_BROANDSIS) is then handled by its `{M#...}{F#...}`
/// pass.
pub fn resolve_sexpro(
    text: &str,
    resolve_token: impl Fn(&str) -> Result<String>,
) -> Result<String> {
    if !text.contains("#SEXPRO[") {
        return Ok(text.to_string());
    }
    let mut out = String::with_capacity(text.len());
    let mut last = 0;
    for caps in SEXPRO.captures_iter(text) {
        let m = caps.get(0).unwrap();
        out.push_str(&text[last..m.start()]);
        let token = caps.get(1).unwrap().as_str();
        out.push_str(&resolve_token(token).with_context(|| format!("SEXPRO token {token}"))?);
        last = m.end();
    }
    out.push_str(&text[last..]);
    Ok(out)
}

/// Clean game text markers and normalize newlines (CHS).
///
/// Does not resolve SEXPRO pronoun placeholders (those need TextMap access);
/// run `resolve_sexpro` first where they may appear. Each regex runs behind a
/// substring guard on a fragment every match must contain, keeping the common
/// marker-free case regex-free. `<i>` runs before `<color>` since a few lines
/// nest `<i>` inside `<color>` and `<color>`'s content class excludes `<`.
pub fn clean_text_markers(text: &str) -> Result<String> {
    if text.is_empty() {
        return Ok(text.to_string());
    }
    let mut text = text.replace("\\n", "\n");
    if text.contains("{NICKNAME}") {
        text = text.replace("{NICKNAME}", "旅行者");
    }
    if text.contains("{M#") {
        text = GENDER_BRANCH.replace_all(&text, "$1").into_owned();
    }
    if text.contains("#{REALNAME[") {
        let mut unmapped: Option<String> = None;
        text = REALNAME
            .replace_all(&text, |caps: &regex::Captures| {
                match caps.get(1).unwrap().as_str() {
                    "1" => "流浪者".to_string(),
                    "2" => "小龙".to_string(),
                    other => {
                        unmapped = Some(other.to_string());
                        String::new()
                    }
                }
            })
            .into_owned();
        if let Some(id) = unmapped {
            anyhow::bail!("Unmapped REALNAME id {id}");
        }
    }
    if text.contains("<center>") {
        text = CENTER.replace_all(&text, "$1").into_owned();
    }
    if text.contains("<right>") {
        text = RIGHT.replace_all(&text, "$1").into_owned();
    }
    if text.contains("<i>") || text.contains("<I>") {
        text = ITALIC.replace_all(&text, "*$1*").into_owned();
    }
    if text.contains("<color=#") {
        text = COLOR.replace_all(&text, "*$1*").into_owned();
    }
    if text.contains("<image name=") {
        text = IMAGE.replace_all(&text, "").into_owned();
    }
    Ok(text)
}
