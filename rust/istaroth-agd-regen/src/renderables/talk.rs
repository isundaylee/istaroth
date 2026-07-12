//! Port of istaroth.agd.renderables._talk: talk info assembly and the shared
//! dialogue graph renderer (including the branch/convergence algorithm).

use crate::firstseen;
use crate::issues::{IssueType, Scope};
use crate::lang::Language;
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::ValueExt;
use anyhow::{Result, anyhow, bail};
use rustc_hash::{FxHashMap, FxHashSet};
use serde_json::Value;

/// (CHS, non-CHS) per-pass error limits (see e.g. `artifact::ERROR_LIMITS`).
pub const ERROR_LIMITS: (usize, usize) = (1000, 1000);

/// Placeholder role for a talk that could not be retrieved; rendered inline as
/// a visible data gap, but never a speaker for title-derivation purposes.
pub const MISSING_TALK_ROLE: &str = "[Missing Talk]";

#[derive(Debug, thiserror::Error)]
#[error("Talk ID {0} not found")]
pub struct TalkNotFound(pub i64);

#[derive(Clone)]
pub struct TalkText {
    pub role: Option<String>,
    pub message: String,
    pub next_dialog_ids: Vec<i64>,
    pub dialog_id: i64,
    pub skip: bool,
}

#[derive(Clone, Default)]
pub struct TalkInfo {
    pub text: Vec<TalkText>,
}

impl TalkInfo {
    pub fn has_non_skip_text(&self) -> bool {
        self.text.iter().any(|t| !t.skip)
    }
}

/// Build TalkInfo from a talk file path.
pub fn get_talk_info(repo: &Repo, scope: &Scope, talk_path: &str) -> Result<TalkInfo> {
    let data = repo
        .talk_files
        .get(talk_path)
        .ok_or_else(|| anyhow!("talk file not loaded: {talk_path}"))?;
    // A missing dialogList and an explicit JSON null both mean "no dialog";
    // anything else present must be a list.
    let dialog_list = match data.get("dialogList") {
        None | Some(Value::Null) => return Ok(TalkInfo::default()),
        Some(v) => v
            .as_array()
            .ok_or_else(|| anyhow!("dialogList must be an array"))?,
    };

    let mut talk_texts = Vec::with_capacity(dialog_list.len());
    for dialog_item in dialog_list {
        let content_hash = dialog_item.i("talkContentTextMapHash")?;
        let next_dialog_ids = match dialog_item.get("nextDialogs") {
            Some(v) => crate::vh::int_array(v)?,
            None => Vec::new(),
        };
        let dialog_id = dialog_item.i("id")?;

        let mut skip = false;
        let message = match repo.tm.get_optional(content_hash, scope)? {
            Some(m) => m,
            None => {
                // An untranslated hash may still be a CHS-only dev/test
                // placeholder (never translated into any language) rather than
                // genuinely missing text; check the source text before
                // flagging it as missing.
                match repo.chs_get_optional(content_hash, scope)? {
                    Some(chs) if util::should_skip_text(&chs, Language::Chs) => {
                        skip = true;
                        chs
                    }
                    _ => {
                        scope.record_issue(IssueType::MissingText, content_hash.to_string());
                        format!("Missing text ({content_hash})")
                    }
                }
            }
        };

        let role = get_role_name(repo, scope, dialog_item, dialog_id)?;
        if !skip {
            skip = role_is_dev(repo, scope, dialog_item, dialog_id)?;
        }
        talk_texts.push(TalkText {
            role,
            message,
            next_dialog_ids,
            dialog_id,
            skip,
        });
    }
    Ok(TalkInfo { text: talk_texts })
}

/// Role-name hash: the dialog's own `talkRoleNameTextMapHash` when nonzero,
/// else the excel dialog-id -> role-hash mapping.
fn role_name_hash(repo: &Repo, dialog_item: &Value, dialog_id: i64) -> Option<i64> {
    match dialog_item.get_i("talkRoleNameTextMapHash") {
        Some(h) if h != 0 => Some(h),
        _ => repo.dialog_id_to_role_hash.get(&dialog_id).copied(),
    }
}

/// NPC id from the role's `_id`/`id` field. Wire role ids ship as strs and
/// occasionally hold non-numeric placeholders (e.g. {QuestNpcID}, PLAYER,
/// empty string); those are unresolvable and fall through to the hash fallback.
fn role_npc_id(talk_role: &Value) -> Result<Option<i64>> {
    let raw = match talk_role.get("_id") {
        Some(v) => Some(v),
        None => talk_role.get("id"),
    };
    let Some(raw) = raw else {
        return Ok(None);
    };
    let Some(s) = raw.as_str() else {
        bail!("non-str talk role id {raw:?}");
    };
    if util::is_ascii_digits(s) {
        Ok(Some(util::parse_i64(s)?))
    } else {
        Ok(None)
    }
}

