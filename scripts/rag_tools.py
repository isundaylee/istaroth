#!/usr/bin/env python3
"""RAG tools for document management and querying."""

import datetime
import functools
import json
import logging
import os
import pathlib
import shutil
import statistics
import sys
from collections.abc import Callable
from dataclasses import dataclass

import anyio
import attrs
import click
import tabulate

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import langsmith as ls

from istaroth import llm_manager, logging_utils, utils
from istaroth.agd import localization
from istaroth.rag import budget as _budget
from istaroth.rag import (
    document_store,
    document_store_set,
    output_rendering,
    pipeline,
    prompt_set,
    retrieval_diff,
    text_set,
    types,
)
from istaroth.rag.eval import judge, retrieval
from istaroth.text import manifest

logger = logging.getLogger(__name__)


def _get_files_to_process(text_path: pathlib.Path) -> list[pathlib.Path]:
    """Get a list of .txt files to process from the manifest directory."""
    assert text_path.is_dir(), f"Path {text_path} must be a directory"
    files = []
    for item in manifest.load_manifest_dir(text_path):
        file_path = text_path / item.relative_path
        if not file_path.exists():
            logger.warning("File from manifest does not exist: %s", file_path)
            continue
        files.append(file_path)
    return files


def _load_store() -> tuple[types.Retriever, localization.Language, text_set.TextSet]:
    """Load document store using default language from env config."""
    store_set = document_store_set.DocumentStoreSet.from_env()
    languages = store_set.available_languages
    assert languages, "No document stores configured in ISTAROTH_DOCUMENT_STORE_SET."
    language = languages[0]
    store = store_set.get_store(language)
    ts = store_set.get_text_set(language)
    if store.num_documents > 0:
        logger.info("Loaded store with %d existing documents", store.num_documents)
    return store, language, ts


@click.group()
def cli() -> None:
    """RAG tools for document management and querying."""
    logging_utils.setup_logging()


@cli.command()
@click.argument("text_path", type=pathlib.Path)
@click.argument("checkpoint_path", type=pathlib.Path)
@click.option("-f", "--force", is_flag=True, help="Delete target if it exists")
@click.option(
    "--concurrency", default=8, help="Concurrent embedding requests in flight"
)
def build(
    text_path: pathlib.Path,
    checkpoint_path: pathlib.Path,
    force: bool,
    concurrency: int,
) -> None:
    """Build document store from a file or folder.

    Set ISTAROTH_EMBEDDING_CACHE to a .npz path to reuse embeddings for
    unchanged chunk text across builds.
    """
    # Check if target exists
    if checkpoint_path.exists():
        if not force:
            logger.error(
                "Target %s already exists. Use -f to overwrite.", checkpoint_path
            )
            sys.exit(1)
        else:
            logger.info("Removing existing target: %s", checkpoint_path)
            shutil.rmtree(checkpoint_path)

    files_to_process = _get_files_to_process(text_path)

    if not files_to_process:
        logger.error("No files found in manifest to process.")
        sys.exit(1)

    metadata = json.loads((text_path / "stats" / "agd" / "metadata.json").read_text())

    match localization.Language(metadata["language"]):
        case localization.Language.CHS:
            chunk_size_multiplier = 1.0
        case localization.Language.ENG:
            chunk_size_multiplier = 3.5
        case _:
            raise RuntimeError(f"Unsupported language: {metadata['language']}.")

    logger.info(
        "Building document store from %d files in: %s", len(files_to_process), text_path
    )
    store = document_store.DocumentStore.build(
        files_to_process,
        text_root=text_path,
        chunk_size_multiplier=chunk_size_multiplier,
        concurrency=concurrency,
        show_progress=True,
    )

    logger.info("Total documents in store: %d", store.num_documents)

    checkpoint_path.mkdir(parents=True, exist_ok=True)
    store.save(checkpoint_path)


