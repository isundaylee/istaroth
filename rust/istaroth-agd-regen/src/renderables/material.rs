//! Port of renderables/material.py.

use crate::firstseen::Domain;
use crate::issues::{IssueType, Scope};
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::ValueExt;
use anyhow::Result;
use rustc_hash::FxHashSet;

/// MaterialTypes pass discovery: sorted distinct materialType values.
pub fn discover(repo: &Repo) -> Result<Vec<String>> {
    let mut types: FxHashSet<String> = FxHashSet::default();
    for material in repo.excel.material.values() {
        types.insert(material.s("materialType")?.to_string());
    }
    let mut v: Vec<String> = types.into_iter().collect();
    v.sort();
    Ok(v)
}

/// MaterialTypes: all same-type materials into one file.
pub fn process(repo: &Repo, scope: &Scope, material_type: &str) -> Result<Option<RenderedItem>> {
    struct MaterialInfo {
        material_id: i64,
        name: String,
        description: String,
    }
    let mut materials: Vec<MaterialInfo> = Vec::new();
    for material in repo.excel.material.values() {
        if material.s("materialType")? != material_type {
            continue;
        }
        let material_id = material.i("id")?;
        let name_hash = material.i("nameTextMapHash")?;
        let name = match repo.tm.get_optional(name_hash, scope)? {
            Some(name) => name,
            None => {
                scope.record_issue(IssueType::MissingMaterialName, name_hash.to_string());
                "Unknown Material".to_string()
            }
        };
        let desc_hash = material.i("descTextMapHash")?;
        let description = match repo.tm.get_optional(desc_hash, scope)? {
            Some(desc) => desc,
            None => {
                scope.record_issue(IssueType::MissingMaterialDesc, desc_hash.to_string());
                "No description available".to_string()
            }
        };
        if util::should_skip_text(&name, repo.language)
            || util::should_skip_text(&description, repo.language)
        {
            continue;
        }
        materials.push(MaterialInfo {
            material_id,
            name,
            description,
        });
    }
    if materials.is_empty() {
        return Ok(None);
    }

    let material_type_id = util::sha256_id(material_type);
    let safe_type = util::make_safe_filename_part(material_type);
    let material_type_name = util::py_title_case(
        &material_type
            .strip_prefix("MATERIAL_")
            .unwrap_or(material_type)
            .replace('_', " "),
    );
    let mut content_lines = vec![format!("# Materials: {material_type_name}\n")];
    materials.sort_by_key(|m| m.material_id);
    for m in &materials {
        content_lines.push(format!("## {}", m.name));
        content_lines.push(String::new());
        content_lines.push(m.description.clone());
        content_lines.push(String::new());
    }
    let content = util::py_rstrip(&content_lines.join("\n")).to_string();
    let versions = repo
        .first_seen
        .resolve_ints(Domain::Material, materials.iter().map(|m| m.material_id))?;
    Ok(Some(RenderedItem::new(
        "agd_material_type",
        material_type_name,
        material_type_id,
        format!("{material_type_id}_{safe_type}.txt"),
        versions,
        content,
    )))
}
