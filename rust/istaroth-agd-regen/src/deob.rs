//! Port of istaroth.agd.deobfuscation: obfuscated-key renames over JSON values.

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
    if !obj.keys().any(|k| mappings.contains_key(k.as_str())) {
        return Ok(Value::Object(obj));
    }
    let mut result = Map::with_capacity(obj.len());
    for (key, mut value) in obj {
        if let Some(&real_key) = mappings.get(key.as_str()) {
            if let Some((_, proc)) = array_processors.iter().find(|(k, _)| *k == real_key) {
                let Value::Array(items) = value else {
                    bail!("{real_key} must be a list");
                };
                value = Value::Array(proc(items)?);
            }
            result.insert(real_key.to_string(), value);
        } else {
            result.insert(key, value);
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

fn process_subquest_items(items: Vec<Value>) -> Result<Vec<Value>> {
    items
        .into_iter()
        .map(|i| deob_map(i, &COMMON, &[("finishCond", process_array_items)]))
        .collect()
}

fn process_dialog_list(dialogs: Vec<Value>) -> Result<Vec<Value>> {
    dialogs
        .into_iter()
        .map(|d| {
            let mut d = deob_map(d, &COMMON, &[])?;
            if let Some(obj) = d.as_object_mut()
                && let Some(role) = obj.get("talkRole")
            {
                // A falsy talkRole ({}/null) is skipped. A truthy non-object
                // would slip through the rename unprocessed, so reject it
                // rather than mask a schema change.
                if crate::vh::truthy(role) {
                    if !role.is_object() {
                        bail!("talkRole must be an object, got {role}");
                    }
                    let role = obj.remove("talkRole").unwrap();
                    obj.insert("talkRole".to_string(), deob_map(role, &COMMON, &[])?);
                }
            }
            Ok(d)
        })
        .collect()
}

pub fn deobfuscate_quest_data(data: Value) -> Result<Value> {
    deob_map(
        data,
        &COMMON,
        &[
            ("subQuests", process_subquest_items),
            ("talks", process_array_items),
        ],
    )
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
            ("talks", process_array_items),
        ],
    )
}

fn process_cond_grp(cond_grp: Value) -> Result<Value> {
    deob_map(cond_grp, &COMMON, &[("coopCondList", process_array_items)])
}

fn process_coop_select_items(select_list: Vec<Value>) -> Result<Vec<Value>> {
    select_list
        .into_iter()
        .map(|item| {
            let mut d = deob_map(item, &COMMON, &[])?;
            if let Some(obj) = d.as_object_mut() {
                for cond_key in ["showCond", "enableCond"] {
                    let Some(cond) = obj.get(cond_key) else {
                        continue;
                    };
                    if crate::vh::truthy(cond) {
                        if !cond.is_object() {
                            bail!("{cond_key} must be an object, got {cond}");
                        }
                        let cond = obj.remove(cond_key).unwrap();
                        obj.insert(cond_key.to_string(), process_cond_grp(cond)?);
                    }
                }
            }
            Ok(d)
        })
        .collect()
}

fn deobfuscate_coop_node(node: Value) -> Result<Value> {
    let mut d = deob_map(node, &COMMON, &[])?;
    if let Some(obj) = d.as_object_mut() {
        if let Some(sel) = obj.get("selectList")
            && crate::vh::truthy(sel)
        {
            if !sel.is_array() {
                bail!("selectList must be a list, got {sel}");
            }
            let Value::Array(items) = obj.remove("selectList").unwrap() else {
                unreachable!()
            };
            obj.insert(
                "selectList".to_string(),
                Value::Array(process_coop_select_items(items)?),
            );
        }
        if let Some(cond) = obj.get("coopCondGrp")
            && crate::vh::truthy(cond)
        {
            if !cond.is_object() {
                bail!("coopCondGrp must be an object, got {cond}");
            }
            let cond = obj.remove("coopCondGrp").unwrap();
            obj.insert("coopCondGrp".to_string(), process_cond_grp(cond)?);
        }
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