@cli.command()
@click.argument("query", type=str)
@click.option("-k", "--k", default=5, help="Number of results to return")
@click.option("-c", "--chunk-context", default=5, help="Context size for each chunk")
@click.option("--save", type=pathlib.Path)
def retrieve(
    query: str, *, k: int, chunk_context: int, save: pathlib.Path | None
) -> None:
    """Retrieve similar documents from the document store."""

    with ls.trace(
        "rag_tools_retrieve",
        "chain",
        inputs={"query": query, "k": k, "chunk_context": chunk_context},
    ) as rt:
        store, _, ts = _load_store()

        if store.num_documents == 0:
            logger.error("No documents in store. Use 'add-documents' command first.")
            sys.exit(1)

        logger.info("Searching for: '%s'", query)
        retrieve_output = store.retrieve(query, k=k, chunk_context=chunk_context)

        if not retrieve_output.results:
            logger.info("No results found.")
            return

        formatted_output = output_rendering.render_retrieve_output(
            retrieve_output.results, text_set=ts
        )
        rt.end(
            outputs=retrieve_output.to_langsmith_output(formatted_output, text_set=ts)
        )

        if save is not None:
            save_path = save / (
                datetime.datetime.now().strftime("%Y%m%d_%H%M%S_")
                + utils.make_safe_filename_part(query, max_length=50)
                + ".txt"
            )
            data = retrieve_output.to_dict()
            data["env"] = {
                k: v for k, v in os.environ.items() if k.startswith("ISTAROTH_")
            }
            save_path.write_text(json.dumps(data))

        print(formatted_output)


def _ranked_source_texts(
    store: types.Retriever,
    fixture: retrieval.RetrievalFixture,
    *,
    k: int,
    chunk_context: int,
    bm25: bool,
) -> tuple[list[str], list[str], int]:
    retrieve_output = (
        store.retrieve_bm25(fixture.query, k=k, chunk_context=chunk_context)
        if bm25
        else store.retrieve(fixture.query, k=k, chunk_context=chunk_context)
    )
    texts: list[str] = []
    paths: list[str] = []
    total_chunks = 0
    for _, docs in retrieve_output.results:
        texts.append("\n".join(doc.page_content for doc in docs))
        paths.append(docs[0].metadata["path"])
        total_chunks += len(docs)
    return texts, paths, total_chunks


@dataclass
class _FixtureEval:
    fixture: retrieval.RetrievalFixture
    runs: list[list[str]]
    first_ranks: list[dict[str, int | None]]
    n_sources: list[int]
    n_chunks: list[int]
    coverage: list[int]
    mean_coverage: float
    missed: list[str]


def _analyze_fixture(
    fixture: retrieval.RetrievalFixture,
    texts_list: list[list[str]],
    *,
    n_chunks: list[int],
) -> _FixtureEval:
    first_ranks = [fixture.first_covered_rank(texts) for texts in texts_list]
    n_sources = [len(texts) for texts in texts_list]
    coverage = [len(fixture.coverage_at_k(texts, len(texts))) for texts in texts_list]
    mean_coverage = statistics.mean(coverage)
    missed = [
        f for f in fixture.expected_coverage if all(fr[f] is None for fr in first_ranks)
    ]
    return _FixtureEval(
        fixture=fixture,
        runs=texts_list,
        first_ranks=first_ranks,
        n_sources=n_sources,
        n_chunks=n_chunks,
        coverage=coverage,
        mean_coverage=mean_coverage,
        missed=missed,
    )


async def _afetch_sources(
    store: types.Retriever,
    fixture: retrieval.RetrievalFixture,
    *,
    k: int,
    chunk_context: int,
    repeat: int,
    bm25: bool,
    sem: anyio.Semaphore,
) -> tuple[list[list[str]], list[list[str]], list[int]]:
    texts_list: list[list[str] | None] = [None] * repeat
    paths_list: list[list[str] | None] = [None] * repeat
    chunks_list: list[int | None] = [None] * repeat

    async def _run_once(idx: int) -> None:
        async with sem:
            texts, paths, n_chunks = await anyio.to_thread.run_sync(
                functools.partial(
                    _ranked_source_texts,
                    store,
                    fixture,
                    k=k,
                    chunk_context=chunk_context,
                    bm25=bm25,
                ),
            )
            texts_list[idx] = texts
            paths_list[idx] = paths
            chunks_list[idx] = n_chunks

    async with anyio.create_task_group() as tg:
        for i in range(repeat):
            tg.start_soon(_run_once, i)

    return (
        [t for t in texts_list if t is not None],
        [p for p in paths_list if p is not None],
        [c for c in chunks_list if c is not None],
    )