fn get_role_name(
    repo: &Repo,
    scope: &Scope,
    dialog_item: &Value,
    dialog_id: i64,
) -> Result<Option<String>> {
    let talk_role = dialog_item.f("talkRole")?;
    if !talk_role.is_object() {
        bail!("talkRole must be an object, got {talk_role}");
    }
    let role_type = talk_role.get_s("type");

    let roles = repo.language.role_names();
    let by_role: Option<String> = match role_type {
        Some("TALK_ROLE_NPC") => role_npc_id(talk_role)?
            .and_then(|id| repo.npc_id_to_name.get(&id))
            .cloned(),
        Some("TALK_ROLE_PLAYER") => Some(roles.player.to_string()),
        Some("TALK_ROLE_MATE_AVATAR") => Some(roles.mate_avatar.to_string()),
        Some("TALK_ROLE_NEED_CLICK_BLACK_SCREEN") | Some("TALK_ROLE_BLACK_SCREEN") => {
            Some(roles.black_screen.to_string())
        }
        _ => None,
    };
    let by_name_hash: Option<String> = match role_name_hash(repo, dialog_item, dialog_id) {
        Some(h) => repo.tm.get_current_optional(h, scope)?,
        None => None,
    };

    if let (Some(role), Some(name_hash)) = (&by_role, &by_name_hash) {
        if role == name_hash {
            return Ok(Some(role.clone()));
        }
        let npc_src = if role_type == Some("TALK_ROLE_NPC") {
            role_npc_id(talk_role)?.and_then(|id| repo.npc_chs_name(id))
        } else {
            None
        };
        // Real scene elements are often implemented as dev-named NPC entities
        // fronting a clean per-dialog display name (e.g. (test)阿圆 displaying
        // as 阿圆); render just the display name rather than leaking the
        // internal dev name into the composite.
        if let Some(src) = npc_src
            && util::should_skip_text(src, Language::Chs)
        {
            return Ok(Some(name_hash.clone()));
        }
        return Ok(Some(format!("{role} ({name_hash})")));
    }
    // Prefer the name-hash resolution, but an EMPTY resolved name falls
    // through to the role-derived name (or-chain truthiness).
    let resolved = match by_name_hash {
        Some(s) if !s.is_empty() => Some(s),
        _ => by_role,
    };
    if resolved.is_some() {
        return Ok(resolved);
    }
    // TALK_ROLE_NONE is speaker-less narration / stage directions; render the
    // message with no role prefix.
    if role_type == Some("TALK_ROLE_NONE") {
        return Ok(None);
    }
    scope.record_issue(
        IssueType::UnknownRole,
        format!("dialog {dialog_id} role {}", role_type.unwrap_or("None")),
    );
    Ok(Some(format!(
        "{} ({})",
        roles.unknown_role,
        role_type.unwrap_or("None")
    )))
}

/// Whether the role's effective displayed name is dev/test-marked.
///
/// Judged on the name the player actually sees: the per-dialog role-name hash
/// when it resolves, the NPC's source name otherwise. Dev-named NPC entities
/// regularly deliver real dialogue under a clean display hash (e.g. (test)阿圆
/// displaying as 阿圆 for the Serenitea Pot tutorial), so the backing entity's
/// name alone must not condemn a line.
fn role_is_dev(repo: &Repo, scope: &Scope, dialog_item: &Value, dialog_id: i64) -> Result<bool> {
    if let Some(h) = role_name_hash(repo, dialog_item, dialog_id)
        && let Some(hash_name) = repo.chs_get_current_optional(h, scope)?
    {
        return Ok(util::should_skip_text(&hash_name, Language::Chs));
    }
    let talk_role = dialog_item.f("talkRole")?;
    let src = if talk_role.get_s("type") == Some("TALK_ROLE_NPC") {
        role_npc_id(talk_role)?.and_then(|id| repo.npc_chs_name(id))
    } else {
        None
    };
    Ok(src.is_some_and(|s| util::should_skip_text(s, Language::Chs)))
}

pub fn get_talk_info_by_id(repo: &Repo, scope: &Scope, talk_id: i64) -> Result<TalkInfo> {
    let path = repo
        .get_talk_file_path(talk_id, scope)
        .ok_or(TalkNotFound(talk_id))?;
    get_talk_info(repo, scope, path)
}

/// Resolve a talk pointed at by an authoritative finish condition.
///
/// COMPLETE_TALK / COMPLETE_ANY_TALK name the talk that completes a step, so a
/// not-found talk is a genuine upstream data gap: surface it inline as a
/// visible placeholder rather than dropping the step or failing the whole
/// quest. Any other error (an existing talk that fails to parse) still
/// propagates.
pub fn resolve_authoritative_talk(repo: &Repo, scope: &Scope, talk_id: i64) -> Result<TalkInfo> {
    match get_talk_info_by_id(repo, scope, talk_id) {
        Ok(info) => Ok(info),
        Err(e) if e.is::<TalkNotFound>() => {
            scope.record_issue(IssueType::MissingTalk, talk_id.to_string());
            Ok(TalkInfo {
                text: vec![TalkText {
                    role: Some(MISSING_TALK_ROLE.to_string()),
                    message: format!("Talk {talk_id} could not be retrieved"),
                    next_dialog_ids: vec![],
                    dialog_id: 0,
                    skip: false,
                }],
            })
        }
        Err(e) => Err(e),
    }
}

