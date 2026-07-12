//! Port of `scripts/agd_tools.py generate-all`: the 19 renderable passes,
//! manifest/hierarchy writes, and stats/agd/* diagnostics.
//!
//! The `agd_*` category strings passed to the passes here (and in the
//! renderables) must be members of the Python `TextCategory` enum in
//! `istaroth/text/types.py` — the readers reject unknown categories.

use crate::issues::Scope;
use crate::lang::Language;
use crate::renderables::{
    achievement, activity, anecdote, artifact, blossom, book, character, creature, hangout,
    material, quest, readable, subtitle, talk, talk_group, weapon,
};
use crate::rendered_item::{RenderedItem, TextMetadata};
use crate::repo::Repo;
use crate::{hierarchy, stats};
use anyhow::{Context, Result, bail};
use rayon::prelude::*;
use rustc_hash::FxHashSet;
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
    /// Per-pass summary rows in run order.
    summary: Vec<stats::PassSummary>,
    /// Pre-formatted "⚠ type: key -> ISSUE: detail" lines in submission order.
    issue_lines: Vec<String>,
    errors_file: std::fs::File,
}

#[allow(clippy::too_many_arguments)]
fn run_pass<K: Sync>(
    state: &mut RunState,
    output_dir: &Path,
    pass_name: &str,
    category: &'static str,
    error_limit: usize,
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
                if errors > error_limit {
                    writeln!(
                        state.errors_file,
                        "Error limit exceeded ({errors} > {error_limit}), stopping generation"
                    )?;
                    bail!(
                        "{pass_name} generation exceeded error limit ({errors} > {error_limit}); {e:#}"
                    );
                }
                // A failed item's accesses and issues are dropped, so a
                // half-parsed item can't skew cross-pass exclusion or stats.
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
    state.summary.push(stats::PassSummary {
        category,
        success,
        errors,
        skipped,
        issues,
    });
    eprintln!(
        "{pass_name}: {success} success, {skipped} skipped ({:.2}s)",
        t0.elapsed().as_secs_f64()
    );
    Ok(())
}

/// Error on duplicate manifest (category, id) keys before writing the manifest.
fn check_manifest_unique(manifest: &[TextMetadata]) -> Result<()> {
    let mut seen: FxHashSet<(&str, i64)> = FxHashSet::default();
    for item in manifest {
        if !seen.insert((item.category, item.id)) {
            bail!(
                "Duplicate manifest (category, id) keys: ({}, {})",
                item.category,
                item.id
            );
        }
    }
    Ok(())
}

