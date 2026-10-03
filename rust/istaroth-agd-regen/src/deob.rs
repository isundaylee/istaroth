//! Port of istaroth.agd.deobfuscation: obfuscated-key renames over JSON values.

use crate::defaults::{self, FieldDefault};
use anyhow::{Result, bail};
use serde_json::{Map, Value};
use std::collections::HashMap;
use std::sync::LazyLock;

static COMMON: LazyLock<HashMap<&'static str, &'static str>> = LazyLock::new(|| {
    HashMap::from([
        ("JOLEJEFDNJJ", "id"),
        ("FJIMHCGKKPJ", "id"),
        ("DLPKBOPINEE", "descTextMapHash"),
        ("HMPOGBDMBOK", "titleTextMapHash"),
        ("NKEKKINIKEB", "chapterId"),
        ("BMCONAJCMAK", "subQuests"),
        ("DCHHEHNNEOO", "talks"),
        ("DMIMNILOLKP", "talks"),
        ("FKJCGCAMNEH", "subId"),
        ("JDCNDABFDFP", "order"),
        ("PDFCHAAMEHA", "talkId"),
        ("IKCBIFLCCOH", "dialogList"),
        ("DBIHEJMJCMK", "talkContentTextMapHash"),
        ("BCBFGKALICJ", "talkRole"),
        ("IJOEEMHDLHF", "talkRoleNameTextMapHash"),
        ("PGCNMMEBDIE", "npcId"),
        ("ELEPNLBFNOP", "npcId"),
        ("DANPPPLPAEE", "configId"),
        ("JEMDGACPOPC", "configId"),
        ("CLNOODHDADD", "configId"),
        ("JCFGGIACLFH", "groupId"),
        ("FHNJHCFCADD", "questId"),
        ("GCABNOAOIFL", "CUSTOM_addlLocalID"),
        ("PFAJMABJOFK", "CUSTOM_addlLocalID"),
        ("JLLIMLALADN", "nextDialogs"),
        ("_type", "type"),
        ("_id", "_id"),
        ("id", "id"),
        // OSRELWin4.3.0_R19706476_S19529137_D19702261
        ("CCFPGAKINNB", "id"),
        ("PCNNNPLAEAI", "talks"),
        ("JDOFKFPHIDC", "npcId"),
        // OSRELWin6.3.0_R41701329_S41708913_D41667700
        ("ILHDNJDDEOP", "id"),
        ("CBBBCAKOFGO", "descTextMapHash"),
        ("MMOEEOFGHHG", "titleTextMapHash"),
        ("IBNCKLKHAKG", "chapterId"),
        ("GFLHMKOOHHA", "subQuests"),
        ("IBEGAHMEABP", "talks"),
        ("KCMPGABPPOD", "subId"),
        ("AOOILFKIPDJ", "order"),
        ("KINCAGMDMHH", "npcId"),
        ("OAOCMNEPKOG", "questId"),
        ("ADHLLDAPKCM", "talkId"),
        ("MOEOFGCKILF", "dialogList"),
        ("GABLFFECBDO", "talkContentTextMapHash"),
        ("LCECPDILLEE", "talkRole"),
        ("OBKPGBMNDJF", "configId"),
        // CNRELWin6.4.0_R42630645_S42523468_D42623923
        ("BLKKAMEMBBJ", "id"),
        ("OCMKKHHNKJO", "descTextMapHash"),
        ("DMLOMLNJCNA", "titleTextMapHash"),
        ("KDKGIPFDENG", "chapterId"),
        ("NLCNGJKMAEN", "subQuests"),
        ("DGJMIPFDEOF", "talks"),
        ("MPKBGPAKIOA", "subId"),
        ("EDICBFEMNNF", "order"),
        ("HOKOLLABBGP", "questId"),
        ("CAKFHGJGEEK", "npcId"),
        ("LBPGKDMGFBN", "talkId"),
        ("LOJEOMAPIIM", "dialogList"),
        ("CMKPOJOEHHA", "talkContentTextMapHash"),
        ("PELBMPLIEKC", "talkRoleNameTextMapHash"),
        ("HJIPOJOECIF", "talkRole"),
        ("EOFLGOBJBCG", "configId"),
        // OSRELWin6.5.0_R43466102_S43178437_D43466102
        ("HFIMFOOGLLF", "activityId"),
        ("NFIEHACCECI", "id"),
        ("AJGGCMPLKHK", "descTextMapHash"),
        ("BPNEONFJEEO", "titleTextMapHash"),
        ("BALAIBAGIEL", "chapterId"),
        ("MEGJPCLADOG", "subQuests"),
        ("NFFIGDHFAJG", "talks"),
        ("KKMJBEPGLGD", "subId"),
        ("DGINIFCGMGL", "order"),
        ("NIBKFBCGDGM", "questId"),
        ("GFFJADIFFGO", "npcId"),
        ("AADKDKPMGNO", "talkId"),
        ("GALIDJOEHOC", "dialogList"),
        ("AIGJBMCHCJG", "talkContentTextMapHash"),
        ("BMFGJJJPBBC", "talkRoleNameTextMapHash"),
        ("PIBKEGJOJHN", "talkRole"),
        ("GBLICFDCPCK", "nextDialogs"),
        ("JJCCNELFGMF", "configId"),
        // CNRELWin6.6.0_R44873995_S44916582_D44916582
        ("LBCEBBMAHEI", "activityId"),
        ("GMOMCKNPBGE", "id"),
        ("JDFENJAFCPF", "descTextMapHash"),
        ("ALLMCLJBBDM", "titleTextMapHash"),
        ("DMKHKJJFOAA", "chapterId"),
        ("IKECHKLEFFK", "subQuests"),
        ("CIAOBJHFJJM", "talks"),
        ("LAFBPKMMBHD", "subId"),
        ("EDPMKKJIKCJ", "order"),
        ("LFCEBJOANIJ", "questId"),
        ("NJNLKKMFCDF", "npcId"),
        ("KAGCBAHODIP", "beginCond"),
        ("KFCNJPJOJLA", "talkId"),
        ("IOEDPLCPFFB", "dialogList"),
        ("HJJLLECCCPI", "talkContentTextMapHash"),
        ("GMENEADIGBP", "talkRoleNameTextMapHash"),
        ("DGGDDIMMIDO", "talkRole"),
        ("JDAPCNPEAEH", "nextDialogs"),
        ("JPCHNCNMMBE", "configId"),
        ("BMLKAELPLNA", "groupId"),
        ("CPAPOLIHGCN", "CUSTOM_addlLocalID"),
        ("PGELADPAKLA", "finishCond"),
        // NOTE: `damageRatio` is the (misleading) cleartext name used by the older
        // 4.8-5.8 AGD dumps; the field is actually the generic enum `_type` reused
        // across finishCond/failCond/guide/exec and even the talk/quest root, not a
        // damage ratio. Kept as-is to match those cleartext dumps.
        ("MEGMIMEDODJ", "damageRatio"),
        ("KFDJJBPNIHG", "param"),
        ("EIOBNIHPLNG", "count"),
        // 6.x-only finishCond string param (e.g. COMPLETE_ANY_TALK's talk-id list);
        // no cleartext lineage name exists, so use the CUSTOM_ convention.
        ("PGEONGPJEPN", "CUSTOM_paramStr"),
        // CNRELWin6.6.0 Coop story graph (BinOutput/Coop/Coop*.json) node-graph fields.
        // `coopNodeType` values are already cleartext enums (COOP_NODE_TALK/SELECT/END);
        // a TALK node's `coopNodeId` equals the local talk id, so `talkConfig` is unused.
        ("NGKBJGGOPEG", "coopInteractionMap"),
        ("CEKCHKLHGFL", "coopMap"),
        ("KNDKMMOMHOG", "startNodeId"),
        ("DACOOAMDHDE", "coopNodeId"),
        ("HMLLJAMHHHG", "coopNodeType"),
        ("MPEMBNCPNJO", "nextNodeArray"),
        ("ICBFHNOKIDE", "selectList"),
        ("LNKEDDLBLEP", "dialogId"),
        // CNRELWin6.6.0 Coop COND/SELECT/END node sub-fields.
        // COND node: coopCondGrp is the routing predicate with nested conds.
        ("AJBJJLPHHOH", "coopCondGrp"),
        ("ONIPBCHBDBF", "condCombType"),
        ("POJHMDGHNLM", "coopCondList"),
        // NOTE: `DLPKMDPABFM -> type` collides with the `_type -> type` entry above,
        // but no single dict carries both (`_type` is on finishCond items,
        // `DLPKMDPABFM` on coopCondList items), so the collision is safe.
        ("DLPKMDPABFM", "type"),
        ("IEKGEJMAOCN", "param"),
        // SELECT option-level showCond/enableCond (cond-groups that gate visibility).
        ("DDBMPGNIHFD", "showCond"),
        ("OPDLPCGPPIL", "enableCond"),
        // END node: the ending/save-point id.
        ("AOOCCGGPPAI", "savePointId"),
        // DialogExcelConfigData dialog id (its other text fields are already cleartext).
        ("GFLDJMJKIKE", "id"),
        // CNRELWin6.7.0_R45768959_S45393582_D45767575. Some Talk/Npc files still use
        // the reshuffled Quest-family dialog schema below (mixed with older-scheme
        // files in the same directory); NpcGroup's own talks-item schema, Coop, and
        // DialogExcelConfigData were untouched this build and still resolve via
        // earlier-version keys.
        ("ANKFNLMKOII", "id"),
        ("BMEACBBPBGK", "descTextMapHash"),
        ("OCCBMCOGDOO", "titleTextMapHash"),
        ("HONEAMECBEN", "chapterId"),
        ("HLCINEMBGEF", "subQuests"),
        ("OBPMJEILMMK", "talks"),
        ("NDOFAOCKPGE", "subId"),
        ("IFDFNEFMPIK", "order"),
        ("LALLFKKNJIB", "questId"),
        ("EAEHJOJPIOG", "npcId"),
        ("BLCEJLFCFPH", "beginCond"),
        ("KEDNDKJHLJF", "configId"),
        ("DLCAICCLBOD", "groupId"),
        ("OKGAHCPMLON", "activityId"),
        ("FCBEKGAHMPD", "finishCond"),
        ("BPEHONLLNNK", "damageRatio"),
        ("PALPAGCBFDI", "param"),
        ("KEHDEPAALMP", "count"),
        ("GFIAGOPKHAK", "CUSTOM_paramStr"),
        // BinOutput/Talk/Quest and some Talk/Npc/Talk/Gadget files (shares the
        // reshuffled Quest scheme).
        ("LDLMECNIJFC", "talkId"),
        ("GDDPNNHLGBL", "dialogList"),
        ("OMAHHDBCAPB", "nextDialogs"),
        ("EENIFNIGHCH", "talkRole"),
        ("DMIFDJDEFAL", "talkContentTextMapHash"),
        ("GBLIAGAIAAK", "talkRoleNameTextMapHash"),
        // ExcelBinOutput/DocumentExcelConfigData.json page-2 localization id (rotates
        // every build; see the CUSTOM_addlLocalID note on the earlier version blocks).
        ("GBAHMGGAMGH", "CUSTOM_addlLocalID"),
        // CNRELWin7.0.0_R47194594_S46814653_D47194594
        ("OIFGMOHKPOI", "id"),
        ("OANENPOPCFO", "descTextMapHash"),
        ("LKAHEACOLML", "titleTextMapHash"),
        ("BEADANLODNC", "chapterId"),
        ("EBNBLBEIFFJ", "subQuests"),
        ("OJACLOOEAMG", "talks"),
        ("KCGAKLCHDCC", "subId"),
        ("EMNMIOBCCLL", "order"),
        ("EPGEOMCHIJF", "questId"),
        ("BMFEMALEAIO", "npcId"),
        ("FCBOEAHDNOL", "beginCond"),
        ("OAENEGDKPNB", "configId"),
        ("OOIJCIKMBOJ", "groupId"),
        ("FAJAGGKJICO", "activityId"),
        ("ANBEKNMDKCH", "finishCond"),
        ("ALBFHGKNMLK", "damageRatio"),
        ("OPDGHDAADJC", "param"),
        ("LIKEIGNEHNP", "count"),
        ("DPMLKCPEIJD", "CUSTOM_paramStr"),
        ("IOKNFDJFGDH", "talkId"),
        ("PFALHAKIILD", "dialogList"),
        ("KMLAFCBMFEI", "nextDialogs"),
        ("LFGCLNLPAPB", "talkRole"),
        ("OACNIBLFFDI", "talkContentTextMapHash"),
        ("ACCOJJPKFCN", "talkRoleNameTextMapHash"),
        ("CGGHOCIFBPC", "CUSTOM_addlLocalID"),
        // CNRELWin7.1.0_R48379043_S48511369_D48533839
        ("NBOJMAHCCGM", "descTextMapHash"),
        ("DOOCLIPFECE", "titleTextMapHash"),
        ("JIJKODHIEED", "subQuests"),
        ("DLLABGGCEBM", "talks"),
        ("NFGFDHPPBIF", "subId"),
        ("GBFIFKGFKHD", "order"),
        ("GCNCAGHDDOJ", "npcId"),
        ("JEDNDGCOMGC", "beginCond"),
        ("NJLNCONMABL", "configId"),
        ("JBELGECAIIL", "CUSTOM_paramStr"),
        ("PCIAMAFDDAA", "dialogList"),
        ("GLJCECCOEDP", "nextDialogs"),
        ("KBPOBGFGLKN", "talkRole"),
        ("LKECPJIFFEE", "talkContentTextMapHash"),
        ("DPHNNJJCFAN", "talkRoleNameTextMapHash"),
        ("PDNGBPKLELB", "CUSTOM_addlLocalID"),
        ("DGAIPHFGBOD", "loadType"),
    ])
});

