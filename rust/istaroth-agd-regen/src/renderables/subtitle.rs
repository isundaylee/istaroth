//! Port of renderables/subtitle.py.

use crate::firstseen::Domain;
use crate::issues::Scope;
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::ValueExt;
use anyhow::Result;
use regex::Regex;
use std::sync::LazyLock;

static QUEST_ID_TOKEN: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\d{4,9}").unwrap());

fn main_quest_title(repo: &Repo, scope: &Scope, quest_id: i64) -> Result<Option<String>> {
    let Some(main_quest) = repo.excel.main_quest.get(&quest_id) else {
        return Ok(None);
    };
    let title_hash = main_quest.i("titleTextMapHash")?;
    let chs_title = repo.tm.get_optional(title_hash, scope)?;
    if let Some(chs) = &chs_title
        && util::should_skip_text(chs)
    {
        return Ok(None);
    }
    Ok(chs_title)
}

fn resolve_quest_title(repo: &Repo, scope: &Scope, number: i64) -> Result<Option<String>> {
    let candidates = [
        repo.sub_quest_to_main.get(&number).copied(),
        repo.talk_to_quest.get(&number).copied(),
        Some(number),
        repo.sub_quest_to_main.get(&(number / 100)).copied(),
        repo.talk_to_quest.get(&(number / 100)).copied(),
        Some(number / 100),
        Some(number / 10000),
    ];
    for quest_id in candidates.into_iter().flatten() {
        if let Some(title) = main_quest_title(repo, scope, quest_id)?
            && !title.is_empty()
        {
            return Ok(Some(title));
        }
    }
    Ok(None)
}

/// Subtitles pass discovery: .srt files under the language's Subtitle dir.
pub fn discover(repo: &Repo) -> Result<Vec<String>> {
    Ok(repo
        .subtitle_names
        .iter()
        .filter(|n| n.ends_with(".srt"))
        .map(|n| format!("Subtitle/{}/{n}", repo.language.short()))
        .collect())
}

/// Subtitles: parse, filter, title, render.
pub fn process(repo: &Repo, scope: &Scope, subtitle_path: &str) -> Result<Option<RenderedItem>> {
    let content = std::fs::read_to_string(repo.agd_path.join(subtitle_path))?;
    let mut text_lines: Vec<String> = Vec::new();
    for line in util::py_strip(&content).split('\n') {
        let line = util::py_strip(line);
        if !line.is_empty() && !util::py_isdigit(line) && !line.contains("-->") {
            text_lines.push(crate::cleanup::clean_text_markers(line)?);
        }
    }
    if !text_lines
        .iter()
        .any(|l| !l.trim_matches(|c| c == ' ' || c == '.').is_empty())
    {
        return Ok(None);
    }

    // Title.
    let stem = util::path_stem(subtitle_path);
    let display_stem = stem
        .strip_suffix(&format!("_{}", repo.language.short()))
        .unwrap_or(stem);
    let mut numbers: Vec<i64> = repo
        .subtitle_stem_to_cutscenes
        .get(stem)
        .cloned()
        .unwrap_or_default();
    let mut tokens: Vec<&str> = QUEST_ID_TOKEN
        .find_iter(display_stem)
        .map(|m| m.as_str())
        .collect();
    tokens.sort_by_key(|t| std::cmp::Reverse(t.len()));
    numbers.extend(tokens.iter().map(|t| t.parse::<i64>().unwrap()));
    let mut title = display_stem.to_string();
    for number in numbers {
        if let Some(t) = resolve_quest_title(repo, scope, number)? {
            title = format!("{t} ({display_stem})");
            break;
        }
    }

    let subtitle_id = util::sha256_id(subtitle_path);
    let safe_name = util::make_safe_filename_part(stem);
    let mut content_lines = vec![format!("# {title}\n")];
    content_lines.extend(text_lines);
    let versions = repo
        .first_seen
        .resolve_stem(Domain::Subtitle, subtitle_path)?;
    Ok(Some(RenderedItem::new(
        "agd_subtitle",
        title,
        subtitle_id,
        format!("{subtitle_id}_{safe_name}.txt"),
        versions,
        content_lines.join("\n"),
    )))
}
