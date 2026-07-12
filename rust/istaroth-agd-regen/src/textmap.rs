//! Port of repo.TextMapTracker: current-build map, older-build fallbacks
//! (via `git show`), SEXPRO pronoun-hash resolution, and per-lookup cleaning.

use crate::cleanup;
use crate::git::git_show;
use crate::issues::Scope;
use crate::lang::Language;
use crate::vh::ValueExt;
use anyhow::{Result, anyhow};
use rustc_hash::FxHashMap;
use std::path::Path;

// Ordered newest-to-oldest; earlier refs win when multiple fallbacks contain a
// hash. Sex-pronoun SEXPRO tokens also resolve against these builds (see
// load_pronouns): 6.x dropped their TextMap rows and reassigned the manual hash
// ids, so both token -> hash and hash -> text are read from here.
//
// 6.6.0/6.5.0 recover the great majority of hashes that a version bump drops
// from the current TextMap (investigated in issue #273): checked back through
// 5.4.0, nothing older than the immediately preceding minor version ever
// contributed a recoverable hash, so there's no benefit to walking further
// back. 8c3aecbd6ed (5.4.0) stays for the older SEXPRO manual-hash pairing.
pub const FALLBACK_REFS: [&str; 3] = [
    "4d9593eb73a", // 6.6.0
    "f9a21406731", // 6.5.0
    "8c3aecbd6ed", // 5.4.0
];

#[derive(Default)]
pub struct TextMaps {
    language: Language,
    current: FxHashMap<i64, String>,
    fallback: FxHashMap<i64, String>,
    pronouns: FxHashMap<String, i64>,
}

fn parse_text_map(bytes: &[u8]) -> Result<FxHashMap<i64, String>> {
    use serde::de::{MapAccess, Visitor};
    struct TmVisitor;
    impl<'de> Visitor<'de> for TmVisitor {
        type Value = FxHashMap<i64, String>;
        fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
            f.write_str("text map object")
        }
        fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<Self::Value, A::Error> {
            let mut out = FxHashMap::with_capacity_and_hasher(
                map.size_hint().unwrap_or(0),
                Default::default(),
            );
            while let Some(key) = map.next_key::<std::borrow::Cow<str>>()? {
                let id: i64 = key
                    .trim()
                    .parse()
                    .map_err(|e| serde::de::Error::custom(format!("text map key {key:?}: {e}")))?;
                out.insert(id, map.next_value::<String>()?);
            }
            Ok(out)
        }
    }
    let mut de = serde_json::Deserializer::from_slice(bytes);
    let result = serde::de::Deserializer::deserialize_map(&mut de, TmVisitor)?;
    de.end()?;
    Ok(result)
}

impl TextMaps {
    #[cfg(test)]
    pub(crate) fn for_tests(
        language: Language,
        current: FxHashMap<i64, String>,
        fallback: FxHashMap<i64, String>,
        pronouns: FxHashMap<String, i64>,
    ) -> TextMaps {
        TextMaps {
            language,
            current,
            fallback,
            pronouns,
        }
    }

    pub fn load(agd_path: &Path, language: Language) -> Result<TextMaps> {
        let language_short = language.short();
        let (current, (fallback, pronouns)) = rayon::join(
            || Self::load_current(agd_path, language_short),
            || {
                rayon::join(
                    || Self::load_fallback(agd_path, language_short),
                    || Self::load_pronouns(agd_path),
                )
            },
        );
        Ok(TextMaps {
            language,
            current: current?,
            fallback: fallback?,
            pronouns: pronouns?,
        })
    }

    fn load_current(agd_path: &Path, language_short: &str) -> Result<FxHashMap<i64, String>> {
        let dir = agd_path.join("TextMap");
        let medium = dir.join(format!("TextMap_Medium{language_short}.json"));
        let mut data = if medium.exists() {
            parse_text_map(&std::fs::read(&medium)?)?
        } else {
            FxHashMap::default()
        };
        let main = parse_text_map(&std::fs::read(
            dir.join(format!("TextMap{language_short}.json")),
        )?)?;
        data.extend(main);
        Ok(data)
    }

