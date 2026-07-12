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

pub struct FirstSeenIndex {
    versions: FxHashMap<Domain, FxHashMap<SourceKey, String>>,
}

impl FirstSeenIndex {
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
                    if mapping.contains_key(&key) {
                        bail!("Source id {key:?} in {domain_name} listed twice");
                    }
                    mapping.insert(key, version.clone());
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
        resolved.sort_by_key(|v| util::version_key(v));
        Ok((resolved[0].clone(), resolved[resolved.len() - 1].clone()))
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
