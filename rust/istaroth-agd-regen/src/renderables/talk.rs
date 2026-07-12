//! Port of istaroth.agd.renderables._talk: talk info assembly and the shared
//! dialogue graph renderer (including the branch/convergence algorithm).

use crate::firstseen;
use crate::issues::{IssueType, Scope};
use crate::pyset::PySet;
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::ValueExt;
use anyhow::{Result, anyhow, bail};
use indexmap::IndexMap;
use rustc_hash::{FxHashMap, FxHashSet};
use serde_json::Value;

pub const MISSING_TALK_ROLE: &str = "[Missing Talk]";
pub const PLAYER: &str = "旅行者";
pub const MATE_AVATAR: &str = "旅行者血亲";
pub const PAIMON: &str = "派蒙";
pub const BLACK_SCREEN: &str = "黑屏文本";
pub const UNKNOWN_ROLE: &str = "Unknown Role";

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

/// Port of get_talk_info: build TalkInfo from a talk file path.
pub fn get_talk_info(repo: &Repo, scope: &Scope, talk_path: &str) -> Result<TalkInfo> {
    let data = repo
        .talk_files
        .get(talk_path)
        .ok_or_else(|| anyhow!("talk file not loaded: {talk_path}"))?;
    // Python: talk_data.get("dialogList") is None covers both a missing key and
    // an explicit JSON null; anything else present must be a list.
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
                // CHS: the source map IS the current map, so an unresolved hash
                // can never resolve as a CHS dev placeholder; it is missing text.
                scope.record_issue(IssueType::MissingText, content_hash.to_string());
                format!("Missing text ({content_hash})")
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

/// The `dialog.talkRoleNameTextMapHash or dialog_id_to_role_hash.get(id)` chain.
fn role_name_hash(repo: &Repo, dialog_item: &Value, dialog_id: i64) -> Option<i64> {
    match dialog_item.get_i("talkRoleNameTextMapHash") {
        Some(h) if h != 0 => Some(h),
        _ => repo.dialog_id_to_role_hash.get(&dialog_id).copied(),
    }
}

/// talk_role.get("_id", talk_role.get("id")) resolved to a digit-checked npc id.
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
    if util::py_isdigit(s) {
        Ok(Some(util::py_int(s)?))
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

    let by_role: Option<String> = match role_type {
        Some("TALK_ROLE_NPC") => role_npc_id(talk_role)?
            .and_then(|id| repo.npc_id_to_name.get(&id))
            .cloned(),
        Some("TALK_ROLE_PLAYER") => Some(PLAYER.to_string()),
        Some("TALK_ROLE_MATE_AVATAR") => Some(MATE_AVATAR.to_string()),
        Some("TALK_ROLE_NEED_CLICK_BLACK_SCREEN") | Some("TALK_ROLE_BLACK_SCREEN") => {
            Some(BLACK_SCREEN.to_string())
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
            role_npc_id(talk_role)?.and_then(|id| repo.npc_source_name(id))
        } else {
            None
        };
        if let Some(src) = npc_src
            && util::should_skip_text(src)
        {
            return Ok(Some(name_hash.clone()));
        }
        return Ok(Some(format!("{role} ({name_hash})")));
    }
    // Python: `by_name_hash or by_role` (empty string falls through).
    let resolved = match &by_name_hash {
        Some(s) if !s.is_empty() => by_name_hash.clone(),
        _ => by_role.clone(),
    };
    if resolved.is_some() {
        return Ok(resolved);
    }
    if role_type == Some("TALK_ROLE_NONE") {
        return Ok(None);
    }
    scope.record_issue(
        IssueType::UnknownRole,
        format!("dialog {dialog_id} role {}", role_type.unwrap_or("None")),
    );
    Ok(Some(format!(
        "{UNKNOWN_ROLE} ({})",
        role_type.unwrap_or("None")
    )))
}

fn role_is_dev(repo: &Repo, scope: &Scope, dialog_item: &Value, dialog_id: i64) -> Result<bool> {
    if let Some(h) = role_name_hash(repo, dialog_item, dialog_id)
        && let Some(hash_name) = repo.tm.get_current_optional(h, scope)?
    {
        return Ok(util::should_skip_text(&hash_name));
    }
    let talk_role = dialog_item.f("talkRole")?;
    let src = if talk_role.get_s("type") == Some("TALK_ROLE_NPC") {
        role_npc_id(talk_role)?.and_then(|id| repo.npc_source_name(id))
    } else {
        None
    };
    Ok(src.is_some_and(|s| util::should_skip_text(s)))
}

pub fn get_talk_info_by_id(repo: &Repo, scope: &Scope, talk_id: i64) -> Result<TalkInfo> {
    let path = repo
        .get_talk_file_path(talk_id, scope)
        .ok_or(TalkNotFound(talk_id))?
        .clone();
    get_talk_info(repo, scope, &path)
}

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
            if !dialog_id_to_text.contains_key(&talk_text.dialog_id) {
                id_first_seen.push(talk_text.dialog_id);
            }
            dialog_id_to_text.insert(talk_text.dialog_id, talk_text);
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

fn render_dialog_line(t: &TalkText) -> Option<String> {
    if t.skip || util::should_skip_text(&t.message) {
        return None;
    }
    match &t.role {
        None => Some(t.message.clone()),
        Some(role) => Some(format!("{role}: {}", t.message)),
    }
}

/// defaultdict(set)-style access into an IndexMap keyed by Option<i64>.
fn dd(
    map: &mut IndexMap<Option<i64>, FxHashSet<usize>>,
    key: Option<i64>,
) -> &mut FxHashSet<usize> {
    map.entry(key).or_default()
}

/// Port of _process_branch: renders branches until their convergence point.
fn process_branch(
    next_dialog_ids: &[i64],
    graph: &TalkTextGraph,
    rendered: &mut FxHashSet<i64>,
    scope: &Scope,
) -> Result<(Option<i64>, Vec<Vec<String>>)> {
    let mut paths: Vec<Vec<Option<i64>>> = next_dialog_ids.iter().map(|&d| vec![Some(d)]).collect();
    let mut path_offered: Vec<FxHashSet<i64>> = next_dialog_ids
        .iter()
        .map(|_| next_dialog_ids.iter().copied().collect())
        .collect();
    let mut cycle_pis: FxHashSet<usize> = FxHashSet::default();
    let mut dialog_paths: IndexMap<Option<i64>, FxHashSet<usize>> = IndexMap::new();
    {
        // dict comprehension {di: {i}} — duplicate keys keep first position, last value.
        let mut tmp: IndexMap<Option<i64>, FxHashSet<usize>> = IndexMap::new();
        for (i, &di) in next_dialog_ids.iter().enumerate() {
            let mut s = FxHashSet::default();
            s.insert(i);
            *tmp.entry(Some(di)).or_default() = s;
        }
        dialog_paths.extend(tmp);
    }
    let seeds: FxHashSet<i64> = next_dialog_ids.iter().copied().collect();

    let reachable = |start: i64| -> FxHashSet<i64> {
        let mut seen = FxHashSet::default();
        let mut stack = vec![start];
        while let Some(top) = stack.pop() {
            for &nxt in graph.graph.get(&top).into_iter().flatten() {
                if !seen.contains(&nxt) {
                    seen.insert(nxt);
                    stack.push(nxt);
                }
            }
        }
        seen
    };

    // _advance(pi)
    macro_rules! advance {
        ($pi:expr) => {{
            let pi: usize = $pi;
            let curr_di = *paths[pi].last().unwrap();
            let Some(curr_di) = curr_di else {
                bail!("Cannot advance an ended path");
            };
            let next_dis: Vec<i64> = graph.graph.get(&curr_di).cloned().unwrap_or_default();
            if next_dis.is_empty() {
                paths[pi].push(None);
                if dd(&mut dialog_paths, None).contains(&pi) {
                    bail!("Path ended multiple times");
                }
                dd(&mut dialog_paths, None).insert(pi);
            } else {
                let uncovered: Vec<i64> = next_dis
                    .iter()
                    .copied()
                    .filter(|di| !path_offered[pi].contains(di))
                    .collect();
                if uncovered.is_empty() {
                    cycle_pis.insert(pi);
                } else {
                    path_offered[pi].extend(uncovered.iter().copied());
                    let mut pis_to_extend = vec![pi];
                    for _ in &uncovered[1..] {
                        let clone = paths[pi].clone();
                        paths.push(clone);
                        let new_pi = paths.len() - 1;
                        path_offered.push(path_offered[pi].clone());
                        pis_to_extend.push(new_pi);
                        let elems: Vec<Option<i64>> = paths[new_pi].clone();
                        for di in elems {
                            let set = dd(&mut dialog_paths, di);
                            if set.contains(&new_pi) {
                                bail!("Found cycle in branch paths");
                            }
                            set.insert(new_pi);
                        }
                    }
                    for (idx, &di_to_extend) in uncovered.iter().enumerate() {
                        let pi_to_extend = pis_to_extend[idx];
                        paths[pi_to_extend].push(Some(di_to_extend));
                        if rendered.contains(&di_to_extend) {
                            cycle_pis.insert(pi_to_extend);
                            continue;
                        }
                        dd(&mut dialog_paths, Some(di_to_extend)).insert(pi_to_extend);
                    }
                }
            }
        }};
    }

    let conv_point: Option<i64> = loop {
        if cycle_pis.len() == paths.len() {
            bail!("All paths ended in cycles");
        }
        let needed: FxHashSet<usize> = (0..paths.len())
            .filter(|pi| !cycle_pis.contains(pi))
            .collect();
        let potential: Vec<Option<i64>> = dialog_paths
            .iter()
            .filter(|(_, visited)| needed.iter().all(|pi| visited.contains(pi)))
            .map(|(di, _)| *di)
            .collect();
        if !potential.is_empty() {
            if potential.len() != 1 && cycle_pis.is_empty() {
                bail!("Multiple convergence points");
            }
            break potential[0];
        }
        let mut waits: IndexMap<usize, i64> = IndexMap::new();
        let mut movers: Vec<usize> = Vec::new();
        for pi in 0..paths.len() {
            if cycle_pis.contains(&pi) {
                continue;
            }
            let Some(curr_di) = *paths[pi].last().unwrap() else {
                continue;
            };
            let incoming = graph.incoming.get(&curr_di).copied().unwrap_or(0);
            let has_unoffered = graph
                .graph
                .get(&curr_di)
                .into_iter()
                .flatten()
                .any(|d| !path_offered[pi].contains(d));
            if !seeds.contains(&curr_di) && incoming >= 2 && has_unoffered {
                waits.insert(pi, curr_di);
            } else {
                movers.push(pi);
            }
        }
        if !movers.is_empty() {
            for pi in movers {
                advance!(pi);
            }
            continue;
        }
        let waiting_nodes = PySet::from_iter_py(waits.values().copied());
        let mut deepest: Option<i64> = None;
        if cycle_pis.is_empty() && !dialog_paths.contains_key(&None) && waiting_nodes.len() > 1 {
            deepest = waiting_nodes.iter().find(|&node| {
                waiting_nodes
                    .iter()
                    .filter(|&o| o != node)
                    .all(|o| reachable(o).contains(&node))
            });
        }
        let waits_snapshot: Vec<(usize, i64)> = waits.iter().map(|(k, v)| (*k, *v)).collect();
        for (pi, node) in waits_snapshot {
            if Some(node) != deepest {
                advance!(pi);
            }
        }
    };

    let mut lines_list: Vec<Vec<String>> = Vec::new();
    for (pi, path) in paths.iter().enumerate() {
        let mut branch_lines: Vec<String> = Vec::new();
        let mut broke = false;
        for &di in path {
            if di == conv_point {
                broke = true;
                break;
            }
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
                    if let Some(rendered_text) = render_dialog_line(text) {
                        branch_lines.push(rendered_text);
                    }
                }
            }
        }
        if !broke {
            if !cycle_pis.contains(&pi) {
                bail!("Path {pi} did not converge");
            }
            branch_lines.push("[Loops back to an already-shown dialog]".to_string());
        }
        lines_list.push(branch_lines);
    }

    Ok((conv_point, lines_list))
}

