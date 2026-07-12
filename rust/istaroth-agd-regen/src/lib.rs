//! Rust port of `scripts/agd_tools.py generate-all` (and the first-seen index
//! builder), producing byte-identical output to the Python CHS pipeline.

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
pub mod pyset;
pub mod renderables;
pub mod rendered_item;
pub mod repo;
pub mod stats;
pub mod talkparse;
pub mod textmap;
pub mod util;
pub mod vh;
