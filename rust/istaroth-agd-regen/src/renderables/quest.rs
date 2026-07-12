//! Port of renderables/quest.py.

use crate::firstseen::Domain;
use crate::issues::{IssueType, Scope};
use crate::renderables::talk::{self, TalkInfo, TalkNotFound};
use crate::rendered_item::RenderedItem;
use crate::repo::Repo;
use crate::util;
use crate::vh::ValueExt;
use anyhow::{Result, anyhow, bail};
use indexmap::IndexMap;
use rustc_hash::{FxHashMap, FxHashSet};
use serde_json::Value;

// Priority of the signals that hint where a quest talk plays, lowest to highest.
const PRIORITY_FINISH_PLOT: i64 = 1;
const PRIORITY_COMPLETE_TALK: i64 = 2;
const PRIORITY_BEGIN_COND: i64 = 3;

// Separators that mark the boundary between a questline name and the chapter
// ordinal inside chapter titles (e.g. 山中好长日·第一章, "Aranyaka: Part I",
// "Fabulous Fungus Frenzy - Act I").
const GROUP_NAME_SEPARATORS: [char; 4] = ['·', ':', '：', '-'];

pub struct QuestStep {
    pub order: i64,
    pub is_lead_in: bool,
    pub description: Option<String>,
    pub talk: Option<TalkInfo>,
}

pub struct QuestInfo {
    pub quest_id: i64,
    pub title: String,
    pub chapter_title: Option<String>,
    pub group_name: Option<String>,
    pub description: Option<String>,
    pub steps: Vec<QuestStep>,
    pub non_subquest_talks: Vec<TalkInfo>,
    pub associated_free_talks: Vec<TalkInfo>,
}

/// Questline name shared by a group's chapter titles, or None when there is none.
///
/// The longest common prefix of the titles, trimmed so a divergence inside an
/// ordinal doesn't leak scaffolding into the name: when any title continues
/// the prefix with a word character (e.g. "Part I" / "Part II" agreeing up to
/// "Part I"), cut back to the last strong separator, or failing that the last
/// non-alphanumeric character. Trailing whitespace/separators are stripped.
fn common_prefix_name(titles: &[String]) -> Option<String> {
    let prefix = util::common_prefix(titles);
    let prefix_chars: Vec<char> = prefix.chars().collect();
    let plen = prefix_chars.len();
    let diverges_into_word = titles.iter().any(|t| {
        let rest: Vec<char> = t.chars().skip(plen).collect();
        !rest.is_empty() && rest[0].is_alphanumeric()
    });
    let mut prefix_chars = prefix_chars;
    if diverges_into_word {
        // max over rfind of each separator (char index; -1 when absent).
        let mut cut: i64 = -1;
        for sep in GROUP_NAME_SEPARATORS {
            if let Some(pos) = prefix_chars.iter().rposition(|&c| c == sep) {
                cut = cut.max(pos as i64);
            }
        }
        let cut = if cut == -1 {
            prefix_chars
                .iter()
                .enumerate()
                .filter(|(_, c)| !c.is_alphanumeric())
                .map(|(i, _)| i + 1)
                .max()
                .unwrap_or(0)
        } else {
            cut as usize
        };
        prefix_chars.truncate(cut);
    }
    let result: String = prefix_chars
        .into_iter()
        .collect::<String>()
        .trim_end_matches(|c: char| c == ' ' || GROUP_NAME_SEPARATORS.contains(&c))
        .to_string();
    if result.is_empty() {
        None
    } else {
        Some(result)
    }
}

/// Whether a chapter is dev/test content (e.g. the 夏活beta测试任务 chapter).
/// The dev/test markers live in the CHS (source) text. Untracked lookups:
/// this check must not mark the chapter hashes as used.
pub fn is_test_or_hidden_chapter(repo: &Repo, chapter: &Value) -> Result<bool> {
    for key in ["chapterNumTextMapHash", "chapterTitleTextMapHash"] {
        if let Some(text) = repo.tm.get_optional_untracked(chapter.i(key)?)?
            && util::should_skip_text(&text)
        {
            return Ok(true);
        }
    }
    Ok(false)
}

