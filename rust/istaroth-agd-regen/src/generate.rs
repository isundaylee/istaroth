//! Port of `scripts/agd_tools.py generate-all`: the 19 renderable passes,
//! manifest/hierarchy writes, and stats/agd/* diagnostics.

use crate::lang::Language;
use crate::meta::{RenderedItem, TextMetadata};
use crate::repo::{Repo, Scope};
use crate::vh::ValueExt;
use crate::{firstseen, hierarchy, render_groups, render_misc, render_quest, stats, talk};
use anyhow::{Context, Result, bail};
use rayon::prelude::*;
use rustc_hash::FxHashSet;
use serde::Serialize;
use std::io::Write;
use std::path::Path;
use std::time::Instant;

struct RunState {
    manifest: Vec<TextMetadata>,
    used_paths: FxHashSet<String>,
    used_talks: FxHashSet<i64>,
    used_readables: FxHashSet<String>,
    accessed_text_map: FxHashSet<i64>,
    errors: usize,
    /// Per-pass (category, success, errors, skipped, issues) in run order.
    summary: Vec<(&'static str, usize, usize, usize, usize)>,
    /// Pre-formatted "⚠ type: key -> ISSUE: detail" lines in submission order.
    issue_lines: Vec<String>,
    errors_file: std::fs::File,
}

fn run_pass<K: Sync>(
    state: &mut RunState,
    output_dir: &Path,
    pass_name: &str,
    category: &'static str,
    keys: &[K],
    key_desc: impl Fn(&K) -> String,
    process: impl Fn(&K, &Scope) -> Result<Option<RenderedItem>> + Sync,
) -> Result<()> {
    let t0 = Instant::now();
    if keys.is_empty() {
        bail!("No renderable keys found for {pass_name}");
    }
    let results: Vec<(Result<Option<RenderedItem>>, Scope)> = keys
        .par_iter()
        .map(|key| {
            let scope = Scope::default();
            let result = process(key, &scope);
            (result, scope)
        })
        .collect();

    let mut success = 0usize;
    let mut errors = 0usize;
    let mut skipped = 0usize;
    let mut issues = 0usize;
    let mut items: Vec<RenderedItem> = Vec::new();
    for (i, (result, scope)) in results.into_iter().enumerate() {
        match result {
            Err(e) => {
                state.errors += 1;
                errors += 1;
                let line = format!("✗ {pass_name}: {} -> ERROR: {e:#}", key_desc(&keys[i]));
                eprintln!("{line}");
                writeln!(state.errors_file, "{line}")?;
                // Python drops a failed item's accesses and issues.
            }
            Ok(item) => {
                state.used_talks.extend(scope.talks.into_inner());
                state.used_readables.extend(scope.readables.into_inner());
                state.accessed_text_map.extend(scope.text_map.into_inner());
                let item_issues = scope.issues.into_inner();
                issues += item_issues.len();
                for issue in item_issues {
                    state.issue_lines.push(format!(
                        "⚠ {pass_name}: {} -> {}: {}",
                        key_desc(&keys[i]),
                        issue.issue_type.name(),
                        issue.detail
                    ));
                }
                match item {
                    None => {
                        skipped += 1;
                        writeln!(
                            state.errors_file,
                            "⚠ {pass_name}: {} -> SKIPPED (filtered)",
                            key_desc(&keys[i])
                        )?;
                    }
                    Some(item) => {
                        if !state.used_paths.insert(item.meta.relative_path.clone()) {
                            bail!(
                                "Path collision detected: '{}' for {pass_name}: {}",
                                item.meta.relative_path,
                                key_desc(&keys[i])
                            );
                        }
                        state.manifest.push(item.meta.clone());
                        items.push(item);
                        success += 1;
                    }
                }
            }
        }
    }
    if let Some(first) = items.first() {
        std::fs::create_dir_all(output_dir.join(&first.meta.relative_path).parent().unwrap())?;
    }
    items.par_iter().try_for_each(|item| -> Result<()> {
        let path = output_dir.join(&item.meta.relative_path);
        std::fs::write(&path, item.content.as_bytes())
            .with_context(|| format!("write {path:?}"))?;
        Ok(())
    })?;
    state
        .summary
        .push((category, success, errors, skipped, issues));
    eprintln!(
        "{pass_name}: {success} success, {skipped} skipped ({:.2}s)",
        t0.elapsed().as_secs_f64()
    );
    Ok(())
}

/// Python `json.dumps(obj, ensure_ascii=False, indent=2).encode()`.
fn dumps_indented<T: Serialize>(value: &T) -> Result<Vec<u8>> {
    Ok(serde_json::to_vec_pretty(value)?)
}

/// Run the full generation. Exits the process directly (like the Python
/// pipeline's `os._exit`) to skip freeing the huge shared caches.
pub fn generate_all(
    agd_path: &Path,
    first_seen_dir: &Path,
    output_dir: &Path,
    language: Language,
    force: bool,
    verbose: bool,
) -> Result<()> {
    let t_start = Instant::now();
    // The load scope collects text-map accesses made building derived mappings
    // (Python: the run-level parent scope); folded into usage stats after all
    // passes so it never affects the passes' cross-pass exclusion sets.
    let load_scope = Scope::default();
    let repo = Repo::load(agd_path, first_seen_dir, language, verbose, &load_scope)?;
    eprintln!("Repo loaded in {:.2}s", t_start.elapsed().as_secs_f64());

    // --force cleanup of AGD-owned outputs.
    if force && output_dir.exists() {
        for entry in std::fs::read_dir(output_dir)? {
            let entry = entry?;
            let name = entry.file_name().to_string_lossy().to_string();
            if name.starts_with("agd_") && entry.path().is_dir() {
                std::fs::remove_dir_all(entry.path())?;
            }
        }
        for sub in ["stats/agd", "metadata/agd"] {
            let p = output_dir.join(sub);
            if p.exists() {
                std::fs::remove_dir_all(&p)?;
            }
        }
        let manifest_path = output_dir.join("manifest/agd.json");
        if manifest_path.exists() {
            std::fs::remove_file(&manifest_path)?;
        }
    }
    std::fs::create_dir_all(output_dir)?;

    let stats_dir = output_dir.join("stats").join("agd");
    std::fs::create_dir_all(&stats_dir)?;

    // metadata.json (git provenance) before generation, like Python.
    {
        let metadata_path = stats_dir.join("metadata.json");
        std::fs::write(
            &metadata_path,
            dumps_indented(&stats::generate_metadata(
                agd_path,
                &std::env::current_dir()?,
                language,
            )?)?,
        )?;
        eprintln!("Metadata written to {}", metadata_path.display());
    }

    let errors_file_path = stats_dir.join("errors.info");
    let mut state = RunState {
        manifest: Vec::new(),
        used_paths: FxHashSet::default(),
        used_talks: FxHashSet::default(),
        used_readables: FxHashSet::default(),
        accessed_text_map: FxHashSet::default(),
        errors: 0,
        summary: Vec::new(),
        issue_lines: Vec::new(),
        errors_file: std::fs::File::create(&errors_file_path)?,
    };

    // 1. ArtifactSets (discovery: file order).
    let artifact_set_ids: Vec<i64> = repo
        .reliquary_set
        .iter()
        .map(|s| s.i("setId"))
        .collect::<Result<_>>()?;
    run_pass(
        &mut state,
        output_dir,
        "ArtifactSets",
        "agd_artifact_set",
        &artifact_set_ids,
        |k| k.to_string(),
        |&set_id, scope| render_misc::process_artifact_set(&repo, scope, set_id),
    )?;

    // 2. Creatures.
    let creature_subtypes: Vec<String> = {
        let mut subtypes: FxHashSet<String> = FxHashSet::default();
        for entry in repo.animal_codex.values() {
            if !entry.b("isDisuse")? {
                subtypes.insert(entry.s("subType")?.to_string());
            }
        }
        let mut v: Vec<String> = subtypes.into_iter().collect();
        v.sort();
        v
    };
    run_pass(
        &mut state,
        output_dir,
        "Creatures",
        "agd_creature",
        &creature_subtypes,
        |k| k.clone(),
        |subtype, scope| render_misc::process_creature_group(&repo, scope, subtype),
    )?;

    // 3. Quests (discovery: main quest ids sorted as STRINGS).
    let quest_ids: Vec<i64> = {
        let mut ids: Vec<i64> = repo.main_quest.keys().copied().collect();
        ids.sort_by_key(|id| id.to_string());
        ids
    };
    run_pass(
        &mut state,
        output_dir,
        "Quests",
        "agd_quest",
        &quest_ids,
        |k| k.to_string(),
        |&quest_id, scope| {
            let Some(quest_info) = render_quest::get_quest_info(&repo, scope, quest_id)? else {
                return Ok(None);
            };
            if !quest_info.steps.iter().any(|s| s.talk.is_some())
                && quest_info.non_subquest_talks.is_empty()
            {
                return Ok(None);
            }
            Ok(Some(render_quest::render_quest(&repo, scope, &quest_info)?))
        },
    )?;

    // 4. CharacterStories.
    let story_avatar_ids: Vec<i64> = {
        let mut ids: FxHashSet<i64> = FxHashSet::default();
        for story in &repo.fetter_story {
            if let Some(avatar_id) = story.get_i("avatarId")
                && avatar_id != 0
            {
                ids.insert(avatar_id);
            }
        }
        let mut v: Vec<i64> = ids.into_iter().collect();
        v.sort();
        v
    };
    run_pass(
        &mut state,
        output_dir,
        "CharacterStories",
        "agd_character_story",
        &story_avatar_ids,
        |k| k.to_string(),
        |&avatar_id, scope| render_misc::process_character_story(&repo, scope, avatar_id),
    )?;

    // 5. Subtitles.
    let subtitle_paths: Vec<String> = repo
        .subtitle_names
        .iter()
        .filter(|n| n.ends_with(".srt"))
        .map(|n| format!("Subtitle/{}/{n}", repo.language.short()))
        .collect();
    run_pass(
        &mut state,
        output_dir,
        "Subtitles",
        "agd_subtitle",
        &subtitle_paths,
        |k| k.clone(),
        |path, scope| render_misc::process_subtitle(&repo, scope, path),
    )?;

    // 6. MaterialTypes.
    let material_types: Vec<String> = {
        let mut types: FxHashSet<String> = FxHashSet::default();
        for material in repo.material.values() {
            types.insert(material.s("materialType")?.to_string());
        }
        let mut v: Vec<String> = types.into_iter().collect();
        v.sort();
        v
    };
    run_pass(
        &mut state,
        output_dir,
        "MaterialTypes",
        "agd_material_type",
        &material_types,
        |k| k.clone(),
        |material_type, scope| render_misc::process_material_type(&repo, scope, material_type),
    )?;

    // 7. Achievements (sections in configured display order).
    let achievement_section_ids: Vec<i64> = {
        let mut sections: Vec<(i64, i64)> = repo
            .achievement_sections
            .values()
            .map(|(section, _)| Ok((section.i("orderId")?, section.i("id")?)))
            .collect::<Result<_>>()?;
        sections.sort();
        sections.into_iter().map(|(_, id)| id).collect()
    };
    run_pass(
        &mut state,
        output_dir,
        "Achievements",
        "agd_achievement",
        &achievement_section_ids,
        |k| k.to_string(),
        |&section_id, scope| render_misc::process_achievement_section(&repo, scope, section_id),
    )?;

    // 8. Voicelines.
    let voiceline_avatar_ids: Vec<i64> = {
        let mut ids: FxHashSet<i64> = FxHashSet::default();
        for fetter in &repo.fetters {
            ids.insert(fetter.i("avatarId")?);
        }
        let mut v: Vec<i64> = ids.into_iter().collect();
        v.sort();
        v
    };
    run_pass(
        &mut state,
        output_dir,
        "Voicelines",
        "agd_voiceline",
        &voiceline_avatar_ids,
        |k| k.to_string(),
        |&avatar_id, scope| render_misc::process_voiceline(&repo, scope, avatar_id),
    )?;

    // 9. TalkGroups.
    let talk_group_keys: Vec<(String, String)> = {
        let mut keys: Vec<(String, String)> =
            repo.parse.talk_group_id_to_path.keys().cloned().collect();
        keys.sort();
        keys
    };
    run_pass(
        &mut state,
        output_dir,
        "TalkGroups",
        "agd_talk_group",
        &talk_group_keys,
        |k| format!("('{}', '{}')", k.0, k.1),
        |(group_type, group_id), scope| {
            render_groups::process_talk_group(&repo, scope, group_type, group_id)
        },
    )?;

    // 10. Hangouts.
    let hangout_quest_ids: Vec<i64> = {
        let mut ids: Vec<i64> = repo.hangout_quest_to_stories.keys().copied().collect();
        ids.sort();
        ids
    };
    run_pass(
        &mut state,
        output_dir,
        "Hangouts",
        "agd_hangout",
        &hangout_quest_ids,
        |k| k.to_string(),
        |&quest_id, scope| {
            let Some(info) = render_groups::get_hangout_info(&repo, scope, quest_id)? else {
                return Ok(None);
            };
            Ok(Some(render_groups::render_hangout(&repo, scope, &info)?))
        },
    )?;

    // 11. Anecdotes.
    let anecdote_ids: Vec<i64> = {
        let mut ids: Vec<i64> = repo.anecdote.keys().copied().collect();
        ids.sort();
        ids
    };
    run_pass(
        &mut state,
        output_dir,
        "Anecdotes",
        "agd_anecdote",
        &anecdote_ids,
        |k| k.to_string(),
        |&anecdote_id, scope| render_groups::process_anecdote(&repo, scope, anecdote_id),
    )?;

    // 12. Blossoms.
    let blossom_cities = render_groups::blossom_city_ids(&repo)?;
    run_pass(
        &mut state,
        output_dir,
        "Blossoms",
        "agd_blossom",
        &blossom_cities,
        |k| k.to_string(),
        |&city_id, scope| render_groups::process_blossom_city(&repo, scope, city_id),
    )?;

    // 13. Activities (used talk ids snapshot at pass creation).
    let activities_used_talks = state.used_talks.clone();
    let activity_ids: Vec<i64> = {
        let mut ids: Vec<i64> =
            render_groups::loose_talk_ids_by_activity(&repo, &activities_used_talks)?
                .keys()
                .copied()
                .collect();
        ids.sort();
        ids
    };
    run_pass(
        &mut state,
        output_dir,
        "Activities",
        "agd_activity",
        &activity_ids,
        |k| k.to_string(),
        |&activity_id, scope| {
            render_groups::process_activity(&repo, scope, &activities_used_talks, activity_id)
        },
    )?;

    // 14. Books: series then standalone.
    enum BookKey {
        Series(i64),
        Standalone(String),
    }
    let book_keys: Vec<BookKey> = {
        let grouped: FxHashSet<&String> = repo.book_series.values().flatten().collect();
        let mut series_ids: Vec<i64> = repo.book_series.keys().copied().collect();
        series_ids.sort();
        let mut keys: Vec<BookKey> = series_ids.into_iter().map(BookKey::Series).collect();
        keys.extend(
            repo.readable_filenames_sorted
                .iter()
                .filter(|f| f.starts_with("Book") && !grouped.contains(f))
                .map(|f| BookKey::Standalone(f.clone())),
        );
        keys
    };
    run_pass(
        &mut state,
        output_dir,
        "Books",
        "agd_book",
        &book_keys,
        // Python str() of the NamedTuple keys.
        |k| match k {
            BookKey::Series(id) => format!("_BookSeriesKey(suit_id={id})"),
            BookKey::Standalone(f) => format!("_BookStandaloneKey(filename='{f}')"),
        },
        |key, scope| match key {
            BookKey::Series(suit_id) => render_misc::process_book_series(&repo, scope, *suit_id),
            BookKey::Standalone(filename) => {
                match render_misc::load_readable(&repo, scope, filename)? {
                    None => Ok(None),
                    Some((content, metadata)) => Ok(Some(render_misc::render_readable_like(
                        &repo, &content, &metadata, filename, "agd_book",
                    )?)),
                }
            }
        },
    )?;

    // 15. Weapons (ids sorted as strings).
    let weapon_ids: Vec<String> = {
        let mut ids: Vec<String> = repo.weapon_excel.keys().map(|id| id.to_string()).collect();
        ids.sort();
        ids
    };
    run_pass(
        &mut state,
        output_dir,
        "Weapons",
        "agd_weapon",
        &weapon_ids,
        |k| k.clone(),
        |weapon_id, scope| render_misc::process_weapon(&repo, scope, weapon_id),
    )?;

    // 16./17. Wings and Costumes.
    for (pass_name, prefix, category) in [
        ("Wings", "Wings", "agd_wings"),
        ("Costumes", "Costume", "agd_costume"),
    ] {
        let filenames: Vec<String> = repo
            .readable_filenames_sorted
            .iter()
            .filter(|f| f.starts_with(prefix))
            .cloned()
            .collect();
        let category: &'static str = category;
        run_pass(
            &mut state,
            output_dir,
            pass_name,
            category,
            &filenames,
            |k| k.clone(),
            |filename, scope| match render_misc::load_readable(&repo, scope, filename)? {
                None => Ok(None),
                Some((content, metadata)) => Ok(Some(render_misc::render_readable_like(
                    &repo, &content, &metadata, filename, category,
                )?)),
            },
        )?;
    }

    // 18. Readables (leftovers).
    let used_readables_snapshot = state.used_readables.clone();
    let readable_keys: Vec<String> = repo
        .readable_filenames_sorted
        .iter()
        .filter(|f| !used_readables_snapshot.contains(*f))
        .cloned()
        .collect();
    run_pass(
        &mut state,
        output_dir,
        "Readables",
        "agd_readable",
        &readable_keys,
        |k| k.clone(),
        |filename, scope| match render_misc::load_readable(&repo, scope, filename)? {
            None => Ok(None),
            Some((content, metadata)) => Ok(Some(render_misc::render_readable_like(
                &repo,
                &content,
                &metadata,
                filename,
                "agd_readable",
            )?)),
        },
    )?;

    // 19. Talks (leftovers; success_limit 50).
    let talks_used_snapshot = state.used_talks.clone();
    let talk_keys: Vec<i64> = {
        let mut ids: Vec<i64> = repo
            .talk_ids_all
            .iter()
            .filter(|id| !talks_used_snapshot.contains(id))
            .copied()
            .collect();
        ids.sort();
        ids
    };
    let talks_before = state.manifest.len();
    run_pass(
        &mut state,
        output_dir,
        "Talks",
        "agd_talk",
        &talk_keys,
        |k| k.to_string(),
        |&talk_id, scope| {
            if repo.get_talk_file_path(talk_id, scope).is_none() {
                return Ok(None);
            }
            let talk_info = talk::get_talk_info_by_id(&repo, scope, talk_id)?;
            if talk_info.text.is_empty() {
                return Ok(None);
            }
            let Some(rendered) = talk::render_talk_body(&talk_info, talk_id, scope)? else {
                return Ok(None);
            };
            let versions = repo
                .first_seen
                .resolve_int(firstseen::Domain::Talk, talk_id)?;
            Ok(Some(RenderedItem::new(
                "agd_talk",
                rendered.title,
                talk_id,
                rendered.filename,
                versions,
                rendered.content,
            )))
        },
    )?;
    if state.manifest.len() - talks_before >= 50 {
        bail!("Talks pass rendered >= 50 items; loose-content sanity bound exceeded");
    }

    // Parent-scope (load-time) text-map accesses fold in only after all passes,
    // like Python folds the run-level scope after the pass loop.
    state
        .accessed_text_map
        .extend(load_scope.text_map.into_inner());

    // Summary table (console + stats/agd/summary_table.txt).
    {
        let summary_table = stats::render_summary_table(&state.summary);
        eprintln!("\n{summary_table}");
        let summary_table_path = stats_dir.join("summary_table.txt");
        std::fs::write(&summary_table_path, summary_table.as_bytes())?;
        eprintln!("Summary table written to {}", summary_table_path.display());
    }

    // Unused-id stats (console + stats/agd/unused_stats.json).
    {
        let unused_stats = stats::UnusedStats {
            text_map: (
                repo.tm.unused_current_ids(&state.accessed_text_map),
                repo.tm.text_map_len(),
            ),
            talk_ids: {
                let mut v: Vec<i64> = repo
                    .talk_ids_all
                    .iter()
                    .filter(|id| !state.used_talks.contains(id))
                    .copied()
                    .collect();
                v.sort();
                (v, repo.talk_ids_all.len())
            },
            readables: {
                let mut v: Vec<String> = repo
                    .readable_filenames
                    .iter()
                    .filter(|f| !state.used_readables.contains(*f))
                    .cloned()
                    .collect();
                v.sort();
                (v, repo.readable_filenames.len())
            },
        };
        unused_stats.echo();
        let unused_stats_path = stats_dir.join("unused_stats.json");
        std::fs::write(&unused_stats_path, dumps_indented(&unused_stats.to_json())?)?;
        eprintln!(
            "Text map usage stats written to {}",
            unused_stats_path.display()
        );
    }

    // Parsing-issue counts (JSON) and detail list (info), mirroring Python.
    {
        let mut counts = serde_json::Map::new();
        for (category, _, _, _, issues) in &state.summary {
            counts.insert(
                category.to_string(),
                serde_json::Value::from(*issues as i64),
            );
        }
        let parsing_issues_path = stats_dir.join("parsing_issues.json");
        std::fs::write(
            &parsing_issues_path,
            dumps_indented(&serde_json::Value::Object(counts))?,
        )?;
        eprintln!(
            "Parsing issue counts written to {}",
            parsing_issues_path.display()
        );
        if !state.issue_lines.is_empty() {
            let parsing_issues_info_path = stats_dir.join("parsing_issues.info");
            let mut body = String::new();
            for line in &state.issue_lines {
                body.push_str(line);
                body.push('\n');
            }
            std::fs::write(&parsing_issues_info_path, body.as_bytes())?;
            eprintln!(
                "Detailed parsing issues written to {}",
                parsing_issues_info_path.display()
            );
        }
    }

    // Manifest: duplicate (category, id) check, then write.
    {
        let mut seen: FxHashSet<(&str, i64)> = FxHashSet::default();
        for item in &state.manifest {
            if !seen.insert((item.category, item.id)) {
                bail!(
                    "Duplicate manifest (category, id) keys: ({}, {})",
                    item.category,
                    item.id
                );
            }
        }
        let manifest_dir = output_dir.join("manifest");
        std::fs::create_dir_all(&manifest_dir)?;
        let manifest_path = manifest_dir.join("agd.json");
        std::fs::write(&manifest_path, dumps_indented(&state.manifest)?)?;
        eprintln!("Manifest written to {}", manifest_path.display());
    }

    // Hierarchies.
    {
        let quest_items: Vec<(i64, String)> = state
            .manifest
            .iter()
            .filter(|m| m.category == "agd_quest")
            .map(|m| (m.id, m.title.clone()))
            .collect();
        if quest_items.is_empty() {
            bail!("quest generation produced no quest manifest items");
        }
        let coop_items: Vec<(i64, String)> = state
            .manifest
            .iter()
            .filter(|m| m.category == "agd_hangout")
            .map(|m| (m.id, m.title.clone()))
            .collect();
        if coop_items.is_empty() {
            bail!("hangout generation produced no coop manifest items");
        }
        #[derive(Serialize)]
        struct Hierarchies {
            agd_quest: hierarchy::Hierarchy,
            agd_hangout: hierarchy::Hierarchy,
        }
        let hierarchies = Hierarchies {
            agd_quest: hierarchy::build_quest_hierarchy(&repo, &quest_items)?,
            agd_hangout: hierarchy::build_coop_hierarchy(&repo, &coop_items)?,
        };
        let metadata_dir = output_dir.join("metadata").join("agd");
        std::fs::create_dir_all(&metadata_dir)?;
        let hierarchy_path = metadata_dir.join("hierarchy.json");
        std::fs::write(&hierarchy_path, dumps_indented(&hierarchies)?)?;
        eprintln!("Document hierarchy written to {}", hierarchy_path.display());
    }

    // errors.info survives only when something actually failed.
    state.errors_file.flush()?;
    drop(state.errors_file);
    if state.errors > 0 {
        eprintln!(
            "\nDetailed errors written to {}",
            errors_file_path.display()
        );
    } else if errors_file_path.exists() {
        std::fs::remove_file(&errors_file_path)?;
    }

    eprintln!(
        "Done: {} items, {} errors, total {:.2}s",
        state.manifest.len(),
        state.errors,
        t_start.elapsed().as_secs_f64()
    );
    // Like the Python pipeline's os._exit: skip freeing the huge shared caches.
    let code = if state.errors > 0 { 1 } else { 0 };
    std::io::Write::flush(&mut std::io::stderr()).ok();
    std::process::exit(code);
}
