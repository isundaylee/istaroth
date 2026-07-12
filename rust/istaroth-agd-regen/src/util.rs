//! Python-semantics helpers shared across the pipeline.

use regex::Regex;
use sha2::{Digest, Sha256};
use std::sync::LazyLock;

static UNSAFE_CHARS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[^\w\s-]").unwrap());
static WHITESPACE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\s+").unwrap());

/// Safe filename fragment: truncate to 50 code points (not bytes), drop
/// unsafe chars, strip, and collapse whitespace runs to `_`.
pub fn make_safe_filename_part(text: &str) -> String {
    let truncated: String = text.chars().take(50).collect();
    let safe = UNSAFE_CHARS.replace_all(&truncated, "");
    let stripped = py_strip(&safe);
    WHITESPACE.replace_all(stripped, "_").into_owned()
}

/// Python `str.strip()` (Unicode whitespace; close enough via char::is_whitespace).
pub fn py_strip(s: &str) -> &str {
    s.trim_matches(|c: char| c.is_whitespace() || ('\x1c'..='\x1f').contains(&c))
}

pub fn py_rstrip(s: &str) -> &str {
    s.trim_end_matches(|c: char| c.is_whitespace() || ('\x1c'..='\x1f').contains(&c))
}

/// Whether (CHS source) text carries a dev/test/hidden marker and should be
/// excluded from output.
pub fn should_skip_text(text: &str) -> bool {
    let lower = text.to_lowercase();
    lower.starts_with("test")
        || lower.starts_with("(test")
        || lower.starts_with("（test")
        || lower.contains("$hidden")
        || lower.contains("$unreleased")
        || lower.contains("beta测试任务")
}

const READABLE_PLACEHOLDERS: [&str; 7] = ["测试", "暂无", "暂缺", "？？？", "test", "none", "n/a"];

/// Whether readable content is an empty/placeholder body to skip.
pub fn should_skip_readable_content(content: &str) -> bool {
    let stripped = py_strip(content);
    stripped.is_empty()
        || READABLE_PLACEHOLDERS.contains(&stripped.to_lowercase().as_str())
        || should_skip_text(stripped)
}

/// First 12 hex chars of sha256(s) as an integer (subtitle/material/creature ids).
pub fn sha256_id(s: &str) -> i64 {
    let digest = Sha256::digest(s.as_bytes());
    let hex: String = digest.iter().map(|b| format!("{b:02x}")).collect();
    i64::from_str_radix(&hex[..12], 16).unwrap()
}

/// Python `text[:n]` by code points.
pub fn py_slice(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}

/// Python `str.title()` (ASCII-adequate port: letter after non-cased char is uppercased).
pub fn py_title_case(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut prev_cased = false;
    for c in s.chars() {
        if c.is_alphabetic() {
            if prev_cased {
                out.extend(c.to_lowercase());
            } else {
                out.extend(c.to_uppercase());
            }
            prev_cased = true;
        } else {
            out.push(c);
            prev_cased = false;
        }
    }
    out
}

/// Python `str.isdigit()` restricted to ASCII digits (wire ids are ASCII), non-empty.
pub fn py_isdigit(s: &str) -> bool {
    !s.is_empty() && s.chars().all(|c| c.is_ascii_digit())
}

/// Python `int(str)` (trims whitespace, optional sign).
pub fn py_int(s: &str) -> anyhow::Result<i64> {
    let t = s.trim();
    t.parse::<i64>()
        .map_err(|e| anyhow::anyhow!("int({s:?}): {e}"))
}

/// os.path.commonprefix over strings, per code point.
pub fn common_prefix(strings: &[String]) -> String {
    if strings.is_empty() {
        return String::new();
    }
    let first: Vec<char> = strings[0].chars().collect();
    let mut len = first.len();
    for s in &strings[1..] {
        let chars: Vec<char> = s.chars().collect();
        let mut i = 0;
        while i < len && i < chars.len() && chars[i] == first[i] {
            i += 1;
        }
        len = len.min(i);
    }
    first[..len].iter().collect()
}

/// Version string ("5.8") sort key.
pub fn version_key(v: &str) -> Vec<i64> {
    v.split('.')
        .map(|p| p.parse::<i64>().unwrap_or(0))
        .collect()
}

/// Strip the trailing `_<LANG>` token, if any, from a readable/subtitle stem.
/// CHS files mostly carry no language suffix while other languages do, so the
/// language-neutral key is the stem with the suffix dropped when present.
pub fn strip_language_suffix(stem: &str) -> &str {
    const SUFFIXES: [&str; 15] = [
        "CHS", "CHT", "DE", "EN", "ES", "FR", "ID", "IT", "JP", "KR", "PT", "RU", "TH", "TR", "VI",
    ];
    if let Some(pos) = stem.rfind('_') {
        let suffix = &stem[pos + 1..];
        if SUFFIXES.contains(&suffix) {
            return &stem[..pos];
        }
    }
    stem
}

/// Path stem (filename without last extension), like pathlib `.stem`.
pub fn path_stem(path: &str) -> &str {
    let name = path.rsplit('/').next().unwrap_or(path);
    match name.rfind('.') {
        Some(0) | None => name,
        Some(i) => &name[..i],
    }
}

pub fn path_name(path: &str) -> &str {
    path.rsplit('/').next().unwrap_or(path)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn safe_filename_part_truncates_sanitizes_collapses() {
        // Truncation is 50 code points, before sanitization.
        assert_eq!(make_safe_filename_part(&"字".repeat(60)), "字".repeat(50));
        assert_eq!(
            make_safe_filename_part("神霄折戟录·第六卷"),
            "神霄折戟录第六卷"
        );
        assert_eq!(
            make_safe_filename_part("「这是引号」—还有破折号！"),
            "这是引号还有破折号"
        );
        assert_eq!(
            make_safe_filename_part("  Title   With   Spaces  "),
            "Title_With_Spaces"
        );
    }

    #[test]
    fn skip_text_markers() {
        for text in [
            "(test)一阶段结束$HIDDEN",
            "（test）旅人兰那罗",
            "TEST quest",
            "夏活beta测试任务",
            "含$UNRELEASED标记",
        ] {
            assert!(should_skip_text(text), "{text}");
        }
        for text in ["山中好长日·第一章", "放假一天！"] {
            assert!(!should_skip_text(text), "{text}");
        }
    }

    #[test]
    fn skip_readable_content_placeholders_only() {
        for content in ["？？？", " ？？？ ", "", "  ", "测试", "暂缺", "N/A"] {
            assert!(should_skip_readable_content(content), "{content:?}");
        }
        for content in ["放假一天！", "我的宝物", "？？", "Real book text."] {
            assert!(!should_skip_readable_content(content), "{content:?}");
        }
    }

    #[test]
    fn strip_language_suffix_variants() {
        for (stem, expected) in [
            ("Book100_EN", "Book100"),
            ("Book100", "Book100"),
            ("Wanderer_Log_CHS", "Wanderer_Log"),
            ("Cs_Inazuma_JP", "Cs_Inazuma"),
        ] {
            assert_eq!(strip_language_suffix(stem), expected);
        }
    }
}
