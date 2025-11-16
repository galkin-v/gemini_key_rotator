"""
Advanced worker pool demo showing all features.

This example demonstrates:
- Worker-pool architecture with multiple slots per key
- Per-slot rate limiting
- Rich task metadata
- Checkpoint/resume functionality
- Live monitoring
- Error logging
- System instructions
"""

import asyncio
import os
from gemini_key_rotator import GeminiGenerator


async def main():
    print("\n" + "=" * 70)
    print("ADVANCED WORKER POOL DEMO")
    print("=" * 70)

    # Get API keys from environment variables
    # You can also hardcode them: api_keys = ["key1", "key2", "key3"]
    api_keys = [
        os.getenv("GOOGLE_API_KEY_1"),
        os.getenv("GOOGLE_API_KEY_2"),
        os.getenv("GOOGLE_API_KEY_3"),
    ]
    
    # Filter out None values
    api_keys = [k for k in api_keys if k]
    
    if not api_keys:
        print("❌ No API keys found! Set environment variables:")
        print("   export GOOGLE_API_KEY_1='your-key-1'")
        print("   export GOOGLE_API_KEY_2='your-key-2'")
        print("   export GOOGLE_API_KEY_3='your-key-3'")
        return

    # Initialize generator with worker pool and all features
    generator = GeminiGenerator(
        model_name="gemini-2.5-flash",
        api_keys=api_keys,
        workers_per_key=4,  # 4 workers per key
        rate_limit_per_slot=12,  # 12 seconds between requests per worker
        system_instruction="You are a creative storyteller who writes engaging short stories.",
        temperature=0.8,  # Higher temperature for creative output
        error_log_path="worker_pool_errors.log",
        enable_monitoring=True,  # Show live progress
        monitoring_interval=2.0,  # Update every 2 seconds
    )

    # Create tasks with rich metadata
    tasks = []
    
    # Category 1: Creative stories
    for i in range(10):
        tasks.append({
            "id": f"story_{i}",
            "prompt": f"Write a 2-sentence micro-story about the number {i}",
            "category": "creative",
            "priority": "normal",
            "index": i,
        })
    
    # Category 2: Technical explanations
    topics = ["AI", "blockchain", "quantum computing", "machine learning", "neural networks"]
    for i, topic in enumerate(topics):
        tasks.append({
            "id": f"tech_{i}",
            "prompt": f"Explain {topic} in exactly one sentence",
            "category": "technical",
            "priority": "high",
            "topic": topic,
        })
    
    # Category 3: Creative challenges
    challenges = [
        "Write a haiku about coding",
        "Create a limerick about debugging",
        "Write a short poem about AI",
    ]
    for i, challenge in enumerate(challenges):
        tasks.append({
            "id": f"challenge_{i}",
            "prompt": challenge,
            "category": "poetry",
            "priority": "low",
        })

    print(f"\n📋 Total tasks: {len(tasks)}")
    print(f"   - Creative stories: 10")
    print(f"   - Technical explanations: {len(topics)}")
    print(f"   - Poetry challenges: {len(challenges)}")
    print(f"\n🔧 Configuration:")
    print(f"   - API keys: {len(api_keys)}")
    print(f"   - Workers per key: 4")
    print(f"   - Total slots: {len(api_keys) * 4}")
    print(f"   - Rate limit: 12s per slot")
    print(f"   - Theoretical throughput: {len(api_keys) * 4 / 12:.2f} req/s")

    # Generate with all features
    print("\n🚀 Starting generation with checkpointing and monitoring...")
    print("   (You can Ctrl+C to stop and resume later)\n")

    results = await generator.generate_batch(
        tasks=tasks,
        output_file="worker_pool_results.json",  # Checkpoint file
        parse_json=False,
        max_retries_per_task=3,  # Retry failed tasks up to 3 times
    )

    # Analyze results
    print("\n" + "=" * 70)
    print("RESULTS ANALYSIS")
    print("=" * 70)

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    
    print(f"\n✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}")

    # Group by category
    categories = {}
    for result in successful:
        cat = result.get("category", "unknown")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(result)
    
    print(f"\n📊 Results by category:")
    for cat, items in categories.items():
        print(f"   {cat}: {len(items)} tasks")

    # Show sample results
    print(f"\n📝 Sample results:")
    for i, result in enumerate(successful[:3], 1):
        task_id = result.get("id", "unknown")
        prompt = result.get("prompt", "")
        response = result.get("result", "")
        
        print(f"\n{i}. [{task_id}]")
        print(f"   Prompt: {prompt[:60]}...")
        if response and len(response) > 100:
            print(f"   Response: {response[:100]}...")
        else:
            print(f"   Response: {response}")

    # Show failed tasks (if any)
    if failed:
        print(f"\n❌ Failed tasks:")
        for result in failed[:3]:
            task_id = result.get("id", "unknown")
            reason = result.get("failure_reason", "unknown")
            print(f"   - {task_id}: {reason}")

    # Show final statistics
    print("\n" + "=" * 70)
    print("FINAL STATISTICS")
    print("=" * 70)
    generator.print_statistics()

    print(f"\n💾 Results saved to: worker_pool_results.json")
    print(f"🧾 Errors logged to: worker_pool_errors.log")
    print("\n✨ Demo complete!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted! Run again to resume from checkpoint.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
