//! Port of renderables/readable.py: readable metadata/content loading and the
//! shared readable-like rendering (also backs Books/Wings/Costumes passes).

use crate::firstseen::Domain;
use crate::issues::{IssueType, Scope};
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use anyhow::{Result, anyhow};
use rustc_hash::FxHashSet;

pub struct ReadableMetadata {
    pub localization_id: i64,
    pub title: String,
}

/// Retrieve metadata (localization id + title) for a readable file.
pub fn get_readable_metadata(
    repo: &Repo,
    scope: &Scope,
    readable_filename: &str,
) -> Result<ReadableMetadata> {
    let readable_stem = util::path_stem(readable_filename);
    let readable_id = readable_stem
        .strip_suffix(&format!("_{}", repo.language.short()))
        .unwrap_or(readable_stem);
    let localization_id = *repo
        .readable_stem_to_loc_id
        .get(readable_stem)
        .ok_or_else(|| anyhow!("Localization ID not found for readable: {readable_id}"))?;
    let title = match repo.loc_id_to_title_hash.get(&localization_id) {
        None => None,
        Some(&h) => repo.tm.get_optional(h, scope)?,
    };
    let title = match title {
        Some(title) => title,
        None => {
            scope.record_issue(IssueType::MissingReadableTitle, readable_id.to_string());
            "Unknown Title".to_string()
        }
    };
    Ok(ReadableMetadata {
        localization_id,
        title,
    })
}

/// Read and clean a readable's content and metadata.
///
/// Returns None for empty/placeholder/dev-test readables (the per-file skip
/// rules) so callers can drop them; errors if the file itself is missing.
/// Reading the content marks it accessed in the readables tracking.
pub fn load_readable(
    repo: &Repo,
    scope: &Scope,
    readable_filename: &str,
) -> Result<Option<(String, ReadableMetadata)>> {
    let content = repo
        .readable_content(readable_filename, scope)
        .ok_or_else(|| anyhow!("Readable not found: {readable_filename}"))?;
    let content = repo.tm.clean_text(content)?;
    if util::should_skip_readable_content(&content) {
        return Ok(None);
    }
    let metadata = get_readable_metadata(repo, scope, readable_filename)?;
    if util::should_skip_text(&metadata.title) {
        return Ok(None);
    }
    Ok(Some((content, metadata)))
}

/// Render readable-style content (readable/wings/costume + standalone book).
pub fn render_readable_like(
    repo: &Repo,
    content: &str,
    metadata: &ReadableMetadata,
    readable_filename: &str,
    category: &'static str,
) -> Result<RenderedItem> {
    let safe_title = util::make_safe_filename_part(&metadata.title);
    let versions = repo
        .first_seen
        .resolve_stem(Domain::Readable, readable_filename)?;
    Ok(RenderedItem::new(
        category,
        metadata.title.clone(),
        metadata.localization_id,
        format!("{}_{safe_title}.txt", metadata.localization_id),
        versions,
        format!("# {}\n\n{content}", metadata.title),
    ))
}

/// Wings/Costumes discovery: readable filenames with the given prefix.
pub fn discover_prefixed(repo: &Repo, prefix: &str) -> Result<Vec<String>> {
    Ok(repo
        .readable_filenames_sorted
        .iter()
        .filter(|f| f.starts_with(prefix))
        .cloned()
        .collect())
}

/// Readables pass discovery: filenames no earlier pass consumed.
pub fn discover_leftover(repo: &Repo, used_readables: &FxHashSet<String>) -> Result<Vec<String>> {
    Ok(repo
        .readable_filenames_sorted
        .iter()
        .filter(|f| !used_readables.contains(*f))
        .cloned()
        .collect())
}

/// Shared readable-like process (Readables/Wings/Costumes and standalone books).
pub fn process(
    repo: &Repo,
    scope: &Scope,
    filename: &str,
    category: &'static str,
) -> Result<Option<RenderedItem>> {
    match load_readable(repo, scope, filename)? {
        None => Ok(None),
        Some((content, metadata)) => Ok(Some(render_readable_like(
            repo, &content, &metadata, filename, category,
        )?)),
    }
}