static ANECDOTE: LazyLock<HashMap<&'static str, &'static str>> = LazyLock::new(|| {
    HashMap::from([
        // CNRELWin6.7.0_R45768959_S45393582_D45767575
        ("GIJOCHMAJCI", "id"),
        ("AEEMNELFAIO", "questIds"),
        ("EHGEFIODFHD", "titleTextMapHash"),
        ("NIKLGDFJAJK", "teaserTextMapHash"),
        ("OBJANDCNDMA", "descTextMapHash"),
        // CNRELWin7.0.0_R47194594_S46814653_D47194594
        ("KKNGMIGLAOM", "id"),
        ("OPLIDDEJLDL", "questIds"),
        ("PFMAHKBHBAB", "titleTextMapHash"),
        ("NAEFBAELNJM", "teaserTextMapHash"),
        ("JKOECCLJMHB", "descTextMapHash"),
        // CNRELWin7.1.0_R48379043_S48511369_D48533839
        ("JJDBNNAJGAA", "id"),
        ("KOOFDCNNHGP", "questIds"),
        ("NLBLEOBAOAJ", "titleTextMapHash"),
        ("JKPOEFMNLAJ", "teaserTextMapHash"),
        ("MBPANALDEMH", "descTextMapHash"),
    ])
});

type ArrayProc = fn(Vec<Value>) -> Result<Vec<Value>>;