pub fn get_chapter_title(repo: &Repo, scope: &Scope, chapter: &Value) -> Result<String> {
    let parts: Vec<String> = [
        repo.tm
            .get_optional(chapter.i("chapterNumTextMapHash")?, scope)?,
        repo.tm
            .get_optional(chapter.i("chapterTitleTextMapHash")?, scope)?,
    ]
    .into_iter()
    .flatten()
    .collect();
    Ok(parts.join(" "))
}

/// All chapters in the same quest group (questline) as `chapter`.
///
/// Grouping is the chapter `groupId`; a `groupId`-less chapter is its own sole
/// member (some questlines, e.g. 山中好长日, embed a questline name in their
/// chapter numbers without any groupId link, but we deliberately don't infer
/// grouping the data doesn't encode). Dev/test chapters are excluded so they
/// can't poison the group's common prefix.
fn group_member_chapters<'r>(repo: &'r Repo, chapter: &Value) -> Result<Vec<&'r Value>> {
    let group_id = chapter.i("groupId")?;
    if group_id == 0 {
        // Return the same chapter object from the repo store.
        let id = chapter.i("id")?;
        return Ok(vec![
            repo.excel
                .chapter
                .get(&id)
                .ok_or_else(|| anyhow!("unknown chapter {id}"))?,
        ]);
    }
    let mut members = Vec::new();
    for c in repo.excel.chapter.values() {
        if c.i("groupId")? == group_id && !is_test_or_hidden_chapter(repo, c)? {
            members.push(c);
        }
    }
    Ok(members)
}

/// Resolve a chapter's questline (quest group) name, or None when it has none.
///
/// AGD has no group-level name field (issue #239), so the name is derived as
/// the common prefix of the group's chapter titles. Single-chapter groups get
/// None: their "group name" would just repeat the chapter title.
pub fn get_quest_group_name(repo: &Repo, scope: &Scope, chapter_id: i64) -> Result<Option<String>> {
    let chapter = repo
        .excel
        .chapter
        .get(&chapter_id)
        .ok_or_else(|| anyhow!("unknown chapter {chapter_id}"))?;
    let members = group_member_chapters(repo, chapter)?;
    if members.len() < 2 {
        return Ok(None);
    }
    let titles: Vec<String> = members
        .iter()
        .map(|c| get_chapter_title(repo, scope, c))
        .collect::<Result<_>>()?;
    Ok(common_prefix_name(&titles))
}

/// Whether a quest title marks a dev/test/hidden quest to exclude
/// (`$HIDDEN`/`(test)` markers, which live in the CHS source text).
fn is_test_or_hidden_title(repo: &Repo, scope: &Scope, title_hash: i64) -> Result<bool> {
    Ok(match repo.tm.get_optional(title_hash, scope)? {
        None => false,
        Some(chs) => util::should_skip_text(&chs),
    })
}

/// Whether a subQuest is a dev/test/hidden step (a `$HIDDEN`/bridge marker).
/// Such steps carry meaningless `order` numbers, so a talk's `beginCond`
/// pointing at one is an internal trigger rather than a real playback location.
fn is_hidden_step(repo: &Repo, scope: &Scope, desc_hash: i64) -> Result<bool> {
    Ok(match repo.tm.get_optional(desc_hash, scope)? {
        None => false,
        Some(chs) => util::should_skip_text(&chs),
    })
}

/// Resolve a subQuest's objective text, or None when there is none to show
/// (no/empty text, or a test/hidden step).
fn resolve_step_description(repo: &Repo, scope: &Scope, desc_hash: i64) -> Result<Option<String>> {
    if is_hidden_step(repo, scope, desc_hash)? {
        return Ok(None);
    }
    Ok(repo
        .tm
        .get_optional(desc_hash, scope)?
        .filter(|t| !t.is_empty() && !util::py_strip(t).is_empty()))
}

