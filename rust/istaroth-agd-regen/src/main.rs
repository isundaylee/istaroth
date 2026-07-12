//! CLI entry point: `generate-all` (the corpus regen) and `build-first-seen`
//! (the first-seen version index builder).

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use istaroth_agd_regen::{firstseen_build, generate, lang};
use mimalloc::MiMalloc;
use std::path::PathBuf;

#[global_allocator]
static GLOBAL: MiMalloc = MiMalloc;

#[derive(Parser)]
#[command(about = "Istaroth AGD corpus generation")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Generate the full text corpus into OUTPUT_DIR (language from
    /// AGD_LANGUAGE, default CHS).
    GenerateAll {
        output_dir: PathBuf,
        /// Delete existing AGD-owned output in OUTPUT_DIR first.
        #[arg(short, long)]
        force: bool,
        /// Print load-phase timing details.
        #[arg(short, long)]
        verbose: bool,
        /// Exit 0 even when some items failed to generate (default: exit 1 on
        /// any error).
        #[arg(long)]
        allow_errors: bool,
    },
    /// Build or update the first-seen version index.
    BuildFirstSeen {
        /// Rebuild the index from scratch instead of appending the new build.
        #[arg(long)]
        rebuild_all: bool,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let agd_path = PathBuf::from(std::env::var("AGD_PATH").context("AGD_PATH not set")?);
    let first_seen_dir = PathBuf::from(
        std::env::var("FIRST_SEEN_DIR").unwrap_or_else(|_| "text/first_seen".to_string()),
    );

    match cli.command {
        Command::GenerateAll {
            output_dir,
            force,
            verbose,
            allow_errors,
        } => {
            let language_str = std::env::var("AGD_LANGUAGE").unwrap_or_else(|_| "CHS".to_string());
            let language = lang::Language::from_value(&language_str)
                .with_context(|| format!("unsupported AGD_LANGUAGE {language_str}"))?;
            generate::generate_all(
                &agd_path,
                &first_seen_dir,
                &output_dir,
                language,
                force,
                verbose,
                allow_errors,
            )
        }
        Command::BuildFirstSeen { rebuild_all } => {
            let t0 = std::time::Instant::now();
            firstseen_build::build_first_seen(&agd_path, &first_seen_dir, rebuild_all)?;
            eprintln!(
                "build-first-seen done in {:.2}s",
                t0.elapsed().as_secs_f64()
            );
            Ok(())
        }
    }
}
