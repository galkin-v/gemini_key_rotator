"""Custom exceptions for the Gemini Key Rotator library."""


class NoAvailableKeysError(Exception):
    """Raised when no API keys are available (all on cooldown)."""

    pass


class AllKeysExhaustedError(Exception):
    """Raised when all keys have been exhausted and cannot be used."""

    pass
