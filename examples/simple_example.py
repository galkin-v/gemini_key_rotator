"""
Simple example demonstrating the Gemini Key Rotator library.

This shows the basic usage with worker-pool architecture.
"""

import asyncio
import os
from gemini_key_rotator import GeminiGenerator


async def main():
    # Get API keys from environment or use your keys directly
    api_keys = [
        os.getenv("GOOGLE_API_KEY_1", "your-key-1"),
        os.getenv("GOOGLE_API_KEY_2", "your-key-2"),
        os.getenv("GOOGLE_API_KEY_3", "your-key-3"),
    ]

    # Initialize generator with worker pool
    generator = GeminiGenerator(
        model_name="gemini-2.5-flash",
        api_keys=api_keys,
        workers_per_key=4,        # 4 workers per key = 12 total slots
        rate_limit_per_slot=12,   # 12 seconds between requests per slot
        system_instruction="You are a helpful assistant.",
        temperature=0.7,
        enable_monitoring=True,   # Show live progress
    )

    # Define simple tasks (can be just strings)
    tasks = [
        "Write a haiku about programming",
        "Explain quantum computing in one sentence",
        "What is the meaning of life?",
        "Tell me a programming joke",
        "Write a short poem about AI",
    ]

    # Generate with automatic retry and checkpointing
    results = await generator.generate_batch(
        tasks=tasks,
        output_file="simple_results.json",
        max_retries_per_task=3,
    )

    # Print results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    for i, result in enumerate(results, 1):
        prompt = result["prompt"]
        response = result.get("result", "Failed")
        success = result.get("success", False)
        
        print(f"\n{i}. {prompt}")
        print(f"   Success: {'✅' if success else '❌'}")
        if response and len(response) > 100:
            print(f"   Response: {response[:100]}...")
        else:
            print(f"   Response: {response}")

    # Show statistics
    print("\n" + "=" * 70)
    generator.print_statistics()


if __name__ == "__main__":
    asyncio.run(main())

