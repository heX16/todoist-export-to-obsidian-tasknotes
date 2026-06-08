"""Shared helpers for unit tests."""

from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / 'scripts'

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

MINIMAL_FIXTURE_PATH = TESTS_DIR / 'todoist_minimal.json'
NUMERIC_IDS_FIXTURE_PATH = TESTS_DIR / 'todoist_minimal_numeric_ids.json'