// --- dialogue graph rendering ---

struct TalkTextGraph<'a> {
    dialog_id_to_text: FxHashMap<i64, &'a TalkText>,
    id_first_seen: Vec<i64>,
    graph: FxHashMap<i64, Vec<i64>>,
    incoming: FxHashMap<i64, i64>,
}

impl<'a> TalkTextGraph<'a> {
    fn new(talk: &'a TalkInfo) -> Self {
        let mut dialog_id_to_text = FxHashMap::default();
        let mut id_first_seen = Vec::new();
        let mut graph: FxHashMap<i64, Vec<i64>> = FxHashMap::default();
        let mut incoming: FxHashMap<i64, i64> = FxHashMap::default();
        for talk_text in &talk.text {
            if dialog_id_to_text
                .insert(talk_text.dialog_id, talk_text)
                .is_none()
            {
                id_first_seen.push(talk_text.dialog_id);
            }
            for &next_id in &talk_text.next_dialog_ids {
                graph.entry(talk_text.dialog_id).or_default().push(next_id);
                *incoming.entry(next_id).or_insert(0) += 1;
            }
        }
        TalkTextGraph {
            dialog_id_to_text,
            id_first_seen,
            graph,
            incoming,
        }
    }

    fn find_entrypoints(&self, talk: &TalkInfo) -> Result<Vec<i64>> {
        let mut entrypoints: Vec<i64> = talk
            .text
            .iter()
            .map(|t| t.dialog_id)
            .collect::<FxHashSet<i64>>()
            .into_iter()
            .filter(|id| self.incoming.get(id).copied().unwrap_or(0) == 0)
            .collect();
        if !entrypoints.is_empty() {
            entrypoints.sort();
            return Ok(entrypoints);
        }
        let cycles = self.find_cycles();
        let min_of_mins = cycles
            .iter()
            .map(|c| c.iter().min().copied().unwrap())
            .min()
            .ok_or_else(|| anyhow!("no entrypoints and no cycles"))?;
        Ok(vec![min_of_mins])
    }

    fn find_cycles(&self) -> Vec<FxHashSet<i64>> {
        let mut visited = FxHashSet::default();
        let mut rec_stack = FxHashSet::default();
        let mut cycles: Vec<FxHashSet<i64>> = Vec::new();
        let mut path: Vec<i64> = Vec::new();

        fn dfs(
            g: &TalkTextGraph,
            node: i64,
            path: &mut Vec<i64>,
            visited: &mut FxHashSet<i64>,
            rec_stack: &mut FxHashSet<i64>,
            cycles: &mut Vec<FxHashSet<i64>>,
        ) {
            if rec_stack.contains(&node) {
                let start = path.iter().position(|&n| n == node).unwrap();
                let cycle: FxHashSet<i64> = path[start..].iter().copied().collect();
                if !cycles.contains(&cycle) {
                    cycles.push(cycle);
                }
                return;
            }
            if visited.contains(&node) {
                return;
            }
            visited.insert(node);
            rec_stack.insert(node);
            path.push(node);
            for next in g.graph.get(&node).into_iter().flatten() {
                dfs(g, *next, path, visited, rec_stack, cycles);
            }
            path.pop();
            rec_stack.remove(&node);
        }

        for &dialog_id in &self.id_first_seen {
            if !visited.contains(&dialog_id) {
                dfs(
                    self,
                    dialog_id,
                    &mut path,
                    &mut visited,
                    &mut rec_stack,
                    &mut cycles,
                );
            }
        }
        cycles
    }
}

/// Whether a dialog line survives rendering (`render_dialog_line`'s filter).
fn dialog_line_renders(t: &TalkText, language: Language) -> bool {
    !t.skip && !util::should_skip_text(&t.message, language)
}

fn render_dialog_line(t: &TalkText, language: Language) -> Option<String> {
    if !dialog_line_renders(t, language) {
        return None;
    }
    match &t.role {
        None => Some(t.message.clone()),
        Some(role) => Some(format!("{role}: {}", t.message)),
    }
}

/// Map from dialog id (None = "path ended") to the paths that visited it,
/// preserving first-visit order: when several convergence candidates qualify,
/// the earliest-discovered one wins. Branch fan-outs are small, so linear
/// lookups are fine.
#[derive(Default)]
struct DialogPaths(Vec<(Option<i64>, FxHashSet<usize>)>);

impl DialogPaths {
    fn entry(&mut self, key: Option<i64>) -> &mut FxHashSet<usize> {
        match self.0.iter().position(|(k, _)| *k == key) {
            Some(i) => &mut self.0[i].1,
            None => {
                self.0.push((key, FxHashSet::default()));
                &mut self.0.last_mut().unwrap().1
            }
        }
    }

    /// Make `pi` the sole visitor of `key`, discarding earlier visitors.
    fn replace(&mut self, key: Option<i64>, pi: usize) {
        let visitors = self.entry(key);
        visitors.clear();
        visitors.insert(pi);
    }

    fn contains_key(&self, key: &Option<i64>) -> bool {
        self.0.iter().any(|(k, _)| k == key)
    }
}

