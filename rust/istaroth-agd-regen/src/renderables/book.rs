//! Port of renderables/book.py: multi-volume series documents plus standalone
//! book readables.

use crate::firstseen::Domain;
use crate::issues::Scope;
use crate::lang::Language;
use crate::renderables::readable;
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::ValueExt;
use anyhow::{Result, anyhow};
use rustc_hash::FxHashSet;

/// (CHS, non-CHS) per-pass error limits (see e.g. `artifact::ERROR_LIMITS`).
pub const ERROR_LIMITS: (usize, usize) = (50, 200);

pub enum BookKey {
    Series(i64),
    Standalone(String),
}

#[cfg(test)]
#[allow(clippy::items_after_test_module)]
mod series_tests {
    use super::*;
    use crate::firstseen::{FirstSeenIndex, SourceKey};
    use crate::textmap::TextMaps;
    use rustc_hash::{FxHashMap, FxHashSet};
    use serde_json::json;

    fn repo(contents: &[(&str, &str)]) -> Repo {
        let filenames = vec!["Book101_EN.txt".to_string(), "Book102_EN.txt".to_string()];
        Repo {
            language: Language::Eng,
            tm: TextMaps::for_tests(
                Language::Eng,
                [(700, "My Series"), (101, "Volume One"), (102, "Volume Two")]
                    .into_iter()
                    .map(|(id, text)| (id, text.to_string()))
                    .collect(),
                FxHashMap::default(),
                FxHashMap::default(),
            ),
            first_seen: FirstSeenIndex::for_tests(filenames.iter().map(|filename| {
                (
                    Domain::Readable,
                    SourceKey::Str(
                        util::strip_language_suffix(util::path_stem(filename)).to_string(),
                    ),
                    "1.0",
                )
            })),
            excel: crate::repo::Excels {
                book_suit: [(7, json!({"suitNameTextMapHash": 700}))]
                    .into_iter()
                    .collect(),
                ..Default::default()
            },
            book_series: [(7, filenames.clone())].into_iter().collect(),
            readable_stem_to_loc_id: [
                ("Book101_EN".to_string(), 101),
                ("Book102_EN".to_string(), 102),
            ]
            .into_iter()
            .collect(),
            loc_id_to_title_hash: [(101, 101), (102, 102)].into_iter().collect(),
            readable_filenames: filenames.into_iter().collect::<FxHashSet<_>>(),
            readable_contents: contents
                .iter()
                .map(|(name, text)| (name.to_string(), text.to_string()))
                .collect(),
            ..Default::default()
        }
    }

    #[test]
    fn series_assembles_volumes_in_reading_order() {
        let rendered = process_book_series(
            &repo(&[
                ("Book101_EN.txt", "First body."),
                ("Book102_EN.txt", "Second body."),
            ]),
            &Scope::default(),
            7,
        )
        .unwrap()
        .unwrap();
        assert!(rendered.content.contains(
            "## Volume One\n\n*My Series — Volume 1 of 2*\n\nFirst body.\n\n## Volume Two"
        ));
    }

    #[test]
    fn series_filters_placeholder_volumes_and_localizes_annotation() {
        let rendered = process_book_series(
            &repo(&[
                ("Book101_EN.txt", "test"),
                ("Book102_EN.txt", "Second body."),
            ]),
            &Scope::default(),
            7,
        )
        .unwrap()
        .unwrap();
        assert!(rendered.content.contains("## Volume Two"));
        assert!(rendered.content.contains("*My Series — Volume 1 of 1*"));
        assert!(!rendered.content.contains("Volume One"));
    }

    #[test]
    fn series_with_only_placeholder_volumes_is_filtered() {
        assert!(
            process_book_series(
                &repo(&[("Book101_EN.txt", "test"), ("Book102_EN.txt", "N/A")]),
                &Scope::default(),
                7
            )
            .unwrap()
            .is_none()
        );
    }
}

impl BookKey {
    /// Item description for error reporting.
    pub fn desc(&self) -> String {
        match self {
            BookKey::Series(id) => format!("series suit {id}"),
            BookKey::Standalone(f) => format!("standalone '{f}'"),
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
        let annotation = match repo.language {
            Language::Chs => format!("*{series_name}·第 {} 卷，共 {total} 卷*", index + 1),
            Language::Eng => format!("*{series_name} — Volume {} of {total}*", index + 1),
        };
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
