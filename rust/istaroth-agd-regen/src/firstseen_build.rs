//! Port of scripts/agd_build_first_seen.py: build the per-version first-seen
//! delta files from AGD git history.
//!
//! For each snapshot in `SNAPSHOTS` (oldest first), enumerates the source ids
//! present in that AGD revision and writes the ids never seen in any earlier
//! snapshot to `<data_dir>/<version>.json` (committed to the `text/` submodule
//! alongside the corpus regen it stamps). The default run only generates files
//! missing on disk (ingesting a new game version = append its `SNAPSHOTS`
//! entry and rerun); `--rebuild-all` regenerates every file, doubling as a
//! determinism check of the committed data.

use crate::git::{git_ls_tree, git_show};
use crate::util;
use anyhow::{Context, Result, anyhow, bail};
use rayon::prelude::*;
use rustc_hash::FxHashSet;
use serde_json::Value;
use std::path::Path;

/// The last AGD snapshot commit of each game version, oldest first. Curated by
/// hand from `git log origin/master v2/main` because commit subjects are not
/// reliable enough to parse blindly:
/// - the 3.3 snapshot's subject is mislabeled "OSRELWin3.0.0_R11806263" (it
///   sits between the 3.2 and 3.4 snapshots and its R build number is above
///   3.2's);
/// - hotfix snapshots repeat a version, and 1.6.1/4.0.1 normalize to 1.6/4.0;
/// - no 4.1 snapshot was ever published, so 4.1 additions attribute to 4.2;
/// - versions before 1.4 predate the history, so the 1.4 file is a baseline
///   ("1.4 or earlier"); CN and OS snapshots of a version are interchangeable.
const SNAPSHOTS: [(&str, &str); 46] = [
    ("1.4", "86c28c0a59526cad72d5ec6548a0d6b3a9413826"),
    ("1.5", "5ee08c0771f257ac06f37293973e6bf42302fa76"),
    ("1.6", "9eeb6591fa5de850a0486fa6c2691e1f468d3d91"),
    ("2.0", "97ec5bf557d7dd301beac19ab72cdf4edf9def0a"),
    ("2.1", "23e4d9800ee43bfc21f16a7441af18b6acf59f68"),
    ("2.2", "a92b5842daa911c095f47ef235b2bcd4b388d65a"),
    ("2.3", "3d39b3502bdcec8d936f82f32ecc36f65eaba2b2"),
    ("2.4", "27a2ca1cb72393e3b4a8420e830912f7704d4fff"),
    ("2.5", "f6b76a7c958c121e43d4612d7d54e327066d2e73"),
    ("2.6", "ecb5c64aa4fcba4ed83f69bee28103770061c189"),
    ("2.7", "ebb117f78dab56e704853b71fa60f45ee2cefe79"),
    ("2.8", "d56ed231c4513963d27051dd6f7828f0e06c2588"),
    ("3.0", "45c509efd76550b17e394774fd90bec248ccefdb"),
    ("3.1", "4c5e4f6889ee820be814c71e663bf19c2bf2275d"),
    ("3.2", "e7c944395d00f0dc1848a66703c73d9763dfc5cc"),
    ("3.3", "1a6597f5a67382119494beae22a4039a1cefc8e1"),
    ("3.4", "28662783890fd9c3a16404e1971d37a23a7045ca"),
    ("3.5", "410cafbc9ba35274b96a44f7b9e9c85be43a2334"),
    ("3.6", "9aa4937b7dddc506677617150e29803004fee964"),
    ("3.7", "23109cab0def51d4b598a91b33a1f642a83d0359"),
    ("3.8", "6b5b54aa48e0158350cd82d0732d1667140dd860"),
    ("4.0", "4f872fefab5ed8c6c6b72899e47bcb0344416a4f"),
    ("4.2", "d2a73df4ff40bd9e666f86773012a5f52b548b0f"),
    ("4.3", "ecce481664b72fa2ea1d141ed7d6d08acb80d63b"),
    ("4.4", "61eaba93568a69466951b1c2bc5efe2157963bdc"),
    ("4.5", "8c43a454992c4e339bf0b79b74cd081f8e8a2cca"),
    ("4.6", "85c2f9e54ced5df20e50065abc3db73d0d07ce87"),
    ("4.7", "c4775ae8295fa55703af9d6cd42ad39acadd508c"),
    ("4.8", "411376ae92931a04d41ae5a9386d45c0d2deb8a8"),
    ("5.0", "f90e7b375ea9a6441952c49a672f868028a9f92d"),
    ("5.1", "92931454c0f7a703c64a1e3baec83571753bc0eb"),
    ("5.2", "3847f0fc6e3119b87767508ac7471dff6a7b51d0"),
    ("5.3", "51f5e2eaab4c1a7f4692ac3454122b28024ec62c"),
    ("5.4", "dee14cc45e977782e1e93be9d3ed4b0d12e90e5a"),
    ("5.5", "0077f79f1676bad3b121017fe2098bedbe284712"),
    ("5.6", "cb46dc84d8897b49fbfbe944035fac5abc520f6f"),
    ("5.7", "de661bd09b262ce320f78a03bc0adc437f8729a3"),
    ("5.8", "13be4fd7343fe4cee8fa0096fe854b1c5b01b124"),
    ("6.0", "4f9f22c8842a9e840baa51ff579b26dd248079ba"),
    ("6.1", "f83066c8c20ced632c6fb07d8a4fb0ab8fbb4192"),
    ("6.2", "2f0f85f19885ee632d9eab37226c9e60d8f1216f"),
    ("6.3", "fe7c8592b2fd1cd3f285de5039285c99e641a5e1"),
    ("6.4", "b761e4d2e9e509eb8aa8c04c381b46d2308d7e85"),
    ("6.5", "f9a21406731cd33242defd88dfc2aa06674ab353"),
    ("6.6", "4d9593eb73a52e3fd79c30c4f22f97be4a71ba36"),
    ("6.7", "82e74382e7788e318ad41fca926739a752c0bed6"),
];

