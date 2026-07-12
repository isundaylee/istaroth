//! Output-language configuration: language codes plus the per-language
//! localized role names (port of istaroth.agd.localization's `_ROLE_NAMES`).

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub enum Language {
    #[default]
    Chs,
    Eng,
}

/// Localized dialogue role names (port of `LocalizedRoleNames`).
pub struct RoleNames {
    pub player: &'static str,
    pub mate_avatar: &'static str,
    pub paimon: &'static str,
    pub black_screen: &'static str,
    pub unknown_role: &'static str,
}

impl Language {
    /// Every language, in a fixed order (delta files and unions depend on it).
    pub const ALL: [Language; 2] = [Language::Chs, Language::Eng];

    /// The AGD short code used in paths and file suffixes.
    pub fn short(self) -> &'static str {
        match self {
            Language::Chs => "CHS",
            Language::Eng => "EN",
        }
    }

    /// The long language code (metadata.json's `language` field). Values must
    /// match the Python `Language` enum in `istaroth/agd/localization.py`,
    /// which the RAG readers parse this field into.
    pub fn value(self) -> &'static str {
        match self {
            Language::Chs => "CHS",
            Language::Eng => "ENG",
        }
    }

    pub fn from_value(value: &str) -> Option<Language> {
        Language::ALL.into_iter().find(|l| l.value() == value)
    }

    pub fn role_names(self) -> &'static RoleNames {
        match self {
            Language::Chs => &RoleNames {
                player: "旅行者",
                mate_avatar: "旅行者血亲",
                paimon: "派蒙",
                black_screen: "黑屏文本",
                unknown_role: "Unknown Role",
            },
            Language::Eng => &RoleNames {
                player: "Traveler",
                mate_avatar: "Traveler's Sibling",
                paimon: "Paimon",
                black_screen: "Black Screen Text",
                unknown_role: "Unknown Role",
            },
        }
    }
}
