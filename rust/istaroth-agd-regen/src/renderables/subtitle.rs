//! Port of renderables/subtitle.py.

use crate::firstseen::Domain;
use crate::issues::Scope;
use crate::lang::Language;
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::ValueExt;
use anyhow::Result;
use regex::Regex;
use std::sync::LazyLock;

// Quest-id-shaped digit runs in a subtitle file stem (e.g. the "1204205" of
// "Cs_Inazuma_LQ1204205_IntoTheVoid"); shorter runs are variant/sequence
// markers.
static QUEST_ID_TOKEN: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\d{4,9}").unwrap());

/// Main-quest title, or None when unknown, untitled, or dev/test-marked
/// (the `$UNRELEASED`/`$HIDDEN` markers live in the CHS title text).
fn main_quest_title(repo: &Repo, scope: &Scope, quest_id: i64) -> Result<Option<String>> {
    let Some(main_quest) = repo.excel.main_quest.get(&quest_id) else {
        return Ok(None);
    };
    let title_hash = main_quest.i("titleTextMapHash")?;
    if let Some(chs) = repo.source_get_optional(title_hash, scope)?
        && util::should_skip_text(&chs, Language::Chs)
    {
        return Ok(None);
    }
    repo.tm.get_optional(title_hash, scope)
}

/// Title of the main quest an id-shaped number points at, or None.
///
/// Cutscene ids and filename tokens encode their trigger site in several
/// historical shapes; try each interpretation and keep the first that lands
/// on a titled main quest: a sub-quest id, a talk id, a main-quest id, then
/// the same with trailing digit pairs stripped (dialog ids are
/// `talkId*100+n`, talk ids `mainQuestId*100+n`, and some ids append both).
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
            text_lines.push(crate::cleanup::clean_text_markers(line, repo.language)?);
        }
    }
    // A few subtitle files ship empty or as a lone `.` placeholder (their
    // videos have no speech); rendering those would produce title-only
    // documents.
    if !text_lines
        .iter()
        .any(|l| !l.trim_matches(|c| c == ' ' || c == '.').is_empty())
    {
        return Ok(None);
    }

    // Document title: owning-quest title plus the file stem as disambiguator.
    // Resolution prefers the cutscene files that bind the subtitle (via their
    // localization subtitleId or video names); the many videos with no
    // cutscene file in AGD fall back to decoding the quest-id token embedded
    // in the filename. When nothing resolves (a handful of system videos like
    // the game intro), the bare stem remains the title (issue #74).
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