/// Domain names in the delta files' JSON key order (must stay stable for
/// byte-identical output).
const DOMAINS: [&str; 10] = [
    "main_quest",
    "talk",
    "readable",
    "subtitle",
    "material",
    "weapon",
    "achievement",
    "avatar",
    "artifact_set",
    "animal_codex",
];

const EXCEL_DOMAINS: [(&str, &str, &str); 7] = [
    ("main_quest", "MainQuestExcelConfigData.json", "id"),
    ("material", "MaterialExcelConfigData.json", "id"),
    ("weapon", "WeaponExcelConfigData.json", "id"),
    ("achievement", "AchievementExcelConfigData.json", "id"),
    ("avatar", "AvatarExcelConfigData.json", "id"),
    ("artifact_set", "ReliquarySetExcelConfigData.json", "setId"),
    ("animal_codex", "AnimalCodexExcelConfigData.json", "id"),
];

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
enum Key {
    Int(i64),
    Str(String),
}

type DomainSets = Vec<FxHashSet<Key>>; // indexed like DOMAINS

fn empty_sets() -> DomainSets {
    DOMAINS.iter().map(|_| FxHashSet::default()).collect()
}

fn domain_index(name: &str) -> Result<usize> {
    DOMAINS
        .iter()
        .position(|d| *d == name)
        .ok_or_else(|| anyhow!("unknown first-seen domain {name}"))
}

/// Field-name style varies by era (and by file within one era): 1.x dumps use
/// PascalCase ("Id"/"SetId"), some ~2.7-3.x dumps underscore-prefixed
/// camelCase ("_id"), current dumps plain camelCase.
fn row_id(row: &Value, id_key: &str) -> Result<i64> {
    let capitalized = format!("{}{}", id_key[..1].to_uppercase(), &id_key[1..]);
    let underscored = format!("_{id_key}");
    for key in [id_key, capitalized.as_str(), underscored.as_str()] {
        if let Some(v) = row.get(key) {
            return v
                .as_i64()
                .or_else(|| v.as_str().and_then(|s| s.trim().parse().ok()))
                .ok_or_else(|| anyhow!("non-int {id_key} in excel row"));
        }
    }
    bail!("No {id_key:?} field in excel row")
}

