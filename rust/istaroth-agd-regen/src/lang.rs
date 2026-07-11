//! Output-language configuration. Only CHS is implemented for generation; ENG
//! needs split source/output text maps and localized render strings (future
//! work). Eng exists so language-independent code (first-seen builds) can
//! enumerate all languages like Python's `localization.Language`.

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Language {
    Chs,
    Eng,
}

impl Language {
    /// Every language, in Python `localization.Language` enum order.
    pub const ALL: [Language; 2] = [Language::Chs, Language::Eng];

    /// The AGD short code used in paths and file suffixes.
    pub fn short(self) -> &'static str {
        match self {
            Language::Chs => "CHS",
            Language::Eng => "EN",
        }
    }

    /// The Python `Language.value` string (metadata.json's `language` field).
    pub fn value(self) -> &'static str {
        match self {
            Language::Chs => "CHS",
            Language::Eng => "ENG",
        }
    }
}
