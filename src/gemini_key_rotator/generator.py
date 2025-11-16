"""Main generator module for async content generation with worker-pool key rotation."""

import asyncio
import contextlib
import json
import logging
import os
import time
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional, Union

import aiofiles
from google import genai
from google.genai import types
from tqdm.asyncio import tqdm as async_tqdm

from .utils import extract_retry_delay, parse_json_safe


class GeminiGenerator:
    """
    High-performance generator with worker-pool architecture and per-slot rate limiting.

    This implementation uses:
    - Worker pool with multiple workers per API key
    - Per-slot rate limiting to maximize throughput
    - Live monitoring of active connections
    - Checkpoint/resume functionality
    - Structured error logging

    Example:
        ```python
        generator = GeminiGenerator(
            model_name="gemini-2.0-flash-exp",
            api_keys=["key1", "key2", "key3"],
            workers_per_key=4,
            rate_limit_per_slot=12
        )

        results = await generator.generate_batch(
            tasks=["Task 1", "Task 2", ...],
            output_file="results.json"
        )
        ```
    """

    def __init__(
        self,
        model_name: str,
        api_keys: Optional[List[str]] = None,
        workers_per_key: int = 4,
        rate_limit_per_slot: float = 12.0,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3,
        error_log_path: str = "errors.log",
        enable_monitoring: bool = True,
        monitoring_interval: float = 2.0,
    ):
        """
        Initialize the GeminiGenerator with worker pool architecture.

        Args:
            model_name: Name of the Gemini model (e.g., "gemini-2.0-flash-exp").
            api_keys: List of Google API keys. If None, loads from environment.
            workers_per_key: Number of worker slots per API key (default: 4).
            rate_limit_per_slot: Seconds between requests per slot (default: 12).
            system_instruction: Optional system instruction for all requests.
            temperature: Temperature for generation (default: 0.3).
            error_log_path: Path for error log file (default: "errors.log").
            enable_monitoring: Enable live monitoring (default: True).
            monitoring_interval: Seconds between monitoring updates (default: 2.0).

        Raises:
            ValueError: If no API keys are provided or found.
        """
        self.model_name = model_name
        self.workers_per_key = workers_per_key
        self.rate_limit_per_slot = rate_limit_per_slot
        self.system_instruction = system_instruction
        self.temperature = temperature
        self.enable_monitoring = enable_monitoring
        self.monitoring_interval = monitoring_interval

        # Load API keys
        if api_keys is None:
            api_keys = self._load_keys_from_env()

        if not api_keys:
            raise ValueError(
                "No API keys provided. Either pass api_keys parameter or set "
                "GOOGLE_API_KEYS (comma-separated) or GOOGLE_API_KEY environment variable."
            )

        # Create client pool (one client per worker slot)
        self.clients = [
            genai.Client(api_key=key)
            for key in api_keys
            for _ in range(workers_per_key)
        ]
        self.total_slots = len(self.clients)

        # Per-slot state
        self.last_call_time = {id(c): 0.0 for c in self.clients}
        self.slot_cooldown_until = {
            id(c): 0.0 for c in self.clients
        }  # Cooldown tracking
        self.slot_exhausted = {
            id(c): False for c in self.clients
        }  # Permanently disabled slots

        # Active connection tracking
        self._active_count = 0
        self._active_lock = asyncio.Lock()

        # Save lock for file writes
        self._save_lock = asyncio.Lock()

        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_api_calls": 0,
            "retried_tasks": 0,
            "keys_on_cooldown": 0,
        }

        # Setup error logging
        self._setup_error_logging(error_log_path)

        print("🚀 Initialized GeminiGenerator:")
        print(f"   - {len(api_keys)} API keys")
        print(f"   - {self.workers_per_key} workers per key")
        print(f"   - {self.total_slots} total worker slots")
        print(f"   - {self.rate_limit_per_slot}s rate limit per slot")

    def _setup_error_logging(self, log_path: str):
        """Setup error logger with rotating file handler."""
        self.err_logger = logging.getLogger(f"gemini_errors_{id(self)}")
        self.err_logger.setLevel(logging.ERROR)

        # Remove existing handlers
        self.err_logger.handlers = []

        err_handler = RotatingFileHandler(
            log_path, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        err_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        self.err_logger.addHandler(err_handler)
        self.err_logger.propagate = False

    @staticmethod
    def _load_keys_from_env() -> List[str]:
        """Load API keys from environment variables."""
        # Try GOOGLE_API_KEYS first (comma-separated list)
        keys_str = os.getenv("GOOGLE_API_KEYS")
        if keys_str:
            return [k.strip() for k in keys_str.split(",") if k.strip()]

        # Fall back to single GOOGLE_API_KEY
        single_key = os.getenv("GOOGLE_API_KEY")
        if single_key:
            return [single_key.strip()]

        return []

    async def _inc_active(self):
        """Increment active connection counter."""
        async with self._active_lock:
            self._active_count += 1

    async def _dec_active(self):
        """Decrement active connection counter."""
        async with self._active_lock:
            self._active_count -= 1

    def _get_active(self) -> int:
        """Get current active connection count."""
        return self._active_count

    def _is_slot_available(self, client_id: int) -> bool:
        """Check if a slot is available (not exhausted and not on cooldown)."""
        if self.slot_exhausted.get(client_id, False):
            return False
        return time.time() >= self.slot_cooldown_until.get(client_id, 0.0)

    def _is_slot_on_cooldown(self, client_id: int) -> bool:
        """Check if a slot is currently on cooldown."""
        return time.time() < self.slot_cooldown_until.get(client_id, 0.0)

    def _put_slot_on_cooldown(self, client_id: int, duration: float):
        """Put a slot on cooldown for specified duration."""
        self.slot_cooldown_until[client_id] = time.time() + duration
        print(
            f"⏱️  Slot {client_id % len(self.clients)} on cooldown for {duration:.1f}s"
        )

    def _mark_slot_exhausted(self, client_id: int, reason: str = ""):
        """Permanently mark a slot as exhausted/unusable."""
        self.slot_exhausted[client_id] = True
        print(f"❌ Slot {client_id % len(self.clients)} permanently disabled: {reason}")

    async def _call_model(
        self, client: genai.Client, text: str, parse_json: bool = False
    ) -> tuple[Optional[Union[str, Any]], str]:
        """
        Make a single API call with rate limiting and error handling.

        Args:
            client: The genai.Client to use.
            text: The prompt text.
            parse_json: Whether to parse response as JSON.

        Returns:
            Tuple of (response, error_type)
            - response: Response text/JSON or None on failure
            - error_type: "success" | "key_issue" | "task_issue" | "skip"
                - "success": Request succeeded
                - "key_issue": Key/rate limit problem (don't count as retry)
                - "task_issue": Problem with task itself (count as retry)
                - "skip": Slot unavailable (cooldown or exhausted)
        """
        cid = id(client)

        # Check if slot is available (not exhausted, not on cooldown)
        if not self._is_slot_available(cid):
            return None, "skip"  # Slot unavailable, try another

        # Per-slot rate limiting
        elapsed = time.time() - self.last_call_time[cid]
        if elapsed < self.rate_limit_per_slot:
            await asyncio.sleep(self.rate_limit_per_slot - elapsed)

        await self._inc_active()
        self.stats["total_api_calls"] += 1

        try:
            config = types.GenerateContentConfig(temperature=self.temperature)
            if self.system_instruction:
                config.system_instruction = self.system_instruction

            resp = await client.aio.models.generate_content(
                model=self.model_name,
                config=config,
                contents=text,
            )

            self.last_call_time[cid] = time.time()

            result = resp.text
            if parse_json:
                parsed = parse_json_safe(result)
                if parsed is not None:
                    return parsed, "success"
                else:
                    # Failed to parse - this is a task issue (bad response format)
                    self.err_logger.error(
                        f"client_id={cid} json_parse_failed text={result[:200]}"
                    )
                    return None, "task_issue"

            return result, "success"

        except Exception as e:
            retry_s = extract_retry_delay(e)
            error_msg = str(e).lower()

            self.err_logger.error(
                f"client_id={cid} exception={repr(e)} retry_hint={retry_s}"
            )

            self.last_call_time[cid] = time.time()

            # Check for permanent key exhaustion (suspended, invalid, etc.)
            is_permanently_exhausted = (
                "consumer_suspended" in error_msg
                or "permission denied" in error_msg
                or "api key not valid" in error_msg
                or "api key expired" in error_msg
                or "invalid api key" in error_msg
                or "403 permission_denied" in error_msg
            )

            if is_permanently_exhausted:
                # This key is permanently dead - mark as exhausted
                self._mark_slot_exhausted(cid, "Key suspended or invalid")
                return None, "key_issue"  # Don't count against task retry limit

            # Check for temporary rate limit issues
            is_rate_limit = (
                retry_s is not None
                or "429" in error_msg
                or "rate limit" in error_msg
                or "quota" in error_msg
                or "resource exhausted" in error_msg
            )

            if is_rate_limit:
                # This is a temporary KEY ISSUE - put slot on cooldown
                cooldown_duration = min(retry_s, 120) if retry_s else 60
                self._put_slot_on_cooldown(cid, cooldown_duration)
                return None, "key_issue"  # Don't count against task retry limit
            else:
                # This is a TASK ISSUE - bad prompt, model error, etc.
                # Don't cooldown the slot, but count against retry limit
                return None, "task_issue"

        finally:
            await self._dec_active()

    async def _worker(
        self,
        worker_id: int,
        queue: asyncio.Queue,
        client: genai.Client,
        results: List[Dict[str, Any]],
        done_ids: set,
        output_file: Optional[str],
        parse_json: bool,
        pbar,
        max_retries_per_task: int = 5,
    ):
        """
        Worker coroutine that pulls tasks from queue and processes them.

        Args:
            worker_id: Unique worker identifier.
            queue: Task queue.
            client: genai.Client for this worker.
            results: Shared results list.
            done_ids: Set of completed task IDs.
            output_file: Path to save results.
            parse_json: Whether to parse responses as JSON.
            pbar: Progress bar.
            max_retries_per_task: Maximum retries for TASK-RELATED errors only.
                                 Key-related errors (rate limits) don't count.
        """
        while True:
            task = await queue.get()

            if task is None:  # Sentinel to stop worker
                queue.task_done()
                return

            task_id = task.get("id")
            prompt = task.get("prompt", "")
            task_error_count = task.get(
                "_task_error_count", 0
            )  # Only count task errors

            # Make API call
            response, error_type = await self._call_model(client, prompt, parse_json)

            # Handle result based on error type
            if error_type == "success":
                # Success!
                self.stats["successful_requests"] += 1
                self.stats["total_requests"] += 1

                result_entry = {
                    **task,
                    "result": response,
                    "success": True,
                }
                # Remove internal counters from result
                result_entry.pop("_task_error_count", None)

                async with self._save_lock:
                    results.append(result_entry)
                    if task_id is not None:
                        done_ids.add(task_id)

                    # Save to file if specified
                    if output_file:
                        async with aiofiles.open(
                            output_file, "w", encoding="utf-8"
                        ) as f:
                            await f.write(
                                json.dumps(results, ensure_ascii=False, indent=2)
                            )

                pbar.update(1)
                queue.task_done()

            elif error_type == "skip":
                # Slot on cooldown/exhausted - put task back for another worker
                await queue.put(task)
                queue.task_done()
                # Small sleep to let other workers pick it up
                # (prevents this exhausted slot from immediately pulling same task)
                await asyncio.sleep(0.01)

            elif error_type == "key_issue":
                # Key/rate limit issue - retry indefinitely (don't count)
                # Just put back in queue - another worker will naturally pick it up
                await queue.put(task)
                self.stats["retried_tasks"] += 1
                queue.task_done()

            elif error_type == "task_issue":
                # Task-related error - count against retry limit
                if task_error_count < max_retries_per_task:
                    # Still have retries left
                    task["_task_error_count"] = task_error_count + 1

                    # Put back in queue - another worker will naturally pick it up
                    await queue.put(task)
                    self.stats["retried_tasks"] += 1

                    print(
                        f"🔄 Task error for {task_id}, retry {task_error_count + 1}/{max_retries_per_task}"
                    )

                    queue.task_done()
                else:
                    # Exhausted all retries - mark as failed
                    self.stats["failed_requests"] += 1
                    self.stats["total_requests"] += 1

                    result_entry = {
                        **task,
                        "result": None,
                        "success": False,
                        "task_errors_attempted": task_error_count,
                        "failure_reason": "task_error",
                    }
                    # Remove internal counters from result
                    result_entry.pop("_task_error_count", None)

                    async with self._save_lock:
                        results.append(result_entry)
                        if task_id is not None:
                            done_ids.add(task_id)

                        # Save to file if specified
                        if output_file:
                            async with aiofiles.open(
                                output_file, "w", encoding="utf-8"
                            ) as f:
                                await f.write(
                                    json.dumps(results, ensure_ascii=False, indent=2)
                                )

                    print(
                        f"❌ Task {task_id} failed after {max_retries_per_task + 1} task error attempts"
                    )
                    pbar.update(1)
                    queue.task_done()

    async def _monitor(self, queue: asyncio.Queue):
        """
        Monitor coroutine that prints live statistics.

        Args:
            queue: Task queue to monitor.
        """
        while True:
            await asyncio.sleep(self.monitoring_interval)
            active = self._get_active()
            queued = queue.qsize()
            exhausted_count = sum(
                1 for cid, exhausted in self.slot_exhausted.items() if exhausted
            )
            cooldown_count = sum(
                1
                for cid in self.slot_cooldown_until
                if not self.slot_exhausted.get(cid, False)
                and self._is_slot_on_cooldown(cid)
            )
            success_rate = (
                (self.stats["successful_requests"] / self.stats["total_requests"] * 100)
                if self.stats["total_requests"] > 0
                else 0
            )

            status_parts = [
                f"active {active}/{self.total_slots}",
                f"cooldown {cooldown_count}",
            ]
            if exhausted_count > 0:
                status_parts.append(f"⚠️ exhausted {exhausted_count}")
            status_parts.extend(
                [
                    f"queued {queued}",
                    f"success {self.stats['successful_requests']}/{self.stats['total_requests']} ({success_rate:.1f}%)",
                    f"retried {self.stats['retried_tasks']}",
                ]
            )

            print(f"📊 {' | '.join(status_parts)}")

    async def generate_batch(
        self,
        tasks: List[Union[str, Dict[str, Any]]],
        output_file: Optional[str] = None,
        parse_json: bool = False,
        id_key: str = "id",
        prompt_key: str = "prompt",
        show_progress: bool = True,
        max_retries_per_task: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Generate content for multiple tasks using worker pool architecture.

        Args:
            tasks: List of prompts (strings) or dictionaries containing prompts.
            output_file: Optional file to save results to (JSON format).
            parse_json: If True, attempts to parse responses as JSON.
            id_key: Key name for task IDs (when tasks are dictionaries).
            prompt_key: Key name for prompts (when tasks are dictionaries).
            show_progress: Whether to show progress bar.
            max_retries_per_task: Maximum retry attempts for TASK-RELATED errors.
                                 Key/rate limit errors don't count - will wait indefinitely.

        Returns:
            List of result dictionaries with 'prompt', 'result', and metadata.

        Note:
            Tasks only fail after max_retries_per_task attempts of TASK errors
            (bad prompts, parsing issues, etc.). If errors are key-related
            (rate limits), tasks will wait indefinitely for keys to become available.
        """
        # Load existing results if output_file exists
        results = []
        done_ids = set()

        if output_file and os.path.exists(output_file):
            async with aiofiles.open(output_file, "r", encoding="utf-8") as f:
                content = await f.read()
                if content:
                    try:
                        results = json.loads(content)
                        done_ids = {r.get(id_key) for r in results if id_key in r}
                        print(
                            f"📂 Loaded {len(results)} existing results from '{output_file}'"
                        )
                    except json.JSONDecodeError:
                        print("⚠️  Could not parse existing results file")

        # Prepare tasks
        task_list = []
        for i, task in enumerate(tasks):
            if isinstance(task, str):
                task_dict = {id_key: i, prompt_key: task}
            else:
                task_dict = task.copy()
                if id_key not in task_dict:
                    task_dict[id_key] = i

            # Skip if already completed
            if task_dict[id_key] not in done_ids:
                task_list.append(task_dict)

        if not task_list:
            print("✅ All tasks already completed!")
            return results

        total = len(tasks)
        remaining = len(task_list)
        print(f"🧮 Remaining tasks: {remaining}/{total}")

        # Create task queue
        queue = asyncio.Queue()
        for task in task_list:
            await queue.put(task)

        # Create progress bar
        pbar = async_tqdm(
            total=total,
            desc="Processing",
            initial=total - remaining,
            disable=not show_progress,
        )

        # Start workers
        workers = [
            asyncio.create_task(
                self._worker(
                    i,
                    queue,
                    self.clients[i],
                    results,
                    done_ids,
                    output_file,
                    parse_json,
                    pbar,
                    max_retries_per_task,
                )
            )
            for i in range(self.total_slots)
        ]

        # Start monitor if enabled
        monitor_task = None
        if self.enable_monitoring and show_progress:
            monitor_task = asyncio.create_task(self._monitor(queue))

        # Wait for queue to be empty
        await queue.join()

        # Stop monitor
        if monitor_task:
            monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await monitor_task

        # Stop workers
        for _ in workers:
            await queue.put(None)
        await asyncio.gather(*workers, return_exceptions=True)

        pbar.close()

        return results

    async def generate_single(
        self, prompt: str, parse_json: bool = False
    ) -> Optional[Union[str, Any]]:
        """
        Generate content for a single prompt.

        Args:
            prompt: The prompt to generate content from.
            parse_json: If True, attempts to parse response as JSON.

        Returns:
            Generated content (string or parsed JSON), or None on failure.
        """
        # Use first available client
        client = self.clients[0]
        response, error_type = await self._call_model(client, prompt, parse_json)
        return response

    def get_statistics(self) -> dict:
        """Get statistics about generation."""
        # Count slots by state
        exhausted_count = sum(
            1 for cid, exhausted in self.slot_exhausted.items() if exhausted
        )
        cooldown_count = sum(
            1
            for cid in self.slot_cooldown_until
            if not self.slot_exhausted.get(cid, False)
            and self._is_slot_on_cooldown(cid)
        )
        available_count = sum(
            1 for cid in self.slot_cooldown_until if self._is_slot_available(cid)
        )

        return {
            "total_slots": self.total_slots,
            "active_connections": self._get_active(),
            "exhausted_slots": exhausted_count,
            "slots_on_cooldown": cooldown_count,
            "available_slots": available_count,
            "total_requests": self.stats["total_requests"],
            "successful_requests": self.stats["successful_requests"],
            "failed_requests": self.stats["failed_requests"],
            "retried_tasks": self.stats["retried_tasks"],
            "total_api_calls": self.stats["total_api_calls"],
            "success_rate": (
                self.stats["successful_requests"] / self.stats["total_requests"] * 100
                if self.stats["total_requests"] > 0
                else 0
            ),
        }

    def print_statistics(self):
        """Print formatted statistics."""
        stats = self.get_statistics()

        print("\n" + "=" * 70)
        print("GEMINI GENERATOR STATISTICS")
        print("=" * 70)
        print(f"Total Slots:          {stats['total_slots']}")
        print(f"Available Slots:      {stats['available_slots']}")
        print(f"Slots on Cooldown:    {stats['slots_on_cooldown']}")
        print(f"Exhausted Slots:      {stats['exhausted_slots']}")
        print(f"Active Connections:   {stats['active_connections']}")
        print(f"Total Requests:       {stats['total_requests']}")
        print(f"Successful:           {stats['successful_requests']}")
        print(f"Failed:               {stats['failed_requests']}")
        print(f"Retried Tasks:        {stats['retried_tasks']}")
        print(f"Success Rate:         {stats['success_rate']:.2f}%")
        print(f"Total API Calls:      {stats['total_api_calls']}")
        print("=" * 70 + "\n")
