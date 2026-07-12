//! Run diagnostics under stats/agd/: git-provenance metadata, the per-type
//! summary table, and unused-id statistics.

use crate::git::git_output;
use anyhow::Result;
use std::path::Path;

/// metadata.json payload: language + AGD/istaroth git provenance.
pub fn generate_metadata(
    agd_path: &Path,
    istaroth_path: &Path,
    language: crate::lang::Language,
) -> Result<serde_json::Value> {
    let commit = |p: &Path| -> Result<String> {
        Ok(git_output(p, &["rev-parse", "HEAD"])?.trim().to_string())
    };
    let dirty = !git_output(
        istaroth_path,
        &["status", "--porcelain", "--ignore-submodules"],
    )?
    .trim()
    .is_empty();
    Ok(serde_json::json!({
        "language": language.value(),
        "agd_git_commit": commit(agd_path)?,
        "istaroth_git_commit": commit(istaroth_path)?,
        "istaroth_git_dirty": dirty,
    }))
}

/// One pass's summary-table row.
pub struct PassSummary {
    pub category: &'static str,
    pub success: usize,
    pub errors: usize,
    pub skipped: usize,
    pub issues: usize,
}

/// Left-aligned ASCII table over the per-type summary rows plus a TOTAL row.
pub fn render_summary_table(summary: &[PassSummary]) -> String {
    const HEADERS: [&str; 5] = ["Content Type", "Success", "Errors", "Skipped", "Issues"];
    let mut rows: Vec<[String; 5]> = summary
        .iter()
        .map(|row| {
            [
                row.category.to_string(),
                row.success.to_string(),
                row.errors.to_string(),
                row.skipped.to_string(),
                row.issues.to_string(),
            ]
        })
        .collect();
    let totals = summary.iter().fold([0usize; 4], |mut acc, row| {
        acc[0] += row.success;
        acc[1] += row.errors;
        acc[2] += row.skipped;
        acc[3] += row.issues;
        acc
    });
    rows.push([
        "TOTAL".to_string(),
        totals[0].to_string(),
        totals[1].to_string(),
        totals[2].to_string(),
        totals[3].to_string(),
    ]);

    let mut widths: [usize; 5] = std::array::from_fn(|i| HEADERS[i].chars().count());
    for row in &rows {
        for (i, cell) in row.iter().enumerate() {
            widths[i] = widths[i].max(cell.chars().count());
        }
    }
    let sep: String = {
        let mut s = String::from("+");
        for w in widths {
            s.push_str(&"-".repeat(w + 2));
            s.push('+');
        }
        s
    };
    let render_row = |cells: &[&str; 5]| -> String {
        let mut s = String::from("|");
        for (i, cell) in cells.iter().enumerate() {
            s.push(' ');
            s.push_str(cell);
            s.push_str(&" ".repeat(widths[i] - cell.chars().count()));
            s.push_str(" |");
        }
        s
    };
    let mut lines = vec![sep.clone(), render_row(&HEADERS), sep.clone()];
    for row in &rows {
        lines.push(render_row(&std::array::from_fn(|i| row[i].as_str())));
    }
    lines.push(sep);
    lines.join("\n")
}

/// One tracked resource's sorted unused-id list and total count.
pub struct ResourceUsage<T> {
    pub unused: Vec<T>,
    pub total: usize,
}

/// Unused/total per tracked resource, plus the sorted unused-id lists.
pub struct UnusedStats {
    pub text_map: ResourceUsage<i64>,
    pub talk_ids: ResourceUsage<i64>,
    pub readables: ResourceUsage<String>,
}

impl UnusedStats {
    /// Console summary lines for the unused-id percentages.
    pub fn echo(&self) {
        for (label, unused, total) in [
            ("Text map", self.text_map.unused.len(), self.text_map.total),
            ("Talk IDs", self.talk_ids.unused.len(), self.talk_ids.total),
            (
                "Readables",
                self.readables.unused.len(),
                self.readables.total,
            ),
        ] {
            let percentage = if total > 0 {
                unused as f64 / total as f64 * 100.0
            } else {
                0.0
            };
            eprintln!("{label}: {unused} / {total} ({percentage:.1}%) unused");
        }
    }

    /// unused_stats.json payload (stats + unused_ids sections).
    pub fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "stats": {
                "text_map": {"unused": self.text_map.unused.len(), "total": self.text_map.total},
                "talk_ids": {"unused": self.talk_ids.unused.len(), "total": self.talk_ids.total},
                "readables": {"unused": self.readables.unused.len(), "total": self.readables.total},
            },
            "unused_ids": {
                "text_map": self.text_map.unused,
                "talk_ids": self.talk_ids.unused,
                "readables": self.readables.unused,
            },
        })
    }
}