    fn load_fallback(agd_path: &Path, language_short: &str) -> Result<FxHashMap<i64, String>> {
        let per_ref: Vec<Result<FxHashMap<i64, String>>> = {
            use rayon::prelude::*;
            FALLBACK_REFS
                .par_iter()
                .map(|git_ref| {
                    let (medium, main) = rayon::join(
                        || -> Result<FxHashMap<i64, String>> {
                            match git_show(
                                agd_path,
                                git_ref,
                                &format!("TextMap/TextMap_Medium{language_short}.json"),
                            )? {
                                Some(bytes) => parse_text_map(&bytes),
                                None => Ok(FxHashMap::default()),
                            }
                        },
                        || -> Result<FxHashMap<i64, String>> {
                            let main = git_show(
                                agd_path,
                                git_ref,
                                &format!("TextMap/TextMap{language_short}.json"),
                            )?
                            .ok_or_else(|| {
                                anyhow!("missing TextMap{language_short} at {git_ref}")
                            })?;
                            parse_text_map(&main)
                        },
                    );
                    let mut ref_data = medium?;
                    ref_data.extend(main?);
                    Ok(ref_data)
                })
                .collect()
        };
        // Merged in FALLBACK_REFS order so earlier (newer) refs win.
        merge_fallbacks(per_ref)
    }

    fn load_pronouns(agd_path: &Path) -> Result<FxHashMap<String, i64>> {
        use rayon::prelude::*;
        let per_ref: Vec<Result<Vec<serde_json::Value>>> = FALLBACK_REFS
            .par_iter()
            .map(|git_ref| {
                let bytes = git_show(
                    agd_path,
                    git_ref,
                    "ExcelBinOutput/ManualTextMapConfigData.json",
                )?
                .ok_or_else(|| anyhow!("missing ManualTextMapConfigData at {git_ref}"))?;
                Ok(serde_json::from_slice(&bytes)?)
            })
            .collect();
        let mut pronouns = FxHashMap::default();
        for entries in per_ref {
            for entry in entries? {
                let token = entry.s("textMapId")?;
                if token.starts_with("INFO_") && !pronouns.contains_key(token) {
                    let hash = entry.f("textMapContentTextMapHash")?;
                    let hash = hash
                        .as_i64()
                        .or_else(|| hash.as_str().and_then(|s| s.trim().parse().ok()))
                        .ok_or_else(|| anyhow!("bad textMapContentTextMapHash"))?;
                    pronouns.insert(token.to_string(), hash);
                }
            }
        }
        Ok(pronouns)
    }

    fn get_raw(&self, key: i64) -> Option<&str> {
        self.current
            .get(&key)
            .or_else(|| self.fallback.get(&key))
            .map(|s| s.as_str())
    }

    pub fn clean_text(&self, text: &str) -> Result<String> {
        let resolved = cleanup::resolve_sexpro(text, |token| {
            let hash = self
                .pronouns
                .get(token)
                .ok_or_else(|| anyhow!("Unresolvable SEXPRO pronoun token: {token}"))?;
            self.get_raw(*hash)
                .map(str::to_string)
                .ok_or_else(|| anyhow!("Unresolvable SEXPRO pronoun token: {token}"))
        })?;
        cleanup::clean_text_markers(&resolved, self.language)
    }

    /// Any lookup that resolves — in the current OR fallback map — records the
    /// hash into the active scope. Fallback-only hashes never inflate the
    /// current-build unused count: `unused_current_ids` subtracts accessed
    /// hashes from the current map's keys only.
    fn track(&self, scope: &Scope, key: i64) {
        scope.text_map.borrow_mut().insert(key);
    }

    pub fn get_optional(&self, key: i64, scope: &Scope) -> Result<Option<String>> {
        let Some(raw) = self.get_raw(key) else {
            return Ok(None);
        };
        self.track(scope, key);
        Ok(Some(self.clean_text(raw)?))
    }

    pub fn get_or(&self, key: i64, default: &str, scope: &Scope) -> Result<String> {
        Ok(self
            .get_optional(key, scope)?
            .unwrap_or_else(|| default.to_string()))
    }

    pub fn get_required(&self, key: i64, scope: &Scope) -> Result<String> {
        self.get_optional(key, scope)?
            .ok_or_else(|| anyhow!("Unresolvable text map hash {key}"))
    }

    pub fn get_current_optional(&self, key: i64, scope: &Scope) -> Result<Option<String>> {
        let Some(raw) = self.current.get(&key) else {
            return Ok(None);
        };
        self.track(scope, key);
        Ok(Some(self.clean_text(raw)?))
    }