/// Mutable state of one `process_branch` walk: the live branch paths plus the
/// bookkeeping `advance` updates in lockstep (Python's `_advance` closure).
struct BranchWalk<'a> {
    graph: &'a TalkTextGraph<'a>,
    /// One dialog-id sequence per branch path; None marks "path ended".
    paths: Vec<Vec<Option<i64>>>,
    /// Per-path set of dialog ids already offered to it (cycle guard).
    path_offered: Vec<FxHashSet<i64>>,
    /// Paths that ended in cycles.
    cycle_pis: FxHashSet<usize>,
    dialog_paths: DialogPaths,
}

impl<'a> BranchWalk<'a> {
    fn new(next_dialog_ids: &[i64], graph: &'a TalkTextGraph<'a>) -> BranchWalk<'a> {
        let mut dialog_paths = DialogPaths::default();
        // A dialog id seeding several paths keeps only the last path index.
        for (i, &di) in next_dialog_ids.iter().enumerate() {
            dialog_paths.replace(Some(di), i);
        }
        BranchWalk {
            graph,
            paths: next_dialog_ids.iter().map(|&d| vec![Some(d)]).collect(),
            path_offered: next_dialog_ids
                .iter()
                .map(|_| next_dialog_ids.iter().copied().collect())
                .collect(),
            cycle_pis: FxHashSet::default(),
            dialog_paths,
        }
    }

    /// Advance path `pi` one step, forking it on uncovered fan-outs.
    fn advance(&mut self, pi: usize, rendered: &FxHashSet<i64>) -> Result<()> {
        let Some(curr_di) = *self.paths[pi].last().unwrap() else {
            bail!("Cannot advance an ended path");
        };
        let next_dis: &[i64] = self
            .graph
            .graph
            .get(&curr_di)
            .map(Vec::as_slice)
            .unwrap_or(&[]);
        if next_dis.is_empty() {
            self.paths[pi].push(None);
            if !self.dialog_paths.entry(None).insert(pi) {
                bail!("Path ended multiple times");
            }
            return Ok(());
        }
        let uncovered: Vec<i64> = next_dis
            .iter()
            .copied()
            .filter(|di| !self.path_offered[pi].contains(di))
            .collect();
        if uncovered.is_empty() {
            self.cycle_pis.insert(pi);
            return Ok(());
        }
        self.path_offered[pi].extend(uncovered.iter().copied());
        let mut pis_to_extend = vec![pi];
        for _ in &uncovered[1..] {
            self.paths.push(self.paths[pi].clone());
            let new_pi = self.paths.len() - 1;
            self.path_offered.push(self.path_offered[pi].clone());
            pis_to_extend.push(new_pi);
            for &di in &self.paths[new_pi] {
                if !self.dialog_paths.entry(di).insert(new_pi) {
                    bail!("Found cycle in branch paths");
                }
            }
        }
        for (&di_to_extend, &pi_to_extend) in uncovered.iter().zip(&pis_to_extend) {
            self.paths[pi_to_extend].push(Some(di_to_extend));
            if rendered.contains(&di_to_extend) {
                self.cycle_pis.insert(pi_to_extend);
                continue;
            }
            self.dialog_paths
                .entry(Some(di_to_extend))
                .insert(pi_to_extend);
        }
        Ok(())
    }
}