fn deob_map(
    data: Value,
    mappings: &HashMap<&'static str, &'static str>,
    array_processors: &[(&str, ArrayProc)],
) -> Result<Value> {
    let Value::Object(obj) = data else {
        return Ok(data);
    };
    let mut result = Map::with_capacity(obj.len());
    for (key, mut value) in obj {
        let real_key = mappings.get(key.as_str()).copied().unwrap_or(&key);
        if let Some((_, proc)) = array_processors.iter().find(|(k, _)| *k == real_key) {
            let Value::Array(items) = value else {
                bail!("{real_key} must be a list");
            };
            value = Value::Array(proc(items)?);
        }
        if result.insert(real_key.to_string(), value).is_some() {
            bail!("duplicate deobfuscated field {real_key}");
        }
    }
    Ok(Value::Object(result))
}

fn process_array_items(items: Vec<Value>) -> Result<Vec<Value>> {
    items
        .into_iter()
        .map(|i| deob_map(i, &COMMON, &[]))
        .collect()
}

// These schemas apply after deobfuscation, including older dumps with explicit defaults.
const QUEST_DEFAULTS: &[(&str, FieldDefault)] = &[
    ("titleTextMapHash", FieldDefault::Int(0)),
    ("descTextMapHash", FieldDefault::Int(0)),
    ("chapterId", FieldDefault::Int(0)),
    ("subQuests", FieldDefault::Array),
    ("talks", FieldDefault::Array),
];
const SUBQUEST_DEFAULTS: &[(&str, FieldDefault)] = &[
    ("descTextMapHash", FieldDefault::Int(0)),
    ("order", FieldDefault::Int(0)),
    ("finishCond", FieldDefault::Array),
];
const TALK_DEFAULTS: &[(&str, FieldDefault)] = &[("beginCond", FieldDefault::Array)];
const BEGIN_COND_DEFAULTS: &[(&str, FieldDefault)] = &[("_param", FieldDefault::Array)];
const DIALOG_DEFAULTS: &[(&str, FieldDefault)] = &[
    ("talkContentTextMapHash", FieldDefault::Int(0)),
    ("talkRoleNameTextMapHash", FieldDefault::Int(0)),
];
const ROLE_DEFAULTS: &[(&str, FieldDefault)] = &[("type", FieldDefault::String("TALK_ROLE_NONE"))];

