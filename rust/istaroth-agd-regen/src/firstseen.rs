//! Port of istaroth.agd.first_seen: folded first-seen version index.
//!
//! Maps raw AGD source ids (main quests, talks, readables, ...) to the game
//! version in which they first appeared. The index is folded from the
//! per-version delta files under `first_seen/` in the `text/` submodule, each
//! listing the ids newly seen in that version's AGD snapshot (built by the
//! `build-first-seen` command / `scripts/agd_build_first_seen.py` from the
//! AGD git history and committed alongside the corpus regenerations they
//! stamp).

use crate::util;
use anyhow::{Context, Result, anyhow, bail};
use rustc_hash::FxHashMap;
use std::collections::hash_map::Entry;
use std::path::Path;

#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Domain {
    MainQuest,
    Talk,
    Readable,
    Subtitle,
    Material,
    Weapon,
    Achievement,
    Avatar,
    ArtifactSet,
    AnimalCodex,
}

impl Domain {
    fn from_name(name: &str) -> Result<Domain> {
        Ok(match name {
            "main_quest" => Domain::MainQuest,
            "talk" => Domain::Talk,
            "readable" => Domain::Readable,
            "subtitle" => Domain::Subtitle,
            "material" => Domain::Material,
            "weapon" => Domain::Weapon,
            "achievement" => Domain::Achievement,
            "avatar" => Domain::Avatar,
            "artifact_set" => Domain::ArtifactSet,
            "animal_codex" => Domain::AnimalCodex,
            other => bail!("unknown first-seen domain {other}"),
        })
    }
}

/// Readable/subtitle domains are keyed by language-neutral filename stems
/// (Str); the rest are int-keyed.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum SourceKey {
    Int(i64),
    Str(String),
}

#[derive(Default)]
pub struct FirstSeenIndex {
    versions: FxHashMap<Domain, FxHashMap<SourceKey, String>>,
}

impl FirstSeenIndex {
    #[cfg(test)]
    pub(crate) fn for_tests(
        versions: impl IntoIterator<Item = (Domain, SourceKey, &'static str)>,
    ) -> FirstSeenIndex {
        let mut index = FirstSeenIndex::default();
        for (domain, key, version) in versions {
            index
                .versions
                .entry(domain)
                .or_default()
                .insert(key, version.to_string());
        }
        index
    }
    pub fn load(data_dir: &Path) -> Result<FirstSeenIndex> {
        let mut paths: Vec<std::path::PathBuf> = std::fs::read_dir(data_dir)
            .with_context(|| format!("first-seen dir {data_dir:?}"))?
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.extension().is_some_and(|e| e == "json"))
            .collect();
        if paths.is_empty() {
            bail!("No first-seen delta files in {data_dir:?}");
        }
        paths.sort_by_key(|p| util::version_key(p.file_stem().unwrap().to_str().unwrap()));
        let mut versions: FxHashMap<Domain, FxHashMap<SourceKey, String>> = FxHashMap::default();
        for path in &paths {
            let data: serde_json::Value = serde_json::from_slice(&std::fs::read(path)?)?;
            let version = data["version"]
                .as_str()
                .ok_or_else(|| anyhow!("version must be a string"))?
                .to_string();
            let stem = path.file_stem().unwrap().to_str().unwrap();
            if version != stem {
                bail!("Version {version:?} in {path:?} does not match filename");
            }
            let new = data
                .get("new")
                .and_then(|v| v.as_object())
                .ok_or_else(|| anyhow!("{path:?} has no \"new\" object"))?;
            for (domain_name, keys) in new {
                let domain = Domain::from_name(domain_name)?;
                let mapping = versions.entry(domain).or_default();
                let keys = keys
                    .as_array()
                    .ok_or_else(|| anyhow!("{domain_name} ids in {path:?} not a list"))?;
                for key in keys {
                    let key = match key {
                        serde_json::Value::Number(n) => {
                            SourceKey::Int(n.as_i64().ok_or_else(|| anyhow!("non-int source id"))?)
                        }
                        serde_json::Value::String(s) => SourceKey::Str(s.clone()),
                        other => bail!("bad source id {other:?}"),
                    };
                    match mapping.entry(key) {
                        Entry::Occupied(e) => {
                            bail!("Source id {:?} in {domain_name} listed twice", e.key())
                        }
                        Entry::Vacant(e) => {
                            e.insert(version.clone());
                        }
                    }
                }
            }
        }
        Ok(FirstSeenIndex { versions })
    }

