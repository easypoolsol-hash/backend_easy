Short governance notes

This directory contains the backend's Single Source of Truth (SSOT) and constitutional core used to guide implementation. The canonical, fully-featured governance/tooling lives in `bus_kiosk_easy/imperial_governance` in this workspace; this copy is the backend-local subset used by the Django package.

Purpose:
- Provide read-only reference for backend engineers
- Allow quick local validation that files referenced by `ssot.yaml` exist

How to validate locally:

1. Ensure you have Python 3.10+ available
2. From the repository root run:

```powershell
python -m venv .venv
.venv\Scripts\activate
python backend_easy/imperial_governance/validate_constitutions.py
```

If the script exits with non-zero status it will print missing files referenced by `ssot.yaml`.

If your team uses the central governance area (`bus_kiosk_easy/imperial_governance`) prefer editing there and follow the approval gate.

Maintainers: update this README if canonical locations change.