fn parse_rows(bytes: &[u8]) -> Result<Vec<Value>> {
    match serde_json::from_slice(bytes)? {
        Value::Array(items) => Ok(items),
        _ => bail!("excel file must be a list"),
    }
}

/// Talk excel at a ref: split TalkExcelConfigData_* files or the single file.
fn load_talk_excel_at(agd_path: &Path, git_ref: &str) -> Result<Vec<Value>> {
    let split: Vec<String> = git_ls_tree(agd_path, git_ref, "ExcelBinOutput")?
        .into_iter()
        .filter(|n| n.starts_with("TalkExcelConfigData_") && n.ends_with(".json"))
        .collect();
    let names = if split.is_empty() {
        vec!["TalkExcelConfigData.json".to_string()]
    } else {
        split
    };
    let mut rows = Vec::new();
    for name in names {
        let bytes = git_show(agd_path, git_ref, &format!("ExcelBinOutput/{name}"))?
            .ok_or_else(|| anyhow!("missing ExcelBinOutput/{name} at {git_ref}"))?;
        rows.extend(parse_rows(&bytes)?);
    }
    Ok(rows)
}

/// Enumerate all source ids present in one AGD snapshot, unioned over both
/// languages.
fn scan_snapshot(agd_path: &Path, commit: &str) -> Result<DomainSets> {
    let mut present = empty_sets();

    // Excel domains + talk are language-independent; scan once.
    let excel_results: Vec<Result<(usize, FxHashSet<Key>)>> = EXCEL_DOMAINS
        .par_iter()
        .map(|(domain, filename, id_key)| {
            let bytes = git_show(agd_path, commit, &format!("ExcelBinOutput/{filename}"))?
                .ok_or_else(|| anyhow!("missing {filename} at {commit}"))?;
            let ids: FxHashSet<Key> = parse_rows(&bytes)?
                .iter()
                .map(|row| Ok(Key::Int(row_id(row, id_key)?)))
                .collect::<Result<_>>()?;
            Ok((domain_index(domain)?, ids))
        })
        .collect();
    for r in excel_results {
        let (idx, ids) = r?;
        present[idx].extend(ids);
    }
    let talk_ids: FxHashSet<Key> = load_talk_excel_at(agd_path, commit)?
        .iter()
        .map(|row| Ok(Key::Int(row_id(row, "id")?)))
        .collect::<Result<_>>()?;
    present[domain_index("talk")?].extend(talk_ids);

    // Filename-keyed domains: union all languages to guard against language
    // stragglers. Subtitles only exist from 1.6 onward, so a missing Subtitle
    // dir yields an empty list rather than erroring.
    for language_short in crate::lang::Language::ALL.map(crate::lang::Language::short) {
        let readable_names: Vec<String> =
            git_ls_tree(agd_path, commit, &format!("Readable/{language_short}"))?
                .into_iter()
                .filter(|n| n.ends_with(".txt"))
                .collect();
        if readable_names.is_empty() {
            bail!("No readable files for {language_short} at {commit}");
        }
        present[domain_index("readable")?].extend(
            readable_names
                .iter()
                .map(|n| Key::Str(util::strip_language_suffix(util::path_stem(n)).to_string())),
        );
        let subtitle_names = git_ls_tree(agd_path, commit, &format!("Subtitle/{language_short}"))?;
        present[domain_index("subtitle")?].extend(
            subtitle_names
                .iter()
                .map(|n| Key::Str(util::strip_language_suffix(util::path_stem(n)).to_string())),
        );
    }
    Ok(present)
}

/// Write one delta file in the reference JSON format (2-space indent,
/// non-ASCII preserved, trailing newline) so rebuilds stay byte-identical.
fn write_delta(path: &Path, version: &str, commit: &str, new: &DomainSets) -> Result<usize> {
    let mut new_obj = serde_json::Map::new();
    let mut total = 0usize;
    for (i, domain) in DOMAINS.iter().enumerate() {
        let mut keys: Vec<&Key> = new[i].iter().collect();
        keys.sort();
        total += keys.len();
        let values: Vec<Value> = keys
            .iter()
            .map(|k| match k {
                Key::Int(n) => Value::from(*n),
                Key::Str(s) => Value::from(s.as_str()),
            })
            .collect();
        new_obj.insert(domain.to_string(), Value::Array(values));
    }
    let mut payload = serde_json::Map::new();
    payload.insert("version".to_string(), Value::from(version));
    payload.insert("commit".to_string(), Value::from(commit));
    payload.insert("new".to_string(), Value::Object(new_obj));
    let mut bytes = serde_json::to_vec_pretty(&Value::Object(payload))?;
    bytes.push(b'\n');
    std::fs::write(path, bytes)?;
    Ok(total)
}