/// Run the full generation. Exits the process directly to skip freeing the
/// huge shared caches.
#[allow(clippy::too_many_arguments)]
pub fn generate_all(
    agd_path: &Path,
    first_seen_dir: &Path,
    output_dir: &Path,
    language: Language,
    force: bool,
    verbose: bool,
    allow_errors: bool,
) -> Result<()> {
    let t_start = Instant::now();
    // The load scope collects text-map accesses made building derived
    // mappings; folded into usage stats after all passes so it never affects
    // the passes' cross-pass exclusion sets.
    let load_scope = Scope::default();
    let repo = Repo::load(agd_path, first_seen_dir, language, verbose, &load_scope)?;
    // Each renderable module declares its (CHS, non-CHS) ERROR_LIMITS pair
    // alongside discover/process; pick the run language's side.
    let error_limit = |(chs, non_chs): (usize, usize)| -> usize {
        if language == Language::Chs {
            chs
        } else {
            non_chs
        }
    };
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

    // metadata.json (git provenance) is written before generation so even a
    // failed run records what it ran against.
    {
        let metadata_path = stats_dir.join("metadata.json");
        std::fs::write(
            &metadata_path,
            serde_json::to_vec_pretty(&stats::generate_metadata(
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
    let artifact_set_ids = artifact::discover(&repo)?;
    let artifact_indexes = artifact::build_indexes(&repo)?;
    run_pass(
        &mut state,
        output_dir,
        "ArtifactSets",
        "agd_artifact_set",
        error_limit(artifact::ERROR_LIMITS),
        &artifact_set_ids,
        |k| k.to_string(),
        |&set_id, scope| artifact::process(&repo, &artifact_indexes, scope, set_id),
    )?;

    // 2. Creatures.
    let creature_subtypes = creature::discover(&repo)?;
    run_pass(
        &mut state,
        output_dir,
        "Creatures",
        "agd_creature",
        error_limit(creature::ERROR_LIMITS),
        &creature_subtypes,
        |k| k.clone(),
        |subtype, scope| creature::process(&repo, scope, subtype),
    )?;

    // 3. Quests.
    let quest_ids = quest::discover(&repo)?;
    run_pass(
        &mut state,
        output_dir,
        "Quests",
        "agd_quest",
        error_limit(quest::ERROR_LIMITS),
        &quest_ids,
        |k| k.to_string(),
        |&quest_id, scope| quest::process(&repo, scope, quest_id),
    )?;

    // 4. CharacterStories.
    let story_avatar_ids = character::discover_stories(&repo)?;
    run_pass(
        &mut state,
        output_dir,
        "CharacterStories",
        "agd_character_story",
        error_limit(character::STORY_ERROR_LIMITS),
        &story_avatar_ids,
        |k| k.to_string(),
        |&avatar_id, scope| character::process_story(&repo, scope, avatar_id),
    )?;

    // 5. Subtitles.
    let subtitle_paths = subtitle::discover(&repo)?;
    run_pass(
        &mut state,
        output_dir,
        "Subtitles",
        "agd_subtitle",
        error_limit(subtitle::ERROR_LIMITS),
        &subtitle_paths,
        |k| k.clone(),
        |path, scope| subtitle::process(&repo, scope, path),
    )?;

    // 6. MaterialTypes.
    let material_types = material::discover(&repo)?;
    run_pass(
        &mut state,
        output_dir,
        "MaterialTypes",
        "agd_material_type",
        error_limit(material::ERROR_LIMITS),
        &material_types,
        |k| k.clone(),
        |material_type, scope| material::process(&repo, scope, material_type),
    )?;

    // 7. Achievements (sections in configured display order).
    let achievement_section_ids = achievement::discover(&repo)?;
    run_pass(
        &mut state,
        output_dir,
        "Achievements",
        "agd_achievement",
        error_limit(achievement::ERROR_LIMITS),
        &achievement_section_ids,
        |k| k.to_string(),
        |&section_id, scope| achievement::process(&repo, scope, section_id),
    )?;

    // 8. Voicelines.
    let voiceline_avatar_ids = character::discover_voicelines(&repo)?;
    run_pass(
        &mut state,
        output_dir,
        "Voicelines",
        "agd_voiceline",
        error_limit(character::VOICELINE_ERROR_LIMITS),
        &voiceline_avatar_ids,
        |k| k.to_string(),
        |&avatar_id, scope| character::process_voiceline(&repo, scope, avatar_id),
    )?;

    // 9. TalkGroups.
    let talk_group_keys = talk_group::discover(&repo)?;
    run_pass(
        &mut state,
        output_dir,
        "TalkGroups",
        "agd_talk_group",
        error_limit(talk_group::ERROR_LIMITS),
        &talk_group_keys,
        |k| format!("('{}', '{}')", k.0.name(), k.1),
        |&(group_type, ref group_id), scope| {
            talk_group::process(&repo, scope, group_type, group_id)
        },
    )?;

    // 10. Hangouts.
    let hangout_quest_ids = hangout::discover(&repo)?;
    run_pass(
        &mut state,
        output_dir,
        "Hangouts",
        "agd_hangout",
        error_limit(hangout::ERROR_LIMITS),
        &hangout_quest_ids,
        |k| k.to_string(),
        |&quest_id, scope| hangout::process(&repo, scope, quest_id),
    )?;

    // 11. Anecdotes.
    let anecdote_ids = anecdote::discover(&repo)?;
    run_pass(
        &mut state,
        output_dir,
        "Anecdotes",
        "agd_anecdote",
        error_limit(anecdote::ERROR_LIMITS),
        &anecdote_ids,
        |k| k.to_string(),
        |&anecdote_id, scope| anecdote::process(&repo, scope, anecdote_id),
    )?;

    // 12. Blossoms.
    let blossom_cities = blossom::discover(&repo)?;
    run_pass(
        &mut state,
        output_dir,
        "Blossoms",
        "agd_blossom",
        error_limit(blossom::ERROR_LIMITS),
        &blossom_cities,
        |k| k.to_string(),
        |&city_id, scope| blossom::process(&repo, scope, city_id),
    )?;

    // 13. Activities (used talk ids snapshot at pass creation).
    let activity_talks = activity::discover(&repo, &state.used_talks)?;
    let mut activity_ids: Vec<i64> = activity_talks.keys().copied().collect();
    activity_ids.sort();
    run_pass(
        &mut state,
        output_dir,
        "Activities",
        "agd_activity",
        error_limit(activity::ERROR_LIMITS),
        &activity_ids,
        |k| k.to_string(),
        |&activity_id, scope| activity::process(&repo, scope, &activity_talks, activity_id),
    )?;

    // 14. Books: series then standalone.
    let book_keys = book::discover(&repo)?;
    run_pass(
        &mut state,
        output_dir,
        "Books",
        "agd_book",
        error_limit(book::ERROR_LIMITS),
        &book_keys,
        book::BookKey::desc,
        |key, scope| book::process(&repo, scope, key),
    )?;

    // 15. Weapons.
    let weapon_ids = weapon::discover(&repo)?;
    run_pass(
        &mut state,
        output_dir,
        "Weapons",
        "agd_weapon",
        error_limit(weapon::ERROR_LIMITS),
        &weapon_ids,
        |k| k.to_string(),
        |&weapon_id, scope| weapon::process(&repo, scope, weapon_id),
    )?;

    // 16./17. Wings and Costumes.
    for (pass_name, prefix, category) in [
        ("Wings", "Wings", "agd_wings"),
        ("Costumes", "Costume", "agd_costume"),
    ] {
        let filenames = readable::discover_prefixed(&repo, prefix)?;
        let category: &'static str = category;
        run_pass(
            &mut state,
            output_dir,
            pass_name,
            category,
            error_limit(readable::ERROR_LIMITS),
            &filenames,
            |k| k.clone(),
            |filename, scope| readable::process(&repo, scope, filename, category),
        )?;
    }

    // 18. Readables (leftovers).
    let used_readables_snapshot = state.used_readables.clone();
    let readable_keys = readable::discover_leftover(&repo, &used_readables_snapshot)?;
    run_pass(
        &mut state,
        output_dir,
        "Readables",
        "agd_readable",
        error_limit(readable::ERROR_LIMITS),
        &readable_keys,
        |k| k.clone(),
        |filename, scope| readable::process(&repo, scope, filename, "agd_readable"),
    )?;

    // 19. Talks (leftovers; success_limit 50).
    let talks_used_snapshot = state.used_talks.clone();
    let talk_keys = talk::discover(&repo, &talks_used_snapshot)?;
    let talks_before = state.manifest.len();
    run_pass(
        &mut state,
        output_dir,
        "Talks",
        "agd_talk",
        error_limit(talk::ERROR_LIMITS),
        &talk_keys,
        |k| k.to_string(),
        |&talk_id, scope| talk::process(&repo, scope, talk_id),
    )?;
    if state.manifest.len() - talks_before >= 50 {
        bail!("Talks pass rendered >= 50 items; loose-content sanity bound exceeded");
    }

    // Parent-scope (load-time) text-map accesses fold in only after all
    // passes; folding earlier would let load-time accesses mask per-pass ones
    // in the unused stats.
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
            text_map: stats::ResourceUsage {
                unused: repo.tm.unused_current_ids(&state.accessed_text_map),
                total: repo.tm.text_map_len(),
            },
            talk_ids: {
                let mut v: Vec<i64> = repo
                    .talk_ids_all
                    .iter()
                    .filter(|id| !state.used_talks.contains(id))
                    .copied()
                    .collect();
                v.sort();
                stats::ResourceUsage {
                    unused: v,
                    total: repo.talk_ids_all.len(),
                }
            },
            readables: {
                let mut v: Vec<String> = repo
                    .readable_contents
                    .keys()
                    .filter(|f| !state.used_readables.contains(*f))
                    .cloned()
                    .collect();
                v.sort();
                stats::ResourceUsage {
                    unused: v,
                    total: repo.readable_contents.len(),
                }
            },
        };
        unused_stats.echo();
        let unused_stats_path = stats_dir.join("unused_stats.json");
        std::fs::write(
            &unused_stats_path,
            serde_json::to_vec_pretty(&unused_stats.to_json())?,
        )?;
        eprintln!(
            "Text map usage stats written to {}",
            unused_stats_path.display()
        );
    }

    // Parsing-issue counts (JSON) and detail list (info).
    {
        let mut counts = serde_json::Map::new();
        for row in &state.summary {
            counts.insert(
                row.category.to_string(),
                serde_json::Value::from(row.issues as i64),
            );
        }
        let parsing_issues_path = stats_dir.join("parsing_issues.json");
        std::fs::write(
            &parsing_issues_path,
            serde_json::to_vec_pretty(&serde_json::Value::Object(counts))?,
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
        check_manifest_unique(&state.manifest)?;
        let manifest_dir = output_dir.join("manifest");
        std::fs::create_dir_all(&manifest_dir)?;
        let manifest_path = manifest_dir.join("agd.json");
        std::fs::write(&manifest_path, serde_json::to_vec_pretty(&state.manifest)?)?;
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
        let hierarchies = hierarchy::Hierarchies {
            agd_quest: hierarchy::build_quest_hierarchy(&repo, &quest_items)?,
            agd_hangout: hierarchy::build_coop_hierarchy(&repo, &coop_items)?,
        };
        let metadata_dir = output_dir.join("metadata").join("agd");
        std::fs::create_dir_all(&metadata_dir)?;
        let hierarchy_path = metadata_dir.join("hierarchy.json");
        std::fs::write(&hierarchy_path, serde_json::to_vec_pretty(&hierarchies)?)?;
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
    // Exit without unwinding: freeing the huge shared caches wastes seconds.
    let code = if state.errors > 0 && !allow_errors {
        1
    } else {
        0
    };
    if code != 0 {
        eprintln!("Some items failed to generate; pass --allow-errors to exit 0 anyway.");
    }
    std::io::Write::flush(&mut std::io::stderr()).ok();
    std::process::exit(code);
}

#[cfg(test)]
mod tests {
    use super::*;

    fn item(category: &'static str, id: i64) -> TextMetadata {
        TextMetadata {
            category,
            title: format!("Item {id}"),
            id,
            relative_path: format!("{category}/{id}.txt"),
            min_version: "1.4".to_string(),
            max_version: "1.4".to_string(),
        }
    }

    #[test]
    fn manifest_rejects_duplicate_category_id() {
        // The same id under different categories is fine; a repeat within one
        // category (e.g. an ActivityGroup/NpcGroup id collision, issue #294)
        // must fail the run before the manifest is written.
        check_manifest_unique(&[
            item("agd_talk_group", 2001),
            item("agd_talk", 2001),
            item("agd_talk_group", 2002),
        ])
        .unwrap();

        let err =
            check_manifest_unique(&[item("agd_talk_group", 2001), item("agd_talk_group", 2001)])
                .unwrap_err();
        assert!(
            err.to_string()
                .contains("Duplicate manifest (category, id) keys: (agd_talk_group, 2001)")
        );
    }
}
