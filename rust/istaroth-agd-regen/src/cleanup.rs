//! Port of istaroth.text_cleanup for the CHS language.

use anyhow::{Context, Result};
use regex::Regex;
use std::sync::LazyLock;

static SEXPRO: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\{(?:PLAYER|MATE)AVATAR#SEXPRO\[([^|\]]+)\|[^\]]+\]\}").unwrap());
static REALNAME: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"#\{REALNAME\[ID\((\d+)\)[^\]]*\]\}").unwrap());
static GENDER_BRANCH: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\{M#([^}]+)\}\{F#[^}]+\}").unwrap());
static CENTER: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?s)<center>(.*?)</center>").unwrap());
static RIGHT: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?s)<right>(.*?)</right>").unwrap());
static ITALIC: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?si)<i>(.*?)</i>").unwrap());
static COLOR: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"<color=#[0-9A-Fa-f]{6,8}>([^<]*)</color>").unwrap());
static IMAGE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"<image name=[^>]*/>\n?").unwrap());

/// Replace SEXPRO placeholders with the male-branch token's raw text.
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

/// Port of clean_text_markers (CHS): marker stripping + newline normalization.
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
