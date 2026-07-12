//! Shared git subprocess helpers.

use anyhow::{Context, Result, bail};
use std::path::Path;
use std::process::Command;

/// Run `git <args>` in `repo_path` and return stdout (errors on failure).
pub fn git_output(repo_path: &Path, args: &[&str]) -> Result<String> {
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

/// `git show REF:PATH` file bytes, or None when the blob doesn't exist.
pub fn git_show(repo_path: &Path, git_ref: &str, path: &str) -> Result<Option<Vec<u8>>> {
    let out = Command::new("git")
        .arg("-C")
        .arg(repo_path)
        .arg("show")
        .arg(format!("{git_ref}:{path}"))
        .output()?;
    if out.status.success() {
        Ok(Some(out.stdout))
    } else {
        Ok(None)
    }
}

/// `git ls-tree --name-only REF dir/` file names (empty for a missing dir).
pub fn git_ls_tree(repo_path: &Path, git_ref: &str, dir: &str) -> Result<Vec<String>> {
    let out = Command::new("git")
        .arg("-C")
        .arg(repo_path)
        .arg("ls-tree")
        .arg("--name-only")
        .arg(git_ref)
        .arg(format!("{dir}/"))
        .output()?;
    if !out.status.success() {
        bail!(
            "git ls-tree {git_ref} {dir} failed: {}",
            String::from_utf8_lossy(&out.stderr).trim()
        );
    }
    let mut names: Vec<String> = String::from_utf8(out.stdout)?
        .lines()
        .filter(|l| !l.is_empty())
        .map(|l| l.rsplit('/').next().unwrap().to_string())
        .collect();
    names.sort();
    Ok(names)
}
