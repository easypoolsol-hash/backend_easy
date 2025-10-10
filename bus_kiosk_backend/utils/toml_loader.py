"""TOML loader with stdlib/fallback compatibility.

Use `load_toml(path)` to read a TOML file and return a dict.
This prefers stdlib `tomllib` (Python 3.11+). If unavailable, it falls
back to the `tomli` package (pure-python, small) which should be added to
dev/testing extras.
"""
from __future__ import annotations

from typing import Any, Dict

try:
    import tomllib as _toml  # type: ignore
except Exception:
    try:
        import tomli as _toml  # type: ignore
    except Exception as exc:  # pragma: no cover - hard to reproduce in CI
        raise ImportError("No TOML parser available; install 'tomli' for Python<3.11") from exc


def load_toml(path: str | bytes) -> Dict[str, Any]:
    """Load TOML file from `path` and return a mapping.

    Args:
        path: filesystem path to TOML file (str or bytes)

    Returns:
        Parsed TOML as a dict
    """
    mode = "rb"
    with open(path, mode) as f:
        return _toml.load(f)
