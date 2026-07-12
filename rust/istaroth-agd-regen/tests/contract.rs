//! Byte-exact contract tests for the JSON schemas the Python readers rely on.
//!
//! The fixtures under `tests/fixtures/rust_agd_regen_contract/` (repo root) are shared with
//! the Python half (`tests/test_schema_contract.py`): this side pins the
//! writer's serialization, that side pins the readers' round-trip. Either
//! side drifting breaks its own CI until the fixture is updated consciously.

use istaroth_agd_regen::hierarchy::{Hierarchies, Hierarchy, HierarchyNode};
use istaroth_agd_regen::rendered_item::RenderedItem;
use std::path::PathBuf;

/// The manifest/hierarchy write sites in `generate.rs` serialize with
/// `serde_json::to_vec_pretty`; mirror that here so the fixture pins the
/// exact bytes they produce.
fn dumps_indented<T: serde::Serialize>(value: &T) -> Vec<u8> {
    serde_json::to_vec_pretty(value).unwrap()
}

fn fixture(name: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../tests/fixtures/rust_agd_regen_contract")
        .join(name);
    String::from_utf8(std::fs::read(&path).unwrap()).unwrap()
}

fn leaf(quest_id: i64, title: &str) -> HierarchyNode {
    HierarchyNode {
        key: format!("q{quest_id}"),
        title: Some(title.to_string()),
        children: None,
        file_id: Some(quest_id),
        toc_eligible: false,
    }
}

fn group(
    key: &str,
    title: Option<&str>,
    children: Vec<HierarchyNode>,
    toc_eligible: bool,
) -> HierarchyNode {
    HierarchyNode {
        key: key.to_string(),
        title: title.map(str::to_string),
        children: Some(children),
        file_id: None,
        toc_eligible,
    }
}

#[test]
fn manifest_fixture_byte_exact() {
    // Through RenderedItem::new so the relative_path construction is pinned too.
    let manifest = vec![
        RenderedItem::new(
            "agd_quest",
            "溪舟的尾波".to_string(),
            74078,
            "74078_溪舟的尾波.txt".to_string(),
            ("4.1".to_string(), "4.2".to_string()),
            String::new(),
        )
        .meta,
        RenderedItem::new(
            "agd_talk_group",
            "Ruins Inscription".to_string(),
            1255,
            "1255_NpcGroup.txt".to_string(),
            ("1.0".to_string(), "1.0".to_string()),
            String::new(),
        )
        .meta,
    ];
    assert_eq!(
        String::from_utf8(dumps_indented(&manifest)).unwrap(),
        fixture("manifest.json")
    );
}

#[test]
fn hierarchy_fixture_byte_exact() {
    let hierarchies = Hierarchies {
        agd_quest: Hierarchy {
            nodes: vec![group(
                "AQ",
                Some("魔神任务"),
                vec![
                    group(
                        "s1",
                        None,
                        vec![group(
                            "c1001",
                            Some("第一章"),
                            vec![leaf(74078, "溪舟的尾波")],
                            true,
                        )],
                        true,
                    ),
                    group(
                        "standalone",
                        Some("独立任务"),
                        vec![leaf(12345, "Standalone Quest")],
                        false,
                    ),
                ],
                true,
            )],
        },
        agd_hangout: Hierarchy {
            nodes: vec![group(
                "a10000048",
                Some("烟绯"),
                vec![leaf(19017, "郊野觅芳踪")],
                true,
            )],
        },
    };
    assert_eq!(
        String::from_utf8(dumps_indented(&hierarchies)).unwrap(),
        fixture("hierarchy.json")
    );
}
