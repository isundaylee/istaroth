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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clean_text_markers_cases() {
        for (input, expected) in [
            ("你好{NICKNAME}，你好吗？", "你好旅行者，你好吗？"),
            ("{M#哥哥}{F#姐姐}来了。", "哥哥来了。"),
            (
                "This is <color=#FF0000FF>red</color> and <color=#37FFFF>cyan</color>.",
                "This is *red* and *cyan*.",
            ),
            (
                "This is <i>italic</i> and <I>also italic</I>.",
                "This is *italic* and *also italic*.",
            ),
            // <i> nested inside <color> resolves fully rather than leaking raw tags.
            (
                "<color=#37FFFFFF><I>emphasized</I></color>",
                "**emphasized**",
            ),
            (
                "<center>Centered line</center>\n<right>Signed</right>",
                "Centered line\nSigned",
            ),
            // <center> can wrap multiple paragraphs.
            (
                "<center>Line one\n\nLine two</center>",
                "Line one\n\nLine two",
            ),
            (
                "Before.\n<image name=UI_Example />\nAfter.",
                "Before.\nAfter.",
            ),
            // Literal \n sequences normalize to newlines.
            (r"Line 1\nLine 2", "Line 1\nLine 2"),
            // All markers combined.
            (
                "你好{NICKNAME}，{M#国王}{F#女王}说<color=#FFD700FF>欢迎</color>！",
                "你好旅行者，国王说*欢迎*！",
            ),
            // REALNAME as speaker label, inline, and standalone.
            (
                "#{REALNAME[ID(1)|HOSTONLY(true)]}: 在经历那么多次徒劳之后，你应该明白吧？",
                "流浪者: 在经历那么多次徒劳之后，你应该明白吧？",
            ),
            (
                "#{REALNAME[ID(2)|SHOWHOST(true)]}摆出了进攻的架势！",
                "小龙摆出了进攻的架势！",
            ),
            ("#{REALNAME[ID(2)|SHOWHOST(true)]}", "小龙"),
        ] {
            assert_eq!(clean_text_markers(input).unwrap(), expected, "{input:?}");
        }
    }

    #[test]
    fn clean_text_markers_unmapped_realname_errors() {
        assert!(clean_text_markers("#{REALNAME[ID(99)|HOSTONLY(true)]}: x").is_err());
    }

    fn pronoun(token: &str) -> Result<String> {
        match token {
            "INFO_MALE_PRONOUN_HE" => Ok("He".to_string()),
            "INFO_FEMALE_PRONOUN_SISTER" => Ok("Sister".to_string()),
            other => anyhow::bail!("unknown token {other}"),
        }
    }

    #[test]
    fn resolve_sexpro_takes_first_branch() {
        // The positional first token wins even when its prefix looks female,
        // and the {MATEAVATAR#...} sibling variant is handled the same way.
        for (input, expected) in [
            (
                "Says {PLAYERAVATAR#SEXPRO[INFO_MALE_PRONOUN_HE|INFO_FEMALE_PRONOUN_SHE]} is here.",
                "Says He is here.",
            ),
            (
                "Find your {PLAYERAVATAR#SEXPRO[INFO_FEMALE_PRONOUN_SISTER|INFO_MALE_PRONOUN_BROTHER]}.",
                "Find your Sister.",
            ),
            (
                "My {MATEAVATAR#SEXPRO[INFO_FEMALE_PRONOUN_SISTER|INFO_MALE_PRONOUN_BROTHER]}.",
                "My Sister.",
            ),
        ] {
            assert_eq!(
                resolve_sexpro(input, pronoun).unwrap(),
                expected,
                "{input:?}"
            );
        }
    }

    #[test]
    fn resolve_sexpro_unmapped_token_errors() {
        assert!(
            resolve_sexpro(
                "{PLAYERAVATAR#SEXPRO[INFO_MALE_PRONOUN_NOPE|INFO_FEMALE_PRONOUN_NOPE]}",
                pronoun,
            )
            .is_err()
        );
    }
}