/// Process multiple branches until their convergence point.
///
/// Renders each branch from `next_dialog_ids` until hitting a convergence
/// point (a dialog with 2+ incoming edges); all branches must converge at the
/// same point (unless some end in cycles).
fn process_branch(
    next_dialog_ids: &[i64],
    graph: &TalkTextGraph,
    rendered: &mut FxHashSet<i64>,
    language: Language,
    scope: &Scope,
) -> Result<(Option<i64>, Vec<Vec<String>>)> {
    let mut walk = BranchWalk::new(next_dialog_ids, graph);
    let seeds: FxHashSet<i64> = next_dialog_ids.iter().copied().collect();

    let reachable = |start: i64| -> FxHashSet<i64> {
        let mut seen = FxHashSet::default();
        let mut stack = vec![start];
        while let Some(top) = stack.pop() {
            for &nxt in graph.graph.get(&top).into_iter().flatten() {
                if seen.insert(nxt) {
                    stack.push(nxt);
                }
            }
        }
        seen
    };

    let conv_point: Option<i64> = loop {
        if walk.cycle_pis.len() == walk.paths.len() {
            bail!("All paths ended in cycles");
        }
        let needed: FxHashSet<usize> = (0..walk.paths.len())
            .filter(|pi| !walk.cycle_pis.contains(pi))
            .collect();
        let potential: Vec<Option<i64>> = walk
            .dialog_paths
            .0
            .iter()
            .filter(|(_, visited)| needed.iter().all(|pi| visited.contains(pi)))
            .map(|(di, _)| *di)
            .collect();
        if !potential.is_empty() {
            if potential.len() != 1 && walk.cycle_pis.is_empty() {
                bail!("Multiple convergence points");
            }
            break potential[0];
        }
        let mut waits: Vec<(usize, i64)> = Vec::new();
        let mut movers: Vec<usize> = Vec::new();
        for pi in 0..walk.paths.len() {
            if walk.cycle_pis.contains(&pi) {
                continue;
            }
            let Some(curr_di) = *walk.paths[pi].last().unwrap() else {
                continue;
            };
            let incoming = graph.incoming.get(&curr_di).copied().unwrap_or(0);
            let has_unoffered = graph
                .graph
                .get(&curr_di)
                .into_iter()
                .flatten()
                .any(|d| !walk.path_offered[pi].contains(d));
            if !seeds.contains(&curr_di) && incoming >= 2 && has_unoffered {
                waits.push((pi, curr_di));
            } else {
                movers.push(pi);
            }
        }
        if !movers.is_empty() {
            for pi in movers {
                walk.advance(pi, rendered)?;
            }
            continue;
        }
        let mut waiting_nodes: Vec<i64> = waits.iter().map(|(_, node)| *node).collect();
        waiting_nodes.sort();
        waiting_nodes.dedup();
        let mut deepest: Option<i64> = None;
        if walk.cycle_pis.is_empty()
            && !walk.dialog_paths.contains_key(&None)
            && waiting_nodes.len() > 1
        {
            deepest = waiting_nodes.iter().copied().find(|&node| {
                waiting_nodes
                    .iter()
                    .filter(|&&o| o != node)
                    .all(|&o| reachable(o).contains(&node))
            });
        }
        for (pi, node) in waits {
            if Some(node) != deepest {
                walk.advance(pi, rendered)?;
            }
        }
    };

    let mut lines_list: Vec<Vec<String>> = Vec::new();
    for (pi, path) in walk.paths.iter().enumerate() {
        let mut branch_lines: Vec<String> = Vec::new();
        let conv_at = path.iter().position(|&di| di == conv_point);
        for &di in &path[..conv_at.unwrap_or(path.len())] {
            let Some(di) = di else {
                bail!("Unexpected None in path");
            };
            match graph.dialog_id_to_text.get(&di) {
                None => {
                    scope.record_issue(IssueType::MissingDialog, di.to_string());
                    branch_lines.push(format!("[Missing Dialog {di}]"));
                }
                Some(text) => {
                    rendered.insert(di);
                    if let Some(rendered_text) = render_dialog_line(text, language) {
                        branch_lines.push(rendered_text);
                    }
                }
            }
        }
        if conv_at.is_none() {
            if !walk.cycle_pis.contains(&pi) {
                bail!("Path {pi} did not converge");
            }
            branch_lines.push("[Loops back to an already-shown dialog]".to_string());
        }
        lines_list.push(branch_lines);
    }

    Ok((conv_point, lines_list))
}

/// Render dialog following single paths until branching, then process branches.
fn render_talk_dialogs(
    dialog_id: i64,
    graph: &TalkTextGraph,
    rendered: &mut FxHashSet<i64>,
    language: Language,
    scope: &Scope,
) -> Result<Vec<String>> {
    let mut lines: Vec<String> = Vec::new();
    let mut current_id: Option<i64> = Some(dialog_id);

    while let Some(cur) = current_id {
        if rendered.contains(&cur) {
            lines.push("[Circling back to a previous dialog]".to_string());
            return Ok(lines);
        }
        rendered.insert(cur);
        match graph.dialog_id_to_text.get(&cur) {
            Some(text) => {
                // An EMPTY rendered line is dropped here (truthiness, not just
                // None), unlike the branch renderer which keeps it.
                if let Some(line) = render_dialog_line(text, language)
                    && !line.is_empty()
                {
                    lines.push(line);
                }
            }
            None => {
                scope.record_issue(IssueType::MissingDialog, cur.to_string());
                lines.push(format!("[Missing Dialog {cur}]"));
                return Ok(lines);
            }
        }
        let next_dialog_ids: &[i64] = graph.graph.get(&cur).map(Vec::as_slice).unwrap_or(&[]);
        if next_dialog_ids.is_empty() {
            break;
        }
        if next_dialog_ids.len() == 1 {
            current_id = Some(next_dialog_ids[0]);
            continue;
        }
        let (conv, branch_lines_list) =
            process_branch(next_dialog_ids, graph, rendered, language, scope)?;
        current_id = conv;
        if branch_lines_list.len() == 1 {
            lines.extend(branch_lines_list.into_iter().next().unwrap());
        } else {
            for (i, branch_lines) in branch_lines_list.into_iter().enumerate() {
                lines.push(String::new());
                lines.push(format!("Option {}:", i + 1));
                lines.push(String::new());
                lines.extend(branch_lines.into_iter().map(|l| format!("> {l}")));
            }
            lines.push(String::new());
        }
    }

    Ok(lines)
}