    pub fn get_optional_untracked(&self, key: i64) -> Result<Option<String>> {
        self.get_raw(key).map(|t| self.clean_text(t)).transpose()
    }

    pub fn get_current_optional_untracked(&self, key: i64) -> Result<Option<String>> {
        self.current
            .get(&key)
            .map(|t| self.clean_text(t))
            .transpose()
    }

    pub fn text_map_len(&self) -> usize {
        self.current.len()
    }

    /// Sorted current-build hashes not in `accessed` (unused-stats output).
    pub fn unused_current_ids(&self, accessed: &rustc_hash::FxHashSet<i64>) -> Vec<i64> {
        let mut unused: Vec<i64> = self
            .current
            .keys()
            .filter(|k| !accessed.contains(k))
            .copied()
            .collect();
        unused.sort();
        unused
    }
}

fn merge_fallbacks(
    per_ref: impl IntoIterator<Item = Result<FxHashMap<i64, String>>>,
) -> Result<FxHashMap<i64, String>> {
    let mut data = FxHashMap::default();
    for ref_data in per_ref {
        for (key, value) in ref_data? {
            data.entry(key).or_insert(value);
        }
    }
    Ok(data)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn string_map(entries: &[(i64, &str)]) -> FxHashMap<i64, String> {
        entries.iter().map(|(k, v)| (*k, v.to_string())).collect()
    }

    #[test]
    fn fallback_only_on_current_miss() {
        let tm = TextMaps::for_tests(
            Language::Chs,
            string_map(&[(100, "Current"), (200, "Current wins")]),
            string_map(&[(200, "Fallback loses"), (300, "Fallback")]),
            FxHashMap::default(),
        );
        let scope = Scope::default();
        assert_eq!(
            tm.get_optional(100, &scope).unwrap(),
            Some("Current".to_string())
        );
        assert_eq!(
            tm.get_optional(200, &scope).unwrap(),
            Some("Current wins".to_string())
        );
        assert_eq!(
            tm.get_optional(300, &scope).unwrap(),
            Some("Fallback".to_string())
        );
        assert_eq!(tm.get_current_optional(300, &scope).unwrap(), None);
        assert_eq!(
            tm.get_optional_untracked(300).unwrap(),
            Some("Fallback".to_string())
        );
        assert_eq!(tm.get_or(400, "Default", &scope).unwrap(), "Default");
        // Every resolving lookup (current or fallback) was tracked; the
        // untracked variant and the miss were not.
        let accessed = scope.text_map.borrow();
        assert_eq!(
            *accessed,
            [100, 200, 300]
                .into_iter()
                .collect::<rustc_hash::FxHashSet<i64>>()
        );
    }

    #[test]
    fn get_required_errors_on_miss() {
        let tm = TextMaps::for_tests(
            Language::Chs,
            FxHashMap::default(),
            FxHashMap::default(),
            FxHashMap::default(),
        );
        let err = tm.get_required(202, &Scope::default()).unwrap_err();
        assert!(err.to_string().contains("Unresolvable text map hash 202"));
    }

    #[test]
    fn sexpro_resolves_via_pronoun_hashes() {
        // 6.x dropped the pronoun TextMap rows, so both the token -> hash
        // pairing and the hash -> text live in the fallback maps.
        let tm = TextMaps::for_tests(
            Language::Chs,
            FxHashMap::default(),
            string_map(&[(500, "他")]),
            [("INFO_MALE_PRONOUN_HE".to_string(), 500)]
                .into_iter()
                .collect(),
        );
        assert_eq!(
            tm.clean_text("找{PLAYERAVATAR#SEXPRO[INFO_MALE_PRONOUN_HE|INFO_FEMALE_PRONOUN_SHE]}")
                .unwrap(),
            "找他"
        );
    }

    #[test]
    fn fallback_refs_merge_in_code_order() {
        assert_eq!(
            merge_fallbacks([
                Ok(string_map(&[(1, "newer"), (2, "newer only")])),
                Ok(string_map(&[(1, "older"), (3, "older only")])),
            ])
            .unwrap(),
            string_map(&[(1, "newer"), (2, "newer only"), (3, "older only")])
        );
    }
}