/// Step order a quest talk begins at (via its `beginCond`), or None.
///
/// A quest talk plays when `QUEST_COND_STATE_EQUAL [subId, 2]` holds (the
/// named subquest activated); the remaining beginCond entries are gating
/// conditions (quest vars, items, ...) that don't locate the talk. When
/// several activation conditions resolve, the talk plays once all hold, i.e.
/// at the latest order. Returns None when no activation condition resolves to
/// a subquest of this quest (e.g. a cross-quest reference), leaving the talk
/// for non-step placement.
fn begin_subquest_order(
    talk_item: &Value,
    subid_to_order: &FxHashMap<i64, i64>,
) -> Result<Option<i64>> {
    let mut orders: Vec<i64> = Vec::new();
    for cond in talk_item.arr("beginCond")? {
        if cond.s("_type")? != "QUEST_COND_STATE_EQUAL" {
            continue;
        }
        let param = cond.arr("_param")?;
        if param.len() <= 1 {
            continue;
        }
        if param[1].as_str() != Some("2") {
            continue;
        }
        let sub = util::py_int(
            param[0]
                .as_str()
                .ok_or_else(|| anyhow!("non-str begin cond param"))?,
        )?;
        if let Some(&order) = subid_to_order.get(&sub) {
            orders.push(order);
        }
    }
    Ok(orders.into_iter().max())
}

/// (talk_id, hint_priority, TalkInfo) for talks referenced by finish conditions.
///
/// Only the condition types that genuinely reference a talk are handled;
/// everything else is an objective step with no talk. COMPLETE_TALK and
/// COMPLETE_ANY_TALK name the talk that completes the step, so they are
/// authoritative pointers and a missing talk becomes a placeholder.
/// FINISH_PLOT is a plot-completion marker whose param is only sometimes a
/// real talk id, so a missing talk is skipped instead. (The enum field is
/// literally named `damageRatio` in legacy cleartext AGD; see deob.rs.)
fn iter_subquest_talks(
    repo: &Repo,
    scope: &Scope,
    subquest: &Value,
) -> Result<Vec<(i64, i64, TalkInfo)>> {
    let mut talks = Vec::new();
    for cond in subquest.arr("finishCond")? {
        match cond.get_s("damageRatio") {
            Some("QUEST_CONTENT_COMPLETE_TALK") => {
                let talk_id = crate::vh::as_i64(&cond.arr("param")?[0])?;
                talks.push((
                    talk_id,
                    PRIORITY_COMPLETE_TALK,
                    talk::resolve_authoritative_talk(repo, scope, talk_id)?,
                ));
            }
            Some("QUEST_CONTENT_COMPLETE_ANY_TALK") => {
                for part in cond.s("CUSTOM_paramStr")?.split(',') {
                    let talk_id = util::py_int(part)?;
                    talks.push((
                        talk_id,
                        PRIORITY_COMPLETE_TALK,
                        talk::resolve_authoritative_talk(repo, scope, talk_id)?,
                    ));
                }
            }
            Some("QUEST_CONTENT_FINISH_PLOT") => {
                let talk_id = crate::vh::as_i64(&cond.arr("param")?[0])?;
                match talk::get_talk_info_by_id(repo, scope, talk_id) {
                    Ok(info) => talks.push((talk_id, PRIORITY_FINISH_PLOT, info)),
                    Err(e) if e.is::<TalkNotFound>() => continue,
                    Err(e) => return Err(e),
                }
            }
            _ => {}
        }
    }
    Ok(talks)
}