fn rename_field(data: &mut Value, source: &str, target: &str) -> Result<()> {
    if let Some(obj) = data.as_object_mut()
        && let Some(value) = obj.remove(source)
        && obj.insert(target.to_string(), value).is_some()
    {
        bail!("duplicate field {target}");
    }
    Ok(())
}

fn process_finish_items(items: Vec<Value>) -> Result<Vec<Value>> {
    process_array_items(items)?
        .into_iter()
        .map(|mut item| {
            rename_field(&mut item, "type", "damageRatio")?;
            Ok(item)
        })
        .collect()
}

fn process_begin_items(items: Vec<Value>) -> Result<Vec<Value>> {
    items
        .into_iter()
        .map(|mut item| {
            rename_field(&mut item, "type", "_type")?;
            rename_field(&mut item, "param", "_param")?;
            defaults::apply(&mut item, BEGIN_COND_DEFAULTS)?;
            Ok(item)
        })
        .collect()
}

fn process_talk_items(items: Vec<Value>) -> Result<Vec<Value>> {
    items
        .into_iter()
        .map(|item| {
            let mut item = deob_map(item, &COMMON, &[("beginCond", process_begin_items)])?;
            defaults::apply(&mut item, TALK_DEFAULTS)?;
            Ok(item)
        })
        .collect()
}

