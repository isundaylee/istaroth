#!/usr/bin/env python3
"""CLI tool for testing reasoning pipeline."""

import pathlib
import sys

import click

# Add the parent directory to Python path to find istaroth module
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from istaroth import llm_manager
from istaroth.agd import localization
from istaroth.rag import document_store
from istaroth.reasoning import pipeline, tools, types


@click.command()
@click.argument("question")
@click.option(
    "--language",
    "-l",
    type=click.Choice([l.value for l in localization.Language], case_sensitive=False),
    default=localization.Language.CHS.value,
    callback=lambda _ctx, _param, value: (
        localization.Language(value) if value else None
    ),
    help="Language for reasoning prompts",
)
@click.option("--max-steps", "-s", type=int, default=3, help="Maximum reasoning steps")
@click.option("--model", "-m", default="gpt-5", help="Model to use for reasoning")
def main(
    question: str, *, language: localization.Language, max_steps: int, model: str
) -> None:
    """Run reasoning pipeline on a question and print results."""

    # Load document store
    doc_store = document_store.DocumentStore.from_env()
    if not doc_store.num_documents:
        print(
            "❌ No document store available - cannot proceed without document retrieval"
        )
        sys.exit(1)

    print(f"✓ Loaded document store with {len(doc_store._documents)} documents")

    # Create LLM
    llm = llm_manager.create_llm(model, max_tokens=5000)
    print(f"✓ Created LLM: {model}")

    # Create reasoning pipeline
    default_tools = tools.get_default_tools(doc_store)
    reasoning_pipeline = pipeline.ReasoningPipeline(
        llm,
        default_tools,
        language=language,
        max_steps=max_steps,
    )

    print(f"✓ Have {len(default_tools)} tools")
    print(f"✓ Using model: {model}")
    print(f"✓ Language: {language.value}")
    print()

    # Create reasoning request
    request = types.ReasoningRequest(question=question, k=10)

    print(f"🤔 Question: {question}")
    print("=" * 60)

    # Execute reasoning
    try:
        response = reasoning_pipeline.reason(request)

        # Print reasoning steps
        print("📝 Reasoning Steps:")
        print("-" * 40)

        for i, step in enumerate(response.reasoning_steps, 1):
            step_type = step.step_type.replace("_", " ").title()
            content_lines = step.content.split("\n")
            char_count = len(step.content)

            print(f"[{i}] {step_type} ({char_count} chars)")

            # Show only first 5 lines for tool output
            if step.step_type == "tool_result":
                display_lines = content_lines[:5]
                if len(content_lines) > 5:
                    display_lines.append(f"... ({len(content_lines) - 5} more lines)")
            else:
                display_lines = content_lines

            for line in display_lines:
                print(f"    {line}")
            print()

        # Print final answer
        print("💡 Final Answer:")
        print("-" * 40)
        print(response.answer)

        # Print summary
        print()
        print("📊 Summary:")
        print(f"    Model: {response.model}")
        print(f"    Steps: {len(response.reasoning_steps)}")

    except Exception as e:
        print(f"❌ Error during reasoning: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