/// Render talk dialog to lines with branching support.
pub fn render_talk_content(
    talk: &TalkInfo,
    language: Language,
    scope: &Scope,
) -> Result<Vec<String>> {
    if talk.text.is_empty() {
        return Ok(Vec::new());
    }
    let graph = TalkTextGraph::new(talk);
    let entrypoints = graph.find_entrypoints(talk)?;

    let mut rendered: FxHashSet<i64> = FxHashSet::default();
    let mut all_lines: Vec<String> = Vec::new();
    for (i, &entrypoint) in entrypoints.iter().enumerate() {
        if i > 0 {
            all_lines.push(String::new());
        }
        let mut entry_rendered = FxHashSet::default();
        let lines = render_talk_dialogs(entrypoint, &graph, &mut entry_rendered, language, scope)?;
        rendered.extend(entry_rendered);
        all_lines.extend(lines);
    }

    // Dialogs unreachable from any entrypoint are appended as orphans, in
    // dialog-id order.
    let mut orphaned: Vec<i64> = talk
        .text
        .iter()
        .map(|t| t.dialog_id)
        .filter(|id| !rendered.contains(id))
        .collect();
    orphaned.sort();
    orphaned.dedup();
    if !orphaned.is_empty() {
        all_lines.push(String::new());
        for orphaned_id in orphaned {
            let text = graph
                .dialog_id_to_text
                .get(&orphaned_id)
                .ok_or_else(|| anyhow!("orphan {orphaned_id} missing"))?;
            if let Some(rendered_text) = render_dialog_line(text, language) {
                all_lines.push(format!("[Orphaned dialog] {rendered_text}"));
            }
        }
    }

    Ok(all_lines)
}

pub struct RenderedTalk {
    pub title: String,
    pub filename: String,
    pub content: String,
}

/// Render a talk's body, title, and filename; metadata assembly happens in
/// the caller. Returns None when no dialog line survives rendering (e.g. a
/// dev/test talk whose every line is skipped), so all-skipped talks emit no
/// file at all.
pub fn render_talk_body(
    talk: &TalkInfo,
    talk_id: i64,
    language: Language,
    scope: &Scope,
) -> Result<Option<RenderedTalk>> {
    let body_lines = render_talk_content(talk, language, scope)?;
    if body_lines.iter().all(|l| l.trim().is_empty()) {
        return Ok(None);
    }
    let first_message = talk
        .text
        .iter()
        .find(|t| dialog_line_renders(t, language) && !t.message.trim().is_empty())
        .map(|t| t.message.clone());
    let (filename, title) = match first_message {
        Some(msg) => {
            let safe_title = util::make_safe_filename_part(&msg);
            let title = if msg.chars().count() > 100 {
                msg.chars().take(100).collect()
            } else {
                msg
            };
            (format!("{talk_id}_{safe_title}.txt"), title)
        }
        None => (format!("{talk_id}_empty.txt"), "Empty Talk".to_string()),
    };
    let mut content_lines = vec!["# Talk Dialog\n".to_string()];
    content_lines.extend(body_lines);
    Ok(Some(RenderedTalk {
        title,
        filename,
        content: content_lines.join("\n"),
    }))
}

/// Talks pass discovery: excel-known talk ids no earlier pass consumed.
pub fn discover(repo: &Repo, used_talk_ids: &FxHashSet<i64>) -> Result<Vec<i64>> {
    let mut ids: Vec<i64> = repo
        .talk_ids_all
        .iter()
        .filter(|id| !used_talk_ids.contains(id))
        .copied()
        .collect();
    ids.sort();
    Ok(ids)
}

