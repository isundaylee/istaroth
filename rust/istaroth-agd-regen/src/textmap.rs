//! Port of repo.TextMapTracker: current-build map, older-build fallbacks
//! (via `git show`), SEXPRO pronoun-hash resolution, and per-lookup cleaning.

use crate::cleanup;
use crate::git::git_show;
use crate::issues::Scope;
use anyhow::{Result, anyhow};
use rustc_hash::FxHashMap;
use std::path::Path;

pub const FALLBACK_REFS: [&str; 3] = ["4d9593eb73a", "f9a21406731", "8c3aecbd6ed"];

pub struct TextMaps {
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
    pub fn load(agd_path: &Path, language_short: &str) -> Result<TextMaps> {
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
        let mut data = FxHashMap::default();
        for ref_data in per_ref {
            for (key, value) in ref_data? {
                data.entry(key).or_insert(value);
            }
        }
        Ok(data)
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
                let token = entry["textMapId"]
                    .as_str()
                    .ok_or_else(|| anyhow!("textMapId must be a string"))?;
                if token.starts_with("INFO_") && !pronouns.contains_key(token) {
                    let hash = &entry["textMapContentTextMapHash"];
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
        cleanup::clean_text_markers(&resolved)
    }

    /// Python TextMapTracker: a lookup that resolves (in the current or
    /// fallback map) records the hash into the active scope.
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
