# Examples

This directory contains example scripts demonstrating the Gemini Key Rotator library.

## 📁 Files

### `simple_example.py`
Basic usage with minimal setup. Great for getting started!

**Features demonstrated:**
- Worker pool initialization
- Simple task format (just strings)
- Live monitoring
- Basic results handling
- Statistics printing

**Run it:**
```bash
python examples/simple_example.py
```

### `worker_pool_demo.py`
Advanced demo showing all features of the worker-pool architecture.

**Features demonstrated:**
- Worker pool with multiple slots per key
- Per-slot rate limiting
- Rich task metadata (id, category, etc.)
- Checkpoint/resume functionality
- Live monitoring with detailed stats
- Error logging
- JSON parsing
- System instructions
- Temperature control

**Run it:**
```bash
python examples/worker_pool_demo.py
```

## 🚀 Quick Start

The simplest possible example:

```python
import asyncio
from gemini_key_rotator import GeminiGenerator

async def main():
    generator = GeminiGenerator(
        model_name="gemini-2.0-flash-exp",
        api_keys=["your-key-1", "your-key-2"],
        workers_per_key=4,
        rate_limit_per_slot=12,
    )
    
    results = await generator.generate_batch(
        tasks=["Hello!", "How are you?"],
        output_file="results.json",
    )
    
    for result in results:
        print(result["result"])

asyncio.run(main())
```

## 📖 Key Concepts

### Worker Pool Architecture

```
3 API keys × 4 workers per key = 12 total worker slots
Each slot operates independently with its own rate limiting
```

### Tasks Format

**Simple (strings):**
```python
tasks = ["Prompt 1", "Prompt 2", "Prompt 3"]
```

**Rich (dictionaries):**
```python
tasks = [
    {
        "id": "task_1",
        "prompt": "What is AI?",
        "category": "tech",
        "metadata": {"user_id": 123}
    }
]
```

### Results Format

```python
{
    "prompt": "What is AI?",
    "result": "AI stands for...",
    "success": True,
    # ... any additional metadata from task
}
```

## 🔧 Configuration Options

### Essential Parameters

```python
GeminiGenerator(
    model_name="gemini-2.0-flash-exp",  # Required
    api_keys=["key1", "key2"],          # Required
    workers_per_key=4,                   # Default: 4
    rate_limit_per_slot=12.0,            # Default: 12.0 seconds
)
```

### Optional Parameters

```python
GeminiGenerator(
    system_instruction="You are...",     # System prompt
    temperature=0.7,                     # 0.0 to 2.0
    error_log_path="errors.log",         # Error logging
    enable_monitoring=True,              # Live stats
    monitoring_interval=2.0,             # Update frequency
)
```

### Batch Generation Options

```python
await generator.generate_batch(
    tasks=tasks,                         # Required
    output_file="results.json",          # Checkpoint/resume
    parse_json=False,                    # Parse as JSON
    max_retries_per_task=3,              # Only for task errors
)
```

## 💡 Tips

1. **Start simple**: Use `simple_example.py` as a template
2. **Enable monitoring**: Set `enable_monitoring=True` for long batches
3. **Use checkpointing**: Always set `output_file` for resumability
4. **Tune rate limits**: Adjust `rate_limit_per_slot` based on your quota
5. **Scale workers**: More `workers_per_key` = higher throughput

## 🐛 Common Issues

### "All keys exhausted"
- One or more keys are suspended/invalid
- Check `error_log_path` for details
- Remove bad keys from `api_keys` list

### "Rate limit errors"
- Increase `rate_limit_per_slot` value
- Or reduce `workers_per_key`

### Tasks taking too long
- Reduce `rate_limit_per_slot` (if quota allows)
- Increase `workers_per_key`
- Add more API keys

## 📚 More Examples

For a real-world use case, see:
- `event_manager_markup.py` in the project root

## 🔗 Resources

- [Main README](../readme.md) - Full documentation
- [Generator Source](../gemini_key_rotator/generator.py) - Implementation details