pub fn build_first_seen(agd_path: &Path, data_dir: &Path, rebuild_all: bool) -> Result<()> {
    std::fs::create_dir_all(data_dir)?;

    // Determine which snapshots need scanning, then scan them all in parallel
    // (each scan is independent; only the delta fold below is sequential).
    let mut to_scan: Vec<(usize, &str, &str)> = Vec::new();
    let mut missing_earlier: Vec<&str> = Vec::new();
    for (i, (version, commit)) in SNAPSHOTS.iter().enumerate() {
        let path = data_dir.join(format!("{version}.json"));
        if !rebuild_all && path.exists() {
            if !missing_earlier.is_empty() {
                bail!(
                    "Delta file for {version} exists but earlier versions {missing_earlier:?} \
                     are missing; run with --rebuild-all"
                );
            }
            continue;
        }
        missing_earlier.push(version);
        to_scan.push((i, version, commit));
    }
    let scans: Vec<(usize, Result<DomainSets>)> = to_scan
        .par_iter()
        .map(|(i, _, commit)| (*i, scan_snapshot(agd_path, commit)))
        .collect();
    let mut scanned: Vec<Option<DomainSets>> = SNAPSHOTS.iter().map(|_| None).collect();
    for (i, result) in scans {
        scanned[i] = Some(result.with_context(|| format!("scan {}", SNAPSHOTS[i].0))?);
    }

    let mut seen = empty_sets();
    for (i, (version, commit)) in SNAPSHOTS.iter().enumerate() {
        let path = data_dir.join(format!("{version}.json"));
        match scanned[i].take() {
            None => {
                // Existing delta: verify commit and fold its ids into `seen`.
                let data: Value = serde_json::from_slice(&std::fs::read(&path)?)?;
                let file_commit = data
                    .get("commit")
                    .and_then(|v| v.as_str())
                    .ok_or_else(|| anyhow!("{version}.json has no commit"))?;
                if file_commit != *commit {
                    bail!(
                        "Committed {version}.json was built from {file_commit}, but SNAPSHOTS \
                         lists {commit}; run with --rebuild-all"
                    );
                }
                let new = data
                    .get("new")
                    .and_then(|v| v.as_object())
                    .ok_or_else(|| anyhow!("{version}.json has no \"new\" object"))?;
                for (domain_name, keys) in new {
                    let idx = domain_index(domain_name)?;
                    let keys = keys
                        .as_array()
                        .ok_or_else(|| anyhow!("{domain_name} ids in {version}.json not a list"))?;
                    for key in keys {
                        let key = match key {
                            Value::Number(n) => {
                                Key::Int(n.as_i64().ok_or_else(|| anyhow!("bad id"))?)
                            }
                            Value::String(s) => Key::Str(s.clone()),
                            other => bail!("bad source id {other:?}"),
                        };
                        seen[idx].insert(key);
                    }
                }
                eprintln!("{version}: kept existing delta");
            }
            Some(present) => {
                let new: DomainSets = present
                    .iter()
                    .zip(seen.iter())
                    .map(|(p, s)| p.difference(s).cloned().collect())
                    .collect();
                for (s, p) in seen.iter_mut().zip(present) {
                    s.extend(p);
                }
                let total = write_delta(&path, version, commit, &new)?;
                let breakdown: Vec<String> = DOMAINS
                    .iter()
                    .enumerate()
                    .filter(|(idx, _)| !new[*idx].is_empty())
                    .map(|(idx, d)| format!("{d}={}", new[idx].len()))
                    .collect();
                eprintln!(
                    "{version}: wrote {total} new ids ({})",
                    breakdown.join(", ")
                );
            }
        }
    }
    Ok(())
}
