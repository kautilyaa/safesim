#!/usr/bin/env python3
"""
SafeSim Demo Script
Demonstrates the SafeSim pipeline with example medical texts
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.safesim_pipeline import SafeSimPipeline
import json


def print_banner():
    """Print welcome banner"""
    print("=" * 70)
    print("  SafeSim: Safe Medical Text Simplification")
    print("  Neuro-Symbolic Approach with Guaranteed Fact Preservation")
    print("=" * 70)
    print()


def print_result(result, index=None):
    """Pretty print a SafeSim result"""
    if index is not None:
        print(f"\n{'='*70}")
        print(f"Example {index}")
        print('='*70)

    print(f"\nORIGINAL TEXT:")
    print(f"  {result.original_text}")

    print(f"\nEXTRACTED ENTITIES ({len(result.entities)}):")
    for entity in result.entities:
        print(f"  - {entity['text']:20} [{entity['type']}]")

    print(f"\nSIMPLIFIED TEXT:")
    print(f"  {result.simplified_text}")

    print(f"\nVERIFICATION:")
    if result.is_safe:
        print(f"  ✅ SAFE - Score: {result.verification['score']:.0%}")
    else:
        print(f"  ⚠️  UNSAFE - Score: {result.verification['score']:.0%}")

    if result.warnings:
        print(f"\nWARNINGS:")
        for warning in result.warnings:
            print(f"  {warning}")

    print()


def run_basic_demo():
    """Run basic demo with a few examples"""
    print_banner()
    print("Running basic demo with rule-based simplifier (no API keys needed)")
    print()

    # Initialize pipeline with dummy backend
    pipeline = SafeSimPipeline(llm_backend="dummy", strictness="high")

    # Example texts
    examples = [
        "Patient prescribed 50mg Atenolol PO q.d. for hypertension. Monitor for bradycardia.",
        "Administer 10 units insulin subcutaneously b.i.d. before meals. Check blood glucose q.i.d.",
        "Start Metoprolol 25mg PO b.i.d. for atrial fibrillation. Hold if HR <60 bpm.",
    ]

    print(f"Processing {len(examples)} examples...\n")

    for i, text in enumerate(examples, 1):
        result = pipeline.process(text, verbose=False)
        print_result(result, index=i)

    print("=" * 70)
    print("Demo complete! Try running the web interface:")
    print("  streamlit run src/ui/app.py")
    print("=" * 70)


def run_batch_demo():
    """Run batch processing demo with example file"""
    print_banner()
    print("Running batch processing demo")
    print()

    # Load examples from JSON
    examples_file = Path(__file__).parent / "examples" / "medical_texts.json"

    if not examples_file.exists():
        print("Error: examples/medical_texts.json not found")
        return

    with open(examples_file, 'r') as f:
        data = json.load(f)

    examples = data['examples']

    print(f"Loaded {len(examples)} examples from medical_texts.json")
    print()

    # Initialize pipeline
    pipeline = SafeSimPipeline(llm_backend="dummy", strictness="high")

    # Process all examples
    texts = [ex['original'] for ex in examples]
    results = pipeline.batch_process(texts, verbose=False)

    # Show results for first 3 examples
    print("\nShowing first 3 results:\n")
    for i, result in enumerate(results[:3], 1):
        print_result(result, index=i)

    # Calculate statistics
    stats = pipeline.get_statistics(results)

    print("=" * 70)
    print("BATCH STATISTICS")
    print("=" * 70)
    print(f"Total processed:       {stats['total_processed']}")
    print(f"Safe simplifications:  {stats['safe_simplifications']}")
    print(f"Unsafe simplifications: {stats['unsafe_simplifications']}")
    print(f"Safety rate:           {stats['safety_rate']:.0%}")
    print(f"Average score:         {stats['average_verification_score']:.0%}")
    print("=" * 70)


def run_interactive_demo():
    """Run interactive demo where user can input text"""
    print_banner()
    print("Interactive Mode")
    print("Enter medical text to simplify (or 'quit' to exit)")
    print()

    # Initialize pipeline
    backend = input("Select LLM backend (dummy/openai/claude) [dummy]: ").strip() or "dummy"

    kwargs = {}
    if backend in ["openai", "claude"]:
        api_key = input("Enter API key: ").strip()
        if api_key:
            kwargs['api_key'] = api_key

    try:
        pipeline = SafeSimPipeline(llm_backend=backend, strictness="high", **kwargs)
        print(f"\nPipeline initialized with {backend} backend")
    except Exception as e:
        print(f"Error initializing pipeline: {e}")
        print("Falling back to dummy backend")
        pipeline = SafeSimPipeline(llm_backend="dummy", strictness="high")

    print()

    while True:
        print("-" * 70)
        text = input("\nEnter medical text (or 'quit'): ").strip()

        if text.lower() in ['quit', 'exit', 'q']:
            print("\nGoodbye!")
            break

        if not text:
            print("Please enter some text")
            continue

        print("\nProcessing...")
        result = pipeline.process(text, verbose=False)
        print_result(result)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="SafeSim Demo")
    parser.add_argument(
        '--mode',
        choices=['basic', 'batch', 'interactive'],
        default='basic',
        help='Demo mode to run (default: basic)'
    )

    args = parser.parse_args()

    try:
        if args.mode == 'basic':
            run_basic_demo()
        elif args.mode == 'batch':
            run_batch_demo()
        elif args.mode == 'interactive':
            run_interactive_demo()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
