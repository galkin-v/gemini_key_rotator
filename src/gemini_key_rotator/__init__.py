"""
Gemini Key Rotator - A Python library for efficient async generation with Google API key rotation.

This library provides an easy-to-use API for:
- Worker-pool architecture with multiple workers per API key
- Per-slot rate limiting for maximum throughput
- Live monitoring of active connections
- Checkpoint/resume functionality
- Structured error logging
- High-performance async processing

Architecture:
- Each API key can have multiple worker slots (default: 4 per key)
- Each worker slot has independent rate limiting
- Workers pull tasks from a shared queue
- Live monitoring shows active connections and progress
"""

from .generator import GeminiGenerator
from .exceptions import NoAvailableKeysError, AllKeysExhaustedError

__version__ = "2.0.0"
__all__ = [
    "GeminiGenerator",
    "NoAvailableKeysError",
    "AllKeysExhaustedError",
]