_MIN_JUDGE_SPAN = 6  # chars; reject over-broad spans that would over-match as anchors

_JudgeFn = Callable[
    [str, list[str], dict[str, str]], tuple[dict[str, str], judge.JudgeUsage]
]


async def _judge_rescue(
    fixture: retrieval.RetrievalFixture,
    texts_list: list[list[str]],
    paths_list: list[list[str]],
    missed: list[str],
    *,
    judge_fn: _JudgeFn,
) -> tuple[list[retrieval.RelevantPassage], judge.JudgeUsage]:
    """Judge missing facets over the union of retrieved sources; return new anchors.

    One judge call per fixture across all runs' sources. Each returned span is
    verified to actually occur in a retrieved source (else it is a hallucination
    and dropped) and turned into an anchor whose ``official`` flag follows the
    source path it was found in.
    """
    # Only facets with a non-empty description are judged; without one there is no
    # reliable statement of what the facet means for the judge to grade against.
    facets = {
        facet: desc for facet in missed if (desc := fixture.expected_coverage[facet])
    }
    if not facets:
        return [], judge.JudgeUsage.zero()
    text_to_path: dict[str, str] = {}
    for texts, paths in zip(texts_list, paths_list):
        for text, path in zip(texts, paths):
            text_to_path.setdefault(text, path)
    union_texts = list(text_to_path)
    spans, usage = await anyio.to_thread.run_sync(
        functools.partial(judge_fn, fixture.query, union_texts, facets)
    )
    new_passages: list[retrieval.RelevantPassage] = []
    for facet, span in spans.items():
        if len("".join(span.split())) < _MIN_JUDGE_SPAN:
            continue
        if (rank := retrieval.locate_span(span, union_texts)) is None:
            continue  # span not actually present → hallucinated, reject
        path = text_to_path[union_texts[rank - 1]]
        new_passages.append(
            retrieval.RelevantPassage(
                passage=span,
                label=f"judge:{path}",
                official=not path.startswith("tps_shishu/"),
                covers=(facet,),
            )
        )
    return new_passages, usage


async def _aeval_fixtures(
    store: types.Retriever,
    fixtures: list[retrieval.RetrievalFixture],
    *,
    budget: int,
    intent_fn: Callable[[str], _budget.QueryIntent],
    repeat: int = 1,
    bm25: bool = False,
    judge_fn: _JudgeFn | None = None,
) -> tuple[list[_FixtureEval], list[tuple[str, str, dict]], judge.JudgeUsage]:
    sem = anyio.Semaphore(5)
    results: list[_FixtureEval | None] = [None] * len(fixtures)
    pending_writes: list[tuple[str, str, dict]] = []
    usages: list[judge.JudgeUsage] = []

    async def _eval_one(idx: int, fixture: retrieval.RetrievalFixture) -> None:
        intent = intent_fn(fixture.query)
        fk, fcc = _budget.allocate(budget, intent)
        print(f"[fixture] {fixture.query} → intent={intent.value} k={fk} cc={fcc}")
        texts_list, paths_list, chunks_list = await _afetch_sources(
            store,
            fixture,
            k=fk,
            chunk_context=fcc,
            repeat=repeat,
            bm25=bm25,
            sem=sem,
        )
        fe = _analyze_fixture(fixture, texts_list, n_chunks=chunks_list)
        if judge_fn is not None and fe.missed:
            try:
                async with sem:
                    new_passages, usage = await _judge_rescue(
                        fixture, texts_list, paths_list, fe.missed, judge_fn=judge_fn
                    )
                usages.append(usage)
            except Exception as exc:  # judge unavailable → misses stand (conservative)
                print(
                    f"[judge] {fixture.query}: judging failed ({exc!r}); misses stand"
                )
                new_passages = []
            if new_passages:
                augmented = attrs.evolve(
                    fixture,
                    relevant_passages=fixture.relevant_passages + tuple(new_passages),
                )
                fe = _analyze_fixture(augmented, texts_list, n_chunks=chunks_list)
                for passage in new_passages:
                    pending_writes.append(
                        (
                            fixture.category,
                            fixture.query,
                            {
                                "passage": passage.passage,
                                "label": passage.label,
                                "official": passage.official,
                                "covers": list(passage.covers),
                            },
                        )
                    )
                print(
                    f"[judge] {fixture.query}: rescued "
                    f"{sorted(p.covers[0] for p in new_passages)}"
                )
        results[idx] = fe

    async with anyio.create_task_group() as tg:
        for idx, fixture in enumerate(fixtures):
            tg.start_soon(_eval_one, idx, fixture)

    total_usage = sum(usages, judge.JudgeUsage.zero())
    return [r for r in results if r is not None], pending_writes, total_usage