    pub fn resolve<'a>(
        &self,
        source_ids: impl IntoIterator<Item = (Domain, &'a SourceKey)>,
    ) -> Result<(String, String)> {
        let mut resolved: Vec<&String> = Vec::new();
        for (domain, key) in source_ids {
            let version = self
                .versions
                .get(&domain)
                .and_then(|m| m.get(key))
                .ok_or_else(|| anyhow!("{domain:?} id {key:?} not in the first-seen index"))?;
            resolved.push(version);
        }
        if resolved.is_empty() {
            bail!("Cannot resolve versions for empty source ids");
        }
        let min = resolved
            .iter()
            .min_by_key(|v| util::version_key(v))
            .unwrap();
        let max = resolved
            .iter()
            .max_by_key(|v| util::version_key(v))
            .unwrap();
        Ok(((*min).clone(), (*max).clone()))
    }

    pub fn resolve_int(&self, domain: Domain, id: i64) -> Result<(String, String)> {
        let key = SourceKey::Int(id);
        self.resolve([(domain, &key)])
    }

    pub fn resolve_ints(
        &self,
        domain: Domain,
        ids: impl IntoIterator<Item = i64>,
    ) -> Result<(String, String)> {
        let keys: Vec<SourceKey> = ids.into_iter().map(SourceKey::Int).collect();
        self.resolve(keys.iter().map(|k| (domain, k)))
    }

    pub fn resolve_stem(&self, domain: Domain, path: &str) -> Result<(String, String)> {
        let key = SourceKey::Str(util::strip_language_suffix(util::path_stem(path)).to_string());
        self.resolve([(domain, &key)])
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn write_delta(dir: &Path, version: &str, new: serde_json::Value) {
        let payload =
            json!({"version": version, "commit": format!("commit-{version}"), "new": new});
        std::fs::write(
            dir.join(format!("{version}.json")),
            serde_json::to_vec(&payload).unwrap(),
        )
        .unwrap();
    }

    /// Fresh delta dir with 1.4 / 2.0 / 10.0 files; 10.0 ensures folding
    /// orders numerically, not lexicographically (10 > 2).
    fn delta_dir(name: &str) -> std::path::PathBuf {
        let dir =
            std::env::temp_dir().join(format!("istaroth-firstseen-{}-{name}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        write_delta(
            &dir,
            "1.4",
            json!({"main_quest": [351], "talk": [100], "readable": ["Book1"]}),
        );
        write_delta(&dir, "2.0", json!({"talk": [200, 201]}));
        write_delta(&dir, "10.0", json!({"talk": [300]}));
        dir
    }

    #[test]
    fn resolve_min_max() {
        let index = FirstSeenIndex::load(&delta_dir("resolve")).unwrap();
        assert_eq!(
            index.resolve_int(Domain::Talk, 200).unwrap(),
            ("2.0".to_string(), "2.0".to_string())
        );
        assert_eq!(
            index.resolve_ints(Domain::Talk, [300, 100, 201]).unwrap(),
            ("1.4".to_string(), "10.0".to_string())
        );
        let book = SourceKey::Str("Book1".to_string());
        let quest = SourceKey::Int(351);
        assert_eq!(
            index
                .resolve([(Domain::MainQuest, &quest), (Domain::Readable, &book)])
                .unwrap(),
            ("1.4".to_string(), "1.4".to_string())
        );
    }

    #[test]
    fn resolve_unknown_or_empty_errors() {
        let index = FirstSeenIndex::load(&delta_dir("unknown")).unwrap();
        let err = index.resolve_int(Domain::Talk, 999).unwrap_err();
        assert!(err.to_string().contains("not in the first-seen index"));
        assert!(index.resolve([]).is_err());
    }

    #[test]
    fn load_rejects_duplicate_id() {
        let dir = delta_dir("duplicate");
        write_delta(&dir, "3.0", json!({"talk": [100]}));
        let Err(err) = FirstSeenIndex::load(&dir) else {
            panic!("duplicate id must fail the load")
        };
        assert!(err.to_string().contains("listed twice"));
    }
}