/// Talks pass process: render one leftover talk.
pub fn process(repo: &Repo, scope: &Scope, talk_id: i64) -> Result<Option<RenderedItem>> {
    if repo.get_talk_file_path(talk_id, scope).is_none() {
        return Ok(None);
    }
    let talk_info = get_talk_info_by_id(repo, scope, talk_id)?;
    if talk_info.text.is_empty() {
        return Ok(None);
    }
    let Some(rendered) = render_talk_body(&talk_info, talk_id, repo.language, scope)? else {
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
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::textmap::TextMaps;
    use serde_json::json;

    fn maps(language: Language, current: &[(i64, &str)], fallback: &[(i64, &str)]) -> TextMaps {
        TextMaps::for_tests(
            language,
            current
                .iter()
                .map(|(id, text)| (*id, text.to_string()))
                .collect(),
            fallback
                .iter()
                .map(|(id, text)| (*id, text.to_string()))
                .collect(),
            FxHashMap::default(),
        )
    }

    #[test]
    fn role_name_hash_ignores_fallback_text() {
        let repo = Repo {
            tm: maps(Language::Eng, &[(10, "Hello")], &[(20, "Stale Name")]),
            talk_files: [(
                "talk.json".to_string(),
                json!({"dialogList": [{
                    "id": 1,
                    "talkContentTextMapHash": 10,
                    "talkRoleNameTextMapHash": 20,
                    "talkRole": {"type": "TALK_ROLE_NPC", "_id": "7"}
                }]}),
            )]
            .into_iter()
            .collect(),
            npc_id_to_name: [(7, "Current NPC".to_string())].into_iter().collect(),
            ..Default::default()
        };
        assert_eq!(
            get_talk_info(&repo, &Scope::default(), "talk.json")
                .unwrap()
                .text[0]
                .role,
            Some("Current NPC".to_string())
        );
    }

    #[test]
    fn untranslated_source_test_placeholder_is_skipped() {
        let repo = Repo {
            language: Language::Eng,
            tm: maps(Language::Eng, &[], &[]),
            tm_chs: Some(maps(Language::Chs, &[(10, "(test) placeholder")], &[])),
            talk_files: [(
                "talk.json".to_string(),
                json!({"dialogList": [{
                    "id": 1,
                    "talkContentTextMapHash": 10,
                    "talkRole": {"type": "TALK_ROLE_NONE"}
                }]}),
            )]
            .into_iter()
            .collect(),
            ..Default::default()
        };
        let scope = Scope::default();
        let info = get_talk_info(&repo, &scope, "talk.json").unwrap();
        assert!(info.text[0].skip);
        assert!(scope.issues.borrow().is_empty());
    }

    fn t(role: Option<&str>, message: &str, next: &[i64], dialog_id: i64) -> TalkText {
        TalkText {
            role: role.map(str::to_string),
            message: message.to_string(),
            next_dialog_ids: next.to_vec(),
            dialog_id,
            skip: false,
        }
    }

    fn render(text: Vec<TalkText>, talk_id: i64) -> Option<RenderedTalk> {
        render_talk_body(
            &TalkInfo { text },
            talk_id,
            Language::Chs,
            &Scope::default(),
        )
        .unwrap()
    }

    #[test]
    fn basic_linear_talk() {
        let rendered = render(
            vec![
                t(Some("派蒙"), "这里看起来很神秘呢！", &[2], 1),
                t(Some("旅行者"), "我们小心一点。", &[3], 2),
                t(Some("神秘声音"), "欢迎来到这里...", &[], 3),
            ],
            12345,
        )
        .unwrap();
        assert_eq!(rendered.filename, "12345_这里看起来很神秘呢.txt");
        assert_eq!(rendered.title, "这里看起来很神秘呢！");
        assert_eq!(
            rendered.content,
            "# Talk Dialog\n\n派蒙: 这里看起来很神秘呢！\n旅行者: 我们小心一点。\n神秘声音: 欢迎来到这里..."
        );
    }

    #[test]
    fn empty_talk_renders_nothing() {
        assert!(render(vec![], 99999).is_none());
    }

    #[test]
    fn all_skipped_talk_renders_nothing() {
        // A talk whose every line is dev/test-skipped emits no file at all:
        // one line arrives skip-flagged, the other trips the (test) marker.
        let mut skipped = t(None, "test台词文本", &[], 1);
        skipped.skip = true;
        assert!(
            render(
                vec![
                    skipped,
                    t(
                        Some("(test)旅人兰那罗"),
                        "(test)好汉不吃眼前亏，我先去东南方向的洞里躲一躲",
                        &[],
                        2,
                    ),
                ],
                6863205,
            )
            .is_none()
        );
    }

    #[test]
    fn branching_convergence() {
        // 1 branches into two options that converge at 4.
        let rendered = render(
            vec![
                t(Some("NPC"), "Line 1", &[2, 5], 1),
                t(Some("Player"), "Line 2a", &[3], 2),
                t(Some("NPC"), "Line 3a", &[4], 3),
                t(Some("NPC"), "Line 4", &[], 4),
                t(Some("Player"), "Line 2b", &[6], 5),
                t(Some("NPC"), "Line 3b", &[4], 6),
            ],
            99999,
        )
        .unwrap();
        assert_eq!(
            rendered.content,
            "# Talk Dialog\n\nNPC: Line 1\n\nOption 1:\n\n> Player: Line 2a\n> NPC: Line 3a\n\nOption 2:\n\n> Player: Line 2b\n> NPC: Line 3b\n\nNPC: Line 4"
        );
    }

    #[test]
    fn nested_branches() {
        // Option 1 (2) itself branches into 4/5; everything converges at 6.
        let rendered = render(
            vec![
                t(Some("NPC"), "Line 1", &[2, 3], 1),
                t(Some("Player"), "Line 2", &[4, 5], 2),
                t(Some("Player"), "Line 3", &[6], 3),
                t(Some("NPC"), "Line 4", &[6], 4),
                t(Some("NPC"), "Line 5", &[6], 5),
                t(Some("NPC"), "Line 6", &[], 6),
            ],
            88888,
        )
        .unwrap();
        assert_eq!(
            rendered.content,
            "# Talk Dialog\n\nNPC: Line 1\n\nOption 1:\n\n> Player: Line 2\n> NPC: Line 4\n\nOption 2:\n\n> Player: Line 3\n\nOption 3:\n\n> Player: Line 2\n> NPC: Line 5\n\nNPC: Line 6"
        );
    }

    #[test]
    fn nested_branches_with_intermediate_convergence() {
        // Branch 2's sub-branches converge at X before the global convergence Y.
        let rendered = render(
            vec![
                t(Some("NPC"), "Start", &[2, 3], 1),
                t(Some("Player"), "Branch 1", &[7], 2),
                t(Some("Player"), "Branch 2", &[4, 5], 3),
                t(Some("NPC"), "Branch 2a", &[6], 4),
                t(Some("NPC"), "Branch 2b", &[6], 5),
                t(Some("NPC"), "Convergence X", &[7], 6),
                t(Some("NPC"), "Convergence Y", &[], 7),
            ],
            77777,
        )
        .unwrap();
        assert_eq!(
            rendered.content,
            "# Talk Dialog\n\nNPC: Start\n\nOption 1:\n\n> Player: Branch 1\n\nOption 2:\n\n> Player: Branch 2\n> NPC: Branch 2a\n> NPC: Convergence X\n\nOption 3:\n\n> Player: Branch 2\n> NPC: Branch 2b\n> NPC: Convergence X\n\nNPC: Convergence Y"
        );
    }

    #[test]
    fn rebranching_convergence_no_duplicate_options() {
        // Mirrors quest 76011 (issue #62): a 2-option choice converges at a
        // node that has its own outgoing branch. The short option reaches the
        // convergence node long before the long option; without pausing there
        // it would walk through and split on the convergence node's out-edges,
        // emitting copies of the short option sharing its prefix.
        let rendered = render(
            vec![
                t(Some("NPC"), "Menu", &[2, 4], 1),
                t(Some("Player"), "Short", &[6], 2),
                t(Some("Player"), "Long", &[5], 4),
                t(Some("NPC"), "Long tail", &[6], 5),
                t(Some("NPC"), "Converged", &[7, 8], 6),
                t(Some("Player"), "After A", &[9], 7),
                t(Some("Player"), "After B", &[9], 8),
                t(Some("NPC"), "End", &[], 9),
            ],
            66666,
        )
        .unwrap();
        // Exactly two options at the first choice, neither duplicated.
        assert_eq!(rendered.content.matches("Player: Short").count(), 1);
        assert_eq!(rendered.content.matches("Player: Long").count(), 1);
        // The convergence node's own branch still renders after the options.
        for line in ["NPC: Converged", "Player: After A", "Player: After B"] {
            assert!(rendered.content.contains(line), "{}", rendered.content);
        }
    }

    #[test]
    fn menu_hub_no_blowup() {
        // Mirrors the "ask about X" hub shape (e.g. quest 6000): answers loop
        // back to a re-presented menu that adds an exit option. Without menu
        // re-entry detection, path enumeration through the cyclic hub renders
        // each answer once per topic ordering (combinatorial blow-up).
        let rendered = render(
            vec![
                t(Some("NPC"), "Ask away", &[2, 4], 1),
                t(Some("Player"), "Topic A?", &[3], 2),
                t(Some("NPC"), "Answer A", &[7], 3),
                t(Some("Player"), "Topic B?", &[5], 4),
                t(Some("NPC"), "Answer B", &[8], 5),
                t(Some("Player"), "Nothing", &[9], 6),
                t(Some("NPC"), "Goodbye", &[], 9),
                t(Some("NPC"), "More?", &[2, 4, 6], 7),
                t(Some("NPC"), "More?", &[2, 4, 6], 8),
            ],
            88888,
        )
        .unwrap();
        // Each unique answer renders exactly once, and the exit branch
        // (reachable only from a re-presented menu) is still present.
        for line in ["NPC: Answer A", "NPC: Answer B", "NPC: Goodbye"] {
            assert_eq!(
                rendered.content.matches(line).count(),
                1,
                "{}",
                rendered.content
            );
        }
    }

    #[test]
    fn cascaded_correct_answer_menus_no_spurious_options() {
        // Mirrors quest 11008's evidence menus: each wrong-answer tail
        // re-offers exactly the seed options (a back-edge join whose out-edges
        // are all covered), and the correct answer runs on into the next such
        // menu. The convergence-wait must not stall at those back-edge joins,
        // or each menu spawns extra empty option branches.
        let rendered = render(
            vec![
                t(Some("NPC"), "M1", &[12, 13, 14], 11),
                t(Some("Player"), "1-correct", &[15], 12),
                t(Some("Player"), "1-wrongA", &[16], 13),
                t(Some("Player"), "1-wrongB", &[16], 14),
                t(Some("NPC"), "right1", &[17], 15),
                t(Some("NPC"), "wrong1", &[12, 13, 14], 16),
                t(Some("NPC"), "mid17", &[18], 17),
                t(Some("NPC"), "mid18", &[22], 18),
                t(Some("NPC"), "M2", &[23, 24, 25], 22),
                t(Some("Player"), "2-correct", &[26], 23),
                t(Some("Player"), "2-wrongA", &[27], 24),
                t(Some("Player"), "2-wrongB", &[27], 25),
                t(Some("NPC"), "right2", &[28], 26),
                t(Some("NPC"), "wrong2", &[23, 24, 25], 27),
                t(Some("NPC"), "End", &[], 28),
            ],
            55555,
        )
        .unwrap();
        // Three options per menu, two menus -> six options; no spurious extras.
        assert_eq!(
            rendered.content.matches("Option ").count(),
            6,
            "{}",
            rendered.content
        );
        for line in [
            "Player: 1-wrongA",
            "Player: 2-wrongA",
            "NPC: right1",
            "NPC: End",
        ] {
            assert_eq!(
                rendered.content.matches(line).count(),
                1,
                "{}",
                rendered.content
            );
        }
    }
}