def _print_detail(
    fe: _FixtureEval,
    *,
    repeat: int,
) -> None:
    total = len(fe.fixture.expected_coverage)
    print("=" * 80)
    print(f"[{fe.fixture.subtype or fe.fixture.category}] {fe.fixture.query}")
    print(
        f"runs={repeat} | sources: {statistics.mean(fe.n_sources):.1f} | "
        f"chunks: {statistics.mean(fe.n_chunks):.1f} | "
        f"coverage: {fe.mean_coverage:.1f}/{total}"
    )
    for facet in fe.fixture.expected_coverage:
        ranks = [fr[facet] for fr in fe.first_ranks]
        covered = [r for r in ranks if r is not None]
        if covered:
            label = f"covered {len(covered)}/{repeat} (median rank {statistics.median(covered):.0f})"
        else:
            label = f"MISSING (0/{repeat} runs)"
        print(f"  - {facet}: {label}")
    for passage in fe.fixture.relevant_passages:
        counts = [sum(passage.matches(t) for t in texts) for texts in fe.runs]
        if (mean_count := statistics.mean(counts)) > 1:
            print(
                f"  [redundant] mean {mean_count:.1f} sources/run match passage: {passage.label}"
            )


def _print_summary(
    evals: list[_FixtureEval],
) -> None:
    sorted_evals = sorted(
        evals,
        key=lambda e: (
            e.mean_coverage / len(e.fixture.expected_coverage)
            if e.fixture.expected_coverage
            else 0
        ),
    )
    rows = []
    for fe in sorted_evals:
        total = len(fe.fixture.expected_coverage)
        rows.append(
            {
                "category": fe.fixture.category,
                "facets": total,
                "coverage": f"{fe.mean_coverage:4.1f}/{total:2d}",
                "rate": f"{fe.mean_coverage / total:>4.0%}" if total else "N/A",
                "files": f"{statistics.mean(fe.n_sources):.1f}",
                "chunks": f"{statistics.mean(fe.n_chunks):.1f}",
                "missed": ", ".join(fe.missed) if fe.missed else "",
                "query": fe.fixture.query[:70],
            }
        )
    print()
    print("#" * 80)
    print("# SUMMARY TABLE (sorted by coverage rate ascending)")
    print("#" * 80)
    print(
        tabulate.tabulate(
            rows,
            headers="keys",
            tablefmt="minimal",
            stralign="left",
            numalign="right",
        )
    )

    total_facets = sum(len(fe.fixture.expected_coverage) for fe in evals)
    covered_facets = sum(fe.mean_coverage for fe in evals)
    rates = [
        fe.mean_coverage / len(fe.fixture.expected_coverage)
        for fe in evals
        if fe.fixture.expected_coverage
    ]
    all_n_sources = [s for fe in evals for s in fe.n_sources]
    all_n_chunks = [c for fe in evals for c in fe.n_chunks]
    print()
    mean_rate = statistics.mean(rates)
    median_rate = statistics.median(rates)
    print(
        f"  Overall: {covered_facets:.1f}/{total_facets} facets ({covered_facets / total_facets:.0%}) "
        f"| avg per-query rate {mean_rate:.0%} (median {median_rate:.0%}) "
        f"| {len(evals)} queries"
    )
    print(
        f"  Avg sources: {statistics.mean(all_n_sources):.1f} | "
        f"Avg chunks: {statistics.mean(all_n_chunks):.1f}"
    )
    print("=" * 80)


