#!/usr/bin/env python3
"""Update SDK version in frontend_easy_api pubspec.yaml"""
import re
from pathlib import Path

pubspec_path = Path("../frontend_easy/packages/frontend_easy_api/pubspec.yaml")
content = pubspec_path.read_text(encoding='utf-8')
updated_content = re.sub(
    r"sdk: '>=\d+\.\d+\.\d+ <\d+\.\d+\.\d+'",
    "sdk: '>=3.9.0 <4.0.0'",
    content
)
pubspec_path.write_text(updated_content, encoding='utf-8')
print("✓ Updated SDK version to >=3.9.0 <4.0.0")
