//! AGD text-corpus generation (`generate-all` and the first-seen index
//! builder) for CHS and ENG.

pub mod cleanup;
pub mod coop;
pub mod deob;
pub mod firstseen;
pub mod firstseen_build;
pub mod generate;
pub mod git;
pub mod hierarchy;
pub mod issues;
pub mod lang;
pub mod renderables;
pub mod rendered_item;
pub mod repo;
pub mod stats;
pub mod talkparse;
pub mod textmap;
pub mod util;
pub mod vh;
