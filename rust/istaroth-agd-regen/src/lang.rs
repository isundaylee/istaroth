//! Output-language configuration. Only CHS is implemented for generation; ENG
//! needs split source/output text maps and localized render strings (future
//! work). Eng exists so language-independent code (first-seen builds) can
//! enumerate all languages.

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Language {
    Chs,
    Eng,
}

impl Language {
    /// Every language, in the reference enum order (delta files and unions
    /// depend on it).
    pub const ALL: [Language; 2] = [Language::Chs, Language::Eng];

    /// The AGD short code used in paths and file suffixes.
    pub fn short(self) -> &'static str {
        match self {
            Language::Chs => "CHS",
            Language::Eng => "EN",
        }
    }

    /// The long language code (metadata.json's `language` field).
    pub fn value(self) -> &'static str {
        match self {
            Language::Chs => "CHS",
            Language::Eng => "ENG",
        }
    }
}