pub fn get_quest_info(repo: &Repo, scope: &Scope, quest_id: i64) -> Result<Option<QuestInfo>> {
    let quest_path = repo
        .quest_mapping
        .get(&quest_id)
        .ok_or_else(|| anyhow!("quest {quest_id} has no file"))?;
    let quest_data = &repo.quest_files[quest_path];

    let title_hash = quest_data.i("titleTextMapHash")?;
    let quest_title = match repo.tm.get_optional(title_hash, scope)? {
        Some(title) => title,
        None => {
            scope.record_issue(IssueType::MissingQuestTitle, title_hash.to_string());
            format!("Missing title ({title_hash})")
        }
    };

    // Surface the quest description only when it adds something beyond the
    // title: this guard drops descriptions that merely repeat the title.
    let mut description = repo
        .tm
        .get_optional(quest_data.i("descTextMapHash")?, scope)?;
    if description.as_deref() == Some(quest_title.as_str()) {
        description = None;
    }

    let mut chapter_title = None;
    let mut group_name = None;
    let mut hidden_chapter = false;
    let chapter_id = quest_data.i("chapterId")?;
    if chapter_id != 0 {
        let chapter = repo
            .excel
            .chapter
            .get(&chapter_id)
            .ok_or_else(|| anyhow!("Unknown chapter {chapter_id} for quest {quest_path}"))?;
        chapter_title = Some(get_chapter_title(repo, scope, chapter)?);
        group_name = get_quest_group_name(repo, scope, chapter_id)?;
        hidden_chapter = is_test_or_hidden_chapter(repo, chapter)?;
    }

    // Resolve where each talk a quest declares actually plays. A talk's
    // `beginCond` names the subQuest it starts on (its true playback
    // location); quest `talks` entries provide it. The finish-condition
    // param, NOT the subId, names the talk a step references (subId matches a
    // talk id only by coincidence of the shared <questId><incremental>
    // numbering, so it is an unreliable pointer).
    let sub_quests = quest_data.arr("subQuests")?;
    let mut subid_to_order: FxHashMap<i64, i64> = FxHashMap::default();
    for subquest in sub_quests {
        subid_to_order.insert(subquest.i("subId")?, subquest.i("order")?);
    }
    let quest_talks = quest_data.arr("talks")?;
    // Duplicate talk ids keep the LAST begin value (reference dict semantics).
    let mut talk_begin_order: FxHashMap<i64, i64> = FxHashMap::default();
    for talk_item in quest_talks {
        if let Some(begin) = begin_subquest_order(talk_item, &subid_to_order)? {
            talk_begin_order.insert(talk_item.i("id")?, begin);
        }
    }

    // Collect every placement hint for every talk, from both sources, into
    // one set. A finish condition names the step a talk COMPLETES
    // (FINISH_PLOT / COMPLETE_TALK priority); a talk's own `beginCond` (from
    // the quest `talks` field) names the step it STARTS playing on — its true
    // location, hence top priority. Track hidden/test steps, whose `order`
    // numbers are meaningless.
    let mut talk_hints: IndexMap<i64, Vec<(i64, i64)>> = IndexMap::new();
    let mut talk_infos: FxHashMap<i64, TalkInfo> = FxHashMap::default();
    let mut order_to_desc: IndexMap<i64, Option<String>> = IndexMap::new();
    let mut hidden_orders: FxHashSet<i64> = FxHashSet::default();
    for subquest in sub_quests {
        let order_index = subquest.i("order")?;
        let desc = resolve_step_description(repo, scope, subquest.i("descTextMapHash")?)?;
        if order_to_desc.contains_key(&order_index) {
            bail!("duplicate subQuest order {order_index} in quest {quest_id}");
        }
        order_to_desc.insert(order_index, desc);
        if is_hidden_step(repo, scope, subquest.i("descTextMapHash")?)? {
            hidden_orders.insert(order_index);
        }
        for (talk_id, priority, talk_info) in iter_subquest_talks(repo, scope, subquest)? {
            talk_hints
                .entry(talk_id)
                .or_default()
                .push((order_index, priority));
            talk_infos.entry(talk_id).or_insert(talk_info);
        }
    }

    // The orders where each talk completes a step (its finish-condition
    // hints); a talk placed elsewhere (at a beginCond order it does not
    // finish) is a lead-in.
    let finish_orders: FxHashMap<i64, FxHashSet<i64>> = talk_hints
        .iter()
        .map(|(talk_id, hints)| (*talk_id, hints.iter().map(|h| h.0).collect()))
        .collect();

    // Fold every quest-declared talk into the same hint set via its
    // beginCond. beginCond is the talk's true start, so a top-priority hint —
    // except when it points at a hidden/test step (an internal trigger),
    // which is ignored only if the talk has a real finishCond placement to
    // fall back on (otherwise beginCond is the sole signal). A talk with
    // neither a finish condition nor a usable beginCond has no anchor in this
    // quest and is rendered in a separate section.
    let mut non_subquest_talks: Vec<TalkInfo> = Vec::new();
    for talk_item in quest_talks {
        let talk_id = talk_item.i("id")?;
        let begin_anchor = match talk_begin_order.get(&talk_id) {
            Some(&begin)
                if !hidden_orders.contains(&begin) || !finish_orders.contains_key(&talk_id) =>
            {
                Some(begin)
            }
            _ => None,
        };
        // Already hinted by a finish condition: just add the beginCond hint
        // (if any) and move on. Such a talk is anchored to this quest, so it
        // must never fall through to `non_subquest_talks` below.
        if let Some(hints) = talk_hints.get_mut(&talk_id) {
            if let Some(anchor) = begin_anchor {
                hints.push((anchor, PRIORITY_BEGIN_COND));
            }
            continue;
        }
        // A talk the quest declares must load; a failure is a genuine data gap.
        let talk_info = talk::get_talk_info_by_id(repo, scope, talk_id)?;
        if talk_info.text.is_empty() {
            continue;
        }
        if let Some(anchor) = begin_anchor {
            talk_hints.insert(talk_id, vec![(anchor, PRIORITY_BEGIN_COND)]);
            talk_infos.insert(talk_id, talk_info);
        } else {
            non_subquest_talks.push(talk_info);
        }
    }

    let mut talk_order: FxHashMap<i64, usize> = FxHashMap::default();
    for (idx, talk_item) in quest_talks.iter().enumerate() {
        talk_order.insert(talk_item.i("id")?, idx);
    }

    struct Placed {
        order: i64,
        tiebreak: usize,
        desc: Option<String>,
        info: TalkInfo,
        is_lead_in: bool,
    }
    // Place each talk at its highest-priority hinted step (earliest order
    // breaks ties). A talk placed at a step it does not itself finish is a
    // lead-in there (it plays during the step but another talk completes it).
    // `tiebreak` orders talks sharing a step: completing talks by finishCond
    // discovery order, lead-ins by their order in the quest `talks` field (a
    // lead-in always has a beginCond, so it is listed there).
    let mut placed: Vec<Placed> = Vec::new();
    for (seq, (talk_id, hints)) in talk_hints.iter().enumerate() {
        // max(key=(priority, -order)); must keep the FIRST maximal on ties.
        let mut best = hints[0];
        let mut best_key = (best.1, -best.0);
        for &h in &hints[1..] {
            let k = (h.1, -h.0);
            if k > best_key {
                best = h;
                best_key = k;
            }
        }
        let best_order = best.0;
        let is_lead_in = !finish_orders
            .get(talk_id)
            .is_some_and(|orders| orders.contains(&best_order));
        let desc = order_to_desc
            .get(&best_order)
            .ok_or_else(|| anyhow!("order {best_order} missing desc"))?
            .clone();
        let tiebreak = if is_lead_in {
            *talk_order
                .get(talk_id)
                .ok_or_else(|| anyhow!("lead-in talk {talk_id} not in quest talks"))?
        } else {
            seq
        };
        placed.push(Placed {
            order: best_order,
            tiebreak,
            desc,
            info: talk_infos
                .get(talk_id)
                .ok_or_else(|| anyhow!("talk {talk_id} has no info"))?
                .clone(),
            is_lead_in,
        });
    }

    // A subQuest whose objective text is usable but that no talk *completes*
    // becomes a non-dialogue objective step — covering subQuests with no
    // talk, ones whose only (FINISH_PLOT) talk relocated, and ones hosting
    // only lead-ins, so the step keeps its objective line instead of
    // vanishing with the talk.
    let owning_orders: FxHashSet<i64> = placed
        .iter()
        .filter(|p| !p.is_lead_in)
        .map(|p| p.order)
        .collect();
    let objective_steps: Vec<(i64, usize, Option<String>)> = order_to_desc
        .iter()
        .enumerate()
        .filter(|(_, (order, desc))| desc.is_some() && !owning_orders.contains(order))
        .map(|(seq, (order, desc))| (*order, seq, desc.clone()))
        .collect();

    // Interleave talk and objective steps by `order`. Within one order,
    // lead-ins (group 0) precede the completing talk (group 1). Objectives
    // (group 2) arise only from talk-less subQuests, and `order` is unique
    // per quest (checked above), so an objective never shares an order with a
    // talk.
    let mut sortable: Vec<(i64, i64, usize, QuestStep)> = Vec::new();
    for p in placed {
        if p.info.text.is_empty() {
            continue;
        }
        sortable.push((
            p.order,
            if p.is_lead_in { 0 } else { 1 },
            p.tiebreak,
            QuestStep {
                order: p.order,
                is_lead_in: p.is_lead_in,
                description: p.desc,
                talk: Some(p.info),
            },
        ));
    }
    for (order, seq, desc) in objective_steps {
        sortable.push((
            order,
            2,
            seq,
            QuestStep {
                order,
                is_lead_in: false,
                description: desc,
                talk: None,
            },
        ));
    }
    sortable.sort_by_key(|(order, group, seq, _)| (*order, *group, *seq));
    let steps: Vec<QuestStep> = sortable.into_iter().map(|(_, _, _, s)| s).collect();

    // Exclude dev/test/hidden quests (by their own title, or by belonging to
    // a dev/test chapter). Checked after the talks above are resolved (which
    // marks them accessed) so this quest's dialogue is also kept out of the
    // standalone agd_talk pass, not just out of agd_quest.
    if is_test_or_hidden_title(repo, scope, title_hash)? || hidden_chapter {
        return Ok(None);
    }

    // FreeGroup "free talks" attached to this quest by talkId numbering
    // (paths arrive pre-sorted by talkId); rendered in a separate section.
    let mut associated_free_talks: Vec<TalkInfo> = Vec::new();
    for path in repo
        .parse
        .free_group_quest_to_paths
        .get(&quest_id)
        .into_iter()
        .flatten()
    {
        let info = talk::get_talk_info(repo, scope, path)?;
        if !info.text.is_empty() {
            associated_free_talks.push(info);
        }
    }

    Ok(Some(QuestInfo {
        quest_id,
        title: quest_title,
        chapter_title,
        group_name,
        description,
        steps,
        non_subquest_talks,
        associated_free_talks,
    }))
}