fn process_subquest_items(items: Vec<Value>) -> Result<Vec<Value>> {
    items
        .into_iter()
        .map(|i| {
            let mut item = deob_map(i, &COMMON, &[("finishCond", process_finish_items)])?;
            defaults::apply(&mut item, SUBQUEST_DEFAULTS)?;
            Ok(item)
        })
        .collect()
}

fn process_dialog_list(dialogs: Vec<Value>) -> Result<Vec<Value>> {
    dialogs
        .into_iter()
        .map(|d| {
            let mut d = deob_map(d, &COMMON, &[])?;
            defaults::apply(&mut d, DIALOG_DEFAULTS)?;
            if let Some(obj) = d.as_object_mut()
                && let Some(role) = obj.get("talkRole")
            {
                // A null talkRole is skipped; an object restores the omitted
                // narration type. Anything else is a schema error.
                match role {
                    Value::Null => {}
                    Value::Object(_) => {
                        let role = obj.remove("talkRole").unwrap();
                        let mut role = deob_map(role, &COMMON, &[])?;
                        rename_field(&mut role, "id", "_id")?;
                        defaults::apply(&mut role, ROLE_DEFAULTS)?;
                        obj.insert("talkRole".to_string(), role);
                    }
                    other => bail!("talkRole must be an object, got {other}"),
                }
            }
            Ok(d)
        })
        .collect()
}

