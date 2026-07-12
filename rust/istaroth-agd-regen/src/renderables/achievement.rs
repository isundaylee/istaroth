//! Port of renderables/achievement.py.

use crate::firstseen::Domain;
use crate::issues::Scope;
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::ValueExt;
use anyhow::{Result, anyhow};

/// (CHS, non-CHS) per-pass error limits (see e.g. `artifact::ERROR_LIMITS`).
pub const ERROR_LIMITS: (usize, usize) = (0, 0);

/// Achievements pass discovery: sections in configured display order.
pub fn discover(repo: &Repo) -> Result<Vec<i64>> {
    let mut sections: Vec<(i64, i64)> = repo
        .achievement_sections
        .values()
        .map(|(section, _)| Ok((section.i("orderId")?, section.i("id")?)))
        .collect::<Result<_>>()?;
    sections.sort();
    Ok(sections.into_iter().map(|(_, id)| id).collect())
}

/// Achievements: one section per file.
pub fn process(repo: &Repo, scope: &Scope, section_id: i64) -> Result<Option<RenderedItem>> {
    let (section, achievement_configs) = repo
        .achievement_sections
        .get(&section_id)
        .ok_or_else(|| anyhow!("Achievement section not found for ID {section_id}"))?;
    let section_name = repo.tm.get_required(section.i("nameTextMapHash")?, scope)?;

    struct AchievementInfo {
        id: i64,
        name: String,
        description: String,
    }
    let achievements: Vec<AchievementInfo> = achievement_configs
        .iter()
        .map(|a| {
            Ok(AchievementInfo {
                id: a.i("id")?,
                name: repo.tm.get_required(a.i("titleTextMapHash")?, scope)?,
                description: repo.tm.get_required(a.i("descTextMapHash")?, scope)?,
            })
        })
        .collect::<Result<_>>()?;

    let filename = format!(
        "{section_id}_{}.txt",
        util::make_safe_filename_part(&section_name)
    );
    let mut content_lines = vec![format!("# {section_name}"), String::new()];
    for a in &achievements {
        content_lines.extend([
            format!("## {}", a.name),
            String::new(),
            a.description.clone(),
            String::new(),
        ]);
    }
    let versions = repo
        .first_seen
        .resolve_ints(Domain::Achievement, achievements.iter().map(|a| a.id))?;
    Ok(Some(RenderedItem::new(
        "agd_achievement",
        section_name,
        section_id,
        filename,
        versions,
        content_lines.join("\n").trim_end().to_string(),
    )))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::lang::Language;
    use crate::textmap::TextMaps;
    use rustc_hash::FxHashMap;
    use serde_json::json;

    #[test]
    fn active_achievement_requires_localized_text() {
        let repo = Repo {
            tm: TextMaps::for_tests(
                Language::Chs,
                [(10, "Section".to_string()), (20, "Achievement".to_string())]
                    .into_iter()
                    .collect(),
                FxHashMap::default(),
                FxHashMap::default(),
            ),
            achievement_sections: [(
                7,
                (
                    json!({"nameTextMapHash": 10}),
                    vec![json!({"id": 1, "titleTextMapHash": 20, "descTextMapHash": 30})],
                ),
            )]
            .into_iter()
            .collect(),
            ..Default::default()
        };
        let Err(error) = process(&repo, &Scope::default(), 7) else {
            panic!("expected missing text error")
        };
        assert!(error.to_string().contains("Unresolvable text map hash 30"));
    }
}
