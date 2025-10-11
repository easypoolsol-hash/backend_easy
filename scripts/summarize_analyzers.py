"""Summarize analyzer JSON outputs (pylint_output.json and bandit_output.json).

Run this from the repository `backend_easy` directory (it will use cwd).
Prints a compact JSON summary to stdout.
"""

from collections import Counter
import json
from pathlib import Path
import sys

p = Path.cwd()
PYLINT = p / "pylint_output.json"
BANDIT = p / "bandit_output.json"

if not PYLINT.exists() and not BANDIT.exists():
    print(json.dumps({"error": "Neither pylint_output.json nor bandit_output.json found in cwd"}))
    sys.exit(1)


def load_json(path):
    # try multiple encodings to cope with BOM or non-utf8
    last_exc = None
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(path, encoding=enc) as fh:
                return json.load(fh)
        except Exception as e:
            last_exc = e
    raise last_exc


summary = {}

if PYLINT.exists():
    try:
        data = load_json(PYLINT)
        total = len(data)
        by_type = Counter(d.get("type") for d in data)
        # message-id is more stable, fallback to symbol
        by_symbol = Counter((d.get("message-id") or d.get("symbol")) for d in data)
        by_file = Counter(d.get("path") for d in data)
        summary["pylint"] = {
            "total_messages": total,
            "by_type": dict(by_type),
            "top_message_ids": by_symbol.most_common(20),
            "top_files": by_file.most_common(20),
        }
    except Exception as e:
        summary["pylint"] = {"error": str(e)}

if BANDIT.exists():
    try:
        data = load_json(BANDIT)
        results = data.get("results") or []
        totals = data.get("metrics", {}).get("_totals", {})
        # count by issue_text or test_name
        by_test = Counter(r.get("test_id") or r.get("test_name") or r.get("issue_text") for r in results)
        by_filename = Counter(r.get("filename") for r in results)
        summary["bandit"] = {
            "total_results": len(results),
            "metrics_totals": totals,
            "top_tests": by_test.most_common(20),
            "top_files": by_filename.most_common(20),
        }
    except Exception as e:
        summary["bandit"] = {"error": str(e)}

print(json.dumps(summary, indent=2))
