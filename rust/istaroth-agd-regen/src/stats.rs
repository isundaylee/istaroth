//! Run diagnostics under stats/agd/: git-provenance metadata, the per-type
//! summary table, and unused-id statistics.

use anyhow::{Context, Result, bail};
use std::path::Path;
use std::process::Command;

fn git_output(repo_path: &Path, args: &[&str]) -> Result<String> {
    let out = Command::new("git")
        .args(args)
        .current_dir(repo_path)
        .output()
        .with_context(|| format!("git {args:?} in {repo_path:?}"))?;
    if !out.status.success() {
        bail!(
            "git {args:?} failed in {repo_path:?}: {}",
            String::from_utf8_lossy(&out.stderr).trim()
        );
    }
    Ok(String::from_utf8(out.stdout)?)
}

/// Port of `_generate_metadata`: language + AGD/istaroth git provenance.
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

/// Python `"{:^w}"` centering (tabulate's padboth): extra pad goes right.
fn py_center(s: &str, width: usize) -> String {
    let len = s.chars().count();
    if len >= width {
        return s.to_string();
    }
    let left = (width - len) / 2;
    format!("{}{s}{}", " ".repeat(left), " ".repeat(width - len - left))
}

/// Port of `tabulate(..., tablefmt="pretty")` over the per-type summary rows.
pub fn render_summary_table(summary: &[(&'static str, usize, usize, usize, usize)]) -> String {
    const HEADERS: [&str; 5] = ["Content Type", "Success", "Errors", "Skipped", "Issues"];
    let mut rows: Vec<[String; 5]> = summary
        .iter()
        .map(|(category, success, errors, skipped, issues)| {
            [
                category.to_string(),
                success.to_string(),
                errors.to_string(),
                skipped.to_string(),
                issues.to_string(),
            ]
        })
        .collect();
    let totals = summary.iter().fold([0usize; 4], |mut acc, row| {
        acc[0] += row.1;
        acc[1] += row.2;
        acc[2] += row.3;
        acc[3] += row.4;
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
            s.push_str(&py_center(cell, widths[i]));
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

/// Unused/total per tracked resource, plus the sorted unused-id lists.
pub struct UnusedStats {
    pub text_map: (Vec<i64>, usize),
    pub talk_ids: (Vec<i64>, usize),
    pub readables: (Vec<String>, usize),
}

impl UnusedStats {
    /// Console lines mirroring Python's `format_unused_stats` echoes.
    pub fn echo(&self) {
        for (label, unused, total) in [
            ("Text map", self.text_map.0.len(), self.text_map.1),
            ("Talk IDs", self.talk_ids.0.len(), self.talk_ids.1),
            ("Readables", self.readables.0.len(), self.readables.1),
        ] {
            let percentage = if total > 0 {
                unused as f64 / total as f64 * 100.0
            } else {
                0.0
            };
            eprintln!("{label}: {unused} / {total} ({percentage:.1}%) unused");
        }
    }

    /// Port of TrackerStats.format_stats (stats + unused_ids sections).
    pub fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "stats": {
                "text_map": {"unused": self.text_map.0.len(), "total": self.text_map.1},
                "talk_ids": {"unused": self.talk_ids.0.len(), "total": self.talk_ids.1},
                "readables": {"unused": self.readables.0.len(), "total": self.readables.1},
            },
            "unused_ids": {
                "text_map": self.text_map.0,
                "talk_ids": self.talk_ids.0,
                "readables": self.readables.0,
            },
        })
    }
}