/// Quests pass discovery: main quest ids sorted as STRINGS.
pub fn discover(repo: &Repo) -> Result<Vec<i64>> {
    let mut ids: Vec<i64> = repo.excel.main_quest.keys().copied().collect();
    ids.sort_by_key(|id| id.to_string());
    Ok(ids)
}

/// Quests pass process: skip quests with no talk-bearing steps.
pub fn process(repo: &Repo, scope: &Scope, quest_id: i64) -> Result<Option<RenderedItem>> {
    let Some(quest_info) = get_quest_info(repo, scope, quest_id)? else {
        return Ok(None);
    };
    if !quest_info.steps.iter().any(|s| s.talk.is_some())
        && quest_info.non_subquest_talks.is_empty()
    {
        return Ok(None);
    }
    Ok(Some(render_quest(repo, scope, &quest_info)?))
}

pub fn render_quest(repo: &Repo, scope: &Scope, quest: &QuestInfo) -> Result<RenderedItem> {
    let safe_title = util::make_safe_filename_part(&quest.title);
    let filename = format!("{}_{safe_title}.txt", quest.quest_id);

    let mut content_lines: Vec<String> = Vec::new();
    if let Some(group_name) = &quest.group_name {
        content_lines.push(format!("(Quest is part of group: {group_name})\n"));
    }
    if let Some(chapter_title) = &quest.chapter_title
        && !chapter_title.is_empty()
    {
        content_lines.push(format!("(Quest is part of chapter: {chapter_title})\n"));
    }
    content_lines.push(format!("# {}\n", quest.title));
    if let Some(description) = &quest.description
        && !description.is_empty()
    {
        content_lines.push(format!("{description}\n"));
    }

    // Render quest progression steps in `order`. Talk steps show their
    // dialogue under a `## Talk <order>` header (lead-ins placed via
    // beginCond marked as such); non-dialogue objective steps show only their
    // objective text under a `## Objective <order>` header. When several
    // completing talks finish the same subQuest `order` (alternative branches
    // of one step), `## Talk <order>` alone would repeat; number them
    // `(variant N)` to keep headers unique. Lead-ins keep their own suffix.
    let mut variants_per_order: FxHashMap<i64, i64> = FxHashMap::default();
    for step in &quest.steps {
        if step.talk.is_some() && !step.is_lead_in {
            *variants_per_order.entry(step.order).or_insert(0) += 1;
        }
    }
    let mut variant_seen: FxHashMap<i64, i64> = FxHashMap::default();
    for step in &quest.steps {
        if let Some(talk_info) = &step.talk {
            let suffix = if step.is_lead_in {
                " (alternative/additional)".to_string()
            } else if variants_per_order.get(&step.order).copied().unwrap_or(0) > 1 {
                let seen = variant_seen.entry(step.order).or_insert(0);
                *seen += 1;
                format!(" (variant {seen})")
            } else {
                String::new()
            };
            content_lines.push(format!("\n## Talk {}{suffix}\n", step.order));
            if let Some(desc) = &step.description {
                content_lines.push(format!("({desc})\n"));
            }
            content_lines.extend(talk::render_talk_content(talk_info, scope)?);
        } else {
            content_lines.push(format!("\n## Objective {}\n", step.order));
            if let Some(desc) = &step.description {
                content_lines.push(format!("({desc})\n"));
            }
        }
    }

    if !quest.non_subquest_talks.is_empty() {
        content_lines.push("\n## Additional Conversations\n".to_string());
        content_lines.push("*Conversations not present as sub-quests.*\n".to_string());
        for (i, talk_info) in quest.non_subquest_talks.iter().enumerate() {
            if quest.non_subquest_talks.len() > 1 {
                content_lines.push(format!("\n### Additional Talk {}\n", i + 1));
            }
            content_lines.extend(talk::render_talk_content(talk_info, scope)?);
        }
    }

    if !quest.associated_free_talks.is_empty() {
        content_lines.push("\n## Associated Free Talks\n".to_string());
        content_lines.push("*Free talks linked to this quest by talk id.*\n".to_string());
        for (i, talk_info) in quest.associated_free_talks.iter().enumerate() {
            if quest.associated_free_talks.len() > 1 {
                content_lines.push(format!("\n### Free Talk {}\n", i + 1));
            }
            content_lines.extend(talk::render_talk_content(talk_info, scope)?);
        }
    }

    let versions = repo
        .first_seen
        .resolve_int(Domain::MainQuest, quest.quest_id)?;
    Ok(RenderedItem::new(
        "agd_quest",
        quest.title.clone(),
        quest.quest_id,
        filename,
        versions,
        content_lines.join("\n"),
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn common_prefix_name_cases() {
        for (titles, expected) in [
            // CHS ·-separated ordinals.
            (
                vec!["山中好长日·序章 魔山", "山中好长日·第一章 天堂"],
                Some("山中好长日"),
            ),
            // Space-separated CHS ordinals.
            (
                vec!["森林书 第一章 林中奇遇", "森林书 第二章 梦中的苗圃"],
                Some("森林书"),
            ),
            // Roman numerals are prefix-closed (I/II); cut at the strong separator.
            (
                vec![
                    "Aranyaka: Part I Woodland Encounter",
                    "Aranyaka: Part II Dream Nursery",
                ],
                Some("Aranyaka"),
            ),
            // Divergence right at the separator (with/without colon) needs no cut.
            (
                vec![
                    "Canticles of Harmony Prelude Petrichorror Dream",
                    "Canticles of Harmony: Finale Requiem",
                ],
                Some("Canticles of Harmony"),
            ),
            // No strong separator: cut back to the last non-alphanumeric character.
            (
                vec![
                    "欢夏！邪龙？童话国！第一页 A",
                    "欢夏！邪龙？童话国！第二页 B",
                ],
                Some("欢夏！邪龙？童话国！"),
            ),
            // Hyphen works as a strong separator too.
            (
                vec![
                    "Fabulous Fungus Frenzy - Act I X",
                    "Fabulous Fungus Frenzy - Act II Y",
                ],
                Some("Fabulous Fungus Frenzy"),
            ),
            // Nothing in common.
            (
                vec!["夏活 夏活beta测试任务", "绘夏！烈日？度假村！其一 C"],
                None,
            ),
        ] {
            let titles: Vec<String> = titles.iter().map(|s| s.to_string()).collect();
            assert_eq!(
                common_prefix_name(&titles),
                expected.map(str::to_string),
                "{titles:?}"
            );
        }
    }
}
