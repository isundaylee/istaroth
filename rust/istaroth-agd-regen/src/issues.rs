//! Port of istaroth.agd.issues + tracking: non-fatal parsing-issue recording
//! and the per-item access-tracking scope.

use rustc_hash::FxHashSet;
use std::cell::RefCell;

/// Non-fatal parsing gap categories (port of issues.IssueType).
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum IssueType {
    MissingTalk,
    MissingDialog,
    MissingText,
    UnknownRole,
    MissingQuestTitle,
    MissingStoryContent,
    MissingMaterialName,
    MissingMaterialDesc,
    MissingReadableTitle,
}

impl IssueType {
    pub fn name(self) -> &'static str {
        match self {
            IssueType::MissingTalk => "MISSING_TALK",
            IssueType::MissingDialog => "MISSING_DIALOG",
            IssueType::MissingText => "MISSING_TEXT",
            IssueType::UnknownRole => "UNKNOWN_ROLE",
            IssueType::MissingQuestTitle => "MISSING_QUEST_TITLE",
            IssueType::MissingStoryContent => "MISSING_STORY_CONTENT",
            IssueType::MissingMaterialName => "MISSING_MATERIAL_NAME",
            IssueType::MissingMaterialDesc => "MISSING_MATERIAL_DESC",
            IssueType::MissingReadableTitle => "MISSING_READABLE_TITLE",
        }
    }
}

/// A single recorded non-fatal parsing gap (item identity stamped by the caller).
pub struct Issue {
    pub issue_type: IssueType,
    pub detail: String,
}

/// Per-item access-tracking scope: ids feeding cross-pass exclusion (talk ids,
/// readable filenames), text-map hashes (unused-stats only), and non-fatal
/// parsing issues recorded inline.
#[derive(Default)]
pub struct Scope {
    pub talks: RefCell<FxHashSet<i64>>,
    pub readables: RefCell<FxHashSet<String>>,
    pub text_map: RefCell<FxHashSet<i64>>,
    pub issues: RefCell<Vec<Issue>>,
}

impl Scope {
    pub fn record_issue(&self, issue_type: IssueType, detail: String) {
        self.issues.borrow_mut().push(Issue { issue_type, detail });
    }
}
