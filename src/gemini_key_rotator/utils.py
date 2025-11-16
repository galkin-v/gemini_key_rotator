"""Utility functions for the Gemini Key Rotator library."""

import json
import re
from typing import Any, Optional

from json_repair import repair_json


def extract_retry_delay(exception: Exception) -> Optional[float]:
    """
    Extract retry delay from an exception.

    Tries multiple methods to extract retry delay information:
    1. Structured RetryInfo from error details
    2. Check for retry_delay attribute
    3. Parse error message for "retry in X seconds" pattern

    Args:
        exception: The exception to extract retry delay from.

    Returns:
        Retry delay in seconds, or None if not found.
    """
    # Method 1: Try structured RetryInfo (google.genai style)
    try:
        payload = (exception.args[0] if exception.args else None) or {}
        if isinstance(payload, dict):
            details = payload.get("error", {}).get("details", [])
            for d in details or []:
                if d.get("@type", "").endswith("RetryInfo"):
                    s = (d.get("retryDelay") or "").strip().strip("s")
                    if s and s.replace(".", "").isdigit():
                        return float(s)
    except Exception:
        pass

    # Method 2: Check for retry_delay attribute
    try:
        retry_delay = getattr(exception, "retry_delay", None)
        if retry_delay is not None:
            # It might be an object with .seconds attribute
            seconds = getattr(retry_delay, "seconds", None)
            if seconds is not None:
                return float(seconds)
            # Or it might be a dict
            if isinstance(retry_delay, dict):
                seconds = retry_delay.get("seconds")
                if seconds is not None:
                    return float(seconds)
            # Or it might be a number directly
            try:
                return float(retry_delay)
            except (ValueError, TypeError):
                pass
    except Exception:
        pass

    # Method 3: Parse error message
    try:
        msg = str(exception)
        # Pattern: "Please retry in 14.8s" or "retry in 14.8 seconds"
        patterns = [
            r"retry in\s*([0-9]+\.?[0-9]*)\s*s(?:econds?)?",
            r"wait\s*([0-9]+\.?[0-9]*)\s*s(?:econds?)?",
        ]
        for pattern in patterns:
            match = re.search(pattern, msg, re.IGNORECASE)
            if match:
                return float(match.group(1))
    except Exception:
        pass

    return None


def parse_json_safe(text: str) -> Optional[Any]:
    """
    Safely parse JSON text, returning None on failure.

    Args:
        text: The text to parse as JSON.

    Returns:
        Parsed JSON object, or None if parsing fails.
    """
    try:
        # Try repair_json if available
        if repair_json is not None:
            cleaned = repair_json(text)
            return json.loads(cleaned)
        else:
            # Fallback: basic cleaning
            cleaned = text.strip()
            # Remove markdown code fences
            cleaned = re.sub(r"^```json\s*", "", cleaned)
            cleaned = re.sub(r"^```\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            return json.loads(cleaned.strip())
    except (json.JSONDecodeError, Exception):
        return None


def format_time(seconds: float) -> str:
    """
    Format seconds into a human-readable time string.

    Args:
        seconds: Time in seconds.

    Returns:
        Formatted time string (e.g., "1h 23m 45s").
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
