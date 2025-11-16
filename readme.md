# Gemini Key Rotator Library

A high-performance Python library for async generation with Google Gemini API using worker-pool architecture and per-slot rate limiting.

## 🚀 Quick Start

```python
import asyncio
from gemini_key_rotator import GeminiGenerator

async def main():
    generator = GeminiGenerator(
        model_name="gemini-2.0-flash-exp",
        api_keys=["key1", "key2", "key3"],
        workers_per_key=4,  # 4 workers per key = 12 total slots
        rate_limit_per_slot=12,  # 12 seconds between requests per slot
    )
    
    tasks = ["Write a haiku", "Explain AI", "Tell a joke"]
    results = await generator.generate_batch(
        tasks=tasks,
        output_file="results.json",
    )
    
    generator.print_statistics()

asyncio.run(main())
```

## 📦 Installation

```bash
pip install -r requirements.txt
```

## ✨ Features

- ✅ **Worker Pool Architecture** - Multiple workers per API key for maximum throughput
- ✅ **Per-Slot Rate Limiting** - Independent rate limiting per worker slot
- ✅ **Intelligent Retry** - Failed tasks auto-retry with different keys
- ✅ **Permanent Key Exhaustion Detection** - Suspended/invalid keys are marked and skipped
- ✅ **Automatic Cooldown** - Failing keys go on cooldown, others keep working
- ✅ **Live Monitoring** - Real-time stats showing active connections and progress
- ✅ **High Throughput** - Process thousands of requests efficiently
- ✅ **Checkpointing** - Save partial results and resume from where you left off
- ✅ **Structured Error Logging** - Detailed error logs with retry hints
- ✅ **Flexible Tasks** - Support for simple prompts or complex task metadata
- ✅ **JSON Parsing** - Built-in JSON response parsing with repair
- ✅ **System Instructions** - Set custom system instructions for all requests

## 📖 Examples

- **[Simple Example](examples/simple_example.py)** - Basic usage with minimal setup
- **[Worker Pool Demo](examples/worker_pool_demo.py)** - Advanced usage showing all features
- **[Your Use Case](event_manager_markup.py)** - Real-world example

## 🎯 API Support

The library supports **Google Gemini API keys only**.

## 📁 Project Structure

```
skill_projects/
├── gemini_key_rotator/        # Main library
│   ├── __init__.py
│   ├── generator.py           # Main GeminiGenerator class
│   ├── utils.py               # Utility functions
│   └── exceptions.py          # Custom exceptions
├── examples/                  # Example scripts
│   ├── simple_example.py      # Basic usage
│   └── worker_pool_demo.py    # Advanced demo
├── requirements.txt           # Dependencies
├── setup.py                   # Package setup
└── readme.md                  # This file
```

## 🔑 Key Features

### 1. Worker Pool Architecture

```python
generator = GeminiGenerator(
    model_name="gemini-2.5-flash",
    api_keys=["key1", "key2", "key3"],  # 3 keys
    workers_per_key=4,  # 4 workers each = 12 total slots
    rate_limit_per_slot=12,  # 12 seconds between requests per slot
)
# Theoretical throughput: 12 slots / 12 seconds = 1 request/second
```

### 2. Per-Slot Rate Limiting

Each worker slot has independent rate limiting:
- Maximizes throughput without hitting rate limits
- Each slot waits its own rate_limit_per_slot seconds between requests
- Multiple slots can make concurrent requests

### 3. Intelligent Retry System

**Key Errors (Rate limits, quota issues, suspended keys)**:
- Task retries indefinitely with different keys
- Failing key goes on cooldown
- Never counts against retry limit
- Suspended keys are permanently disabled

**Task Errors (Bad prompts, parsing failures)**:
- Counts against `max_retries_per_task`
- Still tries different keys
- Fails only after exhausting retry limit

```python
results = await generator.generate_batch(
    tasks=tasks,
    max_retries_per_task=5,  # Only counts TASK errors
)
```

### 4. Live Monitoring

```python
generator = GeminiGenerator(
    api_keys=keys,
    enable_monitoring=True,
    monitoring_interval=2.0,  # Update every 2 seconds
)
```

Output:
```
📊 active 8/48 | queued 42 | ✅ 150 | ❌ 2 | ⏸️  1
```

### 5. Checkpointing & Resume

```python
# Run 1: Process 500 tasks, crashes at task 300
await generator.generate_batch(
    tasks=tasks,
    output_file="results.json",  # 300 results saved
)

# Run 2: Automatically resumes from task 301
await generator.generate_batch(
    tasks=tasks,
    output_file="results.json",  # Skips first 300
)
```

