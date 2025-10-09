from pathlib import Path

import yaml


def _candidate_schema_paths():
    # Search upward from this file for common schema filenames
    base = Path(__file__).resolve().parents[1]
    candidates = []
    # look in tests/ directory, app root, repo root (up to 4 levels)
    for i in range(0, 5):
        p = base.parents[i] if i < len(base.parents) else None
        if p is None:
            continue
        candidates.append(p / "openapi-schema.yaml")
        candidates.append(p / "schema.yaml")
    return candidates


def _load_schema():
    for p in _candidate_schema_paths():
        if p.exists():
            with p.open("r", encoding="utf-8") as fh:
                return yaml.safe_load(fh)
    raise FileNotFoundError(
        f"No OpenAPI schema found in candidate paths: {_candidate_schema_paths()}"
    )


def get_path_by_operation(operation_id, **params):
    """Return a formatted path from the OpenAPI schema by operationId.

    Params are substituted into the path template (e.g. kiosk_id).
    """
    schema = _load_schema()
    paths = schema.get("paths", {})

    # Lookup by operationId
    for raw_path, methods in paths.items():
        for method_meta in methods.values():
            if method_meta.get("operationId") == operation_id:
                formatted = raw_path
                for k, v in params.items():
                    formatted = formatted.replace("{" + k + "}", str(v))
                return f"/{formatted.lstrip('/')}"

    raise KeyError(f"No path found for operationId: {operation_id}")
