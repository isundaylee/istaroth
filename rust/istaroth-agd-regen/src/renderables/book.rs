//! Port of renderables/book.py: multi-volume series documents plus standalone
//! book readables.

use crate::firstseen::Domain;
use crate::issues::Scope;
use crate::renderables::readable;
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::ValueExt;
use anyhow::{Result, anyhow};
use rustc_hash::FxHashSet;

pub enum BookKey {
    Series(i64),
    Standalone(String),
}

impl BookKey {
    /// Item description for error reporting; must match the reference
    /// pipeline's key repr strings.
    pub fn desc(&self) -> String {
        match self {
            BookKey::Series(id) => format!("_BookSeriesKey(suit_id={id})"),
            BookKey::Standalone(f) => format!("_BookStandaloneKey(filename='{f}')"),
        }
    }
}

/// Books pass discovery: series (sorted suit ids) then ungrouped standalone files.
pub fn discover(repo: &Repo) -> Result<Vec<BookKey>> {
    let grouped: FxHashSet<&String> = repo.book_series.values().flatten().collect();
    let mut series_ids: Vec<i64> = repo.book_series.keys().copied().collect();
    series_ids.sort();
    let mut keys: Vec<BookKey> = series_ids.into_iter().map(BookKey::Series).collect();
    keys.extend(
        repo.readable_filenames_sorted
            .iter()
            .filter(|f| f.starts_with("Book") && !grouped.contains(f))
            .map(|f| BookKey::Standalone(f.clone())),
    );
    Ok(keys)
}

pub fn process(repo: &Repo, scope: &Scope, key: &BookKey) -> Result<Option<RenderedItem>> {
    match key {
        BookKey::Series(suit_id) => process_book_series(repo, scope, *suit_id),
        BookKey::Standalone(filename) => readable::process(repo, scope, filename, "agd_book"),
    }
}

/// Render a multi-volume book series into a single file.
///
/// Volumes render in reading order under one series header, each prefixed
/// with an annotation line naming the series and the volume's position so a
/// chunk retrieved in isolation still carries its series context. Reading
/// each volume's content marks it accessed, keeping the per-volume files out
/// of the standalone Books and generic Readables catch-alls. A grouped volume
/// whose readable file is missing errors rather than being silently dropped;
/// empty/placeholder/test volumes are filtered the same way standalone books
/// are. Returns None if no volume survives filtering.
pub fn process_book_series(
    repo: &Repo,
    scope: &Scope,
    suit_id: i64,
) -> Result<Option<RenderedItem>> {
    let filenames = repo
        .book_series
        .get(&suit_id)
        .ok_or_else(|| anyhow!("Book suit {suit_id} is not a multi-volume series"))?;
    let suit = repo
        .excel
        .book_suit
        .get(&suit_id)
        .ok_or_else(|| anyhow!("unknown book suit {suit_id}"))?;
    let series_name = repo
        .tm
        .get_optional(suit.i("suitNameTextMapHash")?, scope)?
        .ok_or_else(|| anyhow!("Missing series name for book suit {suit_id}"))?;

    struct Volume {
        title: String,
        content: String,
        filename: String,
    }
    let mut volumes: Vec<Volume> = Vec::new();
    for filename in filenames {
        if let Some((content, metadata)) = readable::load_readable(repo, scope, filename)? {
            volumes.push(Volume {
                title: metadata.title,
                content,
                filename: filename.clone(),
            });
        }
    }
    if volumes.is_empty() {
        return Ok(None);
    }

    let safe_name = util::make_safe_filename_part(&series_name);
    let total = volumes.len();
    let mut content_parts = vec![format!("# {series_name}")];
    for (index, volume) in volumes.iter().enumerate() {
        let annotation = format!("*{series_name}·第 {} 卷，共 {total} 卷*", index + 1);
        content_parts.push(format!(
            "## {}\n\n{annotation}\n\n{}",
            volume.title, volume.content
        ));
    }
    let keys: Vec<crate::firstseen::SourceKey> = volumes
        .iter()
        .map(|v| {
            crate::firstseen::SourceKey::Str(
                util::strip_language_suffix(util::path_stem(&v.filename)).to_string(),
            )
        })
        .collect();
    let versions = repo
        .first_seen
        .resolve(keys.iter().map(|k| (Domain::Readable, k)))?;
    Ok(Some(RenderedItem::new(
        "agd_book",
        series_name,
        suit_id,
        format!("{suit_id}_{safe_name}.txt"),
        versions,
        content_parts.join("\n\n"),
    )))
}
