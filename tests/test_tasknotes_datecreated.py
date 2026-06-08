#!/usr/bin/env python3
"""Test whether TaskNotes API accepts client-provided dateCreated.

Creates a task with a specified dateCreated, reads it back, and compares the
stored value with the requested one.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / 'scripts'
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from todoist_tasknotes_mapping import (  # noqa: E402
    DEFAULT_API_BASE,
    DEFAULT_API_TOKEN,
    api_request,
)


def _iso_now_for_title() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')


def _extract_task_path(create_response: dict[str, Any]) -> str:
    data = create_response.get('data', {}) if isinstance(create_response, dict) else {}
    path = data.get('path') or data.get('id')
    if not path:
        raise RuntimeError(f'No task path in response: {json.dumps(create_response, ensure_ascii=False)}')
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description='Test TaskNotes dateCreated behavior.')
    parser.add_argument('--api-base', default=DEFAULT_API_BASE)
    parser.add_argument('--api-token', default=DEFAULT_API_TOKEN)
    parser.add_argument(
        '--date-created',
        default='2000-01-02T03:04:05Z',
        help='ISO datetime string to send as dateCreated (e.g. 2026-06-08T00:00:00Z).',
    )
    parser.add_argument(
        '--title',
        default=None,
        help='Optional task title. If omitted, a unique test title is generated.',
    )
    parser.add_argument(
        '--keep',
        action='store_true',
        help='Keep the created task (default). If omitted, the task is kept anyway; this flag is for clarity.',
    )
    args = parser.parse_args()

    requested_date_created = str(args.date_created)
    title = args.title or f'dateCreated API test {_iso_now_for_title()}'

    create_payload: dict[str, Any] = {
        'title': title,
        'details': f'Requested dateCreated: {requested_date_created}\n',
        'dateCreated': requested_date_created,
    }

    print('=== POST /api/tasks payload ===')
    print(json.dumps(create_payload, indent=2, ensure_ascii=False))
    status, body = api_request('POST', f'{args.api_base}/api/tasks', args.api_token, create_payload)
    print('\n=== POST /api/tasks response ===')
    print(f'HTTP {status}')
    print(json.dumps(body, indent=2, ensure_ascii=False))

    if status != 201 or not body.get('success'):
        print('\nRESULT: FAILED to create task with dateCreated.', file=sys.stderr)
        return 2

    task_path = _extract_task_path(body)
    encoded_path = urllib.parse.quote(task_path, safe='')

    status, read_body = api_request('GET', f'{args.api_base}/api/tasks/{encoded_path}', args.api_token)
    print('\n=== GET /api/tasks/:id response ===')
    print(f'HTTP {status}')
    print(json.dumps(read_body, indent=2, ensure_ascii=False))

    if status != 200 or not read_body.get('success'):
        print('\nRESULT: FAILED to read created task back.', file=sys.stderr)
        return 3

    task_data = read_body.get('data', {}) or {}
    stored_date_created = task_data.get('dateCreated')

    print('\n=== Comparison ===')
    print(f'- requested dateCreated: {requested_date_created}')
    print(f'- stored dateCreated:    {stored_date_created}')
    print(f'- task path:             {task_path}')

    if stored_date_created == requested_date_created:
        print('\nRESULT: dateCreated was preserved exactly.')
        return 0

    if stored_date_created:
        print('\nRESULT: dateCreated differs (likely ignored or overwritten by TaskNotes).')
        return 1

    print('\nRESULT: dateCreated is missing in response (unexpected).')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())