### 6. Flexible Task Format

**Simple strings**:
```python
tasks = ["What is AI?", "Explain Python", "Tell a joke"]
```

**Rich metadata**:
```python
tasks = [
    {
        "id": "task_1",
        "prompt": "What is AI?",
        "category": "tech",
        "metadata": {"priority": "high"}
    }
]
```

### 7. JSON Parsing with Repair

```python
results = await generator.generate_batch(
    tasks=tasks,
    parse_json=True,  # Auto-parse and repair malformed JSON
)
```

## 🔧 Full API Reference

### GeminiGenerator

```python
GeminiGenerator(
    model_name: str,                    # Gemini model name
    api_keys: List[str],                # List of API keys
    workers_per_key: int = 4,           # Workers per key
    rate_limit_per_slot: float = 12.0,  # Seconds between requests per slot
    system_instruction: Optional[str] = None,  # System instructions
    temperature: float = 1.0,           # Temperature for generation
    error_log_path: Optional[str] = None,  # Path to error log file
    enable_monitoring: bool = False,    # Enable live monitoring
    monitoring_interval: float = 2.0,   # Monitoring update interval
)
```

### generate_batch

```python
await generator.generate_batch(
    tasks: List[Union[str, dict]],      # Tasks to process
    output_file: Optional[str] = None,  # Save results to JSON file
    parse_json: bool = False,           # Parse responses as JSON
    max_retries_per_task: int = 3,      # Max retries for task errors only
)
```

### generate_single

```python
result = await generator.generate_single(
    prompt: str,                        # Single prompt
    parse_json: bool = False,           # Parse response as JSON
)
```

### Statistics

```python
stats = generator.get_statistics()
generator.print_statistics()
```

## 🎓 How It Works

### Architecture

```
┌─────────────────┐
│  Task Queue     │
│  [Task1, Task2  │
│   Task3, ...]   │
└────────┬────────┘
         │
    ┌────┴────────────────────────┐
    │                             │
┌───▼────┐  ┌────────┐  ┌────────┐
│ Slot 1 │  │ Slot 2 │  │ Slot 3 │ ... (48 total)
│ Key A  │  │ Key A  │  │ Key A  │
└────┬───┘  └────┬───┘  └────┬───┘
     │           │            │
     └───────────┴────────────┘
              │
         ┌────▼────┐
         │ Results │
         └─────────┘
```

### Error Handling Flow

```
Task fails on Slot 5 (Key A)
         ↓
Is it a key error? (rate limit, quota, suspended)
         ↓ YES
   Put key on cooldown
   Put task back in queue
   Don't count as retry
         ↓
Slot 12 (Key B) picks it up
         ↓ SUCCESS ✅
```

## 📊 Performance

With 12 keys × 4 workers = 48 slots @ 12s rate limit:
- **Theoretical throughput**: 4 requests/second
- **Actual throughput**: ~3.5-4 req/s (accounting for network latency)
- **Can process 10,000 tasks in**: ~45 minutes

## 🐛 Error Logging

Errors are logged with detailed information:

```python
generator = GeminiGenerator(
    api_keys=keys,
    error_log_path="errors.log",
)
```

Log format:
```
2024-01-15 10:30:45 ERROR Slot 5: 429 RESOURCE_EXHAUSTED (retry in 60s)
2024-01-15 10:31:00 ERROR Slot 12: CONSUMER_SUSPENDED (permanent)
```

## 🔄 Retry Mechanism

### Key-Related Errors (Never Fail)
- `RESOURCE_EXHAUSTED` - Rate limit hit
- `CONSUMER_SUSPENDED` - Key suspended (permanent)
- `quota exceeded` - Quota limit
- `permission denied` - Invalid key (permanent)

**Behavior**: Retry indefinitely with different keys. Never count against retry limit.

### Task-Related Errors (Counted)
- JSON parsing failures
- Content policy violations
- Invalid prompts
- Model errors

**Behavior**: Retry up to `max_retries_per_task` times with different keys. Fail after exhausting retries.

## 🚀 Best Practices

1. **Set appropriate rate limits**: Start with 12s per slot and adjust based on your quota
2. **Use monitoring**: Enable live monitoring for long-running batches
3. **Enable checkpointing**: Always specify `output_file` for resumability
4. **Handle failures gracefully**: Check `success` field in results
5. **Use error logging**: Set `error_log_path` to debug issues
6. **Scale with workers**: More workers = higher throughput (but watch your quotas!)

## 📝 License

MIT License

## 🤝 Contributing

Contributions welcome! Feel free to open issues or submit PRs.