@cli.command("eval-retrieval")
@click.option(
    "--budget",
    default=110,
    type=int,
    help="Context budget B: allocate k/chunk_context per fixture from budget+intent (default: 110 = 'thorough' preset)",
)
@click.option(
    "--intent",
    default="auto",
    type=click.Choice(["auto", "variety", "balanced", "context"]),
    help="Retrieval intent for budget-based allocation (default: auto = classify per fixture via LLM)",
)
@click.option(
    "--category",
    default=None,
    help="Only run fixtures from this category (default: all)",
)
@click.option(
    "--repeat",
    default=1,
    help="Run each query N times and average (the rewrite transformer is non-deterministic)",
)
@click.option("--bm25", is_flag=True, help="Use BM25-only retrieval instead of hybrid")
@click.option(
    "--judge",
    "use_judge",
    is_flag=True,
    help="Rescue false-miss facets with an LLM judge (DeepSeek V4 Flash on DeepInfra)",
)
@click.option(
    "--judge-model",
    default=judge.DEFAULT_JUDGE_MODEL,
    help="DeepInfra model id for the judge",
)
@click.option(
    "--judge-write/--no-judge-write",
    default=True,
    help="Persist judge-discovered spans back into fixtures as anchors (self-hardening)",
)
def eval_retrieval(
    *,
    budget: int,
    intent: str,
    category: str | None,
    repeat: int,
    bm25: bool,
    use_judge: bool,
    judge_model: str,
    judge_write: bool,
) -> None:
    """Measure facet coverage of the retrieval-eval fixtures against retrieval.

    Runs every fixture category (or just --category) for the store's language.
    Each fixture's relevant passages are matched against the actual chunk content
    (with context window) returned by the retriever, so coverage reflects what
    the LLM actually receives in production. Use --repeat > 1 to average out the
    non-determinism of the rewrite query transformer. Fixture retrieval is
    parallelized with anyio (trio-style structured concurrency).
    """
    _budget_val = budget  # avoid shadowing the budget module
    store, language, _ = _load_store()
    if store.num_documents == 0:
        logger.error("No documents in store.")
        sys.exit(1)

    fixtures = [
        f
        for f in retrieval.load_retrieval_dataset().fixtures
        if f.language == language.value and (category is None or f.category == category)
    ]
    if not fixtures:
        logger.error(
            "No fixtures for store language %s%s.",
            language.value,
            f" in category {category!r}" if category else "",
        )
        sys.exit(1)

    if intent == "auto":
        intent_fn = _make_auto_intent_fn(language)
    else:
        parsed = _budget.parse_intent(intent)
        assert parsed is not None
        intent_fn = lambda _query: parsed

    fevals, pending_writes, judge_usage = anyio.run(
        functools.partial(
            _aeval_fixtures,
            budget=_budget_val,
            intent_fn=intent_fn,
            repeat=repeat,
            bm25=bm25,
            judge_fn=judge.make_judge(judge_model) if use_judge else None,
        ),
        store,
        fixtures,
    )

    current_category = None
    for fe in fevals:
        if fe.fixture.category != current_category:
            current_category = fe.fixture.category
            print("#" * 80)
            print(f"# CATEGORY: {current_category}")
        _print_detail(fe, repeat=repeat)

    _print_summary(fevals)

    if pending_writes:
        if judge_write:
            print(
                f"[judge] persisted {retrieval.persist_anchors(pending_writes)} "
                "new anchor(s) into fixtures"
            )
        else:
            print(
                f"[judge] {len(pending_writes)} anchor(s) discovered "
                "(not persisted; --no-judge-write)"
            )

    if use_judge:
        print(
            f"[judge] tokens: {judge_usage.total_tokens} total "
            f"({judge_usage.input_tokens} in + {judge_usage.output_tokens} out) "
            f"over {judge_usage.calls} call(s)"
        )


