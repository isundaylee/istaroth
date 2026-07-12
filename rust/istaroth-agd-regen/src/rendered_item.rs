//! TextMetadata / RenderedItem and manifest serialization.

use serde::Serialize;

/// Manifest entry schema, deserialized by the Python readers
/// (`TextMetadata` in `istaroth/text/types.py`). Parity is pinned
/// byte-exactly by `tests/contract.rs` and `tests/test_schema_contract.py`
/// (repo root), sharing `tests/fixtures/contract/`.
#[derive(Clone, Serialize)]
pub struct TextMetadata {
    pub category: &'static str,
    pub title: String,
    pub id: i64,
    pub relative_path: String,
    pub min_version: String,
    pub max_version: String,
}

pub struct RenderedItem {
    pub meta: TextMetadata,
    pub content: String,
}

impl RenderedItem {
    pub fn new(
        category: &'static str,
        title: String,
        id: i64,
        filename: String,
        versions: (String, String),
        content: String,
    ) -> RenderedItem {
        RenderedItem {
            meta: TextMetadata {
                category,
                title,
                id,
                relative_path: format!("{category}/{filename}"),
                min_version: versions.0,
                max_version: versions.1,
            },
            content,
        }
    }
}