/// Port of _render_talk_dialogs.
fn render_talk_dialogs(
    dialog_id: i64,
    graph: &TalkTextGraph,
    rendered: &mut FxHashSet<i64>,
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
                // Python walrus truthiness: an empty rendered line is dropped.
                if let Some(line) = render_dialog_line(text)
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
        let next_dialog_ids = graph.graph.get(&cur).cloned().unwrap_or_default();
        if next_dialog_ids.is_empty() {
            break;
        }
        if next_dialog_ids.len() == 1 {
            current_id = Some(next_dialog_ids[0]);
            continue;
        }
        let (conv, branch_lines_list) = process_branch(&next_dialog_ids, graph, rendered, scope)?;
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

/// Port of render_talk_content.
pub fn render_talk_content(talk: &TalkInfo, scope: &Scope) -> Result<Vec<String>> {
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
        let lines = render_talk_dialogs(entrypoint, &graph, &mut entry_rendered, scope)?;
        rendered.extend(entry_rendered);
        all_lines.extend(lines);
    }

    // Orphans: `{dialog ids} - rendered` iterated in CPython set order.
    let all_ids = PySet::from_iter_py(talk.text.iter().map(|t| t.dialog_id));
    let orphaned = all_ids.difference(&rendered);
    if !orphaned.is_empty() {
        all_lines.push(String::new());
        for orphaned_id in orphaned.iter() {
            let text = graph
                .dialog_id_to_text
                .get(&orphaned_id)
                .ok_or_else(|| anyhow!("orphan {orphaned_id} missing"))?;
            if let Some(rendered_text) = render_dialog_line(text) {
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

/// Port of render_talk (body only; metadata assembly happens in the caller).
pub fn render_talk_body(
    talk: &TalkInfo,
    talk_id: i64,
    scope: &Scope,
) -> Result<Option<RenderedTalk>> {
    let body_lines = render_talk_content(talk, scope)?;
    if !body_lines.iter().any(|l| !util::py_strip(l).is_empty()) {
        return Ok(None);
    }
    let first_message = talk
        .text
        .iter()
        .find(|t| render_dialog_line(t).is_some() && !util::py_strip(&t.message).is_empty())
        .map(|t| t.message.clone());
    let (filename, title) = match first_message {
        Some(msg) => {
            let safe_title = util::make_safe_filename_part(&msg);
            let title = if msg.chars().count() > 100 {
                util::py_slice(&msg, 100)
            } else {
                msg.clone()
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
    let Some(rendered) = render_talk_body(&talk_info, talk_id, scope)? else {
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