pub fn deobfuscate_quest_data(data: Value) -> Result<Value> {
    let mut data = deob_map(
        data,
        &COMMON,
        &[
            ("subQuests", process_subquest_items),
            ("talks", process_talk_items),
        ],
    )?;
    defaults::apply(&mut data, QUEST_DEFAULTS)?;
    Ok(data)
}

/// Combined talk-file deobfuscation: processes both `dialogList` (talk files)
/// and `talks` (group files); a file only ever carries one of the two, so this
/// one pass serves both talk and talk-group loading.
pub fn deobfuscate_talk_file(data: Value) -> Result<Value> {
    deob_map(
        data,
        &COMMON,
        &[
            ("dialogList", process_dialog_list),
            ("talks", process_talk_items),
        ],
    )
}

fn process_cond_grp(cond_grp: Value) -> Result<Value> {
    deob_map(cond_grp, &COMMON, &[("coopCondList", process_array_items)])
}

/// Recurse into an optional cond-grp object field in place; an absent, null,
/// or empty-object value passes through untouched, anything non-object errors.
fn process_cond_field_in_place(obj: &mut Map<String, Value>, key: &str) -> Result<()> {
    match obj.get_mut(key) {
        None | Some(Value::Null) => {}
        Some(Value::Object(m)) if m.is_empty() => {}
        Some(v @ Value::Object(_)) => *v = process_cond_grp(std::mem::take(v))?,
        Some(other) => bail!("{key} must be an object, got {other}"),
    }
    Ok(())
}

fn process_coop_select_items(select_list: Vec<Value>) -> Result<Vec<Value>> {
    select_list
        .into_iter()
        .map(|item| {
            let mut d = deob_map(item, &COMMON, &[])?;
            if let Some(obj) = d.as_object_mut() {
                for cond_key in ["showCond", "enableCond"] {
                    process_cond_field_in_place(obj, cond_key)?;
                }
            }
            Ok(d)
        })
        .collect()
}

fn deobfuscate_coop_node(node: Value) -> Result<Value> {
    let mut d = deob_map(node, &COMMON, &[])?;
    if let Some(obj) = d.as_object_mut() {
        match obj.get_mut("selectList") {
            None | Some(Value::Null) => {}
            Some(Value::Array(a)) if a.is_empty() => {}
            Some(Value::Array(items)) => *items = process_coop_select_items(std::mem::take(items))?,
            Some(other) => bail!("selectList must be a list, got {other}"),
        }
        process_cond_field_in_place(obj, "coopCondGrp")?;
    }
    Ok(d)
}

fn deobfuscate_coop_story(story: Value) -> Result<Value> {
    let mut d = deob_map(story, &COMMON, &[])?;
    let Some(obj) = d.as_object_mut() else {
        bail!("coop story must be an object");
    };
    let Some(coop_map) = obj.remove("coopMap") else {
        bail!("coopMap required");
    };
    let Value::Object(coop_map) = coop_map else {
        bail!("coopMap must be an object");
    };
    let processed: Result<Map<String, Value>> = coop_map
        .into_iter()
        .map(|(node_id, node)| Ok((node_id, deobfuscate_coop_node(node)?)))
        .collect();
    obj.insert("coopMap".to_string(), Value::Object(processed?));
    Ok(d)
}

