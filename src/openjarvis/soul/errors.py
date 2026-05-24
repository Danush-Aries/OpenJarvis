"""Soul errors — typed exception hierarchy for the Soul module.

All soul-specific exceptions inherit from ``SoulError`` so callers can
catch the base type or drill into specific failure modes.

Hierarchy::

    SoulError
    ├── SoulNotFoundError       # soul does not exist on disk
    ├── SoulCorruptedError      # soul data is corrupt (with recovery attempt)
    ├── SoulPersistenceError    # disk write/read failure
    ├── SoulEmbeddingError      # embedding model or computation failure
    └── SoulCacheError          # soul cache inconsistency
"""


class SoulError(Exception):
    """Base exception for all Soul module errors."""


class SoulNotFoundError(SoulError):
    """The requested soul does not exist on disk."""


class SoulCorruptedError(SoulError):
    """Soul data on disk is corrupt and could not be recovered from backup."""


class SoulPersistenceError(SoulError):
    """Failed to read or write soul data to disk."""


class SoulEmbeddingError(SoulError):
    """Embedding model loading or vector computation failed."""


class SoulCacheError(SoulError):
    """Internal soul cache inconsistency detected."""