def _make_auto_intent_fn(
    language: localization.Language,
) -> Callable[[str], _budget.QueryIntent]:
    """Build a function that classifies a query's intent via the preprocessing LLM."""
    import pydantic as _pydantic
    from langchain_core import prompts as _prompts

    class _EvalPreprocessOutput(_pydantic.BaseModel):
        intent: str

    lm = llm_manager.LLMManager()
    llm = lm.get_llm("gemini-3.1-flash-lite-preview")
    prompt = _prompts.ChatPromptTemplate.from_messages(
        [
            ("user", prompt_set.get_rag_prompts(language).question_preprocess_prompt),
        ]
    )
    chain = prompt | llm.with_structured_output(_EvalPreprocessOutput)

    def _classify(query: str) -> _budget.QueryIntent:
        try:
            result = chain.invoke({"question": query})
            if isinstance(result, _EvalPreprocessOutput):
                return _budget.QueryIntent(result.intent)
            return _budget.QueryIntent.BALANCED
        except Exception:
            return _budget.QueryIntent.BALANCED

    return _classify


@cli.command()
@click.argument("question", type=str)
@click.option("--budget", default=110)
def query(question: str, *, budget: int) -> None:
    """Answer a question using RAG pipeline."""
    store, language, ts = _load_store()

    if store.num_documents == 0:
        logger.error("No documents in store.")
        sys.exit(1)

    print(f"问题: {question}")
    print("=" * 50)

    # Create RAG pipeline and LLM
    lm = llm_manager.LLMManager()

    rag = pipeline.RAGPipeline(
        store,
        language=language,
        llm=lm.get_default_llm(),
        preprocessing_llm=lm.get_llm("gemini-3.1-flash-lite-preview"),
        proper_noun_llm=lm.get_llm(
            os.environ.get(
                "ISTAROTH_PROPER_NOUN_MODEL", "gemini-3.1-flash-lite-preview"
            )
        ),
        text_set=ts,
    )

    answer = rag.answer(question, budget=budget)
    print(f"回答: {answer}")


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=pathlib.Path))
@click.option(
    "--chunk-size-multiplier", default=1.0, type=float, help="Multiplier for chunk size"
)
def chunk_stats(path: pathlib.Path, *, chunk_size_multiplier: float) -> None:
    """Show statistics about document chunks from a file or folder."""
    files_to_process = _get_files_to_process(path)

    if not files_to_process:
        logger.error("No .txt files found to process.")
        sys.exit(1)

    logger.info("Analyzing chunks from %d files...", len(files_to_process))

    # Determine text root from file paths (common parent)
    if not files_to_process:
        logger.error("No files to process.")
        sys.exit(1)
    text_root = files_to_process[0].parent
    for file_path in files_to_process[1:]:
        # Find common parent by comparing path parts
        current_common = []
        for i, part in enumerate(text_root.parts):
            if i < len(file_path.parent.parts) and file_path.parent.parts[i] == part:
                current_common.append(part)
            else:
                break
        text_root = (
            pathlib.Path(*current_common) if current_common else file_path.parent
        )

    # Chunk the documents
    all_documents = document_store.chunk_documents(
        files_to_process,
        text_root=text_root,
        chunk_size_multiplier=chunk_size_multiplier,
        show_progress=True,
    )

    # Collect chunk lengths and content
    chunk_data = []
    file_count = len(all_documents)

    for file_docs in all_documents.values():
        for doc in file_docs.values():
            chunk_data.append((len(doc.page_content), doc.page_content))

    chunk_lengths = [length for length, _ in chunk_data]

    if not chunk_lengths:
        print("No chunks were generated.")
        return

    # Calculate distribution (bins of 50 characters) and collect examples
    bins: dict[int, int] = {}
    bin_examples: dict[int, list[str]] = {}
    bin_size = 50
    for length, content in chunk_data:
        bin_key = (length // bin_size) * bin_size
        bins[bin_key] = bins.get(bin_key, 0) + 1
        if bin_key not in bin_examples:
            bin_examples[bin_key] = []
        if len(bin_examples[bin_key]) < 3:
            bin_examples[bin_key].append(content)

    # Display statistics
    print("\nDocument Chunk Statistics")
    print("=" * 40)
    print(f"Total files: {file_count}")
    print(f"Total chunks: {len(chunk_lengths)}")
    print(
        f"Average chunk length: {sum(chunk_lengths) / len(chunk_lengths):.1f} characters"
    )
    print(f"Sum chunk length: {sum(chunk_lengths):.1f} characters")
    print(f"Min chunk length: {min(chunk_lengths)} characters")
    print(f"Max chunk length: {max(chunk_lengths)} characters")

    print("\nLength Distribution:")
    print("-" * 40)

    # Sort bins and display histogram
    max_count = max(bins.values())
    for bin_start in sorted(bins.keys()):
        bin_end = bin_start + bin_size - 1
        count = bins[bin_start]
        bar_length = int((count / max_count) * 40)
        bar = "█" * bar_length
        print(f"{bin_start:3d}-{bin_end:3d}: {bar} {count:4d} chunks")

    # Calculate percentiles
    sorted_lengths = sorted(chunk_lengths)
    p25 = sorted_lengths[len(sorted_lengths) // 4]
    p50 = sorted_lengths[len(sorted_lengths) // 2]
    p75 = sorted_lengths[3 * len(sorted_lengths) // 4]

    print("\nPercentiles:")
    print("-" * 40)
    print(f"25th percentile: {p25} characters")
    print(f"50th percentile (median): {p50} characters")
    print(f"75th percentile: {p75} characters")

    print("\nExamples by Size Range:")
    print("=" * 60)
    for bin_start in sorted(bin_examples.keys()):
        print(
            f"\n{bin_start}-{bin_start + bin_size - 1} characters ({bins[bin_start]} chunks):"
        )
        print("-" * 30)

        for i, example in enumerate(bin_examples[bin_start], 1):
            print(f"Example {i}:")
            print("─" * 80)
            print(example)
            print("─" * 80)
            print()


@cli.command("chunk-file")
@click.argument("file", type=click.Path(exists=True, path_type=pathlib.Path))
@click.option(
    "--chunk-size-multiplier", default=1.0, type=float, help="Multiplier for chunk size"
)
def chunk_file(file: pathlib.Path, *, chunk_size_multiplier: float) -> None:
    """Chunk a single text file and print individual chunks."""
    if not file.is_file() or file.suffix != ".txt":
        logger.error("%s must be a .txt file", file)
        sys.exit(1)

    logger.info("Chunking file: %s", file)
    print("=" * 60)

    # Use the existing chunk_documents function from document_store
    # Use file's parent as text root
    all_documents = document_store.chunk_documents(
        [file], text_root=file.parent, chunk_size_multiplier=chunk_size_multiplier
    )

    # Get the documents for this file
    file_id = list(all_documents.keys())[0]
    file_documents = all_documents[file_id]

    # Print each chunk
    for chunk_index, doc in file_documents.items():
        chunk_content = doc.page_content
        print(f"\n--- Chunk {chunk_index + 1} (length: {len(chunk_content)} chars) ---")
        print(chunk_content)
        print("-" * 60)

    # Print summary
    chunks_list = [doc.page_content for doc in file_documents.values()]
    print(f"\nSummary:")
    print(f"  Total chunks: {len(chunks_list)}")
    print(
        f"  Average chunk size: {sum(len(c) for c in chunks_list) / len(chunks_list):.1f} chars"
    )
    print(f"  Min chunk size: {min(len(c) for c in chunks_list)} chars")
    print(f"  Max chunk size: {max(len(c) for c in chunks_list)} chars")


@cli.command("diff-retrieval")
@click.argument("file1", type=click.Path(exists=True, path_type=pathlib.Path))
@click.argument("file2", type=click.Path(exists=True, path_type=pathlib.Path))
def diff_retrieval(file1: pathlib.Path, file2: pathlib.Path) -> None:
    """Compare two retrieval result files and show differences."""
    # Load and compare the JSON files
    json1 = json.loads(file1.read_text())
    json2 = json.loads(file2.read_text())

    # Create the diff object
    diff = retrieval_diff.compare_retrievals(
        json1, json2, filename1=file1.name, filename2=file2.name
    )

    # Render all sections
    print(retrieval_diff.render_comparison_headers(diff))
    print()
    print(retrieval_diff.render_document_sections(diff))
    print()
    print(retrieval_diff.render_summary_table(diff))
    print()
    print(retrieval_diff.render_final_summary(diff))


if __name__ == "__main__":
    cli()