pub fn deobfuscate_coop_graph_data(data: Value) -> Result<Value> {
    let mut top = deob_map(data, &COMMON, &[])?;
    let Some(obj) = top.as_object_mut() else {
        bail!("coop graph must be an object");
    };
    let Some(interaction) = obj.remove("coopInteractionMap") else {
        bail!("coopInteractionMap required");
    };
    let Value::Object(interaction) = interaction else {
        bail!("coopInteractionMap must be an object");
    };
    let processed: Result<Map<String, Value>> = interaction
        .into_iter()
        .map(|(story_id, story)| Ok((story_id, deobfuscate_coop_story(story)?)))
        .collect();
    obj.insert("coopInteractionMap".to_string(), Value::Object(processed?));
    Ok(top)
}

/// Resolve a wire field name through the common rename map (identity if unmapped).
pub fn resolve_field_name(key: &str) -> &str {
    COMMON.get(key).copied().unwrap_or(key)
}

pub fn deobfuscate_document_excel_config_data(data: Vec<Value>) -> Result<Vec<Value>> {
    process_array_items(data)
}

pub fn deobfuscate_anecdote_excel_config_data(data: Vec<Value>) -> Result<Vec<Value>> {
    data.into_iter()
        .map(|i| deob_map(i, &ANECDOTE, &[]))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn cleartext_quest_defaults_and_condition_aliases() {
        let data = deobfuscate_quest_data(json!({
            "id": 74078,
            "subQuests": [{
                "subId": 7407801,
                "finishCond": [{"type": "QUEST_CONTENT_COMPLETE_TALK", "param": [7407801, 0]}],
            }],
            "talks": [
                {"id": 7407801},
                {"id": 7407802, "beginCond": [
                    {"type": "QUEST_COND_STATE_EQUAL", "param": ["7407801", "2"]},
                    {"type": "QUEST_COND_STATE_EQUAL"},
                ]},
            ],
        }))
        .unwrap();
        assert_eq!(data["chapterId"], 0);
        assert_eq!(data["subQuests"][0]["descTextMapHash"], 0);
        assert_eq!(
            data["subQuests"][0]["finishCond"][0]["damageRatio"],
            "QUEST_CONTENT_COMPLETE_TALK"
        );
        assert_eq!(data["talks"][0]["beginCond"], json!([]));
        assert_eq!(
            data["talks"][1]["beginCond"][0],
            json!({"_type": "QUEST_COND_STATE_EQUAL", "_param": ["7407801", "2"]})
        );
        assert_eq!(data["talks"][1]["beginCond"][1]["_param"], json!([]));
    }

    #[test]
    fn cleartext_dialog_preserves_narration_and_rejects_invalid_fields() {
        for role in [json!({}), json!({"id": ""})] {
            let data = deobfuscate_talk_file(json!({
                "talkId": 1,
                "dialogList": [{"id": 101, "talkRole": role}],
            }))
            .unwrap();
            assert_eq!(data["dialogList"][0]["talkRole"]["type"], "TALK_ROLE_NONE");
            assert_eq!(data["dialogList"][0]["talkContentTextMapHash"], 0);
        }
        for invalid in [Value::Null, json!("123"), json!([])] {
            assert!(
                deobfuscate_talk_file(json!({
                    "dialogList": [{"id": 101, "talkRole": {}, "talkContentTextMapHash": invalid}],
                }))
                .is_err()
            );
        }
        assert!(
            deobfuscate_quest_data(json!({"JIJKODHIEED": [{"NFGFDHPPBIF": 1, "finishCond": {}}]}))
                .is_err()
        );
        assert!(
            deobfuscate_quest_data(
                json!({"DLLABGGCEBM": [{"JEDNDGCOMGC": [{"type": "A", "_type": "B"}]}]})
            )
            .is_err()
        );
    }

    #[test]
    fn cleartext_arrays_still_process_nested_obfuscated_fields() {
        let data = deobfuscate_quest_data(json!({
            "subQuests": [{"subId": 1, "finishCond": [{"JBELGECAIIL": "123", "type": "QUEST_CONTENT_COMPLETE_ANY_TALK"}]}],
        })).unwrap();
        assert_eq!(
            data["subQuests"][0]["finishCond"][0]["CUSTOM_paramStr"],
            "123"
        );
        assert_eq!(
            data["subQuests"][0]["finishCond"][0]["damageRatio"],
            "QUEST_CONTENT_COMPLETE_ANY_TALK"
        );
    }

    #[test]
    fn coop_cond_node() {
        let deobf = deobfuscate_coop_node(json!({
            "DACOOAMDHDE": 101, // coopNodeId
            "HMLLJAMHHHG": "COOP_NODE_COND",
            "MPEMBNCPNJO": [201, 202],
            "AJBJJLPHHOH": {
                "ONIPBCHBDBF": "LOGIC_AND",
                "POJHMDGHNLM": [
                    {"DLPKMDPABFM": "COOP_COND_QUEST_FINISH", "IEKGEJMAOCN": [1901503]},
                ],
            },
        }))
        .unwrap();
        assert_eq!(deobf["coopNodeId"], 101);
        assert_eq!(deobf["coopNodeType"], "COOP_NODE_COND");
        assert_eq!(deobf["nextNodeArray"], json!([201, 202]));
        assert_eq!(
            deobf["coopCondGrp"],
            json!({
                "condCombType": "LOGIC_AND",
                "coopCondList": [{"type": "COOP_COND_QUEST_FINISH", "param": [1901503]}],
            })
        );
    }

    #[test]
    fn coop_select_node() {
        let deobf = deobfuscate_coop_node(json!({
            "DACOOAMDHDE": 201,
            "HMLLJAMHHHG": "COOP_NODE_SELECT",
            "MPEMBNCPNJO": [301, 302],
            "ICBFHNOKIDE": [
                {
                    "LNKEDDLBLEP": 1001, // dialogId
                    "DDBMPGNIHFD": {"ONIPBCHBDBF": "LOGIC_NONE", "POJHMDGHNLM": []}, // showCond
                },
                {
                    "LNKEDDLBLEP": 1002,
                    "OPDLPCGPPIL": { // enableCond
                        "ONIPBCHBDBF": "LOGIC_AND",
                        "POJHMDGHNLM": [
                            {"DLPKMDPABFM": "COOP_COND_QUEST_FINISH", "IEKGEJMAOCN": [1904714]},
                        ],
                    },
                },
            ],
        }))
        .unwrap();
        let select = deobf["selectList"].as_array().unwrap();
        assert_eq!(select[0]["dialogId"], 1001);
        assert_eq!(select[0]["showCond"]["condCombType"], "LOGIC_NONE");
        assert_eq!(select[0]["showCond"]["coopCondList"], json!([]));
        assert_eq!(select[1]["dialogId"], 1002);
        assert_eq!(select[1]["enableCond"]["condCombType"], "LOGIC_AND");
        assert_eq!(
            select[1]["enableCond"]["coopCondList"],
            json!([{"type": "COOP_COND_QUEST_FINISH", "param": [1904714]}])
        );
    }

    #[test]
    fn coop_end_node() {
        let deobf = deobfuscate_coop_node(json!({
            "DACOOAMDHDE": 401,
            "HMLLJAMHHHG": "COOP_NODE_END",
            "MPEMBNCPNJO": [],
            "AOOCCGGPPAI": 90501, // savePointId
        }))
        .unwrap();
        assert_eq!(deobf["coopNodeId"], 401);
        assert_eq!(deobf["coopNodeType"], "COOP_NODE_END");
        assert_eq!(deobf["savePointId"], 90501);
    }
}
